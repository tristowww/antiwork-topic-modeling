"""Aggregate a reviewed BERTopic cluster map into provisional theme trends.

The codebook is intentionally external to the model output. This makes the
human decision to retain, merge, exclude, or revisit a cluster inspectable and
lets the same document assignments support revised theme maps without a refit.

Usage:
    python -m src.theme_trends --out-dir outputs/v2_clean_min25
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


def _load(out_dir: Path, codebook_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    docs = pd.read_csv(out_dir / "bertopic_full_document_topics.csv")
    codebook = pd.read_csv(codebook_path)
    required = {"topic", "candidate_theme", "candidate_subtheme", "decision", "confidence"}
    missing = required - set(codebook.columns)
    if missing:
        raise ValueError(f"Codebook missing columns: {sorted(missing)}")
    if codebook["topic"].duplicated().any():
        raise ValueError("Codebook must contain at most one row per BERTopic topic.")
    docs["topic"] = docs["topic"].astype(int)
    docs["created_at"] = pd.to_datetime(docs["created_utc"], unit="s", utc=True)
    docs["month"] = docs["created_at"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    return docs, codebook


def build_theme_outputs(out_dir: Path, codebook_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    docs, codebook = _load(out_dir, codebook_path)
    included = codebook[codebook["decision"].eq("include")].copy()
    mapped = docs.merge(included, on="topic", how="inner", validate="many_to_one")
    monthly_totals = docs.groupby("month", as_index=False).size().rename(columns={"size": "total_posts"})
    mapped_totals = mapped.groupby("month", as_index=False).size().rename(columns={"size": "mapped_posts"})
    themes = included[["candidate_theme"]].drop_duplicates().sort_values("candidate_theme")
    grid = monthly_totals[["month"]].merge(themes, how="cross")
    counts = mapped.groupby(["month", "candidate_theme"], as_index=False).size().rename(columns={"size": "post_count"})
    monthly = grid.merge(counts, on=["month", "candidate_theme"], how="left").merge(monthly_totals, on="month", how="left")
    monthly = monthly.merge(mapped_totals, on="month", how="left")
    monthly[["post_count", "mapped_posts"]] = monthly[["post_count", "mapped_posts"]].fillna(0).astype(int)
    monthly["share_all_posts"] = monthly["post_count"] / monthly["total_posts"]
    monthly["share_mapped_posts"] = monthly["post_count"] / monthly["mapped_posts"].where(monthly["mapped_posts"] > 0)
    monthly["three_month_share_all_posts"] = monthly.groupby("candidate_theme")["share_all_posts"].transform(
        lambda values: values.rolling(3, min_periods=1, center=True).mean()
    )

    summary = mapped.groupby("candidate_theme", as_index=False).agg(
        mapped_posts=("id", "size"),
        candidate_clusters=("topic", "nunique"),
        first_month=("month", "min"),
        last_month=("month", "max"),
    )
    peak = monthly.loc[monthly.groupby("candidate_theme")["share_all_posts"].idxmax(), ["candidate_theme", "month", "share_all_posts"]]
    peak = peak.rename(columns={"month": "peak_month", "share_all_posts": "peak_share_all_posts"})
    summary = summary.merge(peak, on="candidate_theme", how="left")
    summary["share_all_posts"] = summary["mapped_posts"] / len(docs)
    summary["share_mapped_posts"] = summary["mapped_posts"] / len(mapped)
    for column in ("first_month", "last_month", "peak_month"):
        summary[column] = pd.to_datetime(summary[column]).dt.strftime("%Y-%m")
    summary = summary.sort_values("mapped_posts", ascending=False).reset_index(drop=True)

    window = mapped.groupby(["rolling_window", "candidate_theme"], as_index=False).size().rename(columns={"size": "post_count"})
    window_totals = docs.groupby("rolling_window", as_index=False).size().rename(columns={"size": "total_posts"})
    window_mapped = mapped.groupby("rolling_window", as_index=False).size().rename(columns={"size": "mapped_posts"})
    window_grid = window_totals[["rolling_window"]].merge(themes, how="cross")
    window = window_grid.merge(window, on=["rolling_window", "candidate_theme"], how="left")
    window = window.merge(window_totals, on="rolling_window", how="left").merge(window_mapped, on="rolling_window", how="left")
    window[["post_count", "mapped_posts"]] = window[["post_count", "mapped_posts"]].fillna(0).astype(int)
    window["share_all_posts"] = window["post_count"] / window["total_posts"]
    window["share_mapped_posts"] = window["post_count"] / window["mapped_posts"].where(window["mapped_posts"] > 0)
    return monthly, summary, window


def _plot_monthly(monthly: pd.DataFrame, path: Path) -> None:
    theme_order = monthly.groupby("candidate_theme")["post_count"].sum().sort_values(ascending=False).index.tolist()
    ncols = 3
    nrows = (len(theme_order) + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(14, 3.2 * nrows), sharex=True, sharey=True)
    axes = axes.flatten()
    fig.suptitle("Provisional theme prevalence from reviewed v2 clusters", x=0.06, y=0.99, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.06, 0.955, "Three-month rolling share of all filtered posts. The codebook covers selected high-confidence clusters, not the full corpus.", ha="left", color="#475569")
    maximum = float((monthly["three_month_share_all_posts"] * 100).max())
    y_limit = max(1.0, (int(maximum / 1.0) + 2) * 1.0)
    for axis, theme in zip(axes, theme_order):
        series = monthly[monthly["candidate_theme"].eq(theme)]
        axis.plot(series["month"], series["three_month_share_all_posts"] * 100, color="#1F4E79", linewidth=2)
        axis.fill_between(series["month"], 0, series["three_month_share_all_posts"] * 100, color="#D9E6F2", alpha=0.75)
        axis.set_title(theme, loc="left", fontsize=10, fontweight="bold")
        axis.set_ylim(0, y_limit)
        axis.yaxis.set_major_formatter("{x:.0f}%")
        axis.grid(axis="y", alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
    for axis in axes[len(theme_order):]:
        axis.set_visible(False)
    for axis in axes[max(0, len(axes) - ncols):]:
        if axis.get_visible():
            axis.xaxis.set_major_locator(mdates.MonthLocator(interval=12))
            axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.text(0.06, 0.01, "Denominator: all filtered posts per month. Exploratory 27-cluster codebook covers 19.0% of the corpus.", ha="left", color="#475569", fontsize=9)
    fig.tight_layout(rect=[0, 0.035, 1, 0.90])
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_windows(window: pd.DataFrame, path: Path) -> None:
    themes = window.groupby("candidate_theme")["post_count"].sum().sort_values(ascending=True).index.tolist()
    order = ["Y1_2021-22", "Y2_2022-23", "Y3_2023-24", "Y4_2024-25"]
    palette = ["#1F4E79", "#4E79A7", "#A0B8CF", "#B35A27"]
    fig, ax = plt.subplots(figsize=(12, 6.5))
    width = 0.18
    positions = range(len(themes))
    for i, (label, color) in enumerate(zip(order, palette)):
        values = window[window["rolling_window"].eq(label)].set_index("candidate_theme").reindex(themes)["share_all_posts"] * 100
        ax.bar([position + (i - 1.5) * width for position in positions], values, width=width, label=label.replace("_", " "), color=color)
    fig.suptitle("Provisional theme prevalence by rolling window", x=0.06, y=0.99, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.06, 0.945, "Share of all filtered posts. Exploratory 27-cluster map excludes generic, deleted, and community-meta clusters.", ha="left", color="#475569")
    ax.set_ylabel("Share of filtered posts")
    ax.yaxis.set_major_formatter("{x:.0f}%")
    ax.set_xticks(list(positions), themes, rotation=25, ha="right")
    ax.grid(axis="y", alpha=0.2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=2, loc="upper right")
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build provisional theme trends from a reviewed BERTopic codebook")
    parser.add_argument("--out-dir", default="outputs/v2_clean_min25")
    parser.add_argument("--codebook", default="planning/CANDIDATE_THEME_CODEBOOK.csv")
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    analysis_dir = out_dir / "analysis"
    figure_dir = out_dir / "figures"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    monthly, summary, window = build_theme_outputs(out_dir, Path(args.codebook))
    monthly.to_csv(analysis_dir / "candidate_theme_monthly_prevalence.csv", index=False)
    summary.to_csv(analysis_dir / "candidate_theme_summary.csv", index=False)
    window.to_csv(analysis_dir / "candidate_theme_window_prevalence.csv", index=False)
    _plot_monthly(monthly, figure_dir / "candidate_theme_monthly_prevalence.png")
    _plot_windows(window, figure_dir / "candidate_theme_rolling_window_prevalence.png")
    print(f"wrote {analysis_dir / 'candidate_theme_monthly_prevalence.csv'}")
    print(f"wrote {analysis_dir / 'candidate_theme_summary.csv'}")
    print(f"wrote {analysis_dir / 'candidate_theme_window_prevalence.csv'}")
    print(f"wrote {figure_dir / 'candidate_theme_monthly_prevalence.png'}")
    print(f"wrote {figure_dir / 'candidate_theme_rolling_window_prevalence.png'}")


if __name__ == "__main__":
    main()
