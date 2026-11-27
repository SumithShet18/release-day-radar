# Release Day Radar

**Module 1 Data Engineering & Storytelling Case Study** — Can YouTube trailer engagement tell a Mumbai film distributor which releases deserve extra Friday/Saturday screens?

> **Research question.** Across 12 Hindi and regional Indian films released in 2025–26, do films with the most YouTube comments in the first 7 days after their primary official trailer upload also rank highest on 3-day (Friday–Sunday) India net box office — and would a top-half trailer-comment rule have accurately flagged which films warranted extra Friday/Saturday screens?

**GitHub Repository:** `https://github.com/SumithShet18/release-day-radar`

---

## Executive Answer (For the Head of Distribution)
- **Total official trailer views** strongly track 3-day India net opening scale (Spearman $\rho = 0.72$, $p = 0.008$), whereas raw sampled 7-day YouTube comment counts achieve only **50% precision** alone due to API pagination caps on mega-trailers and noisy fan-brigaded star vehicles.
- **Positive trailer-week sentiment** predicts Friday-to-Sunday word-of-mouth momentum ($\rho = 0.55$), separating sleepers (*Su From So* `4.49x`, *Dragon* `1.96x`, *Border 2* `1.82x`) from weekend collapses (*Game Changer* `0.31x`, *Coolie* `0.64x`).
- **Two-Gate Playbook:** Use **Total Trailer Views + Google Trends** on Thursday to allocate initial screens, and **>55% Positive Sentiment + Saturday Occupancy Growth** to add or cut screens by Saturday noon.

---

## Data Architecture — 3 Shapes, 4 Sources

| Shape | Source | Format | Output Files |
| :--- | :--- | :--- | :--- |
| **Structured** | Wikipedia film pages (`pd.read_html`) + Sacnilk daily box-office tables | HTML, CSV | `data/clean/wiki_infobox.csv`, `data/clean/opening_weekend_verified.csv` |
| **Structured** | Google Trends India 90-day exports | CSV | `data/clean/google_trends_combined.csv` (`1,070` rows) |
| **Semi-Structured** | TMDb API v3 (`/search/movie`, `/movie/{id}`) & YouTube Data API v3 (`videos`) | JSON | `data/raw/tmdb/F*_tmdb.json`, `data/clean/youtube_videos.csv` |
| **Unstructured** | YouTube Data API v3 (`commentThreads`, PII-scrubbed) | JSON / Free Text | `data/clean/youtube_comments.csv` (`65,067` rows) |

---

## Quickstart & End-to-End Reproduction

Requires **Python 3.11+**, **Java 17+** (for PySpark), and optional **MySQL 8.0+**.

```powershell
git clone https://github.com/SumithShet18/release-day-radar.git
cd release-day-radar

python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install python-pptx rapidfuzz

Copy-Item .env.example .env
# Add TMDB_API_KEY, YOUTUBE_API_KEY, and MYSQL_* credentials to .env
```

### Run the Full Pipeline (Steps 01–15)

```powershell
# Phase 1: Verify sources & keys
python -m src.test_sources

# Phase 2: Collect, reconcile, model, and query
python -X utf8 src/01_wiki_layer.py
python -X utf8 src/02_reconcile_wiki.py
python -X utf8 src/03_boxoffice_layer.py
python -X utf8 src/04_trends_layer.py
python -X utf8 src/05_resolve_ids.py
python -X utf8 src/06_validate_phase2.py
python -X utf8 src/07_youtube_layer.py
python -X utf8 src/08_load_mysql.py
python -X utf8 src/09_run_sql_queries.py   # Falls back to SQLite mirror if MySQL is offline

# Phase 3: Clean, normalise, PySpark (65K+ rows), VADER sentiment, charts
python -X utf8 src/10_clean_and_normalize.py
python -X utf8 src/11_pyspark_text_job.py
python -X utf8 src/12_vader_sentiment.py
python -X utf8 src/13_generate_charts.py

# Phase 4: Build PPTX deck & package final submission zip
python -X utf8 src/14_build_pptx.py
python -X utf8 src/15_package_submission.py
```

---

## Key Deliverables

| Deliverable | Path |
| :--- | :--- |
| Final Project Report | [docs/final_report.md](docs/final_report.md) |
| Presentation Slides (Markdown + PPTX) | [docs/presentation_slides.md](docs/presentation_slides.md), `docs/Release_Day_Radar_Presentation.pptx` |
| Cleaning Log (19 Decisions) | [docs/cleaning_log.csv](docs/cleaning_log.csv) |
| Source Register & One-Page V Profile | [docs/source_register.md](docs/source_register.md), [docs/v_profile.md](docs/v_profile.md) |
| Data Types Inventory & Spreadsheet Comparison | [docs/data_types_inventory.md](docs/data_types_inventory.md), [docs/spreadsheet_vs_pandas.md](docs/spreadsheet_vs_pandas.md) |
| ER Diagram, Schema DDL & 6 SQL Queries | [docs/er_diagram.md](docs/er_diagram.md), [sql/schema.sql](sql/schema.sql), [sql/queries.sql](sql/queries.sql) |
| Publication Charts (300 DPI) | `docs/charts/chart_01_*.png` – `chart_04_*.png` |
| Team Contribution Split | [docs/team_contribution.md](docs/team_contribution.md) |

---

## Project Status

| Phase | Scope | Status |
| :--- | :--- | :--- |
| 1 — Frame | Question, 12-film roster, source verification harness | **Completed** |
| 2 — Collect & Model | Wiki, Sacnilk, Trends, TMDb, 65K YouTube comments, MySQL schema & queries | **Completed** |
| 3 — Clean & Analyse | Title audit, Min-Max/Z-score, PySpark 65K job, VADER + Spearman, 4 charts | **Completed** |
| 4 — Story & Submit | Final report, 10-slide PPTX, README, team split, submission zip | **Completed** |

---

## Privacy & Ethics
- Official APIs only within rate limits; zero scraping behind logins.
- All YouTube author PII (`authorDisplayName`, `authorProfileImageUrl`, `authorChannelUrl`, `authorChannelId`) is stripped in memory before writing to disk.
- `.env` and large third-party corpora (`data/raw/external/`) are gitignored.
