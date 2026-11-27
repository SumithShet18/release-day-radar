# Release Day Radar — One-Page "V Profile" (Volume, Velocity, Variety)

This profile quantifies the **3 Vs** of our Phase 2 dataset across all 12 Hindi and regional Indian films (`F01`–`F12`) and explains how they shaped our engineering choices.

---

## 1. Volume (Exact Collected Footprint)

| Layer / Source | Format | Files | Rows / Records | Disk Size (MB) |
| :--- | :--- | ---: | ---: | ---: |
| Wikipedia Film Pages (Raw HTML) | HTML | 12 | 12 pages | 6.362 |
| Wikipedia Infobox + Reconciliation (Clean) | CSV | 2 | 24 | 0.004 |
| Sacnilk Box-Office Tables (Raw + Clean) | CSV | 13 | 36 daily + 12 summary | 0.010 |
| Google Trends India 90-Day Exports (Raw + Clean) | CSV | 13 | 1,070 daily points | 0.071 |
| TMDb API v3 (`search` + `movie/{id}`) | JSON | 12 | 12 bundles | 0.033 |
| YouTube Data API v3 (`videos` Raw + Clean) | JSON / CSV | 13 | 12 trailers | 0.087 |
| YouTube Data API v3 (`commentThreads` Raw Scrubbed) | JSON | 12 | 65,067 threads | 65.039 |
| YouTube Comments Flattened (`youtube_comments.csv`) | CSV | 1 | 65,067 rows | 11.737 |
| **Total Phase 2 Pipeline Footprint** | **Mixed** | **78** | **66,185 clean rows** | **83.343 MB** |

> *Note:* The raw `F*_comments.json` bundles total `65.039 MB` (several individual JSONs are `~6 MB`, well under GitHub's 50 MB per-file limit), while the Phase 3 Kaggle IMDb 50K corpus (`>60 MB`) remains gitignored under `data/raw/external/`.

---

## 2. Velocity (Trailer-Launch Buzz & Decay)

Using `trailer_upload_at` (`publishedAt` from YouTube `videos`) as `t = 0`:
- **First 7 Days (`0–168h`):** **`30,130`** of `65,067` collected comments (`46.3%`) arrived in the first 7 days.
- **Launch Day (`0–24h`):** **`14,335`** comments at **`597.29` comments/hour** across the 12-film cohort.
- **Observed Single-Film Peak:** **`1,100` comments/hour** (`F07 Toxic`, hour 1 post-upload; `951` in hour 0).
- **Days 2–7 (`24–168h`):** **`15,795`** comments across 144 hours = **`109.69` comments/hour** — an **`81.6%` drop** in hourly velocity after the first 24 hours.

*(Caveat: For high-volume trailers like `Chhaava` with `96,159` total comments, `order=time` returns the most recent ~4,500 comments, so absolute 7-day counts are under-sampled on older mega-trailers unless combined with `order=relevance`.)*

---

## 3. Variety (3 Data Shapes & 4 Sources)

1. **Structured (`HTML`, `CSV`):** Wikipedia infobox tables (`pd.read_html`), Sacnilk daily India Net tables (`₹ Cr`), and Google Trends daily `0–100` search indices.
2. **Semi-Structured (`JSON`):** Nested TMDb `/search/movie` + `/movie/{id}` payloads (`genres[]`, `runtime`, `popularity`) and YouTube `videos` payloads (`snippet.publishedAt`, `statistics.*`), flattened with `pd.json_normalize()`.
3. **Unstructured (`Free Text`):** `65,067` multilingual YouTube viewer comments (English, Hindi, Hinglish, Tamil, Telugu, Kannada, Malayalam) requiring PII stripping, newline normalization, VADER benchmarking, and PySpark text aggregation.

---

## 4. Which "V" Dominated & How It Changed Our Tool Choices

**Variety dominated first**, followed by **Velocity**:
- **Why Variety dominated:** Before any modeling could begin, the same film appeared as `"Dhurandhar: The Revenge"`, `"Dhurandhar 2"`, and YouTube trailer ID `"NHk7scrb_9I"`, while box-office figures arrived as `"₹807.91 crore"` vs `"₹1.81 billion"` and Thursday/Wednesday/Sunday releases misaligned calendar Fri–Sun windows. This forced us to build a deterministic `film_id` (`F01`–`F12`) master roster, `crore_from_text()` parser, non-Friday window standardization (`opening_weekend_verified.csv`), and a 4-table relational MySQL schema (`sql/schema.sql`).
- **How Velocity shaped Phase 2–3:** Because `46.3%` of trailer comments cluster in a narrow 7-day window with an `81.6%` decay after 24 hours, we computed `hours_since_trailer` and `in_first_7d` at ingestion (`07_youtube_layer.py`), indexed `(film_id, in_first_7d)` and `hours_since_trailer` in MySQL, and batched `65,067` rows for PySpark text processing in Phase 3.
