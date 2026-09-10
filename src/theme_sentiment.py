"""Aggregate fixed whole-post sentiment estimates by reviewed theme and time.

This module joins the local per-post outputs from ``src.sentiment`` to the
full-corpus BERTopic assignments and the documented candidate-theme codebook.
It never refits either model. Theme sentiment therefore describes the polarity
of posts assigned to an included candidate-theme cluster, while theme
prevalence remains a separate all-filtered-post measure.

Usage:
    python -m src.theme_sentiment
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


DEFAULT_SENTIMENT_DIR = "outputs/sentiment/twitter_roberta_base_sentiment_latest"
DEFAULT_TOPIC_DIR = "outputs/v2_clean_min25"
DEFAULT_CODEBOOK = "planning/CANDIDATE_THEME_CODEBOOK.csv"
THEME_ORDER = [
    "Health safety and attendance",
    "Scheduling hours and time off",
    "Compensation and pay rights",
    "Career precarity and exit",
    "Workplace authority and interpersonal conflict",
    "Recruitment and labor market",
    "Work arrangements and control",
    "Service work and tips",
    "Collective worker power and rights",
]
GREAT_RESIGNATION_START = pd.Timestamp("2021-03-01")
GREAT_RESIGNATION_END = pd.Timestamp("2022-03-01")


def load_mapped_sentiment(sentiment_dir: Path, topic_dir: Path, codebook_path: Path) -> pd.DataFrame:
    labels = pd.read_parquet(sentiment_dir / "sentiment_post_labels.parquet")
    docs = pd.read_csv(topic_dir / "bertopic_full_document_topics.csv")
    codebook = pd.read_csv(codebook_path)
    required_labels = {"id", "p_negative", "p_neutral", "p_positive", "sentiment_label", "max_probability"}
    required_codebook = {"topic", "candidate_theme", "decision"}
    if missing := required_labels - set(labels.columns):
        raise ValueError(f"Sentiment labels missing columns: {sorted(missing)}")
    if missing := required_codebook - set(codebook.columns):
        raise ValueError(f"Codebook missing columns: {sorted(missing)}")
    if labels["id"].duplicated().any() or docs["id"].duplicated().any():
        raise ValueError("Sentiment labels and document assignments must each have one row per post ID.")

    labels["id"] = labels["id"].astype(str)
    docs["id"] = docs["id"].astype(str)
    included = codebook.loc[codebook["decision"].eq("include"), ["topic", "candidate_theme"]].copy()
    included["topic"] = included["topic"].astype(int)
    docs["topic"] = docs["topic"].astype(int)
    # The sentiment output retains the frozen corpus timestamp and window labels.
    # Join only the BERTopic assignment to avoid duplicate metadata columns.
    merged = labels.merge(docs[["id", "topic"]], on="id", how="inner", validate="one_to_one")
    if len(merged) != len(labels):
        raise ValueError("Some sentiment labels could not be joined to a BERTopic document assignment.")
    mapped = merged.merge(included, on="topic", how="inner", validate="many_to_one")
    mapped["month"] = pd.to_datetime(mapped["created_utc"], unit="s", utc=True).dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    return mapped


def aggregate(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    result = frame.groupby(group_columns, as_index=False).agg(
        posts=("id", "size"),
        negative_mean_probability=("p_negative", "mean"),
        neutral_mean_probability=("p_neutral", "mean"),
        positive_mean_probability=("p_positive", "mean"),
        hard_negative_share=("sentiment_label", lambda values: values.eq("negative").mean()),
        hard_neutral_share=("sentiment_label", lambda values: values.eq("neutral").mean()),
        hard_positive_share=("sentiment_label", lambda values: values.eq("positive").mean()),
        mean_max_probability=("max_probability", "mean"),
    )
    return result


def plot_monthly(monthly: pd.DataFrame, path: Path) -> None:
    present = [theme for theme in THEME_ORDER if theme in set(monthly["candidate_theme"])]
    fig, axes = plt.subplots(3, 3, figsize=(12, 9), sharex=True, sharey=True)
    for axis, theme in zip(axes.flat, present):
        series = monthly.loc[monthly["candidate_theme"].eq(theme)].sort_values("month")
        smoothed = series["negative_mean_probability"].rolling(3, min_periods=1, center=True).mean()
        theme_n = int(series["posts"].sum())
        axis.axvspan(GREAT_RESIGNATION_START, GREAT_RESIGNATION_END, color="#E5C07B", alpha=0.24, zorder=0)
        axis.axvline(GREAT_RESIGNATION_END, color="#9A6A24", linestyle="--", linewidth=0.9, alpha=0.9, zorder=2)
        axis.plot(series["month"], smoothed * 100, color="#B35A27", linewidth=2.1)
        axis.scatter(series["month"], series["negative_mean_probability"] * 100, color="#B35A27", s=10, alpha=0.6)
        axis.set_title(f"{theme}\n(n={theme_n:,})", loc="left", fontsize=9.2, fontweight="bold")
        axis.set_ylim(0, 100)
        axis.yaxis.set_major_formatter("{x:.0f}%")
        axis.grid(axis="y", alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
    for axis in axes.flat[len(present):]:
        axis.set_visible(False)
    for axis in axes[-1, :]:
        axis.xaxis.set_major_locator(mdates.MonthLocator(interval=12))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle("Modeled negative-polarity probability within reviewed themes", x=0.06, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.06, 0.94, "Three-month rolling mean of post-level RoBERTa negative probability. Shading marks the Y1 Great Resignation window (Mar 2021-Feb 2022); dashed line marks March 2022. The thematic map covers 19.0% of the filtered corpus.", ha="left", color="#475569", fontsize=9)
    fig.text(0.06, 0.01, "This is model-based whole-post polarity, not human-validated or management-targeted sentiment. Theme prevalence is analyzed separately.", ha="left", color="#475569", fontsize=8.5)
    fig.tight_layout(rect=[0, 0.04, 1, 0.90])
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate whole-post RoBERTa sentiment by candidate theme and time.")
    parser.add_argument("--sentiment-dir", default=DEFAULT_SENTIMENT_DIR)
    parser.add_argument("--topic-dir", default=DEFAULT_TOPIC_DIR)
    parser.add_argument("--codebook", default=DEFAULT_CODEBOOK)
    parser.add_argument("--out-dir", help="Defaults to a theme subdirectory under --sentiment-dir.")
    args = parser.parse_args()

    sentiment_dir = Path(args.sentiment_dir)
    out_dir = Path(args.out_dir) if args.out_dir else sentiment_dir / "theme_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)
    mapped = load_mapped_sentiment(sentiment_dir, Path(args.topic_dir), Path(args.codebook))
    monthly = aggregate(mapped, ["month", "candidate_theme"])
    window = aggregate(mapped, ["rolling_window", "candidate_theme"])
    summary = aggregate(mapped, ["candidate_theme"]).sort_values("posts", ascending=False)
    monthly.to_csv(out_dir / "candidate_theme_sentiment_by_month.csv", index=False)
    window.to_csv(out_dir / "candidate_theme_sentiment_by_rolling_window.csv", index=False)
    summary.to_csv(out_dir / "candidate_theme_sentiment_summary.csv", index=False)
    plot_monthly(monthly, out_dir / "candidate_theme_negative_probability_by_month.png")
    sentiment_metadata = json.loads((sentiment_dir / "sentiment_summary.json").read_text(encoding="utf-8"))
    theme_metadata = {
        "interpretation": "Whole-post RoBERTa polarity estimates conditional on assignment to an included candidate-theme cluster; not theme prevalence, human-validated sentiment, or management-targeted sentiment.",
        "join": "One-to-one join from complete post-level sentiment labels to full-corpus BERTopic assignments, then many-to-one mapping to the documented included codebook clusters. Neither model was refit.",
        "mapped_posts": int(len(mapped)),
        "candidate_themes": int(mapped["candidate_theme"].nunique()),
        "sentiment_model": sentiment_metadata["model"],
        "source_sentiment_output": str(sentiment_dir),
    }
    (out_dir / "theme_sentiment_summary.json").write_text(json.dumps(theme_metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Mapped sentiment posts: {len(mapped):,}")
    print(f"Wrote {out_dir}")


if __name__ == "__main__":
    main()
