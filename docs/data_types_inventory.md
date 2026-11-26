# Release Day Radar — Data Types Inventory Table

Every field used across the four sources is classified below on both **Statistical Measurement Scale** (`Nominal`, `Ordinal`, `Discrete`, `Continuous`) and **Data Structure Shape** (`Structured`, `Semi-Structured`, `Unstructured`).

| Field Name | Source | Statistical Scale | Data Shape | Description / Example |
| :--- | :--- | :--- | :--- | :--- |
| `film_id` | Master Roster | Nominal | Structured | Canonical join key (`F01`–`F12`) |
| `canonical_title` | Master Roster | Nominal | Structured | Standardized film title (`Chhaava`) |
| `language` | Master Roster | Nominal | Structured | Primary release language (`Hindi`, `Tamil`, `Telugu`, `Kannada`, `Malayalam`) |
| `release_date` | Master Roster / Sacnilk | Continuous (Interval) | Structured | Theatrical release date (`YYYY-MM-DD`) |
| `release_day` | Master Roster | Nominal | Structured | Day of week of release (`Thu`, `Fri`, `Wed`, `Sun`) |
| `verdict` | Master Roster | Ordinal | Structured | Trade verdict (`Disaster` < `Flop` < `Hit` < `Blockbuster` < `All-Time Blockbuster`) |
| `est_budget_cr` | Wikipedia / Master | Continuous (Ratio) | Structured | Production budget in ₹ Crore (`5.5`–`475.0`) |
| `lifetime_ww_gross_cr` | Wikipedia / Master | Continuous (Ratio) | Structured | Lifetime worldwide gross in ₹ Crore |
| `day1_net_cr`, `day2_net_cr`, `day3_net_cr` | Sacnilk | Continuous (Ratio) | Structured | Daily India net box-office collection in ₹ Crore |
| `fri_sun_india_net_cr` | Sacnilk | Continuous (Ratio) | Structured | Standardized 3-day India net collection in ₹ Crore |
| `is_non_friday_release` | Derived (Sacnilk) | Nominal | Structured | Boolean flag for Wed/Thu/Sun openers |
| `day_number` | Sacnilk | Ordinal | Structured | Standardized opening day slot (`1`, `2`, `3`) |
| `trend_date` | Google Trends | Continuous (Interval) | Structured | Daily search-interest date (`YYYY-MM-DD`) |
| `search_interest_index` | Google Trends | Ordinal / Continuous (0–100) | Structured | Relative India search interest (`0`–`100` normalized to window peak) |
| `tmdb_id` | TMDb API v3 | Nominal | Semi-Structured | TMDb numeric movie identifier |
| `runtime_mins` | TMDb API v3 | Continuous (Ratio) | Semi-Structured | Film runtime in minutes (`121`–`218`) |
| `genres` | TMDb API v3 | Nominal | Semi-Structured | Comma-separated genre tags (`Action, Crime, Thriller`) |
| `tmdb_popularity` | TMDb API v3 | Continuous (Ratio) | Semi-Structured | TMDb popularity index |
| `tmdb_vote_average` | TMDb API v3 | Continuous (Interval) | Semi-Structured | TMDb user rating average (`0–10`) |
| `youtube_video_id` | YouTube Data API v3 | Nominal | Semi-Structured | 11-character official trailer ID |
| `trailer_published_at` | YouTube Data API v3 | Continuous (Interval) | Semi-Structured | UTC timestamp of trailer upload |
| `yt_total_views` | YouTube Data API v3 | Discrete | Semi-Structured | Cumulative trailer view count |
| `yt_total_likes` | YouTube Data API v3 | Discrete | Semi-Structured | Cumulative trailer like count |
| `yt_total_comments` | YouTube Data API v3 | Discrete | Semi-Structured | Cumulative trailer comment count |
| `comment_id` | YouTube `commentThreads` | Nominal | Semi-Structured | Unique YouTube thread ID |
| `published_at` | YouTube `commentThreads` | Continuous (Interval) | Semi-Structured | UTC timestamp of viewer comment |
| `like_count` | YouTube `commentThreads` | Discrete | Semi-Structured | Comment upvote count |
| `total_reply_count` | YouTube `commentThreads` | Discrete | Semi-Structured | Number of replies to top-level comment |
| `hours_since_trailer` | Derived (YouTube) | Continuous (Ratio) | Structured | Hours elapsed between trailer upload and comment |
| `in_first_7d` | Derived (YouTube) | Nominal | Structured | Boolean (`0 <= hours_since_trailer <= 168`) |
| `text_original` | YouTube `commentThreads` | Nominal (Free Text) | Unstructured | Raw multilingual viewer comment text |
| `char_length`, `word_count` | PySpark Derived | Discrete | Structured | Character and token counts of cleaned comment text |
| `vader_compound` | VADER Derived | Continuous (Interval) | Structured | Compound sentiment score (`-1.0` to `+1.0`) |
| `sentiment_label` | VADER Derived | Ordinal | Structured | Sentiment tier (`Negative` < `Neutral` < `Positive`) |
