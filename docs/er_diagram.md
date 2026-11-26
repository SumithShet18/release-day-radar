# Release Day Radar — Relational ER Diagram

This schema normalizes all three data shapes (Structured HTML/CSV, Semi-Structured JSON APIs, and Unstructured free-text comments) around the canonical **`film_id`** key (`F01`–`F12`).

## Entity-Relationship Diagram (Mermaid)

```mermaid
erDiagram
    FILMS {
        varchar(10) film_id PK
        varchar(120) canonical_title
        varchar(32) language
        date release_date
        varchar(10) release_day
        decimal(8_2) est_budget_cr
        decimal(8_2) fri_sun_india_net_cr
        decimal(10_2) lifetime_ww_gross_cr
        varchar(40) verdict
        varchar(80) trailer_channel
        varchar(32) youtube_video_id
        int tmdb_id
        int runtime_mins
        varchar(160) genres
        decimal(10_3) tmdb_popularity
        datetime trailer_upload_at
        bigint yt_total_views
        bigint yt_total_likes
        bigint yt_total_comments
    }

    DAILY_COLLECTIONS {
        int collection_id PK
        varchar(10) film_id FK
        tinyint day_number
        varchar(16) day_label
        date collection_date
        decimal(8_2) india_net_cr
        boolean is_non_friday_release
        varchar(120) window_note
        varchar(64) source_name
    }

    YOUTUBE_COMMENTS {
        varchar(64) comment_id PK
        varchar(10) film_id FK
        text comment_text
        datetime published_at
        int like_count
        decimal(10_2) hours_since_trailer
        boolean in_first_7d
    }

    GOOGLE_TRENDS {
        int trend_id PK
        varchar(10) film_id FK
        date trend_date
        tinyint search_interest_index
    }

    FILMS ||--|{ DAILY_COLLECTIONS : "has 3 opening days (1:3)"
    FILMS ||--o{ YOUTUBE_COMMENTS : "has trailer comments (1:N)"
    FILMS ||--o{ GOOGLE_TRENDS : "has daily search interest (1:N)"
```

## ASCII Relationship Overview

```text
+-----------------------------------+
|              films                |
|-----------------------------------|
| PK  film_id (VARCHAR(10))         |
|     canonical_title, language,    |
|     release_date, est_budget_cr,  |
|     fri_sun_india_net_cr,         |
|     tmdb_id, runtime_mins,        |
|     genres, yt_total_views, ...   |
+-----------------------------------+
   | 1                | 1                | 1
   |                  |                  |
   | 3                | N                | N
   v                  v                  v
+--------------------+ +----------------------+ +------------------------+
| daily_collections  | |   youtube_comments   | |     google_trends      |
|--------------------| |----------------------| |------------------------|
| PK collection_id   | | PK comment_id        | | PK trend_id            |
| FK film_id         | | FK film_id           | | FK film_id             |
|    day_number      | |    comment_text      | |    trend_date          |
|    collection_date | |    published_at      | |    search_interest_idx |
|    india_net_cr    | |    like_count        | |                        |
|    window_note     | |    hours_since_tr.   | |                        |
|                    | |    in_first_7d       | |                        |
+--------------------+ +----------------------+ +------------------------+
```

## Key & Cardinality Notes
- **`films` → `daily_collections` (`1:3`):** Every film (`F01`–`F12`) has 3 standardized opening-window rows (`day_number` 1–3; total 36 rows), with `(film_id, day_number)` enforced as a unique key.
- **`films` → `youtube_comments` (`1:N`):** Each unique `comment_id` belongs to one `film_id`. All author PII fields (`authorDisplayName`, `authorProfileImageUrl`, `authorChannelUrl`, `authorChannelId`) are stripped prior to persistence.
- **`films` → `google_trends` (`1:N`):** One row per `(film_id, trend_date)` with `search_interest_index` normalized on a `0–100` scale.
