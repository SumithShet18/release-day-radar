"""Step 5 - deterministic TMDb ID resolution and YouTube trailer gate.

TMDb: search by title + release year, require an exact year match, fetch
/movie/{id}, save the raw responses and write tmdb_id back to films_master.csv.

YouTube: fetch stats only for IDs already present; for TBD rows print the
manual checklist (avoids burning 100 units per search call).

Run:  python src/05_resolve_ids.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

STEP = "05_tmdb"
TMDB_API = "https://api.themoviedb.org/3"
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"

load_dotenv(c.REPO_ROOT / ".env")


def tmdb_key() -> str:
    key = os.getenv("TMDB_API_KEY", "").strip()
    if not key:
        raise SystemExit("TMDB_API_KEY missing from .env")
    return key


def get_json(url: str, params: dict, retries: int = 3) -> tuple[dict, int]:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json(), response.status_code
            last = RuntimeError(f"HTTP {response.status_code}: {response.text[:120]}")
        except (requests.RequestException, ValueError) as exc:
            last = exc
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def search_queries(title: str) -> list[str]:
    queries = [title, title.split(":")[0].strip(), title.replace(":", "").strip()]
    if "revenge" in title.lower():
        queries.append(title.split(":")[0].strip() + " 2")
    seen: list[str] = []
    for query in queries:
        if query and query not in seen:
            seen.append(query)
    return seen


def resolve_tmdb(title: str, year: int, key: str) -> tuple[dict, dict, str, str]:
    best: tuple[float, dict, str] | None = None
    for query in search_queries(title):
        payload, _ = get_json(
            f"{TMDB_API}/search/movie",
            {
                "api_key": key,
                "query": query,
                "year": year,
                "language": "en-IN",
                "include_adult": "false",
            },
        )
        for movie in payload.get("results", []):
            release_date = str(movie.get("release_date", ""))
            if not release_date.startswith(str(year)):
                continue
            wanted = c.title_key(title)
            found = c.title_key(movie.get("title"))
            score = float(movie.get("popularity", 0))
            if found == wanted:
                score += 1000
            elif wanted and (wanted in found or found in wanted):
                score += 500
            if best is None or score > best[0]:
                best = (score, movie, query)
        if best:
            break
        time.sleep(0.25)

    if best is None:
        raise LookupError(f"no TMDb match for {title} ({year})")

    _, movie, query = best
    details, _ = get_json(
        f"{TMDB_API}/movie/{movie['id']}",
        {"api_key": key, "language": "en-IN"},
    )
    return movie, details, query, f"{TMDB_API}/movie/{movie['id']}"


def tmdb_access_records() -> list[dict]:
    """Rebuild provenance from every saved bundle so partial retries stay complete."""
    records: list[dict] = []
    for path in sorted((c.RAW / "tmdb").glob("F*_tmdb.json")):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        stamp = bundle.get("fetched_at_utc") or c.utc_stamp()
        query = str(bundle.get("resolved_query", "")).replace(" ", "+")
        records.append(
            {
                "source_name": "TMDb API",
                "url": f"{TMDB_API}/search/movie?query={query}",
                "http_status": 200,
                "format": "JSON",
                "access_timestamp_utc": stamp,
                "notes": f"search for {bundle.get('film_id')}",
            }
        )
        records.append(
            {
                "source_name": "TMDb API",
                "url": bundle.get("details_url", ""),
                "http_status": 200,
                "format": "JSON",
                "access_timestamp_utc": stamp,
                "notes": f"details for {bundle.get('film_id')}",
            }
        )
    return records


def main() -> int:
    c.ensure_dirs()
    key = tmdb_key()
    master = pd.read_csv(c.MASTER, dtype=str).fillna("")
    access: list[dict] = []
    resolved: list[dict] = []

    print(f"Resolving {len(master)} films on TMDb")
    for index, film in master.iterrows():
        film_id = film["film_id"]
        year = int(str(film["release_date"])[:4])
        try:
            movie, details, query, details_url = resolve_tmdb(
                film["canonical_title"], year, key
            )
        except Exception as exc:
            existing = str(film.get("tmdb_id", "")).strip()
            if existing and existing != "TBD":
                print(
                    f"  {film_id} {film['canonical_title'][:28]:28} "
                    f"fetch failed ({exc.__class__.__name__}); keeping cached id {existing}"
                )
                resolved.append(
                    {
                        "film_id": film_id,
                        "canonical_title": film["canonical_title"],
                        "tmdb_id": existing,
                        "status": "CACHED",
                    }
                )
            else:
                print(f"  {film_id} {film['canonical_title'][:28]:28} NO MATCH ({exc})")
                resolved.append(
                    {
                        "film_id": film_id,
                        "canonical_title": film["canonical_title"],
                        "tmdb_id": "TBD",
                        "status": "UNRESOLVED",
                    }
                )
            continue

        bundle = {
            "film_id": film_id,
            "resolved_query": query,
            "search_url": f"{TMDB_API}/search/movie",
            "details_url": details_url,
            "fetched_at_utc": c.utc_stamp(),
            "search_response": movie,
            "details_response": details,
        }
        path = c.RAW / "tmdb" / f"{film_id}_tmdb.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        master.at[index, "tmdb_id"] = str(movie["id"])

        access.append(
            {
                "source_name": "TMDb API",
                "url": f"{TMDB_API}/search/movie?query={query.replace(' ', '+')}&year={year}",
                "http_status": 200,
                "format": "JSON",
                "notes": f"resolved {film_id} to {movie['id']}",
            }
        )
        access.append(
            {
                "source_name": "TMDb API",
                "url": details_url,
                "http_status": 200,
                "format": "JSON",
                "notes": f"details for {film_id}",
            }
        )
        resolved.append(
            {
                "film_id": film_id,
                "canonical_title": film["canonical_title"],
                "tmdb_id": str(movie["id"]),
                "status": "RESOLVED",
                "tmdb_title": movie.get("title"),
                "tmdb_release_date": movie.get("release_date"),
            }
        )
        print(
            f"  {film_id} {film['canonical_title'][:28]:28} -> {movie['id']} "
            f"{movie.get('title')} ({movie.get('release_date')}) via '{query}'"
        )
        time.sleep(0.25)

    # Write the master back in place, preserving every original column.
    master.to_csv(c.MASTER, index=False, encoding="utf-8")

    # YouTube gate.
    video_rows: list[dict] = []
    checklist: list[dict] = []
    youtube_key = os.getenv("YOUTUBE_API_KEY", "").strip()
    for _, film in master.iterrows():
        video_id = str(film["youtube_video_id"]).strip()
        if video_id and video_id != "TBD":
            if not youtube_key:
                checklist.append(
                    {
                        "film_id": film["film_id"],
                        "canonical_title": film["canonical_title"],
                        "trailer_channel": film["trailer_channel"],
                        "expected_search_query": f"{film['canonical_title']} official trailer",
                        "note": "video id set but YOUTUBE_API_KEY missing",
                    }
                )
                continue
            payload, _ = get_json(
                f"{YOUTUBE_API}/videos",
                {
                    "part": "snippet,statistics",
                    "id": video_id,
                    "key": youtube_key,
                },
            )
            path = c.RAW / "youtube" / f"{film['film_id']}_video.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            access.append(
                {
                    "source_name": "YouTube Data API v3",
                    "url": f"{YOUTUBE_API}/videos?part=snippet,statistics&id={video_id}",
                    "http_status": 200,
                    "format": "JSON",
                    "notes": f"trailer stats for {film['film_id']}",
                }
            )
            video_rows.append(
                {"film_id": film["film_id"], "youtube_video_id": video_id, "status": "FETCHED"}
            )
        else:
            checklist.append(
                {
                    "film_id": film["film_id"],
                    "canonical_title": film["canonical_title"],
                    "trailer_channel": film["trailer_channel"],
                    "expected_search_query": (
                        f"{film['canonical_title']} {film['trailer_channel']} official trailer"
                    ),
                    "note": "paste 11-character video id into films_master.csv",
                }
            )

    youtube_access = [r for r in access if r["source_name"] == "YouTube Data API v3"]
    access = tmdb_access_records() + youtube_access
    log = c.write_access_log(STEP, access)
    print(f"\nWrote {log.relative_to(c.REPO_ROOT)} ({len(access)} access records)")
    print("Updated data/raw/films_master.csv tmdb_id column")
    final = pd.read_csv(c.MASTER, dtype=str).fillna("")
    resolved_count = int((final["tmdb_id"] != "TBD").sum())
    print(f"TMDb resolved: {resolved_count}/12")
    for _, row in final.iterrows():
        if row["tmdb_id"] == "TBD":
            print(f"  UNRESOLVED {row['film_id']} {row['canonical_title']}")
    print(f"YouTube video stats fetched: {len(video_rows)}")

    print("\nYouTube trailer ID checklist")
    print("=" * 104)
    header = f"{'film_id':8} {'title':30} {'channel':24} expected search query"
    print(header)
    print("-" * 104)
    for row in checklist:
        print(
            f"{row['film_id']:8} {row['canonical_title'][:29]:30} "
            f"{row['trailer_channel'][:23]:24} {row['expected_search_query']}"
        )
    print("-" * 104)
    print(f"{len(checklist)}/12 trailer IDs still TBD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
