-- Release Day Radar — Relational MySQL Schema
-- Normalizes Structured (Wikipedia/Sacnilk/Trends), Semi-Structured (TMDb/YouTube videos),
-- and Unstructured (YouTube commentThreads) data around film_id.

CREATE DATABASE IF NOT EXISTS release_day_radar
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE release_day_radar;

DROP TABLE IF EXISTS google_trends;
DROP TABLE IF EXISTS youtube_comments;
DROP TABLE IF EXISTS daily_collections;
DROP TABLE IF EXISTS films;

CREATE TABLE films (
    film_id               VARCHAR(10)   NOT NULL,
    canonical_title       VARCHAR(120)  NOT NULL,
    language              VARCHAR(32)   NOT NULL,
    release_date          DATE          NOT NULL,
    release_day           VARCHAR(10)   NOT NULL,
    est_budget_cr         DECIMAL(8,2)  NOT NULL,
    fri_sun_india_net_cr  DECIMAL(8,2)  NOT NULL,
    lifetime_ww_gross_cr  DECIMAL(10,2) NOT NULL,
    verdict               VARCHAR(40)   NOT NULL,
    trailer_channel       VARCHAR(80)   NOT NULL,
    youtube_video_id      VARCHAR(32)   NOT NULL,
    tmdb_id               INT           NOT NULL,
    runtime_mins          INT           NULL,
    genres                VARCHAR(160)  NULL,
    tmdb_popularity       DECIMAL(10,3) NULL,
    trailer_upload_at     DATETIME      NULL,
    yt_total_views        BIGINT        NOT NULL DEFAULT 0,
    yt_total_likes        BIGINT        NOT NULL DEFAULT 0,
    yt_total_comments     BIGINT        NOT NULL DEFAULT 0,
    PRIMARY KEY (film_id),
    UNIQUE KEY uq_films_youtube_video (youtube_video_id),
    INDEX idx_films_language (language),
    INDEX idx_films_release_date (release_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE daily_collections (
    collection_id         INT           NOT NULL AUTO_INCREMENT,
    film_id               VARCHAR(10)   NOT NULL,
    day_number            TINYINT       NOT NULL,
    day_label             VARCHAR(16)   NOT NULL,
    collection_date       DATE          NOT NULL,
    india_net_cr          DECIMAL(8,2)  NOT NULL,
    is_non_friday_release BOOLEAN       NOT NULL DEFAULT FALSE,
    window_note           VARCHAR(120)  NULL,
    source_name           VARCHAR(64)   NOT NULL,
    PRIMARY KEY (collection_id),
    UNIQUE KEY uq_daily_film_day (film_id, day_number),
    INDEX idx_daily_film_id (film_id),
    CONSTRAINT fk_daily_film
        FOREIGN KEY (film_id) REFERENCES films (film_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE youtube_comments (
    comment_id            VARCHAR(64)   NOT NULL,
    film_id               VARCHAR(10)   NOT NULL,
    comment_text          TEXT          NOT NULL,
    published_at          DATETIME      NULL,
    like_count            INT           NOT NULL DEFAULT 0,
    hours_since_trailer   DECIMAL(10,2) NULL,
    in_first_7d           BOOLEAN       NOT NULL DEFAULT FALSE,
    PRIMARY KEY (comment_id),
    INDEX idx_comments_film_7d (film_id, in_first_7d),
    INDEX idx_comments_hours (hours_since_trailer),
    CONSTRAINT fk_comments_film
        FOREIGN KEY (film_id) REFERENCES films (film_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE google_trends (
    trend_id              INT           NOT NULL AUTO_INCREMENT,
    film_id               VARCHAR(10)   NOT NULL,
    trend_date            DATE          NOT NULL,
    search_interest_index TINYINT       NOT NULL,
    PRIMARY KEY (trend_id),
    UNIQUE KEY uq_trends_film_date (film_id, trend_date),
    INDEX idx_trends_film_id (film_id),
    CONSTRAINT fk_trends_film
        FOREIGN KEY (film_id) REFERENCES films (film_id)
        ON UPDATE CASCADE ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
