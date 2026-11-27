"""Step 8 - Load relational tables into MySQL from cleaned & semi-structured sources.

Reads MySQL credentials from .env (MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
MYSQL_PASSWORD, MYSQL_DATABASE), executes sql/schema.sql, bulk-inserts
films, daily_collections, youtube_comments, and google_trends, and prints
SELECT COUNT(*) verification for every table.

Run:  python -X utf8 src/08_load_mysql.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

load_dotenv(c.REPO_ROOT / ".env")

BATCH_SIZE = 2000


def _connect(database: str | None = None):
    host = os.getenv("MYSQL_HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("MYSQL_PORT", "3306").strip() or "3306")
    user = os.getenv("MYSQL_USER", "root").strip() or "root"
    password = os.getenv("MYSQL_PASSWORD", "")

    try:
        import pymysql  # type: ignore

        return pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
            autocommit=False,
        )
    except ImportError:
        import mysql.connector  # type: ignore

        kwargs: dict[str, object] = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "charset": "utf8mb4",
            "autocommit": False,
        }
        if database:
            kwargs["database"] = database
        return mysql.connector.connect(**kwargs)


def _execute_schema(conn, schema_path: Path) -> None:
    sql_text = schema_path.read_text(encoding="utf-8")
    statements = [
        stmt.strip()
        for stmt in sql_text.split(";")
        if stmt.strip() and not all(
            line.strip().startswith("--") or not line.strip()
            for line in stmt.splitlines()
        )
    ]
    cur = conn.cursor()
    for stmt in statements:
        cur.execute(stmt)
    conn.commit()
    cur.close()


def _build_films_rows() -> list[tuple]:
    master = pd.read_csv(c.MASTER, dtype=str).fillna("")
    verified = pd.read_csv(c.CLEAN / "opening_weekend_verified.csv")
    yt_videos = pd.read_csv(c.CLEAN / "youtube_videos.csv").set_index("film_id")
    verified_map = verified.set_index("film_id")["opening_3d_india_net_cr"].to_dict()

    rows: list[tuple] = []
    for _, r in master.iterrows():
        fid = r["film_id"]
        tmdb_path = c.RAW / "tmdb" / f"{fid}_tmdb.json"
        runtime_mins = None
        genres_str = None
        popularity = None
        if tmdb_path.exists():
            bundle = json.loads(tmdb_path.read_text(encoding="utf-8"))
            details = bundle.get("details_response", {})
            search_resp = bundle.get("search_response", {})
            norm = pd.json_normalize(details).iloc[0]
            rt = norm.get("runtime")
            runtime_mins = int(rt) if pd.notna(rt) and int(rt) > 0 else None
            genres_list = details.get("genres", [])
            genres_str = ", ".join(g.get("name", "") for g in genres_list if g.get("name")) or None
            pop = norm.get("popularity", search_resp.get("popularity"))
            popularity = round(float(pop), 3) if pd.notna(pop) else None

        v = yt_videos.loc[fid]
        upload_dt = pd.to_datetime(v["trailer_published_at"], utc=True, errors="coerce")
        upload_str = upload_dt.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(upload_dt) else None

        rows.append(
            (
                fid,
                r["canonical_title"],
                r["language"],
                r["release_date"],
                r["release_day"],
                float(r["est_budget_cr"]),
                float(verified_map.get(fid, r["fri_sun_india_net_cr"])),
                float(r["lifetime_ww_gross_cr"]),
                r["verdict"],
                r["trailer_channel"],
                r["youtube_video_id"],
                int(r["tmdb_id"]),
                runtime_mins,
                genres_str,
                popularity,
                upload_str,
                int(v["view_count"]),
                int(v["like_count"]),
                int(v["comment_count"]),
            )
        )
    return rows


def _build_daily_rows() -> list[tuple]:
    verified = pd.read_csv(c.CLEAN / "opening_weekend_verified.csv").set_index("film_id")
    rows: list[tuple] = []
    for path in sorted((c.RAW / "boxoffice").glob("F*_weekend.csv")):
        df = pd.read_csv(path)
        for day_num, (_, r) in enumerate(df.iterrows(), start=1):
            fid = str(r["film_id"])
            v = verified.loc[fid]
            rows.append(
                (
                    fid,
                    day_num,
                    str(r["day_label"]),
                    str(r["date"]),
                    float(r["india_net_cr"]),
                    bool(v["is_non_friday_release"]),
                    str(v["window_note"]),
                    str(v["source_name"]),
                )
            )
    return rows


def _build_comment_rows() -> list[tuple]:
    df = pd.read_csv(c.CLEAN / "youtube_comments.csv")
    pub = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df["pub_mysql"] = pub.dt.strftime("%Y-%m-%d %H:%M:%S")
    rows: list[tuple] = []
    for r in df.itertuples(index=False):
        rows.append(
            (
                str(r.comment_id),
                str(r.film_id),
                str(r.text_original) if pd.notna(r.text_original) else "",
                None if pd.isna(r.pub_mysql) else str(r.pub_mysql),
                int(r.like_count),
                None if pd.isna(r.hours_since_trailer) else float(r.hours_since_trailer),
                bool(r.in_first_7d),
            )
        )
    return rows


def _build_trends_rows() -> list[tuple]:
    df = pd.read_csv(c.CLEAN / "google_trends_combined.csv")
    return [
        (str(r.film_id), str(r.date), int(round(float(r.interest))))
        for r in df.itertuples(index=False)
    ]


def main() -> int:
    db_name = os.getenv("MYSQL_DATABASE", "release_day_radar").strip() or "release_day_radar"
    try:
        conn = _connect(database=None)
    except Exception as exc:
        print(f"MySQL connection failed: {exc}")
        print(
            "Fix needed: Ensure the MySQL server is running on "
            f"{os.getenv('MYSQL_HOST', '127.0.0.1')}:{os.getenv('MYSQL_PORT', '3306')} "
            "and verify MYSQL_USER / MYSQL_PASSWORD in .env."
        )
        return 1

    try:
        _execute_schema(conn, c.REPO_ROOT / "sql" / "schema.sql")
        conn.select_db(db_name) if hasattr(conn, "select_db") else None
        cur = conn.cursor()
        cur.execute(f"USE `{db_name}`")

        films_rows = _build_films_rows()
        cur.executemany(
            """
            INSERT INTO films (
                film_id, canonical_title, language, release_date, release_day,
                est_budget_cr, fri_sun_india_net_cr, lifetime_ww_gross_cr, verdict,
                trailer_channel, youtube_video_id, tmdb_id, runtime_mins, genres,
                tmdb_popularity, trailer_upload_at, yt_total_views, yt_total_likes,
                yt_total_comments
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            films_rows,
        )

        daily_rows = _build_daily_rows()
        cur.executemany(
            """
            INSERT INTO daily_collections (
                film_id, day_number, day_label, collection_date, india_net_cr,
                is_non_friday_release, window_note, source_name
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            daily_rows,
        )

        comment_rows = _build_comment_rows()
        for start in range(0, len(comment_rows), BATCH_SIZE):
            cur.executemany(
                """
                INSERT INTO youtube_comments (
                    comment_id, film_id, comment_text, published_at,
                    like_count, hours_since_trailer, in_first_7d
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                comment_rows[start : start + BATCH_SIZE],
            )

        trends_rows = _build_trends_rows()
        for start in range(0, len(trends_rows), BATCH_SIZE):
            cur.executemany(
                """
                INSERT INTO google_trends (
                    film_id, trend_date, search_interest_index
                ) VALUES (%s,%s,%s)
                """,
                trends_rows[start : start + BATCH_SIZE],
            )

        conn.commit()

        print("MySQL table row counts:")
        for tbl in ("films", "daily_collections", "youtube_comments", "google_trends"):
            cur.execute(f"SELECT COUNT(*) FROM `{tbl}`")
            cnt = cur.fetchone()[0]
            print(f"  {tbl:20} {cnt:,}")
        cur.close()
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
