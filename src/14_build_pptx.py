"""Step 14 - Build the 10-slide PowerPoint deck (docs/Release_Day_Radar_Presentation.pptx).

Generates a widescreen (16:9) executive presentation tailored for a 7-minute
talk + Q&A, embedding all four 300 DPI finding-titled charts.

Run:  python -X utf8 src/14_build_pptx.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

NAVY = RGBColor(20, 36, 61)
ACCENT = RGBColor(43, 131, 186)
DARK_TEXT = RGBColor(33, 37, 41)
MUTED = RGBColor(100, 110, 120)


def _add_header(slide, title: str, subtitle: str = "") -> None:
    tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.95))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = title
    p.font.size = Pt(24)
    p.font.bold = True
    p.font.color.rgb = NAVY
    if subtitle:
        p2 = tf.add_paragraph()
        p2.text = subtitle
        p2.font.size = Pt(13)
        p2.font.color.rgb = MUTED


def _add_bullets(slide, bullets: list[str], top: float = 1.4, width: float = 12.0, font_size: int = 16) -> None:
    tb = slide.shapes.add_textbox(Inches(0.7), Inches(top), Inches(width), Inches(5.4))
    tf = tb.text_frame
    tf.word_wrap = True
    for idx, line in enumerate(bullets):
        p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        p.text = f"•  {line}"
        p.font.size = Pt(font_size)
        p.font.color.rgb = DARK_TEXT
        p.space_after = Pt(12)


def _add_chart_slide(prs: Presentation, title: str, takeaway: str, chart_name: str) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _add_header(slide, title, takeaway)
    chart_path = c.DOCS / "charts" / chart_name
    if chart_path.exists():
        slide.shapes.add_picture(str(chart_path), Inches(0.8), Inches(1.45), width=Inches(11.6))


def main() -> int:
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # Slide 1: Title + Immediate 3-Sentence Answer
    s1 = prs.slides.add_slide(blank)
    _add_header(
        s1,
        "Release Day Radar: Can Trailer Buzz Guide Friday Screen Allocation?",
        "Executive Briefing for Head of Distribution (Mumbai) | 12 Indian Releases (2025–2026)",
    )
    _add_bullets(
        s1,
        [
            "ANSWER (1/3): Total official trailer views strongly predict 3-day India net opening scale (Spearman rho = 0.72, p = 0.008), whereas raw 7-day comment counts achieve only 50% precision alone.",
            "ANSWER (2/3): Positive trailer-week viewer sentiment predicts Friday-to-Sunday word-of-mouth growth (rho = 0.55), separating sleepers (Su From So 4.49x) from collapses (Game Changer 0.31x).",
            "ANSWER (3/3): Next Friday, use Views + Google Trends on Thursday for initial screens, and >55% Positive Sentiment + Saturday Occupancy Growth to add or cut screens by Saturday noon.",
        ],
        top=1.7,
        font_size=18,
    )

    # Slide 2: Business Problem & Cohort
    s2 = prs.slides.add_slide(blank)
    _add_header(
        s2,
        "The 72-Hour Decision & 12-Film 2025–26 Cohort",
        "Replacing gut feel with a reproducible multi-source radar",
    )
    _add_bullets(
        s2,
        [
            "Decision Served: Within 72 hours of release, advise the Head of Distribution to Add Screens, Cut Screens, or Push Promotion.",
            "Research Question: Do films with the most YouTube comments in the first 7 days post-trailer rank highest on 3-day India net, and does a Top-6 comment rule flag screen winners?",
            "Cohort Scope: 12 films across 5 languages — Hindi (6), Tamil (2), Kannada (2), Telugu (1), Malayalam (1).",
            "Scale Variance: Budgets span 86x (₹5.5 Cr Su From So to ₹475.0 Cr Toxic); 3-day India net spans ₹6.45 Cr to ₹308.57 Cr (Dhurandhar: The Revenge).",
        ],
    )

    # Slide 3: Data Architecture & The 3 Vs
    s3 = prs.slides.add_slide(blank)
    _add_header(
        s3,
        "Data Architecture & The 3 Vs (4 Sources, 3 Shapes)",
        "Variety dominated first, followed by Velocity",
    )
    _add_bullets(
        s3,
        [
            "Structured (HTML / CSV): Wikipedia infoboxes, Sacnilk daily India Net (36 rows), Google Trends India 90-day exports (1,070 rows).",
            "Semi-Structured (JSON): TMDb API v3 (/search/movie, /movie/{id}) + YouTube Data API v3 (videos endpoint).",
            "Unstructured (Free Text): 65,067 privacy-scrubbed YouTube commentThreads (clearing the 50,000+ PySpark floor).",
            "Volume: 78 files, 83.343 MB total | Velocity: 597.3 comments/hr in 0–24h (1,100/hr peak on Toxic), decaying 81.6% after Day 1.",
        ],
    )

    # Slide 4: Relational Modeling & Cleaning Rigor
    s4 = prs.slides.add_slide(blank)
    _add_header(
        s4,
        "Relational Schema & Cleaning Rigor (19 Audited Decisions)",
        "4-table MySQL schema (sql/schema.sql) + full provenance in docs/cleaning_log.csv",
    )
    _add_bullets(
        s4,
        [
            "4 Linked Tables: films (12) -> daily_collections (36), youtube_comments (65,067), google_trends (1,070).",
            "Privacy First: Stripped authorDisplayName, authorProfileImageUrl, authorChannelUrl, authorChannelId in memory before disk write (0 PII keys stored).",
            "Window Standardization: Aligned Wed/Thu/Sun releases (F08 Sikandar Sun–Tue Days 1–3) and corrected F04 (88.50 Cr) & F07 (75.35 Cr) to Sacnilk day-wise sums.",
            "Cross-Source Join Audit: Resolved Sacnilk working-title slugs (RC15_2022, Lucifer_2_2023) deterministically on film_id.",
        ],
    )

    # Slides 5-8: 4 Finding-Titled Charts
    _add_chart_slide(
        prs,
        "Finding 1: Total Views Track Opening Scale (rho = 0.72), Raw Comments Miss Mega-Trailers",
        "4,500-comment API cap truncates 67K–96K comment mega-trailers; total views avoid sampling bias",
        "chart_01_normalised_buzz_vs_opening.png",
    )
    _add_chart_slide(
        prs,
        "Finding 2: Positive Trailer Sentiment (rho = 0.55) Predicts Weekend WOM Growth",
        "High-positivity trailers expand Fri->Sun (Su From So 4.49x, Dragon 1.96x); front-loaded vehicles drop",
        "chart_02_weekend_momentum_wom.png",
    )
    _add_chart_slide(
        prs,
        "Finding 3: Trailer Buzz Decays 81.6% After 24 Hours While Search Peaks on Release Day",
        "Fast Saturday morning action is essential before weekend momentum locks in",
        "chart_03_buzz_velocity_decay.png",
    )
    _add_chart_slide(
        prs,
        "Finding 4: Hindi Recovers 77% of Budget in 3 Days; Raw Top-6 Rule Hits 50% Precision",
        "Regional releases carry higher budget risk; naive comment counts split 3 TP / 3 FP / 3 FN / 3 TN",
        "chart_04_language_efficiency.png",
    )

    # Slide 9: Next Friday Playbook
    s9 = prs.slides.add_slide(blank)
    _add_header(
        s9,
        "Next Friday's Two-Gate Distribution Playbook",
        "Zero-code decision rules for the Mumbai theatrical desk",
    )
    _add_bullets(
        s9,
        [
            "GATE 1 — Thursday Night (Initial Screens): Rank releases by Total Trailer Views + Google Trends Peak (rho = 0.72), NOT raw comment counts.",
            "GATE 1 RISK FILTER: Discount >₹200 Cr star vehicles with <45% positive trailer sentiment (cap Saturday expansion commitments upfront).",
            "GATE 2 — Saturday Noon (ADD SCREENS): Expand screens when trailer sentiment >55% positive AND Saturday net grows vs. Friday (Su From So, Dragon, Saiyaara, Border 2).",
            "GATE 2 — Saturday Noon (CUT SCREENS): Trim screens immediately if Saturday net drops >25% vs. Friday (Game Changer -57.6%, Coolie -27.9%).",
        ],
    )

    # Slide 10: Limitations & Next Steps
    s10 = prs.slides.add_slide(blank)
    _add_header(
        s10,
        "Limitations, Confounders & What Comes Next",
        "Honest boundaries on how far the data can be trusted",
    )
    _add_bullets(
        s10,
        [
            "Small Sample & Confounders: n = 12 films; star power, sequels (Dhurandhar 2, Border 2), and holiday dates confound correlation.",
            "API & Platform Bias: YouTube order=time truncation on >50K comment trailers; coordinated fan-club/bot bursts.",
            "Multilingual NLP Gap: VADER is English-lexicon-based and under-scores Hinglish/Tanglish/Kannada praise.",
            "With Better Data: Capture live Day-0 daily trailer snapshots, BookMyShow hourly occupancy feeds, and Indic-BERT sentiment.",
        ],
    )

    out_path = c.DOCS / "Release_Day_Radar_Presentation.pptx"
    prs.save(str(out_path))
    print(f"Wrote {out_path.relative_to(c.REPO_ROOT)} ({out_path.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
