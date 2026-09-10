"""Aggregate a reviewed BERTopic cluster map into provisional theme trends.

The codebook is intentionally external to the model output. This makes the
human decision to retain, merge, exclude, or revisit a cluster inspectable and
lets the same document assignments support revised theme maps without a refit.

Usage:
    python -m src.theme_trends --out-dir outputs/v2_clean_min25
"""
from __future__ import annotations

import argparse
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


GREAT_RESIGNATION_START = pd.Timestamp("2021-03-01")
GREAT_RESIGNATION_END = pd.Timestamp("2022-03-01")


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
    fig.text(0.06, 0.955, "Three-month rolling share of all filtered posts. Shading marks the Y1 Great Resignation window (Mar 2021-Feb 2022); dashed line marks March 2022.", ha="left", color="#475569")
    maximum = float((monthly["three_month_share_all_posts"] * 100).max())
    y_limit = max(1.0, (int(maximum / 1.0) + 2) * 1.0)
    for axis, theme in zip(axes, theme_order):
        series = monthly[monthly["candidate_theme"].eq(theme)]
        axis.axvspan(GREAT_RESIGNATION_START, GREAT_RESIGNATION_END, color="#E5C07B", alpha=0.24, zorder=0)
        axis.axvline(GREAT_RESIGNATION_END, color="#9A6A24", linestyle="--", linewidth=0.9, alpha=0.9, zorder=2)
        axis.plot(series["month"], series["three_month_share_all_posts"] * 100, color="#1F4E79", linewidth=2)
        axis.fill_between(series["month"], 0, series["three_month_share_all_posts"] * 100, color="#D9E6F2", alpha=0.75)
        total_n = int(series["post_count"].sum())
        axis.set_title(f"{theme}\n(n={total_n:,} across all windows)", loc="left", fontsize=9.2, fontweight="bold")
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
    fig.text(0.06, 0.01, "Percentages divide theme posts by all filtered posts per month; title n values are theme counts across all windows. Exploratory 27-cluster codebook covers 19.0% of the corpus.", ha="left", color="#475569", fontsize=8.5)
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
        subset = window[window["rolling_window"].eq(label)].set_index("candidate_theme").reindex(themes)
        values = subset["share_all_posts"] * 100
        total_n = int(subset["total_posts"].iloc[0])
        ax.bar([position + (i - 1.5) * width for position in positions], values, width=width, label=f"{label.replace('_', ' ')} (n={total_n:,})", color=color)
    fig.suptitle("Provisional theme prevalence by rolling window", x=0.06, y=0.99, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.06, 0.945, "Share of all filtered posts; rolling-window denominators are shown in the legend. Exploratory 27-cluster map excludes generic, deleted, and community-meta clusters.", ha="left", color="#475569")
    ax.set_ylabel("Share of filtered posts")
    ax.yaxis.set_major_formatter("{x:.0f}%")
    ax.set_xticks(list(positions), themes, rotation=25, ha="right")
    ax.grid(axis="y", alpha=0.2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, ncol=2, loc="upper right")
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_y1_y4_comparison(window: pd.DataFrame, path: Path) -> None:
    y1 = window[window["rolling_window"].eq("Y1_2021-22")].set_index("candidate_theme")
    y4 = window[window["rolling_window"].eq("Y4_2024-25")].set_index("candidate_theme")
    comparison = y1[["share_all_posts", "post_count", "total_posts"]].join(
        y4[["share_all_posts", "post_count", "total_posts"]], lsuffix="_y1", rsuffix="_y4"
    )
    comparison["difference_pp"] = (comparison["share_all_posts_y4"] - comparison["share_all_posts_y1"]) * 100
    comparison = comparison.sort_values("difference_pp")
    fig, ax = plt.subplots(figsize=(10.8, 6.2))
    y_positions = range(len(comparison))
    for y, (_, row) in zip(y_positions, comparison.iterrows()):
        ax.plot([row["share_all_posts_y1"] * 100, row["share_all_posts_y4"] * 100], [y, y], color="#9AA9B5", linewidth=1.5, zorder=1)
    ax.scatter(comparison["share_all_posts_y1"] * 100, y_positions, color="#1F4E79", s=46, label=f"Y1 Great Resignation period (n={int(comparison['total_posts_y1'].iloc[0]):,})", zorder=2)
    ax.scatter(comparison["share_all_posts_y4"] * 100, y_positions, color="#B35A27", s=46, label=f"Y4 most recent period (n={int(comparison['total_posts_y4'].iloc[0]):,})", zorder=2)
    ax.set_yticks(list(y_positions), comparison.index)
    ax.xaxis.set_major_formatter("{x:.0f}%")
    ax.set_xlabel("Share of all filtered posts")
    ax.grid(axis="x", alpha=0.2)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.suptitle("Candidate-theme prevalence in Y1 and Y4", x=0.08, y=0.98, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.08, 0.935, "Exploratory comparison of the user-defined Great Resignation period (Mar 2021-Feb 2022) with Mar 2024-Feb 2025. Lines show percentage-point change, not causal effects.", ha="left", color="#475569", fontsize=9)
    for y, (_, row) in zip(y_positions, comparison.iterrows()):
        ax.text(max(row["share_all_posts_y1"], row["share_all_posts_y4"]) * 100 + 0.08, y, f"{row['difference_pp']:+.2f} pp", va="center", fontsize=8.4, color="#475569")
    fig.legend(frameon=False, loc="upper right", bbox_to_anchor=(0.96, 0.89), ncol=2, fontsize=8.8)
    fig.tight_layout(rect=[0, 0, 1, 0.79])
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _build_top_cluster_monthly(out_dir: Path, codebook_path: Path, top_n: int = 10) -> pd.DataFrame:
    docs, codebook = _load(out_dir, codebook_path)
    included = codebook[codebook["decision"].eq("include")].copy()
    topic_sizes = docs[docs["topic"].isin(included["topic"])].groupby("topic", as_index=False).size().rename(columns={"size": "cluster_n"})
    selected = included.merge(topic_sizes, on="topic", how="inner").nlargest(top_n, "cluster_n").copy()
    selected["cluster_label"] = selected["candidate_subtheme"] + "\n" + selected["candidate_theme"]
    monthly_totals = docs.groupby("month", as_index=False).size().rename(columns={"size": "total_posts"})
    counts = docs[docs["topic"].isin(selected["topic"])].groupby(["month", "topic"], as_index=False).size().rename(columns={"size": "post_count"})
    grid = monthly_totals.merge(selected[["topic", "cluster_label", "cluster_n"]], how="cross")
    result = grid.merge(counts, on=["month", "topic"], how="left")
    result["post_count"] = result["post_count"].fillna(0).astype(int)
    result["share_all_posts"] = result["post_count"] / result["total_posts"]
    return result.sort_values(["cluster_n", "topic", "month"], ascending=[False, True, True])


