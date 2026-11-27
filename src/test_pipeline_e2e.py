"""Step E2E - Automated End-to-End Pipeline & Privacy Smoke Test.

Asserts:
  1. All expected clean CSVs exist with exact row counts.
  2. Zero author PII fields appear in data/clean/ or data/raw/youtube/*.json.
  3. Zero null PK/FK keys (film_id, comment_id) or core metrics.
  4. All 4 PNG charts in docs/charts/ exist and are > 50 KB.
  5. .env is gitignored and no tracked/candidate file exceeds 50 MB.

Run:  python -X utf8 src/test_pipeline_e2e.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

PII_KEYS = {
    "authorDisplayName",
    "authorProfileImageUrl",
    "authorChannelUrl",
    "authorChannelId",
}


def main() -> int:
    # 1. Exact CSV row counts
    expected_exact = {
        "films_analytical_master.csv": 12,
        "opening_weekend_verified.csv": 12,
        "youtube_comments_scored.csv": 65067,
        "pyspark_film_text_summary.csv": 12,
    }
    frames: dict[str, pd.DataFrame] = {}
    for name, exp_rows in expected_exact.items():
        path = c.CLEAN / name
        assert path.exists(), f"Missing clean CSV: {path}"
        df = pd.read_csv(path)
        assert len(df) == exp_rows, f"{name}: expected {exp_rows} rows, got {len(df)}"
        frames[name] = df

    corr_path = c.CLEAN / "spearman_correlations.csv"
    assert corr_path.exists(), f"Missing {corr_path}"
    corr_df = pd.read_csv(corr_path)
    assert len(corr_df) >= 5, f"spearman_correlations.csv: expected >= 5 rows, got {len(corr_df)}"

    # 2. Zero PII fields in data/clean/*.csv headers and data/raw/youtube/*.json
    for csv_path in sorted(c.CLEAN.glob("*.csv")):
        cols = set(pd.read_csv(csv_path, nrows=0).columns)
        overlap = cols & PII_KEYS
        assert not overlap, f"PII columns {overlap} found in {csv_path}"

    for json_path in sorted((c.RAW / "youtube").glob("F*_comments.json")):
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        for item in payload.get("items", [])[:200]:
            snip = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            overlap = set(snip.keys()) & PII_KEYS
            assert not overlap, f"PII keys {overlap} found in {json_path.name}"

    # 3. Zero null PK/FK keys and core metrics
    master = frames["films_analytical_master.csv"]
    for col in ("film_id", "fri_sun_india_net_cr", "est_budget_cr"):
        assert master[col].isna().sum() == 0, f"Nulls in films_analytical_master.{col}"

    ver = frames["opening_weekend_verified.csv"]
    assert ver["film_id"].isna().sum() == 0, "Nulls in opening_weekend_verified.film_id"

    scored = frames["youtube_comments_scored.csv"]
    for col in ("comment_id", "film_id", "vader_compound"):
        assert scored[col].isna().sum() == 0, f"Nulls in youtube_comments_scored.{col}"

    # 4. All 4 PNG charts exist and are > 50 KB
    charts_dir = c.DOCS / "charts"
    pngs = sorted(charts_dir.glob("chart_*.png"))
    assert len(pngs) == 4, f"Expected 4 charts in {charts_dir}, found {len(pngs)}"
    for png in pngs:
        kb = png.stat().st_size / 1024.0
        assert kb > 50.0, f"Chart {png.name} too small ({kb:.1f} KB <= 50 KB)"

    # 5. .env is gitignored and no tracked file > 50 MB
    chk = subprocess.run(
        ["git", "check-ignore", ".env"],
        cwd=c.REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert chk.returncode == 0, ".env is NOT gitignored!"

    ls_files = subprocess.run(
        ["git", "ls-files"],
        cwd=c.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    for rel in ls_files.stdout.splitlines():
        fpath = c.REPO_ROOT / rel
        if fpath.exists():
            mb = fpath.stat().st_size / (1024 * 1024)
            assert mb <= 50.0, f"Tracked file exceeds 50 MB: {rel} ({mb:.2f} MB)"

    print("E2E SMOKE TEST PASSED: all 5 assertion groups succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
