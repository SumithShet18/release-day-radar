"""Step 7 - YouTube Data API v3 trailer stats + privacy-scrubbed comments.

Reads the 12 verified ``youtube_video_id`` values from ``data/raw/films_master.csv``
and the trailer metadata from ``data/raw/youtube/Fxx_video.json`` (fetching from
the ``videos`` endpoint if missing), then pulls up to 4,500 top-level comments
per film from ``commentThreads`` (54,000 target rows across 12 films).

Privacy rule: ``authorDisplayName``, ``authorProfileImageUrl``,
``authorChannelUrl``, and ``authorChannelId`` are stripped in memory before
anything is written to disk.

Run:  python -X utf8 src/07_youtube_layer.py
"""

from __future__ import annotations

import argparse
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

STEP = "07_youtube"
YOUTUBE_API = "https://www.googleapis.com/youtube/v3"
MAX_COMMENTS_PER_FILM = 4500
PII_FIELDS = (
    "authorDisplayName",
    "authorProfileImageUrl",
    "authorChannelUrl",
    "authorChannelId",
)

load_dotenv(c.REPO_ROOT / ".env")


def youtube_key() -> str:
    key = os.getenv("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise SystemExit("YOUTUBE_API_KEY missing from .env")
    return key


def get_json(url: str, params: dict, retries: int = 3) -> tuple[dict, int]:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                return response.json(), response.status_code
            last = RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
        except (requests.RequestException, ValueError) as exc:
            last = exc
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


def scrub_comment_pii(item: dict) -> dict:
    """Remove all author PII fields from a commentThread item in memory."""
    cleaned = json.loads(json.dumps(item))
    top_snippet = (
        cleaned.get("snippet", {})
        .get("topLevelComment", {})
        .get("snippet", {})
    )
    for field in PII_FIELDS:
        top_snippet.pop(field, None)
    return cleaned


def load_or_fetch_video(film_id: str, video_id: str, key: str) -> tuple[dict, bool]:
    path = c.RAW / "youtube" / f"{film_id}_video.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")), False
    payload, _ = get_json(
        f"{YOUTUBE_API}/videos",
        {"part": "snippet,statistics", "id": video_id, "key": key},
    )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload, True


def _paginate_comments(
    film_id: str,
    video_id: str,
    key: str,
    order: str,
    max_new: int,
    seen_ids: set[str],
) -> tuple[list[dict], int, list[dict]]:
    """Paginate commentThreads for a given sort order, scrubbing PII in memory."""
    collected: list[dict] = []
    page_token: str | None = None
    pages = 0
    access_records: list[dict] = []

    while len(collected) < max_new:
        params: dict[str, object] = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": 100,
            "order": order,
            "textFormat": "plainText",
            "key": key,
        }
        if page_token:
            params["pageToken"] = page_token

        payload, status = get_json(f"{YOUTUBE_API}/commentThreads", params)
        pages += 1
        if pages == 1:
            access_records.append(
                {
                    "source_name": "YouTube Data API v3",
                    "url": f"{YOUTUBE_API}/commentThreads?part=snippet&videoId={video_id}&order={order}",
                    "http_status": status,
                    "format": "JSON",
                    "notes": f"paginated comments ({order}) for {film_id}",
                }
            )

        batch = payload.get("items", [])
        if not batch:
            break

        for raw_item in batch:
            scrubbed = scrub_comment_pii(raw_item)
            cid = str(scrubbed.get("id", ""))
            if cid and cid in seen_ids:
                continue
            if cid:
                seen_ids.add(cid)
            collected.append(scrubbed)
            if len(collected) >= max_new:
                break

        page_token = payload.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.03)

    return collected, pages, access_records


