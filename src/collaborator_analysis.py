"""Build reviewable, collaborator-facing summaries from the v2 BERTopic run.

The v2 topic model is exploratory: it has substantial HDBSCAN outlier coverage,
so this module does not manufacture a single "theme" taxonomy. Instead it
exports a review packet, coverage diagnostics, and a small set of clearly
interpretable anchor clusters for discussion and human codebook development.

Usage:
    python -m src.collaborator_analysis --out-dir outputs/v2_clean_min25
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


@dataclass(frozen=True)
class AnchorTopic:
    topic: int
    label: str


# These are deliberately individual BERTopic clusters, not a final thematic
# codebook. Their labels make the review meeting concrete without overstating
# current semantic validity.
ANCHOR_TOPICS = (
    AnchorTopic(0, "Hiring and interviews"),
    AnchorTopic(2, "Pay raises and salary"),
    AnchorTopic(4, "COVID and illness"),
    AnchorTopic(6, "Remote and return-to-office"),
    AnchorTopic(9, "Resignation and notice"),
    AnchorTopic(10, "Scheduling and shifts"),
    AnchorTopic(11, "Paid time off"),
    AnchorTopic(14, "Unionization and strikes"),
)


def _excerpt(value: object, limit: int = 420) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else f"{text[: limit - 3].rstrip()}..."


def _load_inputs(out_dir: Path, preprocessed_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    docs = pd.read_csv(out_dir / "bertopic_full_document_topics.csv")
    topics = pd.read_csv(out_dir / "bertopic_full_topics.csv")
    posts = pd.read_parquet(preprocessed_path)

    if docs["id"].duplicated().any():
        raise ValueError("Document-topic assignments must have one row per post id.")
    if not docs["id"].isin(posts["id"]).all():
        raise ValueError("Document-topic assignments contain ids absent from the preprocessed corpus.")

    docs["created_at"] = pd.to_datetime(docs["created_utc"], unit="s", utc=True)
    docs["month"] = docs["created_at"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    docs["topic"] = docs["topic"].astype(int)
    return docs, topics, posts


def _coverage_table(docs: pd.DataFrame) -> pd.DataFrame:
    monthly = docs.assign(assigned=docs["topic"].ne(-1)).groupby("month", as_index=False).agg(
        total_posts=("id", "size"),
        assigned_posts=("assigned", "sum"),
    )
    monthly["outlier_posts"] = monthly["total_posts"] - monthly["assigned_posts"]
    monthly["assigned_rate"] = monthly["assigned_posts"] / monthly["total_posts"]
    monthly["outlier_rate"] = monthly["outlier_posts"] / monthly["total_posts"]
    return monthly.sort_values("month").reset_index(drop=True)


def _topic_overview(docs: pd.DataFrame, topics: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    inliers = docs[docs["topic"] != -1].copy()
    total_posts = len(docs)
    total_assigned = len(inliers)
    counts = inliers.groupby("topic", as_index=False).size().rename(columns={"size": "assigned_posts"})
    months = inliers.groupby("topic", as_index=False).agg(
        first_month=("month", "min"),
        last_month=("month", "max"),
    )
    by_month = inliers.groupby(["topic", "month"], as_index=False).size().rename(columns={"size": "post_count"})
    by_month = by_month.merge(coverage[["month", "total_posts", "assigned_posts"]], on="month", how="left")
    by_month["share_all_posts"] = by_month["post_count"] / by_month["total_posts"]
    by_month["share_assigned_posts"] = by_month["post_count"] / by_month["assigned_posts"]
    peak = by_month.loc[by_month.groupby("topic")["share_all_posts"].idxmax(), ["topic", "month", "share_all_posts"]]
    peak = peak.rename(columns={"month": "peak_month", "share_all_posts": "peak_share_all_posts"})

    overview = topics.merge(counts, on="topic", how="inner").merge(months, on="topic", how="left").merge(peak, on="topic", how="left")
    overview["share_all_posts"] = overview["assigned_posts"] / total_posts
    overview["share_assigned_posts"] = overview["assigned_posts"] / total_assigned
    overview = overview[[
        "topic", "name", "top_terms", "assigned_posts", "share_all_posts", "share_assigned_posts",
        "first_month", "last_month", "peak_month", "peak_share_all_posts",
    ]].sort_values("assigned_posts", ascending=False)
    for column in ("first_month", "last_month", "peak_month"):
        overview[column] = pd.to_datetime(overview[column]).dt.strftime("%Y-%m")
    return overview.reset_index(drop=True)


def _review_posts(docs: pd.DataFrame, posts: pd.DataFrame, topic_overview: pd.DataFrame, *, top_n: int, per_topic: int, seed: int) -> pd.DataFrame:
    top_topics = topic_overview.head(top_n)[["topic", "assigned_posts", "top_terms"]].copy()
    source_posts = posts[["id", "body"]].copy()
    review = docs.merge(source_posts, on="id", how="left").merge(top_topics, on="topic", how="inner")
    selected = []
    for topic, group in review.groupby("topic", sort=False):
        stable_key = pd.util.hash_pandas_object(group["id"].astype(str) + f"|{topic}|{seed}", index=False)
        group = group.assign(_stable_key=stable_key).sort_values("_stable_key").head(per_topic)
        selected.append(group)
    result = pd.concat(selected, ignore_index=True)
    result["month"] = result["month"].dt.strftime("%Y-%m")
    result["body_excerpt"] = result["body"].map(_excerpt)
    result["title"] = result["title"].map(_excerpt)
    return result[["topic", "assigned_posts", "top_terms", "id", "month", "title", "body_excerpt"]].sort_values(["assigned_posts", "topic"], ascending=[False, True])


def _anchor_trends(docs: pd.DataFrame, coverage: pd.DataFrame) -> pd.DataFrame:
    available = [anchor for anchor in ANCHOR_TOPICS if anchor.topic in set(docs["topic"])]
    months = coverage[["month", "total_posts", "assigned_posts"]].copy()
    records = []
    for anchor in available:
        counts = docs.loc[docs["topic"] == anchor.topic].groupby("month").size().rename("post_count").reset_index()
        series = months.merge(counts, on="month", how="left")
        series["post_count"] = series["post_count"].fillna(0).astype(int)
        series["topic"] = anchor.topic
        series["label"] = anchor.label
        series["share_all_posts"] = series["post_count"] / series["total_posts"]
        series["share_assigned_posts"] = series["post_count"] / series["assigned_posts"]
        series["three_month_share_all_posts"] = series["share_all_posts"].rolling(3, min_periods=1, center=True).mean()
        records.append(series)
    return pd.concat(records, ignore_index=True)


def _plot_coverage(coverage: pd.DataFrame, path: Path) -> None:
    fig, (ax_volume, ax_coverage) = plt.subplots(2, 1, figsize=(12, 7), sharex=True, height_ratios=[1, 1.25])
    fig.suptitle("Full-corpus BERTopic assignment coverage", x=0.06, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.06, 0.93, "97,254 filtered r/antiwork posts, March 2021 through February 2025", ha="left", color="#475569")

    ax_volume.bar(coverage["month"], coverage["total_posts"], width=20, color="#8FA6B8", edgecolor="none")
    ax_volume.axvspan(pd.Timestamp("2021-03-01"), pd.Timestamp("2022-03-01"), color="#E5C07B", alpha=0.24, zorder=0)
    ax_volume.axvline(pd.Timestamp("2022-03-01"), color="#9A6A24", linestyle="--", linewidth=1.0, alpha=0.9)
    ax_volume.set_ylabel("Posts")
    ax_volume.grid(axis="y", alpha=0.2)
    ax_volume.spines[["top", "right"]].set_visible(False)

    ax_coverage.plot(coverage["month"], coverage["assigned_rate"] * 100, color="#1F4E79", linewidth=2.4, label="Assigned to a topic")
    ax_coverage.plot(coverage["month"], coverage["outlier_rate"] * 100, color="#B35A27", linewidth=2.0, linestyle="--", label="HDBSCAN outlier")
    ax_coverage.axvspan(pd.Timestamp("2021-03-01"), pd.Timestamp("2022-03-01"), color="#E5C07B", alpha=0.24, zorder=0)
    ax_coverage.axvline(pd.Timestamp("2022-03-01"), color="#9A6A24", linestyle="--", linewidth=1.0, alpha=0.9)
    ax_coverage.set_ylim(0, 100)
    ax_coverage.set_ylabel("Share of monthly posts")
    ax_coverage.yaxis.set_major_formatter("{x:.0f}%")
    ax_coverage.grid(axis="y", alpha=0.2)
    ax_coverage.legend(frameon=False, ncol=2, loc="upper center")
    ax_coverage.spines[["top", "right"]].set_visible(False)
    ax_coverage.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    ax_coverage.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    fig.text(0.06, 0.01, "Shading marks the Y1 Great Resignation window (Mar 2021-Feb 2022); dashed line marks March 2022. Interpret raw topic trends alongside this changing assignment rate; outliers are not a substantive category.", ha="left", color="#475569", fontsize=9)
    fig.tight_layout(rect=[0, 0.04, 1, 0.91])
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_anchor_topics(trends: pd.DataFrame, path: Path) -> None:
    labels = trends[["topic", "label"]].drop_duplicates().sort_values("topic")
    fig, axes = plt.subplots(4, 2, figsize=(12, 11), sharex=True, sharey=True)
    fig.suptitle("Preliminary monthly prevalence of selected v2 anchor clusters", x=0.06, y=0.985, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.06, 0.94, "Three-month rolling share of all filtered posts. These are model clusters, not final human-coded themes.", ha="left", color="#475569")
    color = "#1F4E79"
    maximum = float((trends["three_month_share_all_posts"] * 100).max())
    y_limit = max(1.0, (int(maximum / 0.5) + 2) * 0.5)
    for axis, row in zip(axes.flat, labels.itertuples(index=False)):
        series = trends[trends["topic"] == row.topic]
        axis.plot(series["month"], series["three_month_share_all_posts"] * 100, color=color, linewidth=2)
        axis.fill_between(series["month"], 0, series["three_month_share_all_posts"] * 100, color="#D9E6F2", alpha=0.75)
        axis.set_title(f"{row.label} (topic {row.topic})", loc="left", fontsize=10, fontweight="bold")
        axis.grid(axis="y", alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
        axis.set_ylim(0, y_limit)
        axis.yaxis.set_major_formatter("{x:.0f}%")
    for axis in axes[-1, :]:
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=12))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.text(0.06, 0.01, "Denominator: all filtered posts per month. Coverage of the full topic model varies materially by month.", ha="left", color="#475569", fontsize=9)
    fig.tight_layout(rect=[0, 0.035, 1, 0.89])
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def build_outputs(
    out_dir: Path,
    preprocessed_path: Path,
    *,
    top_n: int,
    per_topic: int,
    seed: int,
    review_filename: str = "topic_review_posts.csv",
) -> None:
    docs, topics, posts = _load_inputs(out_dir, preprocessed_path)
    analysis_dir = out_dir / "analysis"
    figure_dir = out_dir / "figures"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    coverage = _coverage_table(docs)
    overview = _topic_overview(docs, topics, coverage)
    review_posts = _review_posts(docs, posts, overview, top_n=top_n, per_topic=per_topic, seed=seed)
    anchors = _anchor_trends(docs, coverage)

    coverage.to_csv(analysis_dir / "monthly_assignment_coverage.csv", index=False)
    overview.to_csv(analysis_dir / "topic_overview.csv", index=False)
    review_path = analysis_dir / review_filename
    review_posts.to_csv(review_path, index=False)
    anchors.to_csv(analysis_dir / "monthly_anchor_topic_prevalence.csv", index=False)
    _plot_coverage(coverage, figure_dir / "monthly_assignment_coverage.png")
    _plot_anchor_topics(anchors, figure_dir / "monthly_anchor_topic_prevalence.png")

    metrics = {
        "corpus_posts": int(len(docs)),
        "months": int(coverage["month"].nunique()),
        "non_outlier_topics": int(len(overview)),
        "assigned_posts": int(docs["topic"].ne(-1).sum()),
        "outlier_posts": int(docs["topic"].eq(-1).sum()),
        "assigned_rate": round(float(docs["topic"].ne(-1).mean()), 6),
        "outlier_rate": round(float(docs["topic"].eq(-1).mean()), 6),
        "assignment_rate_min": round(float(coverage["assigned_rate"].min()), 6),
        "assignment_rate_max": round(float(coverage["assigned_rate"].max()), 6),
        "review_topics": int(min(top_n, len(overview))),
        "review_posts": int(len(review_posts)),
    }
    (analysis_dir / "analysis_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    print(f"wrote {analysis_dir / 'analysis_metrics.json'}")
    print(f"wrote {analysis_dir / 'topic_overview.csv'}")
    print(f"wrote {review_path}")
    print(f"wrote {analysis_dir / 'monthly_assignment_coverage.csv'}")
    print(f"wrote {analysis_dir / 'monthly_anchor_topic_prevalence.csv'}")
    print(f"wrote {figure_dir / 'monthly_assignment_coverage.png'}")
    print(f"wrote {figure_dir / 'monthly_anchor_topic_prevalence.png'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create collaborator-facing v2 BERTopic review outputs")
    parser.add_argument("--out-dir", default="outputs/v2_clean_min25")
    parser.add_argument("--preprocessed", default="data/processed/posts_preprocessed.parquet")
    parser.add_argument("--top-n", type=int, default=30, help="Number of largest non-outlier topics to sample for review")
    parser.add_argument("--per-topic", type=int, default=4, help="Deterministic review posts per sampled topic")
    parser.add_argument("--seed", type=int, default=29)
    parser.add_argument("--review-filename", default="topic_review_posts.csv", help="CSV name for the sampled topic-review output")
    args = parser.parse_args()
    build_outputs(
        Path(args.out_dir),
        Path(args.preprocessed),
        top_n=args.top_n,
        per_topic=args.per_topic,
        seed=args.seed,
        review_filename=args.review_filename,
    )


if __name__ == "__main__":
    main()
