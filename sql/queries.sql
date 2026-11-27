-- Release Day Radar — 6 Analytical SQL Queries
-- Database: release_day_radar

-- Q1: Trailer-Week Buzz vs. Opening Weekend (JOIN + GROUP BY)
-- Ranks all 12 films by 3-day India net collection alongside first-7-day YouTube comments and total trailer views.
SELECT
    f.film_id,
    f.canonical_title,
    f.language,
    f.fri_sun_india_net_cr,
    f.yt_total_views,
    COUNT(yc.comment_id) AS fetched_comments,
    SUM(CASE WHEN yc.in_first_7d = 1 THEN 1 ELSE 0 END) AS first_7d_comments
FROM films f
LEFT JOIN youtube_comments yc ON f.film_id = yc.film_id
GROUP BY
    f.film_id, f.canonical_title, f.language,
    f.fri_sun_india_net_cr, f.yt_total_views
ORDER BY f.fri_sun_india_net_cr DESC;

-- Q2: Distribution Decision Rule Backtest (Top-6 Screen Allocation)
-- Compares Top-6 films by first-7-day trailer comments against Top-6 films by 3-day India net.
WITH ranked AS (
    SELECT
        f.film_id,
        f.canonical_title,
        f.fri_sun_india_net_cr,
        SUM(CASE WHEN yc.in_first_7d = 1 THEN 1 ELSE 0 END) AS first_7d_comments,
        ROW_NUMBER() OVER (
            ORDER BY SUM(CASE WHEN yc.in_first_7d = 1 THEN 1 ELSE 0 END) DESC, f.yt_total_comments DESC
        ) AS comment_rank,
        ROW_NUMBER() OVER (ORDER BY f.fri_sun_india_net_cr DESC) AS boxoffice_rank
    FROM films f
    LEFT JOIN youtube_comments yc ON f.film_id = yc.film_id
    GROUP BY f.film_id, f.canonical_title, f.fri_sun_india_net_cr, f.yt_total_comments
)
SELECT
    film_id,
    canonical_title,
    first_7d_comments,
    comment_rank,
    fri_sun_india_net_cr,
    boxoffice_rank,
    CASE
        WHEN comment_rank <= 6 AND boxoffice_rank <= 6 THEN 'TRUE_POSITIVE (Add Screens Accurate)'
        WHEN comment_rank <= 6 AND boxoffice_rank > 6  THEN 'FALSE_POSITIVE (Over-Indexed Hype)'
        WHEN comment_rank > 6  AND boxoffice_rank <= 6 THEN 'FALSE_NEGATIVE (Missed Winner)'
        ELSE 'TRUE_NEGATIVE (Hold/Cut Accurate)'
    END AS screen_rule_outcome
FROM ranked
ORDER BY comment_rank ASC;

-- Q3: Regional vs. Hindi Conversion (GROUP BY language)
-- Compares average budget, 3-day net, trailer-week comments, and opening collection-to-budget ratio by language.
SELECT
    f.language,
    COUNT(DISTINCT f.film_id) AS film_count,
    ROUND(AVG(f.est_budget_cr), 2) AS avg_budget_cr,
    ROUND(AVG(f.fri_sun_india_net_cr), 2) AS avg_3d_net_cr,
    ROUND(AVG(c.first_7d_comments), 1) AS avg_first_7d_comments,
    ROUND(SUM(f.fri_sun_india_net_cr) / NULLIF(SUM(f.est_budget_cr), 0), 3) AS opening_to_budget_ratio
FROM films f
LEFT JOIN (
    SELECT film_id, SUM(CASE WHEN in_first_7d = 1 THEN 1 ELSE 0 END) AS first_7d_comments
    FROM youtube_comments
    GROUP BY film_id
) c ON f.film_id = c.film_id
GROUP BY f.language
ORDER BY avg_3d_net_cr DESC;

-- Q4: Weekend Momentum (JOIN films + daily_collections)
-- Computes Day 3 to Day 1 collection ratio to separate word-of-mouth growers from front-loaded drops.
SELECT
    f.film_id,
    f.canonical_title,
    f.release_day,
    MAX(CASE WHEN dc.day_number = 1 THEN dc.india_net_cr END) AS day1_net_cr,
    MAX(CASE WHEN dc.day_number = 2 THEN dc.india_net_cr END) AS day2_net_cr,
    MAX(CASE WHEN dc.day_number = 3 THEN dc.india_net_cr END) AS day3_net_cr,
    ROUND(
        MAX(CASE WHEN dc.day_number = 3 THEN dc.india_net_cr END) /
        NULLIF(MAX(CASE WHEN dc.day_number = 1 THEN dc.india_net_cr END), 0),
        2
    ) AS day3_to_day1_ratio,
    CASE
        WHEN MAX(CASE WHEN dc.day_number = 3 THEN dc.india_net_cr END) /
             NULLIF(MAX(CASE WHEN dc.day_number = 1 THEN dc.india_net_cr END), 0) >= 1.25 THEN 'Strong WOM Grower'
        WHEN MAX(CASE WHEN dc.day_number = 3 THEN dc.india_net_cr END) /
             NULLIF(MAX(CASE WHEN dc.day_number = 1 THEN dc.india_net_cr END), 0) >= 0.90 THEN 'Steady Hold'
        ELSE 'Front-Loaded Drop'
    END AS momentum_profile
FROM films f
JOIN daily_collections dc ON f.film_id = dc.film_id
GROUP BY f.film_id, f.canonical_title, f.release_day
ORDER BY day3_to_day1_ratio DESC;

-- Q5: Trailer Buzz Velocity Decay (GROUP BY 24-hour buckets across Days 0-7)
-- Measures comment volume and average likes per 24-hour bucket after trailer upload.
SELECT
    FLOOR(hours_since_trailer / 24) AS day_bucket_post_trailer,
    COUNT(*) AS comment_volume,
    ROUND(AVG(like_count), 2) AS avg_comment_likes
FROM youtube_comments
WHERE hours_since_trailer >= 0 AND hours_since_trailer <= 168
GROUP BY FLOOR(hours_since_trailer / 24)
ORDER BY day_bucket_post_trailer ASC;

-- Q6: Budget-Adjusted Hype Efficiency
-- Ranks films by 3-day net / budget alongside first-7-day comment share to spotlight sleeper hits vs high-burn flops.
WITH total_7d AS (
    SELECT SUM(CASE WHEN in_first_7d = 1 THEN 1 ELSE 0 END) AS cohort_7d_comments
    FROM youtube_comments
)
SELECT
    f.film_id,
    f.canonical_title,
    f.verdict,
    f.est_budget_cr,
    f.fri_sun_india_net_cr,
    ROUND(f.fri_sun_india_net_cr / NULLIF(f.est_budget_cr, 0), 3) AS net_to_budget_ratio,
    SUM(CASE WHEN yc.in_first_7d = 1 THEN 1 ELSE 0 END) AS first_7d_comments,
    ROUND(
        100.0 * SUM(CASE WHEN yc.in_first_7d = 1 THEN 1 ELSE 0 END) / NULLIF(t.cohort_7d_comments, 0),
        2
    ) AS first_7d_comment_share_pct
FROM films f
LEFT JOIN youtube_comments yc ON f.film_id = yc.film_id
CROSS JOIN total_7d t
GROUP BY
    f.film_id, f.canonical_title, f.verdict,
    f.est_budget_cr, f.fri_sun_india_net_cr, t.cohort_7d_comments
ORDER BY net_to_budget_ratio DESC;
