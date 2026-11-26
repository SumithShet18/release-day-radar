"""Phase 1 source verification for Release Day Radar.

Proves that every planned source is reachable and returns the shape the
pipeline expects, before any collection work begins:

    structured    Wikipedia box-office HTML tables, Google Trends CSV exports
    semi-structured  YouTube Data API v3 (videos), TMDb API v3
    unstructured  YouTube commentThreads, local Kaggle IMDb 50K corpus

Credential-gated checks report SKIP when the matching key is absent, so the
script is safe to run on a fresh clone. No usernames, profile links or comment
text are written to disk - only counts and metadata (see privacy rules in the
brief).

Usage::

    python -m src.test_sources              # every check
    python -m src.test_sources --offline    # local files only
    python -m src.test_sources --json       # machine-readable report

Exit code 0 when nothing fails, 2 when at least one check fails, 1 on bad usage.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import pandas as pd
import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
EXTERNAL_DIR = RAW_DIR / "external"

USER_AGENT = (
    "ReleaseDayRadar/0.1 (student research project; "
    "contact: sumithshet35@gmail.com)"
)
TIMEOUT = 25

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_Hindi_films_of_2025"
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
TMDB_API = "https://api.themoviedb.org/3"
TMDB_SMOKE_QUERY = "Dhurandhar"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"

Status = tuple[str, str]


@dataclass
class Result:
    check: str
    source: str
    status: str
    detail: str
    elapsed_ms: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _env(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _api_error(response: requests.Response) -> str:
    """Pull Google/TMDb's human-readable error message out of a response."""
    try:
        payload = response.json()
    except ValueError:
        return response.text[:160]
    error = payload.get("error")
    if isinstance(error, dict):  # Google style
        return str(error.get("message", error))[:160]
    if error:  # TMDb style
        return str(payload.get("status_message", error))[:160]
    return response.text[:160]


# ---------------------------------------------------------------------------
# Checks - each returns (status, detail)
# ---------------------------------------------------------------------------
def check_wikipedia() -> Status:
    response = requests.get(
        WIKI_URL, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT
    )
    response.raise_for_status()
    tables = pd.read_html(io.StringIO(response.text))
    substantial = [table for table in tables if len(table) >= 10]
    if not substantial:
        return FAIL, f"{len(tables)} tables parsed, none with 10+ rows"
    largest = max(substantial, key=len)
    columns = ", ".join(str(c) for c in largest.columns[:3])
    return PASS, (
        f"{len(tables)} tables parsed; largest {len(largest)}x{len(largest.columns)}"
        f" rows/cols ({columns}, ...)"
    )


def check_trends() -> Status:
    exports = sorted((RAW_DIR / "trends").glob("*.csv"))
    if not exports:
        return SKIP, "no exports yet - drop Google Trends India CSVs in data/raw/trends/"
    frame = None
    for skiprows in (0, 1, 2):
        try:
            frame = pd.read_csv(exports[0], skiprows=skiprows)
            break
        except (pd.errors.ParserError, pd.errors.EmptyDataError):
            continue
    if frame is None:
        return FAIL, f"could not parse {exports[0].name} - re-export from Trends UI"
    return PASS, (
        f"{len(exports)} CSV(s); {exports[0].name}: "
        f"{len(frame)} rows x {len(frame.columns)} cols"
    )


def check_youtube_videos() -> Status:
    key = _env("YOUTUBE_API_KEY")
    if not key:
        return SKIP, "YOUTUBE_API_KEY not set (copy .env.example to .env)"
    video_id = _env("YOUTUBE_SMOKE_VIDEO_ID") or "dQw4w9WgXcQ"
    response = requests.get(
        f"{YOUTUBE_API}/videos",
        params={"part": "snippet,statistics", "id": video_id, "key": key},
        timeout=TIMEOUT,
    )
    if response.status_code in (400, 403):
        return FAIL, f"HTTP {response.status_code}: {_api_error(response)}"
    response.raise_for_status()
    items = response.json().get("items", [])
    if not items:
        return FAIL, f"no video returned for id={video_id}"
    snippet = items[0]["snippet"]
    stats = items[0].get("statistics", {})
    return PASS, (
        f"publishedAt={snippet.get('publishedAt')} views={stats.get('viewCount')} "
        f"comments={stats.get('commentCount')} | {snippet.get('title', '')[:40]}"
    )


def check_youtube_comments() -> Status:
    key = _env("YOUTUBE_API_KEY")
    if not key:
        return SKIP, "YOUTUBE_API_KEY not set (copy .env.example to .env)"
    video_id = _env("YOUTUBE_SMOKE_VIDEO_ID") or "dQw4w9WgXcQ"
    response = requests.get(
        f"{YOUTUBE_API}/commentThreads",
        params={
            "part": "snippet",
            "videoId": video_id,
            "maxResults": 5,
            "textFormat": "plainText",
            "key": key,
        },
        timeout=TIMEOUT,
    )
    if response.status_code in (400, 403):
        return FAIL, f"HTTP {response.status_code}: {_api_error(response)}"
    response.raise_for_status()
    payload = response.json()
    page = payload.get("pageInfo", {})
    threads = payload.get("items", [])
    if not threads:
        return FAIL, f"comments disabled or empty for id={video_id}"
    return PASS, (
        f"{len(threads)} threads on page 1 (totalResults={page.get('totalResults')}); "
        "text/author not persisted"
    )


