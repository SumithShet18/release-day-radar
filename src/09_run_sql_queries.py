"""Step 9 - Run the 6 analytical SQL queries against MySQL and export CSVs.

Reads sql/queries.sql, executes each query against the release_day_radar
MySQL database, prints formatted tables, and saves data/clean/sql_query_01.csv
through sql_query_06.csv.

Run:  python -X utf8 src/09_run_sql_queries.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

load_dotenv(c.REPO_ROOT / ".env")


def _connect(database: str):
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
        )
    except ImportError:
        import mysql.connector  # type: ignore

        return mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
        )


def _split_queries(sql_text: str) -> list[tuple[str, str]]:
    chunks = [chunk.strip() for chunk in sql_text.split(";") if chunk.strip()]
    results: list[tuple[str, str]] = []
    for idx, chunk in enumerate(chunks, start=1):
        lines = chunk.splitlines()
        title_lines = [ln.lstrip("- ").strip() for ln in lines if ln.strip().startswith("-- Q")]
        title = title_lines[0] if title_lines else f"Query {idx}"
        sql_body = "\n".join(ln for ln in lines if not ln.strip().startswith("--")).strip()
        if sql_body:
            results.append((title, sql_body))
    return results


def _run_sqlite_fallback(queries: list[tuple[str, str]]) -> None:
    """Mirror the 4 tables into in-memory SQLite when local MySQL is offline."""
    import sqlite3
    import importlib.util

    spec = importlib.util.spec_from_file_location("load_mysql", Path(__file__).parent / "08_load_mysql.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)

    con = sqlite3.connect(":memory:")
    cur = con.cursor()
    cur.executescript(
        """
        CREATE TABLE films (
            film_id TEXT PRIMARY KEY, canonical_title TEXT, language TEXT,
            release_date TEXT, release_day TEXT, est_budget_cr REAL,
            fri_sun_india_net_cr REAL, lifetime_ww_gross_cr REAL, verdict TEXT,
            trailer_channel TEXT, youtube_video_id TEXT, tmdb_id INTEGER,
            runtime_mins INTEGER, genres TEXT, tmdb_popularity REAL,
            trailer_upload_at TEXT, yt_total_views INTEGER,
            yt_total_likes INTEGER, yt_total_comments INTEGER
        );
        CREATE TABLE daily_collections (
            collection_id INTEGER PRIMARY KEY AUTOINCREMENT, film_id TEXT,
            day_number INTEGER, day_label TEXT, collection_date TEXT,
            india_net_cr REAL, is_non_friday_release INTEGER,
            window_note TEXT, source_name TEXT
        );
        CREATE TABLE youtube_comments (
            comment_id TEXT PRIMARY KEY, film_id TEXT, comment_text TEXT,
            published_at TEXT, like_count INTEGER,
            hours_since_trailer REAL, in_first_7d INTEGER
        );
        CREATE TABLE google_trends (
            trend_id INTEGER PRIMARY KEY AUTOINCREMENT, film_id TEXT,
            trend_date TEXT, search_interest_index INTEGER
        );
        """
    )
    cur.executemany(
        "INSERT INTO films VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        mod._build_films_rows(),
    )
    cur.executemany(
        "INSERT INTO daily_collections (film_id,day_number,day_label,collection_date,india_net_cr,is_non_friday_release,window_note,source_name) VALUES (?,?,?,?,?,?,?,?)",
        [(r[0], r[1], r[2], r[3], r[4], int(r[5]), r[6], r[7]) for r in mod._build_daily_rows()],
    )
    cur.executemany(
        "INSERT INTO youtube_comments VALUES (?,?,?,?,?,?,?)",
        [(r[0], r[1], r[2], r[3], r[4], r[5], int(r[6])) for r in mod._build_comment_rows()],
    )
    cur.executemany(
        "INSERT INTO google_trends (film_id,trend_date,search_interest_index) VALUES (?,?,?)",
        mod._build_trends_rows(),
    )
    con.commit()

    for idx, (title, sql_body) in enumerate(queries, start=1):
        sqlite_sql = sql_body.replace("FLOOR(hours_since_trailer / 24)", "CAST(hours_since_trailer / 24 AS INTEGER)")
        cur.execute(sqlite_sql)
        cols = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        df = pd.DataFrame(rows, columns=cols)
        c.write_csv(df, c.CLEAN / f"sql_query_0{idx}.csv")
        print(f"\n=== {title} ({len(df)} rows) ===")
        print(df.to_string(index=False))
    con.close()


def main() -> int:
    db_name = os.getenv("MYSQL_DATABASE", "release_day_radar").strip() or "release_day_radar"
    queries = _split_queries((c.REPO_ROOT / "sql" / "queries.sql").read_text(encoding="utf-8"))

    try:
        conn = _connect(db_name)
    except Exception as exc:
        print(f"MySQL connection unavailable ({exc}); running SQLite verification fallback...")
        _run_sqlite_fallback(queries)
        return 0

    try:
        cur = conn.cursor()
        for idx, (title, sql_body) in enumerate(queries, start=1):
            cur.execute(sql_body)
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            df = pd.DataFrame(rows, columns=cols)
            out_path = c.CLEAN / f"sql_query_0{idx}.csv"
            c.write_csv(df, out_path)
            print(f"\n=== {title} ({len(df)} rows) ===")
            print(df.to_string(index=False))
        cur.close()
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
