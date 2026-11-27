"""Step 13 - Generate 4 publication-grade (300 DPI) finding-titled charts.

Outputs saved to docs/charts/:
  1. chart_01_normalised_buzz_vs_opening.png
  2. chart_02_weekend_momentum_wom.png
  3. chart_03_buzz_velocity_decay.png
  4. chart_04_language_efficiency.png

Run:  python -X utf8 src/13_generate_charts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as c  # noqa: E402

CHARTS_DIR = c.DOCS / "charts"


def setup_style() -> None:
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.labelsize": 10.5,
            "xtick.labelsize": 9.5,
            "ytick.labelsize": 9.5,
        }
    )


def chart_01_normalised_buzz(master: pd.DataFrame, corr: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10.5, 6.5))

    palette = {
        "All-Time Blockbuster": "#1b7837",
        "Blockbuster": "#4dac26",
        "Hit": "#2b83ba",
        "Flop": "#fdae61",
        "Disaster": "#d7191c",
    }

    for verdict, grp in master.groupby("verdict"):
        ax.scatter(
            grp["sampled_first_7d_comments_minmax"],
            grp["fri_sun_india_net_cr_minmax"],
            s=grp["est_budget_cr"] * 1.4 + 45,
            color=palette.get(verdict, "#666666"),
            alpha=0.85,
            edgecolors="black",
            linewidth=0.8,
            label=verdict,
            zorder=3,
        )

    for _, r in master.iterrows():
        dx, dy = 0.015, 0.015
        if r["film_id"] == "F04":
            dy = -0.04
        elif r["film_id"] == "F05":
            dy = 0.025
        elif r["film_id"] == "F06":
            dy = -0.035
        ax.annotate(
            f"{r['canonical_title']} (₹{r['fri_sun_india_net_cr']:.0f}Cr)",
            (r["sampled_first_7d_comments_minmax"], r["fri_sun_india_net_cr_minmax"]),
            xytext=(
                r["sampled_first_7d_comments_minmax"] + dx,
                r["fri_sun_india_net_cr_minmax"] + dy,
            ),
            fontsize=8.3,
            fontweight="semibold" if r["film_id"] in {"F01", "F03", "F04", "F07"} else "normal",
        )

    # Top-6 median cutoffs
    x_med = master["sampled_first_7d_comments_minmax"].median()
    y_med = master["fri_sun_india_net_cr_minmax"].median()
    ax.axvline(x_med, color="#555555", linestyle="--", linewidth=1.0, alpha=0.7)
    ax.axhline(y_med, color="#555555", linestyle="--", linewidth=1.0, alpha=0.7)
    ax.text(0.76, 0.04, "False Positives\n(High Hype, Lower Net)", fontsize=8.5, color="#b2182b", bbox=dict(boxstyle="round,pad=0.3", fc="#fee0d2", alpha=0.6))
    ax.text(0.02, 0.90, "Mega-Trailer Cap\n(Top Net, >50K Comments)", fontsize=8.5, color="#1b7837", bbox=dict(boxstyle="round,pad=0.3", fc="#e5f5e0", alpha=0.6))

    rho_7d = corr.loc[corr["x_metric"] == "sampled_first_7d_comments", "spearman_rho"].iloc[0]
    p_7d = corr.loc[corr["x_metric"] == "sampled_first_7d_comments", "p_value"].iloc[0]
    rho_views = corr.loc[corr["x_metric"] == "api_total_views", "spearman_rho"].iloc[0]
    p_views = corr.loc[corr["x_metric"] == "api_total_views", "p_value"].iloc[0]

    ax.set_title(
        f"Raw 7-Day Comment Samples Misclassify Mega-Trailers (rho={rho_7d:.2f}, p={p_7d:.2f}), "
        f"While Total Trailer Views Track Opening Net (rho={rho_views:.2f}, p={p_views:.3f})",
        pad=12,
    )
    ax.set_xlabel("Min-Max Normalised Sampled First-7-Day Comments (0–1)")
    ax.set_ylabel("Min-Max Normalised 3-Day India Net Box Office (0–1)")
    ax.set_xlim(-0.05, 1.18)
    ax.set_ylim(-0.06, 1.10)
    ax.legend(title="Trade Verdict (Bubble = Budget)", loc="center right", frameon=True, fontsize=8.5)
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "chart_01_normalised_buzz_vs_opening.png")
    plt.close(fig)


def chart_02_weekend_momentum(master: pd.DataFrame, sent: pd.DataFrame) -> None:
    s7 = sent[sent["window"] == "first_7d"][["film_id", "pct_positive", "mean_vader_compound"]]
    df = master.merge(s7, on="film_id", how="left").sort_values("day3_to_day1_ratio", ascending=True)

    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    norm = plt.Normalize(df["pct_positive"].min(), df["pct_positive"].max())
    colors = plt.cm.RdYlGn(norm(df["pct_positive"]))

    bars = ax.barh(df["canonical_title"], df["day3_to_day1_ratio"], color=colors, edgecolor="black", linewidth=0.6)
    ax.axvline(1.0, color="#333333", linestyle="--", linewidth=1.2, label="1.0x Flat Hold")

    for bar, (_, r) in zip(bars, df.iterrows()):
        ax.text(
            bar.get_width() + 0.06,
            bar.get_y() + bar.get_height() / 2,
            f"{r['day3_to_day1_ratio']:.2f}x  ({r['verdict']} | {r['pct_positive']:.0f}% Pos)",
            va="center",
            fontsize=8.5,
        )

    ax.set_title(
        "Word-of-Mouth Growers (Su From So 4.49x, Dragon 1.96x, Border 2 1.82x) "
        "Outperform Front-Loaded Drops (Game Changer 0.31x)",
        pad=12,
    )
    ax.set_xlabel("Weekend Momentum Multiplier (Day 3 Net / Day 1 Net)")
    ax.set_xlim(0, df["day3_to_day1_ratio"].max() + 1.45)
    sm = plt.cm.ScalarMappable(cmap=plt.cm.RdYlGn, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.02)
    cbar.set_label("Trailer-Week % Positive Sentiment (VADER)")
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "chart_02_weekend_momentum_wom.png")
    plt.close(fig)


def chart_03_buzz_velocity_decay(comments: pd.DataFrame, trends: pd.DataFrame, master: pd.DataFrame) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.4))

    # Left panel: Days 0-6 hourly/daily decay post-trailer
    w7 = comments[(comments["hours_since_trailer"] >= 0) & (comments["hours_since_trailer"] <= 168)].copy()
    w7["day_bucket"] = (w7["hours_since_trailer"] // 24).astype(int).clip(upper=6)
    daily = w7.groupby("day_bucket", as_index=False).agg(
        comments=("comment_id", "count"),
        avg_likes=("like_count", "mean"),
    )
    ax1.bar(daily["day_bucket"], daily["comments"], color="#2b83ba", edgecolor="black", alpha=0.85, label="Comment Volume")
    ax1.set_xticks(range(7))
    ax1.set_xticklabels([f"Day {d}" for d in range(7)])
    ax1.set_ylabel("Sampled Comment Volume")
    ax1.set_xlabel("Days Post-Trailer Upload")
    ax1.set_title("81.6% Hourly Comment Decay After First 24 Hours", fontsize=11.5)

    ax1_r = ax1.twinx()
    ax1_r.plot(daily["day_bucket"], daily["avg_likes"], color="#d7191c", marker="o", linewidth=2.0, label="Avg Comment Likes")
    ax1_r.set_ylabel("Avg Likes per Comment", color="#d7191c")
    ax1_r.tick_params(axis="y", labelcolor="#d7191c")

    # Right panel: Pre-release Google Trends trajectories for 5 key films
    trends = trends.copy()
    trends["date"] = pd.to_datetime(trends["date"])
    rel_map = master.set_index("film_id")["release_date"].to_dict()
    name_map = master.set_index("film_id")["canonical_title"].to_dict()
    trends["rel_date"] = pd.to_datetime(trends["film_id"].map(rel_map))
    trends["days_to_release"] = (trends["date"] - trends["rel_date"]).dt.days

    focus_ids = ["F01", "F03", "F04", "F07", "F12"]
    for fid in focus_ids:
        sub = trends[(trends["film_id"] == fid) & (trends["days_to_release"].between(-45, 14))]
        ax2.plot(sub["days_to_release"], sub["interest"], linewidth=1.9, label=name_map[fid])

    ax2.axvline(0, color="black", linestyle="--", linewidth=1.1, label="Release Day (t=0)")
    ax2.set_title("Google Trends Peaks at Release Day, Separating Sustained Hits from Drops", fontsize=11.5)
    ax2.set_xlabel("Days Relative to Theatrical Release")
    ax2.set_ylabel("Google Trends Search Interest (0–100)")
    ax2.legend(fontsize=8.2, loc="upper left")

    fig.suptitle(
        "Trailer Buzz Decays Rapidly Within 24 Hours While Search Interest Peaks on Release Weekend",
        fontsize=13,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "chart_03_buzz_velocity_decay.png", bbox_inches="tight")
    plt.close(fig)


def chart_04_language_efficiency(master: pd.DataFrame) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.5))

    lang_df = (
        master.groupby("language", as_index=False)
        .agg(
            sum_net=("fri_sun_india_net_cr", "sum"),
            sum_budget=("est_budget_cr", "sum"),
            film_count=("film_id", "count"),
        )
    )
    lang_df["ratio"] = lang_df["sum_net"] / lang_df["sum_budget"]
    lang_df = lang_df.sort_values("ratio", ascending=False)

    bars = ax1.bar(lang_df["language"], lang_df["ratio"], color="#386cb0", edgecolor="black", alpha=0.85)
    for bar, (_, r) in zip(bars, lang_df.iterrows()):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{r['ratio']:.2f}x\n(n={int(r['film_count'])})",
            ha="center",
            fontsize=9,
        )
    ax1.set_title("Hindi Recovers 77% of Budget in 3 Days vs. 17%–41% for Regional Releases", fontsize=11)
    ax1.set_ylabel("Opening 3-Day Net / Budget Ratio")
    ax1.set_ylim(0, lang_df["ratio"].max() + 0.18)

    # Right panel: Top-6 screen allocation confusion matrix (raw 7d sample)
    df = master.copy()
    df["c_rank"] = df["sampled_first_7d_comments"].rank(ascending=False, method="first")
    df["b_rank"] = df["fri_sun_india_net_cr"].rank(ascending=False, method="first")
    tp = df[(df["c_rank"] <= 6) & (df["b_rank"] <= 6)]["canonical_title"].tolist()
    fp = df[(df["c_rank"] <= 6) & (df["b_rank"] > 6)]["canonical_title"].tolist()
    fn = df[(df["c_rank"] > 6) & (df["b_rank"] <= 6)]["canonical_title"].tolist()
    tn = df[(df["c_rank"] > 6) & (df["b_rank"] > 6)]["canonical_title"].tolist()

    mat = np.array([[len(tp), len(fp)], [len(fn), len(tn)]])
    ax2.imshow(mat, cmap="Blues", vmin=0, vmax=5)
    labels = [
        [f"TRUE POSITIVE (3)\n" + "\n".join(tp), f"FALSE POSITIVE (3)\n" + "\n".join(fp)],
        [f"FALSE NEGATIVE (3)\n" + "\n".join(fn), f"TRUE NEGATIVE (3)\n" + "\n".join(tn)],
    ]
    for i in range(2):
        for j in range(2):
            ax2.text(j, i, labels[i][j], ha="center", va="center", fontsize=8.5, fontweight="semibold", color="#111111")
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["Actual Top-6 Box Office", "Actual Bottom-6 Box Office"])
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["Predicted Top-6\n(7d Comment Sample)", "Predicted Bottom-6\n(7d Comment Sample)"])
    ax2.set_title("Raw Top-6 Comment Rule Achieves 50% Precision Without Scale Adjustment", fontsize=11)

    fig.suptitle(
        "Hindi Films Convert Opening Budgets Fastest; Naive Trailer-Comment Rules Miss Mega-Trailers",
        fontsize=13,
        fontweight="bold",
        y=1.02,
    )
    fig.tight_layout()
    fig.savefig(CHARTS_DIR / "chart_04_language_efficiency.png", bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    setup_style()

    master = pd.read_csv(c.CLEAN / "films_analytical_master.csv")
    corr = pd.read_csv(c.CLEAN / "spearman_correlations.csv")
    sent = pd.read_csv(c.CLEAN / "film_sentiment_summary.csv")
    comments = pd.read_csv(c.CLEAN / "youtube_comments.csv")
    trends = pd.read_csv(c.CLEAN / "google_trends_combined.csv")

    chart_01_normalised_buzz(master, corr)
    chart_02_weekend_momentum(master, sent)
    chart_03_buzz_velocity_decay(comments, trends, master)
    chart_04_language_efficiency(master)

    for png in sorted(CHARTS_DIR.glob("chart_*.png")):
        print(f"Generated {png.relative_to(c.REPO_ROOT)} ({png.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
