"""Step 12 - VADER sentiment benchmark (IMDb 50K) + YouTube comment scoring & Spearman tests.

1. Checks for data/raw/external/IMDB Dataset.csv; if present, benchmarks VADER
   across 50,000 labelled reviews and writes docs/vader_imdb_benchmark.md.
2. Scores all 65,067 comments in data/clean/youtube_comments.csv using
   vaderSentiment (compound >= 0.05 Positive, <= -0.05 Negative, else Neutral).
3. Writes data/clean/youtube_comments_scored.csv and aggregated
   data/clean/film_sentiment_summary.csv.
4. Computes Spearman rank correlations (rho, p-value) against 3-day India net
   and Day 3 / Day 1 momentum, saving data/clean/spearman_correlations.csv.

Run:  python -X utf8 src/12_vader_sentiment.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402


def label_sentiment(compound: float) -> str:
    if compound >= 0.05:
        return "Positive"
    if compound <= -0.05:
        return "Negative"
    return "Neutral"


def benchmark_imdb(analyzer: SentimentIntensityAnalyzer) -> None:
    imdb_path = c.RAW / "external" / "IMDB Dataset.csv"
    out_md = c.DOCS / "vader_imdb_benchmark.md"
    if not imdb_path.exists():
        print("WARNING: data/raw/external/IMDB Dataset.csv not found; skipping 50K IMDb benchmark.")
        out_md.write_text(
            "# VADER Sentiment Benchmark on IMDb 50K\n\n"
            "**Status:** `PENDING_EXTERNAL_CORPUS` (`data/raw/external/IMDB Dataset.csv` "
            "is not yet placed in the workspace).\n\n"
            "Once `IMDB Dataset.csv` is downloaded from Kaggle into `data/raw/external/`, "
            "re-run `python -X utf8 src/12_vader_sentiment.py` to populate Accuracy, Precision, "
            "Recall, and the Confusion Matrix.\n",
            encoding="utf-8",
        )
        return

    imdb = pd.read_csv(imdb_path)
    preds = [
        "positive" if analyzer.polarity_scores(str(txt))["compound"] >= 0.05 else "negative"
        for txt in imdb["review"]
    ]
    actual = imdb["sentiment"].str.lower().str.strip()
    tp = int(((pd.Series(preds) == "positive") & (actual == "positive")).sum())
    tn = int(((pd.Series(preds) == "negative") & (actual == "negative")).sum())
    fp = int(((pd.Series(preds) == "positive") & (actual == "negative")).sum())
    fn = int(((pd.Series(preds) == "negative") & (actual == "positive")).sum())
    acc = (tp + tn) / len(imdb)
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)

    out_md.write_text(
        "# VADER Sentiment Benchmark on IMDb 50K\n\n"
        f"- **Rows evaluated:** {len(imdb):,}\n"
        f"- **Accuracy:** {acc:.4f}\n"
        f"- **Precision (Positive):** {prec:.4f}\n"
        f"- **Recall (Positive):** {rec:.4f}\n\n"
        "## Confusion Matrix\n\n"
        "| Actual \\ Predicted | Positive | Negative |\n"
        "| :--- | ---: | ---: |\n"
        f"| **Positive** | {tp:,} | {fn:,} |\n"
        f"| **Negative** | {fp:,} | {tn:,} |\n",
        encoding="utf-8",
    )
    print(f"IMDb 50K VADER benchmark: acc={acc:.4f}, prec={prec:.4f}, rec={rec:.4f}")


def main() -> int:
    c.ensure_dirs()
    analyzer = SentimentIntensityAnalyzer()
    benchmark_imdb(analyzer)

    comments = pd.read_csv(c.CLEAN / "youtube_comments.csv")
    texts = comments["text_original"].fillna("").astype(str).tolist()
    compounds = [round(analyzer.polarity_scores(t)["compound"], 4) for t in texts]
    comments["vader_compound"] = compounds
    comments["sentiment_label"] = [label_sentiment(v) for v in compounds]

    scored_path = c.CLEAN / "youtube_comments_scored.csv"
    c.write_csv(comments, scored_path)
    print(f"Wrote {scored_path.relative_to(c.REPO_ROOT)} ({len(comments):,} rows)")

    # Aggregated sentiment summary by film_id and window
    comments["window"] = comments["in_first_7d"].astype(bool).map(
        {True: "first_7d", False: "post_7d"}
    )
    grouped = (
        comments.groupby(["film_id", "window"], as_index=False)
        .agg(
            comment_count=("comment_id", "count"),
            mean_vader_compound=("vader_compound", "mean"),
            pct_positive=("sentiment_label", lambda s: (s == "Positive").mean() * 100.0),
            pct_negative=("sentiment_label", lambda s: (s == "Negative").mean() * 100.0),
            pct_neutral=("sentiment_label", lambda s: (s == "Neutral").mean() * 100.0),
        )
    )
    overall = (
        comments.groupby("film_id", as_index=False)
        .agg(
            comment_count=("comment_id", "count"),
            mean_vader_compound=("vader_compound", "mean"),
            pct_positive=("sentiment_label", lambda s: (s == "Positive").mean() * 100.0),
            pct_negative=("sentiment_label", lambda s: (s == "Negative").mean() * 100.0),
            pct_neutral=("sentiment_label", lambda s: (s == "Neutral").mean() * 100.0),
        )
    )
    overall.insert(1, "window", "all")
    summary = pd.concat([overall, grouped], ignore_index=True).sort_values(["film_id", "window"])
    for col in ("mean_vader_compound", "pct_positive", "pct_negative", "pct_neutral"):
        summary[col] = summary[col].round(3)
    c.write_csv(summary, c.CLEAN / "film_sentiment_summary.csv")

    # Spearman rank correlations against analytical master
    master = pd.read_csv(c.CLEAN / "films_analytical_master.csv")
    s_7d = summary[summary["window"] == "first_7d"][
        ["film_id", "mean_vader_compound", "pct_positive"]
    ].rename(
        columns={
            "mean_vader_compound": "first_7d_mean_vader",
            "pct_positive": "first_7d_pct_positive",
        }
    )
    merged = master.merge(s_7d, on="film_id", how="left")

    corr_tests = [
        ("sampled_first_7d_comments", "fri_sun_india_net_cr"),
        ("est_true_first_7d_comments", "fri_sun_india_net_cr"),
        ("api_total_views", "fri_sun_india_net_cr"),
        ("api_total_comments", "fri_sun_india_net_cr"),
        ("first_7d_pct_positive", "fri_sun_india_net_cr"),
        ("first_7d_mean_vader", "fri_sun_india_net_cr"),
        ("first_7d_pct_positive", "day3_to_day1_ratio"),
        ("first_7d_mean_vader", "day3_to_day1_ratio"),
    ]
    corr_rows: list[dict] = []
    for x_col, y_col in corr_tests:
        rho, pval = spearmanr(merged[x_col], merged[y_col], nan_policy="omit")
        corr_rows.append(
            {
                "x_metric": x_col,
                "y_outcome": y_col,
                "spearman_rho": round(float(rho), 4),
                "p_value": round(float(pval), 4),
                "n_films": int(merged[[x_col, y_col]].dropna().shape[0]),
            }
        )
    corr_df = pd.DataFrame(corr_rows)
    c.write_csv(corr_df, c.CLEAN / "spearman_correlations.csv")
    print("\nSpearman rank correlations:")
    print(corr_df.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
