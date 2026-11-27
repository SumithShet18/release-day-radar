"""Step 4 - Google Trends scaffolding and validator.

Google Trends has no official export API, so the 12 CSVs are manual browser
exports. This script validates whatever is present, normalises it into one
long table, and prints the exact files still missing.

Expected input: data/raw/trends/F01_trends.csv ... F12_trends.csv
Output:        data/clean/google_trends_combined.csv

Run:  python src/04_trends_layer.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

TRENDS_DIR = c.RAW / "trends"
OUT = c.CLEAN / "google_trends_combined.csv"
COLUMNS = ["film_id", "term", "date", "interest", "source_file"]
DATE_HEADERS = {"day", "week", "month", "hour", "date", "time"}


def parse_export(path: Path, film_id: str) -> tuple[list[dict], str | None]:
    """Parse one Google Trends interest-over-time CSV export."""
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()

    header_index = None
    for index, line in enumerate(lines[:20]):
        cells = next(csv.reader([line]), [])
        if len(cells) >= 2 and cells[0].strip().lower() in DATE_HEADERS:
            header_index = index
            break
    if header_index is None:
        raise ValueError("no Day/Week header row found (is this an interest-over-time export?)")

    rows: list[dict] = []
    reader = csv.reader(lines[header_index:])
    header = next(reader)
    term = ",".join(part.strip() for part in header[1:]) or film_id
    for record in reader:
        if len(record) < 2:
            continue
        raw_date = record[0].strip()
        stamp = pd.to_datetime(raw_date, errors="coerce")
        if pd.isna(stamp):
            continue
        raw_value = record[1].strip().replace(",", "")
        if raw_value in ("", "-"):
            continue
        if raw_value == "<1":
            value = 0.5
        else:
            parsed = pd.to_numeric(raw_value, errors="coerce")
            if pd.isna(parsed):
                continue
            value = float(parsed)
        rows.append(
            {
                "film_id": film_id,
                "term": term,
                "date": stamp.date().isoformat(),
                "interest": value,
                "source_file": path.name,
            }
        )
    return rows, term


def main() -> int:
    c.ensure_dirs()
    master = c.load_master()
    combined: list[dict] = []
    present: set[str] = set()
    errors: list[tuple[str, str]] = []

    for _, film in master.iterrows():
        film_id = film["film_id"]
        path = TRENDS_DIR / f"{film_id}_trends.csv"
        if not path.exists():
            continue
        present.add(film_id)
        try:
            rows, _ = parse_export(path, film_id)
            combined.extend(rows)
            print(f"  {film_id}: parsed {len(rows)} daily points from {path.name}")
        except Exception as exc:
            errors.append((film_id, str(exc)))
            print(f"  {film_id}: ERROR {exc}")

    frame = pd.DataFrame(combined, columns=COLUMNS)
    if not frame.empty:
        frame = frame.sort_values(["film_id", "date"]).reset_index(drop=True)
    out = c.write_csv(frame, OUT)
    print(f"\nWrote {out.relative_to(c.REPO_ROOT)} ({len(frame)} rows)")

    # Coverage audit: row counts, date range, gaps and release-window overlap.
    coverage: list[dict] = []
    for _, film in master.iterrows():
        film_id = film["film_id"]
        part = frame.loc[frame["film_id"] == film_id]
        release = c.as_date(film["release_date"])
        if part.empty:
            coverage.append(
                {
                    "film_id": film_id,
                    "canonical_title": film["canonical_title"],
                    "points": 0,
                    "start": "",
                    "end": "",
                    "span_days": 0,
                    "missing_dates": 0,
                    "release_date": release.isoformat(),
                    "release_in_range": False,
                }
            )
            continue
        dates = pd.to_datetime(part["date"])
        start, end = dates.min(), dates.max()
        full = pd.date_range(start, end, freq="D")
        coverage.append(
            {
                "film_id": film_id,
                "canonical_title": film["canonical_title"],
                "points": len(part),
                "start": start.date().isoformat(),
                "end": end.date().isoformat(),
                "span_days": (end - start).days + 1,
                "missing_dates": len(full.difference(dates)),
                "release_date": release.isoformat(),
                "release_in_range": start.date() <= release <= end.date(),
            }
        )

    print("\nTrends coverage")
    print("=" * 104)
    print(
        f"{'film_id':8} {'points':7} {'start':11} {'end':11} {'span':5} "
        f"{'gaps':5} {'release':11} in-range"
    )
    print("-" * 104)
    for row in coverage:
        print(
            f"{row['film_id']:8} {row['points']:7} {row['start']:11} {row['end']:11} "
            f"{row['span_days']:5} {row['missing_dates']:5} {row['release_date']:11} "
            f"{'yes' if row['release_in_range'] else 'NO'}"
        )

    log_rows: list[dict] = []
    for row in coverage:
        if row["points"] == 0:
            problem = f"{row['film_id']} {row['canonical_title']}: no Trends export found."
            action = "Excluded the film from the combined table and kept it on the missing-file checklist."
        elif not row["release_in_range"]:
            gap_days = (pd.Timestamp(row["release_date"]) - pd.Timestamp(row["end"])).days
            problem = (
                f"{row['film_id']} {row['canonical_title']}: Trends export covers "
                f"{row['start']} to {row['end']} and ends {gap_days} days before release "
                f"({row['release_date']}); release-window interest is missing."
            )
            action = (
                "Retained the parsed pre-release series and flagged the film for a "
                "re-export covering the theatrical release window."
            )
        else:
            continue
        log_rows.append(
            {
                "step_id": "STEP_04",
                "table_affected": "google_trends_combined",
                "problem_found": problem,
                "rows_affected": 1,
                "action_taken": action,
                "justification": (
                    "Release-day search interest is a predictor in the study; an export "
                    "that stops before release cannot represent the outcome window."
                ),
            }
        )
    if log_rows:
        c.upsert_cleaning_log("STEP_04", log_rows)

    if errors:
        print("\nParse errors:")
        for film_id, message in errors:
            print(f"  {film_id}: {message}")

    print("\nGoogle Trends export checklist")
    print("=" * 86)
    print(f"{'film_id':8} {'status':9} {'expected file':22} suggested query")
    print("-" * 86)
    missing = 0
    for _, film in master.iterrows():
        film_id = film["film_id"]
        status = "PRESENT" if film_id in present else "MISSING"
        if status == "MISSING":
            missing += 1
        print(
            f"{film_id:8} {status:9} {film_id}_trends.csv{'':9} "
            f"{film['canonical_title']}"
        )
    print("-" * 86)
    print(f"{len(present)}/12 present, {missing}/12 awaiting manual browser export")
    if missing:
        print(
            "Export path: https://trends.google.com/trends/explore?geo=IN -> "
            "90 days spanning trailer + release -> Download -> CSV"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