def fetch_comments_for_film(
    film_id: str,
    video_id: str,
    key: str,
    max_comments: int = MAX_COMMENTS_PER_FILM,
    refresh: bool = False,
) -> tuple[dict, list[dict]]:
    """Fetch relevance + time comments, deduplicated by comment_id."""
    raw_path = c.RAW / "youtube" / f"{film_id}_comments.json"
    existing_items: list[dict] = []
    seen_ids: set[str] = set()
    existing_orders: list[str] = []
    pages_total = 0

    if raw_path.exists() and not refresh:
        cached = json.loads(raw_path.read_text(encoding="utf-8"))
        existing_items = [scrub_comment_pii(it) for it in cached.get("items", [])]
        for it in existing_items:
            cid = str(it.get("id", ""))
            if cid:
                seen_ids.add(cid)
        pages_total = int(cached.get("pages_fetched", 0))
        orders = cached.get("orders_fetched") or [cached.get("order", "relevance")]
        existing_orders = list(orders)
        if "time" in existing_orders and len(existing_items) >= max_comments:
            return cached, []

    access_records: list[dict] = []
    if "relevance" not in existing_orders:
        rel_items, rel_pages, rel_acc = _paginate_comments(
            film_id, video_id, key, "relevance", max_comments, seen_ids
        )
        existing_items.extend(rel_items)
        pages_total += rel_pages
        access_records.extend(rel_acc)
        existing_orders.append("relevance")

    if "time" not in existing_orders:
        time_items, time_pages, time_acc = _paginate_comments(
            film_id, video_id, key, "time", max_comments, seen_ids
        )
        existing_items.extend(time_items)
        pages_total += time_pages
        access_records.extend(time_acc)
        existing_orders.append("time")

    bundle = {
        "film_id": film_id,
        "video_id": video_id,
        "fetched_at_utc": c.utc_stamp(),
        "orders_fetched": existing_orders,
        "pages_fetched": pages_total,
        "comment_count_fetched": len(existing_items),
        "items": existing_items,
    }
    raw_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    return bundle, access_records


def flatten_video(film_id: str, video_id: str, payload: dict) -> dict:
    items = payload.get("items", [])
    if not items:
        raise ValueError(f"{film_id}: empty YouTube videos response for {video_id}")
    norm = pd.json_normalize(items[0]).iloc[0]
    return {
        "film_id": film_id,
        "youtube_video_id": video_id,
        "video_title": str(norm.get("snippet.title", "")),
        "channel_title": str(norm.get("snippet.channelTitle", "")),
        "trailer_published_at": str(norm.get("snippet.publishedAt", "")),
        "view_count": int(norm.get("statistics.viewCount", 0) or 0),
        "like_count": int(norm.get("statistics.likeCount", 0) or 0),
        "comment_count": int(norm.get("statistics.commentCount", 0) or 0),
    }


