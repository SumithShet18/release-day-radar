# Release Day Radar — 10-Slide Presentation Deck (7-Minute Talk)

---

## Slide 1: Title + The Answer for the Head of Distribution
- **Title:** Release Day Radar — Can Trailer Buzz Guide Friday Screen Allocation?
- **The 3-Sentence Answer:**
  1. **Total official trailer views** strongly predict 3-day India net opening scale ($\rho = 0.72, p = 0.008$), whereas raw 7-day comment counts achieve only **50% precision** alone.
  2. **Positive trailer-week sentiment** predicts Friday-to-Sunday word-of-mouth growth ($\rho = 0.55$), separating sleepers (*Su From So* `4.49x`) from collapses (*Game Changer* `0.31x`).
  3. **Next Friday's Rule:** Use **Views + Trends** on Thursday to set screens, and **>55% Positive Sentiment + Saturday Occupancy** to add or cut screens by Saturday noon.

---

## Slide 2: Business Problem, Research Question & 12-Film Cohort
- **Decision:** Within 72 hours of release, advise a non-technical Head of Distribution to **Add Screens, Cut Screens, or Push Promotion**.
- **Research Question:** Across 12 Hindi & regional films (2025–26), do 7-day trailer comments rank highest on 3-day India net, and would a Top-6 comment rule flag screen winners?
- **Cohort:** 12 releases across 5 languages (6 Hindi, 2 Tamil, 2 Kannada, 1 Telugu, 1 Malayalam); budgets from `₹5.5 Cr` (*Su From So*) to `₹475 Cr` (*Toxic*).

---

## Slide 3: Data Architecture & The 3 Vs
- **3 Shapes, 4 Sources:**
  - *Structured:* Wikipedia infoboxes, Sacnilk 3-day India Net, Google Trends India (90-day CSVs).
  - *Semi-Structured:* TMDb API v3 JSON + YouTube `videos` JSON.
  - *Unstructured:* `65,067` PII-scrubbed YouTube `commentThreads` (exceeding 50K PySpark floor).
- **The 3 Vs:** `83.34 MB` across 78 files | `597.3 comments/hr` in 0–24h (`81.6%` decay after Day 1) | **Variety dominated first**, followed by **Velocity**.

---

## Slide 4: Relational Modeling & Cleaning Rigor
- **4-Table MySQL Schema (`sql/schema.sql`):** `films` (12) → `daily_collections` (36), `youtube_comments` (65,067), `google_trends` (1,070).
- **Top Cleaning Wins (`docs/cleaning_log.csv`):**
  - Stripped all 4 YouTube author PII fields in memory before disk write (`0` PII keys stored).
  - Standardized Wed/Thu/Sun openers (`F08 Sikandar` Sun–Tue Days 1–3).
  - Resolved Sacnilk working-title slugs (`RC15_2022` → *Game Changer*) via deterministic `film_id` keys.

---

## Slide 5: Finding 1 — Views Track Opening Size ($\rho = 0.72$), Raw Comments Miss Mega-Trailers
- **Visual:** `docs/charts/chart_01_normalised_buzz_vs_opening.png`
- **Takeaway:** Raw sampled 7-day comments give **50% precision (3/6)** because `order=time` caps truncate 67K–96K comment mega-trailers (*Dhurandhar: The Revenge*, *Chhaava*) while over-indexing *Toxic* and *Dragon*.

---

## Slide 6: Finding 2 — Trailer Sentiment Predicts Weekend Word-of-Mouth ($\rho = 0.55$)
- **Visual:** `docs/charts/chart_02_weekend_momentum_wom.png`
- **Takeaway:** High-positivity trailers (*Su From So* `77.7%` → `4.49x`, *Dragon* `55.7%` → `1.96x`, *Border 2* `57.5%` → `1.82x`) surge on Sunday; *Game Changer* (`0.31x`) and *Coolie* (`0.64x`) fade after Day 1.

---

## Slide 7: Finding 3 — Buzz Decays 81.6% After 24 Hours
- **Visual:** `docs/charts/chart_03_buzz_velocity_decay.png`
- **Takeaway:** `46.3%` of sampled comments arrive in Days 0–6, peaking at `1,100/hr` on *Toxic* hour 1 and decaying `81.6%` after 24h, while Google Trends peaks on release day.

---

## Slide 8: Finding 4 — Regional Capital Efficiency & Top-6 Confusion Matrix
- **Visual:** `docs/charts/chart_04_language_efficiency.png`
- **Takeaway:** Hindi films recover **`77.0%`** of budget in 3 days vs. `17%–41%` for regional releases; naive Top-6 comment rules split evenly (`3 TP, 3 FP, 3 FN, 3 TN`).

---

## Slide 9: Next Friday's Two-Gate Distribution Playbook
- **Gate 1 (Thursday Night — Initial Screens):** Use **Total Trailer Views + Google Trends Peak** ($\rho = 0.72$); discount `>₹200 Cr` vehicles with `<45%` positive trailer sentiment.
- **Gate 2 (Saturday Noon — 24h Adjustment):**
  - **ADD SCREENS:** `>55%` positive trailer sentiment + Saturday growth.
  - **CUT SCREENS:** Saturday net drops `>25%` vs. Friday.

---

## Slide 10: Limitations, Confounders & What's Next
- **Limits:** Small sample ($n=12$), star/franchise/holiday confounders, YouTube `order=time` cap on mega-trailers, fan-club spam, and VADER's English bias on Hinglish/Tanglish comments.
- **Next Iteration:** Live Day-0 trailer scraping, BookMyShow hourly seat-occupancy feeds, and Indic-BERT multilingual sentiment.
