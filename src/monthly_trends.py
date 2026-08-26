"""Monthly topic prevalence figures from BERTopic document assignments.

This is the first Phase 5 trend-line pass. It uses the full-corpus BERTopic
model's document-topic assignments so topic IDs are stable across all 48
months. Per-window topic IDs are useful for alignment, but they are not stable
enough for a continuous monthly trend chart.

Usage:
    python -m src.monthly_trends --out-dir outputs/v2_clean_min25 --top-n 20
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _topic_label(row: pd.Series, max_terms: int = 4) -> str:
    terms = str(row["top_terms"]).split()[:max_terms]
    return f"T{int(row['topic'])}: {' '.join(terms)}"


def build_monthly_prevalence(out_dir: Path, *, label: str, top_n: int) -> pd.DataFrame:
    docs_path = out_dir / f"bertopic_{label}_document_topics.csv"
    topics_path = out_dir / f"bertopic_{label}_topics.csv"
    if not docs_path.exists():
        raise FileNotFoundError(docs_path)
    if not topics_path.exists():
        raise FileNotFoundError(topics_path)

    docs = pd.read_csv(docs_path)
    topics = pd.read_csv(topics_path)

    docs["created_at"] = pd.to_datetime(docs["created_utc"], unit="s", utc=True)
    docs["month"] = docs["created_at"].dt.strftime("%Y-%m")
    docs["topic"] = docs["topic"].astype(int)

    inlier_docs = docs[docs["topic"] != -1].copy()
    top_topics = (
        inlier_docs["topic"]
        .value_counts()
        .head(top_n)
        .rename_axis("topic")
        .reset_index(name="topic_total")
    )

    topic_lookup = topics[["topic", "size", "top_terms"]].copy()
    topic_lookup["topic"] = topic_lookup["topic"].astype(int)
    topic_lookup = topic_lookup.merge(top_topics, on="topic", how="inner")
    topic_lookup["label"] = topic_lookup.apply(_topic_label, axis=1)

    monthly_totals = docs.groupby("month").size().rename("total_posts").reset_index()
    monthly_topic_counts = (
        inlier_docs[inlier_docs["topic"].isin(topic_lookup["topic"])]
        .groupby(["month", "topic"])
        .size()
        .rename("count")
        .reset_index()
    )

    # Fill missing month/topic combinations with zero so plotted lines are continuous.
    months = pd.DataFrame({"month": sorted(docs["month"].unique())})
    grid = months.merge(topic_lookup[["topic"]], how="cross")
    trend = (
        grid.merge(monthly_topic_counts, on=["month", "topic"], how="left")
        .merge(monthly_totals, on="month", how="left")
        .merge(topic_lookup[["topic", "label", "top_terms", "topic_total"]], on="topic", how="left")
    )
    trend["count"] = trend["count"].fillna(0).astype(int)
    trend["prevalence"] = trend["count"] / trend["total_posts"]
    return trend.sort_values(["month", "topic"]).reset_index(drop=True)


def plot_monthly_prevalence(trend: pd.DataFrame, out_path: Path, *, top_n: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 7))

    labels = (
        trend[["topic", "label", "topic_total"]]
        .drop_duplicates()
        .sort_values("topic_total", ascending=False)
    )
    cmap = plt.get_cmap("tab20")

    for i, row in enumerate(labels.itertuples(index=False)):
        series = trend[trend["topic"] == row.topic]
        ax.plot(
            series["month"],
            series["prevalence"] * 100,
            linewidth=1.6,
            alpha=0.9,
            color=cmap(i % 20),
            label=row.label,
        )

    ax.set_title(f"Monthly prevalence of top {top_n} full-corpus BERTopic topics")
    ax.set_xlabel("Month")
    ax.set_ylabel("% of filtered posts")
    ax.grid(True, alpha=0.25)
    ax.tick_params(axis="x", rotation=60)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monthly BERTopic prevalence trends")
    parser.add_argument("--out-dir", default="outputs", help="Directory containing BERTopic CSV outputs")
    parser.add_argument("--label", default="full", help="BERTopic output label, usually 'full'")
    parser.add_argument("--top-n", type=int, default=20, help="Number of non-outlier topics to plot")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    trend = build_monthly_prevalence(out_dir, label=args.label, top_n=args.top_n)

    csv_path = out_dir / f"monthly_topic_prevalence_top{args.top_n}_{args.label}.csv"
    trend.to_csv(csv_path, index=False)

    fig_path = out_dir / "figures" / f"monthly_topic_prevalence_top{args.top_n}_{args.label}.png"
    plot_monthly_prevalence(trend, fig_path, top_n=args.top_n)

    print(f"wrote {csv_path}")
    print(f"wrote {fig_path}")
    print("\nTop topic labels:")
    for row in (
        trend[["topic", "label", "topic_total"]]
        .drop_duplicates()
        .sort_values("topic_total", ascending=False)
        .itertuples(index=False)
    ):
        print(f"  {row.label} ({int(row.topic_total):,} docs)")


if __name__ == "__main__":
    main()
