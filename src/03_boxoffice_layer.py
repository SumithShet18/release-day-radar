"""Step 3 - standardized opening 3-day India net from Sacnilk.

Resolves every film on Sacnilk, fetches its day-wise table, extracts the
locked opening window (Fri-Sun for 11 films, Sun-Tue for F08), writes one
raw CSV per film plus the consolidated verified table and a 36-row daily
table for validation.

Run:  python src/03_boxoffice_layer.py
"""

from __future__ import annotations

import io
import re
import sys
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

STEP = "03_boxoffice"
STEP_ID = "STEP_03"
SACNILK = "https://www.sacnilk.com"
SEARCH_URL = f"{SACNILK}/api/search"
DELAY_SECONDS = 1.5

RAW_DIR = c.RAW / "boxoffice"
CONSOLIDATED = c.CLEAN / "opening_weekend_verified.csv"
DAILY = c.CLEAN / "opening_3d_daily.csv"

CONSOLIDATED_COLUMNS = [
    "film_id",
    "canonical_title",
    "day1_label",
    "day1_date",
    "day1_net_cr",
    "day2_label",
    "day2_date",
    "day2_net_cr",
    "day3_label",
    "day3_date",
    "day3_net_cr",
    "opening_3d_india_net_cr",
    "is_non_friday_release",
    "window_note",
    "source_name",
    "source_url",
    "access_date",
]

DAILY_COLUMNS = [
    "film_id",
    "day_slot",
    "day_index",
    "calendar_date",
    "weekday",
    "india_net_cr",
    "is_non_friday_release",
    "source_url",
    "access_date",
]


def request_json(url: str, params: dict) -> tuple[dict, int]:
    last: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                url,
                params=params,
                headers={
                    "User-Agent": c.BROWSER_UA,
                    "Accept": "application/json",
                },
                timeout=30,
            )
            if response.status_code == 200:
                return response.json(), response.status_code
            last = RuntimeError(f"HTTP {response.status_code}")
        except (requests.RequestException, ValueError) as exc:
            last = exc
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"search failed for {params}: {last}")


def request_html(url: str) -> tuple[str, int]:
    last: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                url, headers={"User-Agent": c.BROWSER_UA}, timeout=30
            )
            response.raise_for_status()
            return response.text, response.status_code
        except requests.RequestException as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"page failed for {url}: {last}")


def resolve_film(payload: dict, title: str, release_date) -> dict | None:
    """Find the Sacnilk film entry whose release date/year matches the roster."""
    year = release_date.year

    answer = payload.get("answer") or {}
    answer_film = answer.get("film")
    if answer_film and str(answer_film.get("release", "")).startswith(str(release_date)):
        return answer_film

    exact: list[dict] = []
    for group in payload.get("groups", []):
        for item in group.get("items", []):
            if not str(item.get("url", "")).startswith("/movie/"):
                continue
            sub = str(item.get("sub", ""))
            if str(year) in sub:
                exact.append(item)
    if not exact:
        return None

    wanted = c.title_key(title)
    scored = []
    for item in exact:
        key = c.title_key(item.get("title"))
        ratio = 0.0
        if key and wanted:
            common = sum(1 for a, b in zip(key, wanted) if a == b)
            ratio = common / max(len(key), len(wanted))
        if key == wanted:
            ratio += 1.0
        scored.append((ratio, item))
    return max(scored, key=lambda pair: pair[0])[1]


def day_table(html: str) -> pd.DataFrame:
    tables = pd.read_html(io.StringIO(html))
    for table in tables:
        columns = [str(col) for col in table.columns]
        if any("india net" in col.lower() for col in columns) and any(
            col.lower() == "day" for col in columns
        ):
            return table
    raise ValueError("no day-wise India net table found")


def extract_days(table: pd.DataFrame) -> list[dict]:
    day_col = next(i for i, col in enumerate(table.columns) if str(col).lower() == "day")
    net_col = next(
        i for i, col in enumerate(table.columns) if "india net" in str(col).lower()
    )
    days = []
    for _, row in table.iterrows():
        match = re.match(r"Day\s+(\d+)", str(row.iloc[day_col]))
        if not match:
            continue
        days.append(
            {
                "day_index": int(match.group(1)),
                "net_raw": str(row.iloc[net_col]),
                "net_cr": c.crore_from_text(row.iloc[net_col]),
                "row_text": str(row.iloc[day_col])[:60],
            }
        )
    return days


def window_offsets(release_date) -> list[int]:
    """Day offsets (0-based from release) covering the locked 3-day window."""
    if release_date.weekday() == 6:  # Sunday release -> Sun, Mon, Tue
        return [0, 1, 2]
    return [
        offset
        for offset in range(0, 7)
        if (release_date + timedelta(days=offset)).weekday() in (4, 5, 6)
    ][:3]


