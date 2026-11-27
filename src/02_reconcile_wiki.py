"""Step 2 - reconcile the audited roster against Wikipedia infobox figures.

Joins data/raw/films_master.csv to data/clean/wiki_infobox.csv on film_id,
computes percentage deltas for budget and worldwide gross, flags any delta
above 5% or any missing infobox value, writes the reconciliation report and
seeds docs/cleaning_log.csv.

Run:  python src/02_reconcile_wiki.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

STEP_ID = "STEP_02"
TOLERANCE_PCT = 5.0

WIKI = c.CLEAN / "wiki_infobox.csv"
OUT = c.CLEAN / "wiki_reconciliation_report.csv"


def delta_pct(roster: float, wiki: float | None) -> float | None:
    if wiki is None or pd.isna(wiki) or not roster:
        return None
    return round((float(wiki) - float(roster)) / float(roster) * 100, 2)


def status_for(delta: float | None) -> str:
    if delta is None:
        return "FLAG_MISSING"
    if abs(delta) > TOLERANCE_PCT:
        return "FLAG_MISMATCH"
    return "OK"


def main() -> int:
    c.ensure_dirs()
    master = c.load_master()
    wiki = pd.read_csv(WIKI, dtype={"film_id": str})
    merged = master.merge(wiki, on="film_id", how="left", suffixes=("", "_wiki"))

    rows: list[dict] = []
    log_rows: list[dict] = []

    for _, film in merged.iterrows():
        budget_delta = delta_pct(film["est_budget_cr"], film.get("wiki_budget_cr"))
        gross_delta = delta_pct(
            film["lifetime_ww_gross_cr"], film.get("wiki_ww_gross_cr")
        )
        budget_status = status_for(budget_delta)
        gross_status = status_for(gross_delta)

        statuses = {budget_status, gross_status}
        if "FLAG_MISSING" in statuses:
            overall = "FLAG_MISSING"
        elif "FLAG_MISMATCH" in statuses:
            overall = "FLAG_MISMATCH"
        else:
            overall = "OK"

        notes = []
        if film.get("notes") and str(film["notes"]) not in ("snapshot saved", "nan"):
            notes.append(str(film["notes"]))
        if budget_status == "FLAG_MISSING":
            notes.append("Wikipedia infobox has no parsable Budget")
        if gross_status == "FLAG_MISSING":
            notes.append("Wikipedia infobox has no parsable Box office")

        rows.append(
            {
                "film_id": film["film_id"],
                "canonical_title": film["canonical_title"],
                "roster_budget_cr": film["est_budget_cr"],
                "wiki_budget_cr": film.get("wiki_budget_cr"),
                "budget_delta_pct": budget_delta,
                "budget_status": budget_status,
                "roster_ww_gross_cr": film["lifetime_ww_gross_cr"],
                "wiki_ww_gross_cr": film.get("wiki_ww_gross_cr"),
                "gross_delta_pct": gross_delta,
                "gross_status": gross_status,
                "overall_status": overall,
                "notes": "; ".join(notes),
            }
        )

        for field, roster_value, wiki_value, delta, status in (
            ("budget", film["est_budget_cr"], film.get("wiki_budget_cr"), budget_delta, budget_status),
            ("worldwide gross", film["lifetime_ww_gross_cr"], film.get("wiki_ww_gross_cr"), gross_delta, gross_status),
        ):
            if status == "OK":
                continue
            if status == "FLAG_MISSING":
                problem = (
                    f"{film['film_id']} {film['canonical_title']}: Wikipedia infobox "
                    f"has no parsable {field}; roster value is {roster_value} crore."
                )
                action = "Retained the audited roster value; recorded the gap for manual source review."
            else:
                problem = (
                    f"{film['film_id']} {film['canonical_title']}: Wikipedia {field} "
                    f"{wiki_value} crore vs roster {roster_value} crore "
                    f"({delta:+.2f}%, tolerance ±{TOLERANCE_PCT:.0f}%)."
                )
                action = (
                    "Kept the audited roster value as the primary; retained the "
                    "Wikipedia figure for traceability and Phase 3 sensitivity checks."
                )
            log_rows.append(
                {
                    "step_id": STEP_ID,
                    "table_affected": "films_master vs wiki_infobox",
                    "problem_found": problem,
                    "rows_affected": 1,
                    "action_taken": action,
                    "justification": (
                        "Roster is the signed-off project baseline; Wikipedia infoboxes are "
                        "community-maintained, often ranges, and can lag trade reporting."
                    ),
                }
            )

    report = c.write_csv(pd.DataFrame(rows), OUT)

    # Locked methodology decisions belong in the log even when no mismatch occurs.
    log_rows.extend(
        [
            {
                "step_id": STEP_ID,
                "table_affected": "opening_weekend_verified",
                "problem_found": (
                    "5 of 12 releases are not Friday openers (F01, F02, F10 Thursday; "
                    "F07 Wednesday; F08 Sunday), so a calendar Fri-Sun window is not "
                    "comparable across the cohort."
                ),
                "rows_affected": 5,
                "action_taken": (
                    "Standardized the outcome to opening 3-day India net: Fri-Sun for "
                    "11 films, Sun-Tue (Days 1-3) for F08; added is_non_friday_release."
                ),
                "justification": (
                    "Keeps the studio decision metric (first three days of ticket sales) "
                    "on one footing while preserving the full 12-film sample."
                ),
            },
            {
                "step_id": STEP_ID,
                "table_affected": "opening_weekend_verified",
                "problem_found": (
                    "F08 Sikandar released on Sunday 2025-03-30, so it has no Friday or "
                    "Saturday shows in its opening window."
                ),
                "rows_affected": 1,
                "action_taken": (
                    "Included F08 with a Sun-Tue (Days 1-3) window and flagged it "
                    "is_non_friday_release=True for Phase 3 sensitivity testing."
                ),
                "justification": (
                    "Dropping a 200 crore release would shrink an already small sample "
                    "and bias the cohort toward Friday openers."
                ),
            },
            {
                "step_id": STEP_ID,
                "table_affected": "films_master",
                "problem_found": (
                    "F01 Dhurandhar: The Revenge and F05 Dhurandhar are the same "
                    "franchise, so 2 of 12 rows are not statistically independent."
                ),
                "rows_affected": 2,
                "action_taken": (
                    "Retained both rows; flagged the overlap for a Phase 3 leave-one-out "
                    "sensitivity check."
                ),
                "justification": (
                    "Both are theatrically significant releases, but franchise spillover "
                    "must be disclosed rather than silently pooled."
                ),
            },
        ]
    )

    c.upsert_cleaning_log(STEP_ID, log_rows)

    print("\nRoster vs Wikipedia reconciliation")
    print("=" * 96)
    display = pd.DataFrame(rows)[
        [
            "film_id",
            "canonical_title",
            "roster_budget_cr",
            "wiki_budget_cr",
            "budget_delta_pct",
            "roster_ww_gross_cr",
            "wiki_ww_gross_cr",
            "gross_delta_pct",
            "overall_status",
        ]
    ]
    print(display.to_string(index=False))
    counts = pd.Series([r["overall_status"] for r in rows]).value_counts().to_dict()
    print(f"\nOverall status: {counts}")
    print(f"Wrote {report.relative_to(c.REPO_ROOT)} ({len(rows)} rows)")
    print(f"Cleaning log rows for {STEP_ID}: {len(log_rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