def _plot_top_cluster_monthly(monthly: pd.DataFrame, path: Path) -> None:
    selected = monthly[["topic", "cluster_label", "cluster_n"]].drop_duplicates().sort_values("cluster_n", ascending=False)
    fig, axes = plt.subplots(2, 5, figsize=(15, 6.9), sharex=True, sharey=False)
    fig.suptitle("Month-by-month prevalence of the ten largest reviewed subthemes", x=0.06, y=0.99, ha="left", fontsize=15, fontweight="bold")
    fig.text(0.06, 0.953, "Exact monthly shares of all filtered posts. Shading marks the Y1 Great Resignation window (Mar 2021-Feb 2022); dashed line marks March 2022.", ha="left", color="#475569", fontsize=9)
    for axis, (_, row) in zip(axes.flat, selected.iterrows()):
        series = monthly[monthly["topic"].eq(row["topic"])].sort_values("month")
        axis.axvspan(GREAT_RESIGNATION_START, GREAT_RESIGNATION_END, color="#E5C07B", alpha=0.24, zorder=0)
        axis.axvline(GREAT_RESIGNATION_END, color="#9A6A24", linestyle="--", linewidth=0.8, alpha=0.9, zorder=2)
        axis.plot(series["month"], series["share_all_posts"] * 100, color="#1F4E79", linewidth=1.8)
        axis.scatter(series["month"], series["share_all_posts"] * 100, color="#1F4E79", s=8, zorder=3)
        subtheme, theme = row["cluster_label"].split("\n", maxsplit=1)
        label = f"{textwrap.fill(subtheme, width=27)}\n{textwrap.fill(theme, width=27)}\n(n={int(row['cluster_n']):,})"
        axis.set_title(label, loc="left", fontsize=7.3, fontweight="bold", pad=7)
        axis.yaxis.set_major_formatter("{x:.0f}%")
        axis.grid(axis="y", alpha=0.2)
        axis.spines[["top", "right"]].set_visible(False)
        axis.tick_params(labelsize=7.5)
    for axis in axes[-1, :]:
        axis.xaxis.set_major_locator(mdates.YearLocator())
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.text(0.06, 0.012, "Subthemes are individual included BERTopic clusters nested under the nine reviewed themes. Percentages use all filtered posts in each month as the denominator.", ha="left", color="#475569", fontsize=8.5)
    fig.tight_layout(rect=[0, 0.035, 1, 0.90])
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
    top_cluster_monthly = _build_top_cluster_monthly(out_dir, Path(args.codebook))
    monthly.to_csv(analysis_dir / "candidate_theme_monthly_prevalence.csv", index=False)
    summary.to_csv(analysis_dir / "candidate_theme_summary.csv", index=False)
    window.to_csv(analysis_dir / "candidate_theme_window_prevalence.csv", index=False)
    top_cluster_monthly.to_csv(analysis_dir / "top10_reviewed_subtheme_monthly_prevalence.csv", index=False)
    _plot_monthly(monthly, figure_dir / "candidate_theme_monthly_prevalence.png")
    _plot_windows(window, figure_dir / "candidate_theme_rolling_window_prevalence.png")
    _plot_y1_y4_comparison(window, figure_dir / "candidate_theme_y1_y4_comparison.png")
    _plot_top_cluster_monthly(top_cluster_monthly, figure_dir / "top10_reviewed_subtheme_monthly_prevalence.png")
    print(f"wrote {analysis_dir / 'candidate_theme_monthly_prevalence.csv'}")
    print(f"wrote {analysis_dir / 'candidate_theme_summary.csv'}")
    print(f"wrote {analysis_dir / 'candidate_theme_window_prevalence.csv'}")
    print(f"wrote {analysis_dir / 'top10_reviewed_subtheme_monthly_prevalence.csv'}")
    print(f"wrote {figure_dir / 'candidate_theme_monthly_prevalence.png'}")
    print(f"wrote {figure_dir / 'candidate_theme_rolling_window_prevalence.png'}")
    print(f"wrote {figure_dir / 'candidate_theme_y1_y4_comparison.png'}")
    print(f"wrote {figure_dir / 'top10_reviewed_subtheme_monthly_prevalence.png'}")


if __name__ == "__main__":
    main()
