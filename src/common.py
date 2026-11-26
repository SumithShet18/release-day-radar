"""Shared helpers for the Release Day Radar Phase 2 collection scripts.

Run the numbered scripts directly, e.g. ``python src/01_wiki_layer.py``.
Each script inserts ``src/`` on ``sys.path`` before importing this module.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW = REPO_ROOT / "data" / "raw"
CLEAN = REPO_ROOT / "data" / "clean"
DOCS = REPO_ROOT / "docs"

MASTER = RAW / "films_master.csv"

WIKI_UA = (
    "ReleaseDayRadar/0.1 (student research project; "
    "contact: sumithshet35@gmail.com)"
)
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# Locked methodology: these releases are not Friday openers.
NON_FRIDAY_IDS = {"F01", "F02", "F07", "F08", "F10"}

ACCESS_COLUMNS = [
    "step",
    "source_name",
    "url",
    "http_status",
    "format",
    "access_timestamp_utc",
    "notes",
]

CLEANING_COLUMNS = [
    "step_id",
    "table_affected",
    "problem_found",
    "rows_affected",
    "action_taken",
    "justification",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_stamp() -> str:
    return utc_now().isoformat(timespec="seconds")


def utc_date() -> str:
    return utc_now().date().isoformat()


def ensure_dirs() -> None:
    for path in (
        CLEAN,
        DOCS,
        RAW / "wiki",
        RAW / "trends",
        RAW / "youtube",
        RAW / "tmdb",
        RAW / "boxoffice",
    ):
        path.mkdir(parents=True, exist_ok=True)


def load_master() -> pd.DataFrame:
    df = pd.read_csv(
        MASTER,
        dtype={"film_id": str, "youtube_video_id": str, "tmdb_id": str},
    )
    df["release_date"] = pd.to_datetime(df["release_date"]).dt.date
    return df


def write_csv(df: pd.DataFrame, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    return path


_AMOUNT_RE = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)"
    r"(?:\s*[–-]\s*(\d[\d,]*(?:\.\d+)?))?"
    r"\s*(crores?|crs?|cr|lakhs?|lacs?|lakh|lac|billions?|billion|bn|millions?|million|mn|l)\b",
    re.IGNORECASE,
)

_UNIT_FACTOR = {
    "cr": 1.0,
    "crore": 1.0,
    "crores": 1.0,
    "crs": 1.0,
    "lakh": 0.01,
    "lakhs": 0.01,
    "lac": 0.01,
    "lacs": 0.01,
    "billion": 100.0,
    "billions": 100.0,
    "bn": 100.0,
    "million": 0.1,
    "millions": 0.1,
    "mn": 0.1,
    "l": 0.01,
}


def crore_from_text(text: object) -> float | None:
    """Convert a money string to crore.

    Handles ``₹807.91 crore``, ``₹90 lakh``, ``₹1.81 billion`` and ranges
    such as ``₹250–300 crore`` (midpoint). Returns ``None`` when no amount
    with a recognised unit is present.
    """
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None
    match = _AMOUNT_RE.search(str(text))
    if not match:
        return None
    first = float(match.group(1).replace(",", ""))
    second = float(match.group(2).replace(",", "")) if match.group(2) else first
    value = (first + second) / 2
    factor = _UNIT_FACTOR[match.group(3).lower()]
    return round(value * factor, 2)


_DATE_RE = re.compile(r"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2})")


def parse_date(text: object) -> str | None:
    """Extract the first date found in free text, as ISO ``YYYY-MM-DD``."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return None
    match = _DATE_RE.search(str(text))
    if not match:
        return None
    stamp = pd.to_datetime(match.group(1), errors="coerce", dayfirst=True)
    if pd.isna(stamp):
        return None
    return stamp.date().isoformat()


def title_key(text: object) -> str:
    """Case/punctuation-insensitive key for cross-source title matching."""
    return re.sub(r"[^a-z0-9]+", "", str(text).casefold())


def clean_text(text: object) -> str:
    value = str(text).replace("\xa0", " ")
    value = re.sub(r"\[\s*\d+\s*\]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def write_access_log(step: str, records: list[dict]) -> Path:
    ensure_dirs()
    for record in records:
        record.setdefault("step", step)
        record.setdefault("access_timestamp_utc", utc_stamp())
    frame = pd.DataFrame(records, columns=ACCESS_COLUMNS)
    return write_csv(frame, CLEAN / f"access_log_{step}.csv")


def upsert_cleaning_log(step_id: str, rows: list[dict]) -> pd.DataFrame:
    """Replace this step's rows in docs/cleaning_log.csv, keep every other step."""
    ensure_dirs()
    path = DOCS / "cleaning_log.csv"
    if path.exists():
        existing = pd.read_csv(path, dtype=str)
        existing = existing[existing["step_id"] != step_id]
    else:
        existing = pd.DataFrame(columns=CLEANING_COLUMNS)
    new = pd.DataFrame(rows, columns=CLEANING_COLUMNS)
    combined = pd.concat([existing, new], ignore_index=True)
    write_csv(combined, path)
    return combined


def as_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()
