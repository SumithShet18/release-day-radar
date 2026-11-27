"""Step 6 - automated Phase 2 validation and source register.

Runs the agreed assertions over every generated table, prints a PASS/FAIL
summary, and builds docs/source_register.csv + .md from the per-step access
logs.

Run:  python src/06_validate_phase2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

STEP = "06_validate"

CONSOLIDATED = c.CLEAN / "opening_weekend_verified.csv"
DAILY = c.CLEAN / "opening_3d_daily.csv"
RECONCILIATION = c.CLEAN / "wiki_reconciliation_report.csv"
WIKI = c.CLEAN / "wiki_infobox.csv"
TRENDS = c.CLEAN / "google_trends_combined.csv"

EXPECTED_CONSOLIDATED = [
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

TERMS = {
    "Wikipedia": "CC BY-SA 4.0; attribution required; one request per 1.5 s.",
    "Sacnilk": (
        "Proprietary estimates; robots.txt allows /movie/ and /news/; "
        "one request per 1.5 s; figures not redistributed as a bulk dataset."
    ),
    "Sacnilk search API": (
        "Proprietary; internal search endpoint used at one request per 1.5 s; "
        "no bulk redistribution."
    ),
    "TMDb API": (
        "TMDb API Terms of Use; attribution required; no endorsement implied."
    ),
    "YouTube Data API v3": "YouTube API Services Terms of Service.",
    "Project owner roster": "Internal audited project data; cross-checked against Sacnilk.",
}

RESULTS: list[dict] = []


def record(check: str, ok: bool, detail: str, warn: bool = False) -> None:
    if ok:
        status = "PASS"
    elif warn:
        status = "WARN"
    else:
        status = "FAIL"
    RESULTS.append({"check": check, "status": status, "detail": detail})


def main() -> int:
    c.ensure_dirs()
    master = pd.read_csv(c.MASTER, dtype={"film_id": str, "tmdb_id": str})
    consolidated = pd.read_csv(CONSOLIDATED, dtype={"film_id": str})
    daily = pd.read_csv(DAILY, dtype={"film_id": str})
    reconciliation = pd.read_csv(RECONCILIATION, dtype={"film_id": str})
    wiki = pd.read_csv(WIKI, dtype={"film_id": str})
    trends = pd.read_csv(TRENDS, dtype={"film_id": str})

    # 1. Row counts -------------------------------------------------------
    record("Films in master", len(master) == 12, f"{len(master)} rows (expected 12)")
    record("Verified weekend rows", len(consolidated) == 12, f"{len(consolidated)} rows (expected 12)")
    record("Daily box-office rows", len(daily) == 36, f"{len(daily)} rows (expected 36)")
    record("Reconciliation rows", len(reconciliation) == 12, f"{len(reconciliation)} rows")
    record("Wikipedia infobox rows", len(wiki) == 12, f"{len(wiki)} rows")
    record(
        "TMDb JSON bundles",
        len(list((c.RAW / "tmdb").glob("F*_tmdb.json"))) == 12,
        f"{len(list((c.RAW / 'tmdb').glob('F*_tmdb.json')))} files (expected 12)",
    )

    # 2. Keys -------------------------------------------------------------
    for name, frame in (
        ("master", master),
        ("consolidated", consolidated),
        ("reconciliation", reconciliation),
    ):
        record(f"{name}: unique film_id", not frame["film_id"].duplicated().any(),
               f"{int(frame['film_id'].duplicated().sum())} duplicates")
        record(f"{name}: no null film_id", frame["film_id"].notna().all(),
               f"{int(frame['film_id'].isna().sum())} nulls")
    daily_dupes = int(daily.duplicated(["film_id", "day_slot"]).sum())
    record("daily: unique film_id+day_slot", daily_dupes == 0, f"{daily_dupes} duplicates")
    record("daily: no null film_id", daily["film_id"].notna().all(),
           f"{int(daily['film_id'].isna().sum())} nulls")

    # 3. Domain logic -----------------------------------------------------
    record("est_budget_cr > 0", bool((master["est_budget_cr"] > 0).all()),
           f"min={master['est_budget_cr'].min()}")
    record("opening_3d_india_net_cr > 0", bool((consolidated["opening_3d_india_net_cr"] > 0).all()),
           f"min={consolidated['opening_3d_india_net_cr'].min()}")
    merged = consolidated.merge(
        master[["film_id", "lifetime_ww_gross_cr"]], on="film_id", how="left"
    )
    over = merged[merged["opening_3d_india_net_cr"] > merged["lifetime_ww_gross_cr"]]
    record("opening_3d <= lifetime WW", over.empty,
           f"{len(over)} violations" + (f": {over['film_id'].tolist()}" if len(over) else ""))

    wide_sum = (
        consolidated[["day1_net_cr", "day2_net_cr", "day3_net_cr"]].sum(axis=1).round(2)
    )
    mismatch = (wide_sum - consolidated["opening_3d_india_net_cr"]).abs() > 0.01
    record("3-day components sum to total", not mismatch.any(),
           f"{int(mismatch.sum())} rows off by more than 0.01 crore")

    daily_sum = daily.groupby("film_id")["india_net_cr"].sum().round(2)
    totals = consolidated.set_index("film_id")["opening_3d_india_net_cr"]
    aligned = (daily_sum - totals).abs() <= 0.01
    record("daily table matches consolidated", bool(aligned.all()),
           f"{int((~aligned).sum())} films differ")

    # 4. Schema / dtypes --------------------------------------------------
    record("consolidated schema", list(consolidated.columns) == EXPECTED_CONSOLIDATED,
           "columns and order match the locked schema")
    record("est_budget_cr dtype float", pd.api.types.is_float_dtype(master["est_budget_cr"]),
           str(master["est_budget_cr"].dtype))
    record("opening total dtype float",
           pd.api.types.is_float_dtype(consolidated["opening_3d_india_net_cr"]),
           str(consolidated["opening_3d_india_net_cr"].dtype))
    record("is_non_friday_release dtype bool",
           pd.api.types.is_bool_dtype(consolidated["is_non_friday_release"]),
           str(consolidated["is_non_friday_release"].dtype))
    parsed_dates = pd.to_datetime(consolidated["day1_date"], errors="coerce")
    record("day1_date parses as datetime", parsed_dates.notna().all(),
           f"{int(parsed_dates.isna().sum())} unparsable")
    record("day_slot dtype int", pd.api.types.is_integer_dtype(daily["day_slot"]),
           str(daily["day_slot"].dtype))
    record("daily india_net_cr dtype float",
           pd.api.types.is_float_dtype(daily["india_net_cr"]), str(daily["india_net_cr"].dtype))

    # 5. Google Trends ----------------------------------------------------
    trend_columns = ["film_id", "term", "date", "interest", "source_file"]
    record(
        "Trends combined schema",
        list(trends.columns) == trend_columns,
        f"{len(trends.columns)} columns",
    )
    record("Trends combined non-empty", len(trends) > 0, f"{len(trends)} rows")
    film_count = trends["film_id"].nunique() if not trends.empty else 0
    record("Trends films covered", film_count == 12, f"{film_count}/12 films")

    trend_dates = pd.to_datetime(trends["date"], errors="coerce")
    record(
        "Trends dates parse",
        trend_dates.notna().all(),
        f"{int(trend_dates.isna().sum())} unparsable",
    )
    trend_dupes = int(trends.duplicated(["film_id", "date"]).sum())
    record(
        "Trends unique film_id+date",
        trend_dupes == 0,
        f"{trend_dupes} duplicates",
    )
    if trends.empty:
        record("Trends interest within 0-100", False, "no rows")
        record("Trends one term per film", False, "no rows")
        record("Trends >= 60 daily points per film", False, "no rows")
    else:
        record(
            "Trends interest within 0-100",
            bool(trends["interest"].between(0, 100).all()),
            f"min={trends['interest'].min():g} max={trends['interest'].max():g}",
        )
        terms_per_film = trends.groupby("film_id")["term"].nunique()
        record(
            "Trends one term per film",
            bool((terms_per_film <= 1).all()),
            f"max={int(terms_per_film.max())} terms",
        )
        points_per_film = trends.groupby("film_id").size()
        record(
            "Trends >= 60 daily points per film",
            bool((points_per_film >= 60).all()),
            f"min={int(points_per_film.min())} points",
        )

    release_by_film = master.set_index("film_id")["release_date"]
    uncovered: list[str] = []
    for film_id, part in trends.groupby("film_id"):
        dates = pd.to_datetime(part["date"])
        release = pd.to_datetime(release_by_film.get(film_id), errors="coerce")
        if pd.isna(release) or not (dates.min() <= release <= dates.max()):
            uncovered.append(film_id)
    record(
        "Trends span covers release date",
        not uncovered,
        f"{12 - len(uncovered)}/12 covered"
        + (f"; missing: {', '.join(uncovered)}" if uncovered else ""),
        warn=True,
    )

    # 6. Coverage / manual inputs ----------------------------------------
    tmdb_ok = (master["tmdb_id"].astype(str) != "TBD").sum()
    record("TMDb coverage", tmdb_ok == 12, f"{tmdb_ok}/12 resolved")
    trends_present = len(list((c.RAW / "trends").glob("F*_trends.csv")))
    record("Trends exports present", trends_present == 12,
           f"{trends_present}/12 exports present", warn=True)
    videos_set = (master["youtube_video_id"].astype(str) != "TBD").sum()
    record("YouTube trailer IDs set", videos_set == 12,
           f"{videos_set}/12 awaiting manual input", warn=True)

    # Source register -----------------------------------------------------
    logs = []
    for path in sorted(c.CLEAN.glob("access_log_*.csv")):
        frame = pd.read_csv(path, dtype=str).fillna("")
        logs.append(frame)
    access = pd.concat(logs, ignore_index=True) if logs else pd.DataFrame(columns=c.ACCESS_COLUMNS)
    access["terms_compliance"] = access["source_name"].map(TERMS).fillna("Review required")
    access = access[
        [
            "source_name",
            "url",
            "http_status",
            "format",
            "access_timestamp_utc",
            "step",
            "terms_compliance",
            "notes",
        ]
    ]
    roster_row = pd.DataFrame(
        [
            {
                "source_name": "Project owner roster",
                "url": "data/raw/films_master.csv",
                "http_status": "local",
                "format": "CSV",
                "access_timestamp_utc": c.utc_stamp(),
                "step": "00_roster",
                "terms_compliance": TERMS["Project owner roster"],
                "notes": "12 audited films supplied by the project owner",
            }
        ]
    )
    register = pd.concat([roster_row, access], ignore_index=True)
    c.write_csv(register, c.DOCS / "source_register.csv")

    summary = (
        register.groupby("source_name")
        .agg(urls=("url", "count"), first_access=("access_timestamp_utc", "min"))
        .reset_index()
    )
    lines = [
        "# Source register",
        "",
        f"Generated: {c.utc_stamp()}  ",
        f"Total URL accesses logged: **{len(register)}**",
        "",
        "## Summary",
        "",
        "| Source | URLs | First access (UTC) |",
        "| --- | --- | --- |",
    ]
    for _, row in summary.iterrows():
        lines.append(f"| {row['source_name']} | {row['urls']} | {row['first_access']} |")
    lines += [
        "",
        "## Access log",
        "",
        "| Source | URL | HTTP | Format | Accessed (UTC) | Step | Terms |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in register.iterrows():
        url = str(row["url"]).replace("|", "%7C")
        terms = str(row["terms_compliance"]).replace("|", "/")
        lines.append(
            f"| {row['source_name']} | {url} | {row['http_status']} | {row['format']} | "
            f"{row['access_timestamp_utc']} | {row['step']} | {terms} |"
        )
    lines += [
        "",
        "## Manual inputs",
        "",
        f"- Google Trends exports: {trends_present}/12 present (manual browser export; no API URL)",
        f"- YouTube trailer IDs: {videos_set}/12 present",
        "",
    ]
    (c.DOCS / "source_register.md").write_text("\n".join(lines), encoding="utf-8")

    # Print ---------------------------------------------------------------
    print("\nPhase 2 validation")
    print("=" * 88)
    print(f"{'check':42} {'status':6} detail")
    print("-" * 88)
    for result in RESULTS:
        print(f"{result['check'][:41]:42} {result['status']:6} {result['detail'][:38]}")
    failed = sum(r["status"] == "FAIL" for r in RESULTS)
    passed = sum(r["status"] == "PASS" for r in RESULTS)
    warned = sum(r["status"] == "WARN" for r in RESULTS)
    print("-" * 88)
    print(f"{passed} passed, {warned} warnings, {failed} failed")

    print("\nSource register")
    print("=" * 88)
    print(summary.to_string(index=False))
    print(f"\nWrote docs/source_register.csv ({len(register)} rows)")
    print("Wrote docs/source_register.md")
    print(f"Wrote docs/cleaning_log.csv ({len(pd.read_csv(c.DOCS / 'cleaning_log.csv'))} rows)")

    print("\nRemaining manual inputs")
    print("=" * 88)
    print(f"Google Trends CSVs : {trends_present}/12 -> data/raw/trends/Fxx_trends.csv")
    print(f"YouTube trailer IDs: {videos_set}/12 -> youtube_video_id in data/raw/films_master.csv")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