def check_tmdb() -> Status:
    key = _env("TMDB_API_KEY")
    if not key:
        return SKIP, "TMDB_API_KEY not set (copy .env.example to .env)"
    search = requests.get(
        f"{TMDB_API}/search/movie",
        params={
            "api_key": key,
            "query": TMDB_SMOKE_QUERY,
            "language": "en-IN",
            "include_adult": "false",
        },
        timeout=TIMEOUT,
    )
    if search.status_code in (401, 403):
        return FAIL, f"HTTP {search.status_code}: {_api_error(search)}"
    search.raise_for_status()
    results = search.json().get("results", [])
    if not results:
        return FAIL, f"/search/movie returned no results for '{TMDB_SMOKE_QUERY}'"

    details = requests.get(
        f"{TMDB_API}/movie/{results[0]['id']}",
        params={"api_key": key, "language": "en-IN"},
        timeout=TIMEOUT,
    )
    details.raise_for_status()
    movie = details.json()
    genres = ", ".join(g.get("name", "") for g in movie.get("genres", []))
    return PASS, (
        f"{movie.get('title')} ({movie.get('release_date')}) "
        f"runtime={movie.get('runtime')}m genres={genres} "
        f"popularity={movie.get('popularity')}"
    )


def check_imdb_corpus() -> Status:
    if not EXTERNAL_DIR.exists():
        return SKIP, "data/raw/external/ missing"
    candidates = [
        path
        for path in EXTERNAL_DIR.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".csv", ".tsv"}
        and "imdb" in path.name.lower()
    ]
    if not candidates:
        return SKIP, "place the Kaggle IMDb 50K CSV in data/raw/external/"
    corpus = candidates[0]
    try:
        sample = pd.read_csv(corpus, nrows=5)
    except UnicodeDecodeError:
        sample = pd.read_csv(corpus, nrows=5, encoding="latin-1")
    with corpus.open("r", encoding="utf-8", errors="ignore") as handle:
        approx_rows = max(sum(1 for _ in handle) - 1, 0)
    return PASS, (
        f"{corpus.name}: ~{approx_rows:,} rows x {len(sample.columns)} cols "
        f"({corpus.stat().st_size / 1e6:.1f} MB)"
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Check:
    name: str
    source: str
    func: Callable[[], Status]
    network: bool


CHECKS: tuple[Check, ...] = (
    Check("Wikipedia box-office tables", "Wikipedia (HTML)", check_wikipedia, True),
    Check("Google Trends exports", "Google Trends (CSV)", check_trends, False),
    Check("YouTube trailer metadata", "YouTube Data API v3 (JSON)", check_youtube_videos, True),
    Check("YouTube trailer comments", "YouTube Data API v3 (JSON/text)", check_youtube_comments, True),
    Check("TMDb film metadata", "TMDb API v3 (JSON)", check_tmdb, True),
    Check("IMDb 50K practice corpus", "Kaggle (local CSV)", check_imdb_corpus, False),
)


def run(offline: bool = False) -> list[Result]:
    load_dotenv(REPO_ROOT / ".env", override=False)
    results: list[Result] = []
    for check in CHECKS:
        started = time.perf_counter()
        if offline and check.network:
            status, detail = SKIP, "offline mode"
        else:
            try:
                status, detail = check.func()
            except requests.HTTPError as exc:
                status = FAIL
                detail = f"HTTP {exc.response.status_code}: {_api_error(exc.response)}"
            except requests.RequestException as exc:
                status = FAIL
                detail = f"network error: {exc.__class__.__name__}"
            except Exception as exc:  # keep the harness running for other checks
                status = FAIL
                detail = f"{exc.__class__.__name__}: {exc}"
        elapsed = int((time.perf_counter() - started) * 1000)
        results.append(Result(check.name, check.source, status, detail, elapsed))
    return results


def render(results: list[Result]) -> str:
    width = max(len(r.check) for r in results)
    lines = [
        "Release Day Radar - Phase 1 source verification",
        "=" * 64,
    ]
    for result in results:
        lines.append(
            f"[{result.status:<4}] {result.check:<{width}}  "
            f"({result.source}, {result.elapsed_ms} ms)"
        )
        lines.append(f"         {result.detail}")
    passed = sum(r.status == PASS for r in results)
    failed = sum(r.status == FAIL for r in results)
    skipped = sum(r.status == SKIP for r in results)
    lines.append("-" * 64)
    lines.append(f"{passed} passed, {skipped} skipped, {failed} failed")
    if skipped:
        lines.append("SKIP is expected on a fresh clone: add keys to .env or drop data files.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--offline",
        action="store_true",
        help="skip checks that need the network",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print a JSON report instead of a table",
    )
    args = parser.parse_args(argv)

    results = run(offline=args.offline)
    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print(render(results))
    return 2 if any(r.status == FAIL for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
