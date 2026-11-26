"""Step 1 - Wikipedia HTML snapshots and infobox extraction.

For each film in data/raw/films_master.csv:
  * fetch the Wikipedia page with a polite User-Agent and a 1.5 s gap;
  * save the untouched HTML to data/raw/wiki/{film_id}.html;
  * parse table.infobox for Release date, Language, Budget and Box office;
  * write data/clean/wiki_infobox.csv with raw strings and crore estimates.

Run:  python src/01_wiki_layer.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import lxml.html
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

STEP = "01_wiki"
DELAY_SECONDS = 1.5

FIELDS = {
    "release date": "release_date",
    "release dates": "release_date",
    "language": "language",
    "budget": "budget",
    "box office": "box_office",
}

OUT = c.CLEAN / "wiki_infobox.csv"


def fetch(url: str) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                url, headers={"User-Agent": c.WIKI_UA}, timeout=30
            )
            response.raise_for_status()
            return response
        except requests.RequestException as exc:  # transient TLS / 5xx
            last_error = exc
            time.sleep(2 * (attempt + 1))
    raise last_error  # type: ignore[misc]


def parse_infobox(html: str) -> dict[str, str]:
    """Return the first value seen for each wanted infobox field."""
    document = lxml.html.fromstring(html)
    tables = document.xpath(
        "//table[contains(concat(' ', normalize-space(@class), ' '), ' infobox ')]"
    )
    values: dict[str, str] = {}
    for table in tables:
        # Wikipedia's parser wraps rows in <tbody>, so descend instead of ./tr.
        for row in table.xpath(".//tr"):
            headers = row.xpath("./th")
            cells = row.xpath("./td")
            if not headers or not cells:
                continue
            key = c.clean_text(headers[0].text_content()).rstrip(":").lower()
            target = FIELDS.get(key)
            if target and target not in values:
                values[target] = c.clean_text(cells[0].text_content())
        if len(values) == len(FIELDS) - 1:  # release date / language / budget / box office
            break
    return values


def primary_language(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.split(",")[0].strip() or None


def main() -> int:
    c.ensure_dirs()
    master = c.load_master()
    rows: list[dict] = []
    access: list[dict] = []

    print(f"Fetching {len(master)} Wikipedia pages -> data/raw/wiki/")
    for _, film in master.iterrows():
        film_id = film["film_id"]
        url = film["wikipedia_url"]
        snapshot = c.RAW / "wiki" / f"{film_id}.html"
        status = None
        note = ""
        infobox: dict[str, str] = {}

        try:
            response = fetch(url)
            status = response.status_code
            snapshot.write_text(response.text, encoding="utf-8")
            infobox = parse_infobox(response.text)
            note = "snapshot saved" if infobox else "infobox not found"
        except Exception as exc:  # keep the batch running
            status = getattr(getattr(exc, "response", None), "status_code", None)
            note = f"fetch failed: {exc.__class__.__name__}"

        budget = c.crore_from_text(infobox.get("budget"))
        gross = c.crore_from_text(infobox.get("box_office"))
        parsed_date = c.parse_date(infobox.get("release_date"))
        rows.append(
            {
                "film_id": film_id,
                "canonical_title": film["canonical_title"],
                "roster_release_date": film["release_date"].isoformat(),
                "roster_language": film["language"],
                "wiki_release_date_raw": infobox.get("release_date"),
                "wiki_release_date_parsed": parsed_date,
                "wiki_language_raw": infobox.get("language"),
                "wiki_language_primary": primary_language(infobox.get("language")),
                "wiki_budget_raw": infobox.get("budget"),
                "wiki_budget_cr": budget,
                "wiki_ww_gross_raw": infobox.get("box_office"),
                "wiki_ww_gross_cr": gross,
                "http_status": status,
                "access_date": c.utc_stamp(),
                "source_url": url,
                "notes": note,
            }
        )
        access.append(
            {
                "source_name": "Wikipedia",
                "url": url,
                "http_status": status,
                "format": "HTML",
                "notes": note,
            }
        )
        print(
            f"  {film_id} {film['canonical_title'][:28]:28} "
            f"HTTP {status} budget={budget} gross={gross}"
        )
        time.sleep(DELAY_SECONDS)

    out = c.write_csv(pd.DataFrame(rows), OUT)
    log = c.write_access_log(STEP, access)
    print(f"\nWrote {out.relative_to(c.REPO_ROOT)} ({len(rows)} rows)")
    print(f"Wrote {log.relative_to(c.REPO_ROOT)} ({len(access)} access records)")
    missing = sum(pd.isna(r["wiki_budget_cr"]) for r in rows)
    print(f"Budget parsed: {len(rows) - missing}/{len(rows)} | missing infobox values: {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
