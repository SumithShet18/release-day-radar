# Release Day Radar

**Module 1 data-engineering case study** — can trailer-week YouTube engagement
tell a Mumbai film distributor which releases deserve extra Friday screens?

> **Research question.** Across 12 Hindi and regional Indian films released in
> 2025–26, do films with the most YouTube comments in the first 7 days after
> their primary official trailer upload also rank highest on 3-day
> (Friday–Sunday) India net box office — and would a top-half trailer-comment
> rule have accurately flagged which films warranted extra Friday/Saturday
> screens?

**Decision it serves.** By Thursday night the Head of Distribution must decide
whether to hold, add or cut screens for a Friday release. Today that call rests
on gut feel, trade tweets and the Friday-night number. This project tests
whether a free, observable signal — trailer-comment volume in week one — would
have made that call better.

**Reader.** A non-technical Head of Distribution. One clear answer, the evidence
behind it, and an honest note on how far the data can be trusted.

---

## Data architecture — 3 shapes, 4 sources

| Shape | What it gives us | Source | Format |
| --- | --- | --- | --- |
| Structured | Weekend India net box office, screens, release dates | Wikipedia film pages (`pd.read_html`) + verified trade table | HTML |
| Structured | Relative search interest around trailer and release | Google Trends India exports | CSV |
| Semi-structured | Trailer `publishedAt`, views, likes, comment counts | YouTube Data API v3 (`videos`) | JSON |
| Semi-structured | Runtime, genres, popularity | TMDb API v3 (`/search/movie`, `/movie/{id}`) | JSON |
| Unstructured | What viewers actually say | YouTube Data API v3 (`commentThreads`) | Free text |
| Unstructured (practice) | Labelled sentiment benchmark, 50K+ rows | Kaggle IMDb 50K reviews | CSV |

Films are joined on a cleaned `film_key` (title + release year), because the
same title arrives as `Dhurandhar`, `Dhurandhar (2025)` and
`DHURANDHAR - Official Trailer` across sources.

---

## Repository layout

```text
release-day-radar/
├── .env.example          # credential template (copy to .env)
├── .gitignore
├── requirements.txt
├── README.md
├── data/
│   ├── raw/
│   │   ├── wiki/         # Wikipedia box-office HTML snapshots
│   │   ├── trends/       # Google Trends India CSV exports
│   │   ├── youtube/      # videos + commentThreads JSON
│   │   ├── tmdb/         # search/movie + movie/{id} JSON
│   │   └── external/     # Kaggle IMDb 50K (downloaded, not redistributed)
│   └── clean/            # typed, joined, analysis-ready tables
├── notebooks/            # exploration and cleaning notebooks
├── sql/                  # schema DDL, ER diagram, 5+ queries
└── src/
    ├── __init__.py
    └── test_sources.py   # Phase 1 source verification harness
```

---

## Quickstart

Requires **Python 3.11+**.

```powershell
git clone https://github.com/SumithShet18/release-day-radar.git
cd release-day-radar

python -m venv .venv
.\.venv\Scripts\Activate.ps1        # bash: source .venv/bin/activate
python -m pip install -r requirements.txt

Copy-Item .env.example .env         # bash: cp .env.example .env
# then paste your keys into .env
```

Get free credentials:

- **YouTube Data API v3** — Google Cloud Console → enable the API → create an
  API key. `videos` and `commentThreads` both draw on the same key.
- **TMDb** — <https://www.themoviedb.org/settings/api> → API Key (v3 auth).

Google Trends has no official export API; download India, 90-day CSVs per film
from the Trends web UI into `data/raw/trends/`.

---

## Verify every source (Phase 1 gate)

```powershell
python -m src.test_sources            # all checks
python -m src.test_sources --offline  # local files only, no network
python -m src.test_sources --json     # machine-readable report
```

The harness returns `PASS`, `FAIL` or `SKIP` per source and exits `2` if
anything failed. On a fresh clone, `SKIP` is normal for checks whose key or
local file is not yet present — that is exactly what the go/no-go gate is meant
to surface. It never stores comment text, usernames or profile links; only
counts and metadata are reported.

---

## Privacy and source ethics

- Official APIs only, within rate limits; no scraping behind a login.
- Usernames, channel IDs and profile links are dropped from comment and review
  data before analysis and are never published.
- Kaggle is a practice/benchmark supplement, never the primary source.
- Every source's URL, access date, method and terms of use are recorded in the
  source register (Phase 2 deliverable).

---

## Project status

| Phase | Scope | Status |
| --- | --- | --- |
| 1 — Frame | Question, film roster (12), sources verified | Scaffold + verification harness in place; keys and film roster pending |
| 2 — Collect & model | Raw pulls, JSON flattening, ER diagram, MySQL load | Not started |
| 3 — Clean & analyse | Film-name join, type casting, PySpark text job, sentiment | Not started |
| 4 — Story & submit | Report, slides, README, 7-minute talk | Not started |

---

## Git workflow

- `main` stays releasable; work lands through short-lived branches such as
  `chore/phase-1-scaffold`.
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`,
  `chore:`, `build:`), one logical change per commit.
- Raw data and notebooks are committed so the pipeline can be rerun end-to-end;
  large third-party corpora and all credentials stay out of git.