def main() -> int:
    c.ensure_dirs()
    master = c.load_master()
    access: list[dict] = []
    consolidated: list[dict] = []
    daily_rows: list[dict] = []
    log_rows: list[dict] = []

    print(f"Resolving {len(master)} films on Sacnilk")
    for _, film in master.iterrows():
        film_id = film["film_id"]
        release_date = c.as_date(film["release_date"])
        query = film["canonical_title"].replace(":", " ")

        payload, search_status = request_json(SEARCH_URL, {"q": query})
        access.append(
            {
                "source_name": "Sacnilk search API",
                "url": f"{SEARCH_URL}?q={query.replace(' ', '+')}",
                "http_status": search_status,
                "format": "JSON",
                "notes": f"resolved {film_id}",
            }
        )
        time.sleep(DELAY_SECONDS)

        match = resolve_film(payload, film["canonical_title"], release_date)
        if not match:
            raise RuntimeError(f"no Sacnilk match for {film_id} {film['canonical_title']}")

        url = SACNILK + match["url"]
        html, status = request_html(url)
        access.append(
            {
                "source_name": "Sacnilk",
                "url": url,
                "http_status": status,
                "format": "HTML",
                "notes": f"day-wise table for {film_id}",
            }
        )
        time.sleep(DELAY_SECONDS)

        days = extract_days(day_table(html))
        by_index = {day["day_index"]: day for day in days}
        offsets = window_offsets(release_date)
        picked = [by_index.get(offset + 1) for offset in offsets]

        if any(day is None or day["net_cr"] is None for day in picked):
            raise RuntimeError(f"incomplete 3-day window for {film_id}: offsets={offsets}")

        total = round(sum(day["net_cr"] for day in picked), 2)
        access_date = c.utc_date()
        non_friday = film_id in c.NON_FRIDAY_IDS

        if release_date.weekday() == 6:
            window_note = (
                f"Sun-Tue (Days 1-3); Sunday release {release_date.isoformat()} "
                "has no Fri-Sat shows"
            )
        elif release_date.weekday() in (3, 2):  # Thu or Wed
            window_note = (
                f"Fri-Sun calendar window = release Days {offsets[0] + 1}-{offsets[-1] + 1}; "
                f"{release_date.strftime('%a')} release {release_date.isoformat()}"
            )
        else:
            window_note = (
                f"Fri-Sun; Friday release {release_date.isoformat()} = Days 1-3"
            )

        # Raw per-film CSV (3 rows, full provenance).
        raw_rows = []
        for slot, offset in enumerate(offsets, start=1):
            day = by_index[offset + 1]
            calendar_date = release_date + timedelta(days=offset)
            raw_rows.append(
                {
                    "film_id": film_id,
                    "day_index": day["day_index"],
                    "day_label": calendar_date.strftime("%a"),
                    "date": calendar_date.isoformat(),
                    "india_net_cr": day["net_cr"],
                    "source_url": url,
                    "access_date": access_date,
                    "extraction_note": f"Sacnilk All Language India net; {window_note}",
                }
            )
            daily_rows.append(
                {
                    "film_id": film_id,
                    "day_slot": slot,
                    "day_index": day["day_index"],
                    "calendar_date": calendar_date.isoformat(),
                    "weekday": calendar_date.strftime("%a"),
                    "india_net_cr": day["net_cr"],
                    "is_non_friday_release": non_friday,
                    "source_url": url,
                    "access_date": access_date,
                }
            )
        c.write_csv(pd.DataFrame(raw_rows), RAW_DIR / f"{film_id}_weekend.csv")

        consolidated.append(
            {
                "film_id": film_id,
                "canonical_title": film["canonical_title"],
                "day1_label": raw_rows[0]["day_label"],
                "day1_date": raw_rows[0]["date"],
                "day1_net_cr": raw_rows[0]["india_net_cr"],
                "day2_label": raw_rows[1]["day_label"],
                "day2_date": raw_rows[1]["date"],
                "day2_net_cr": raw_rows[1]["india_net_cr"],
                "day3_label": raw_rows[2]["day_label"],
                "day3_date": raw_rows[2]["date"],
                "day3_net_cr": raw_rows[2]["india_net_cr"],
                "opening_3d_india_net_cr": total,
                "is_non_friday_release": non_friday,
                "window_note": window_note,
                "source_name": "Sacnilk",
                "source_url": url,
                "access_date": access_date,
            }
        )

        roster_total = float(film["fri_sun_india_net_cr"])
        delta = round(total - roster_total, 2)
        print(
            f"  {film_id} {film['canonical_title'][:26]:26} {match['url']:32} "
            f"3d={total:8.2f} roster={roster_total:8.2f} delta={delta:+.2f}"
        )
        if abs(delta) > 0.01:
            log_rows.append(
                {
                    "step_id": STEP_ID,
                    "table_affected": "opening_weekend_verified",
                    "problem_found": (
                        f"{film_id} {film['canonical_title']}: Sacnilk day-wise sum "
                        f"{total} crore differs from the roster Fri-Sun figure "
                        f"{roster_total} crore by {delta:+.2f} crore."
                    ),
                    "rows_affected": 1,
                    "action_taken": (
                        "Used the Sacnilk day-wise sum as the verified outcome; kept the "
                        "roster figure in films_master for audit."
                    ),
                    "justification": (
                        "Sacnilk is the locked primary trade source; day-wise cells are "
                        "more granular than the pre-audited summary and supersede it."
                    ),
                }
            )

    wide = c.write_csv(pd.DataFrame(consolidated, columns=CONSOLIDATED_COLUMNS), CONSOLIDATED)
    long = c.write_csv(pd.DataFrame(daily_rows, columns=DAILY_COLUMNS), DAILY)
    log = c.write_access_log(STEP, access)
    if log_rows:
        c.upsert_cleaning_log(STEP_ID, log_rows)

    print(f"\nWrote {wide.relative_to(c.REPO_ROOT)} ({len(consolidated)} rows)")
    print(f"Wrote {long.relative_to(c.REPO_ROOT)} ({len(daily_rows)} daily rows)")
    print(f"Wrote 12 per-film files under {RAW_DIR.relative_to(c.REPO_ROOT)}/")
    print(f"Wrote {log.relative_to(c.REPO_ROOT)} ({len(access)} access records)")
    print(f"Cleaning log deltas: {len(log_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