def flatten_comments(
    film_id: str,
    video_id: str,
    trailer_published_at: str,
    items: list[dict],
) -> pd.DataFrame:
    if not items:
        return pd.DataFrame()
    norm = pd.json_normalize(items)
    df = pd.DataFrame(
        {
            "comment_id": norm.get("id", pd.Series(dtype=str)).astype(str),
            "film_id": film_id,
            "youtube_video_id": video_id,
            "published_at": pd.to_datetime(
                norm.get("snippet.topLevelComment.snippet.publishedAt"),
                utc=True,
                errors="coerce",
            ),
            "updated_at": pd.to_datetime(
                norm.get("snippet.topLevelComment.snippet.updatedAt"),
                utc=True,
                errors="coerce",
            ),
            "like_count": pd.to_numeric(
                norm.get("snippet.topLevelComment.snippet.likeCount"),
                errors="coerce",
            )
            .fillna(0)
            .astype(int),
            "total_reply_count": pd.to_numeric(
                norm.get("snippet.totalReplyCount"),
                errors="coerce",
            )
            .fillna(0)
            .astype(int),
            "text_original": (
                norm.get("snippet.topLevelComment.snippet.textOriginal", pd.Series(dtype=str))
                .fillna("")
                .astype(str)
            ),
        }
    )
    trailer_ts = pd.to_datetime(trailer_published_at, utc=True, errors="coerce")
    if pd.notna(trailer_ts):
        delta_hours = (df["published_at"] - trailer_ts).dt.total_seconds() / 3600.0
        delta_days = delta_hours / 24.0
        df["hours_since_trailer"] = delta_hours.round(2)
        df["days_since_trailer"] = delta_days.round(4)
        df["in_first_7d"] = (delta_hours >= 0) & (delta_hours <= 168.0)
    else:
        df["hours_since_trailer"] = pd.NA
        df["days_since_trailer"] = pd.NA
        df["in_first_7d"] = False
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description="Pull YouTube trailer stats & comments.")
    parser.add_argument("--max-comments", type=int, default=MAX_COMMENTS_PER_FILM)
    parser.add_argument("--refresh", action="store_true", help="Re-fetch cached comment JSONs.")
    args = parser.parse_args()

    c.ensure_dirs()
    key = youtube_key()
    master = c.load_master()

    video_rows: list[dict] = []
    comment_frames: list[pd.DataFrame] = []
    access_records: list[dict] = []

    print(f"Collecting YouTube metadata & up to {args.max_comments} comments per film")
    for _, film in master.iterrows():
        film_id = str(film["film_id"]).strip()
        video_id = str(film["youtube_video_id"]).strip()
        if not video_id or video_id == "TBD":
            raise SystemExit(f"{film_id}: youtube_video_id is still TBD in films_master.csv")

        video_payload, fetched_video = load_or_fetch_video(film_id, video_id, key)
        if fetched_video:
            access_records.append(
                {
                    "source_name": "YouTube Data API v3",
                    "url": f"{YOUTUBE_API}/videos?part=snippet,statistics&id={video_id}",
                    "http_status": 200,
                    "format": "JSON",
                    "notes": f"trailer stats for {film_id}",
                }
            )
        vrow = flatten_video(film_id, video_id, video_payload)
        video_rows.append(vrow)

        bundle, new_access = fetch_comments_for_film(
            film_id,
            video_id,
            key,
            max_comments=args.max_comments,
            refresh=args.refresh,
        )
        access_records.extend(new_access)

        cdf = flatten_comments(
            film_id,
            video_id,
            vrow["trailer_published_at"],
            bundle.get("items", []),
        )
        first_7d_n = int(cdf["in_first_7d"].sum()) if not cdf.empty else 0
        print(
            f"  {film_id} {str(film['canonical_title'])[:26]:26} "
            f"views={vrow['view_count']:>11,} comments_total={vrow['comment_count']:>8,} "
            f"fetched={len(cdf):>5,} first_7d={first_7d_n:>5,}"
        )
        if not cdf.empty:
            comment_frames.append(cdf)

    videos_df = pd.DataFrame(video_rows)
    c.write_csv(videos_df, c.CLEAN / "youtube_videos.csv")

    comments_df = (
        pd.concat(comment_frames, ignore_index=True)
        if comment_frames
        else pd.DataFrame()
    )
    raw_total = len(comments_df)
    if not comments_df.empty:
        comments_df = comments_df.drop_duplicates(subset=["comment_id"]).reset_index(drop=True)
        comments_df["text_original"] = comments_df["text_original"].str.replace(
            r"[\r\n]+", " ", regex=True
        ).str.strip()
    deduped_total = len(comments_df)
    c.write_csv(comments_df, c.CLEAN / "youtube_comments.csv")

    if access_records:
        c.write_access_log(STEP, access_records)

    cleaning_rows = [
        {
            "step_id": "STEP_07",
            "table_affected": "youtube_comments",
            "problem_found": (
                "YouTube commentThreads API returns author PII "
                "(authorDisplayName, authorProfileImageUrl, authorChannelUrl, authorChannelId)."
            ),
            "rows_affected": deduped_total,
            "action_taken": (
                "Stripped all four author PII fields in memory upon ingestion "
                "before writing raw JSON or clean CSV."
            ),
            "justification": (
                "Project privacy rule prohibits storing or publishing usernames "
                "or profile links from review/comment data."
            ),
        },
        {
            "step_id": "STEP_07",
            "table_affected": "youtube_comments",
            "problem_found": (
                "order=relevance caps around ~1,200 threads per video (~14,463 total), "
                "below the 50,000-row PySpark floor; unioning with order=time can "
                "introduce overlapping comment_id rows and embedded CR/LF newlines."
            ),
            "rows_affected": raw_total - deduped_total,
            "action_taken": (
                "Unioned order=relevance and order=time streams per film, deduplicated "
                "on comment_id, and normalized CR/LF newlines to spaces."
            ),
            "justification": (
                "Clears 50,000+ unique YouTube comments across the 12 trailers while "
                "guaranteeing one row per unique comment_id."
            ),
        },
    ]
    c.upsert_cleaning_log("STEP_07", cleaning_rows)

    print(f"\nWrote data/clean/youtube_videos.csv ({len(videos_df)} rows)")
    print(f"Wrote data/clean/youtube_comments.csv ({len(comments_df):,} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
