"""Phase 2 sanity checks + reconciliation against the original CSV.

Produces:
- outputs/figures/01_monthly_counts.png
- outputs/figures/02_term_frequency.png
- outputs/figures/03_window_distribution.png
- Console: author-uniqueness stats, reconciliation results

Reconciliation: fuzzy-text-match the original 6,132-row CSV against our
Y1 (2021-22) titles. The original CSV has no IDs, so we normalize both
sides to alphanumerics+spaces, lowercase, then check overlap.

Usage:
    python -m src.sanity_check
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no display backend needed
import matplotlib.pyplot as plt
import pandas as pd

# Use the same FILTER_PATTERN as src/filter.py for the term-frequency plot
from src.filter import FILTER_PATTERN

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _normalize_for_match(s: str) -> str:
    """Lowercase, strip non-alphanumerics, collapse whitespace.

    Robust to smart-quote / encoding differences between the Excel-exported
    Latin-1 CSV and Arctic Shift's UTF-8 JSON.
    """
    s = s.lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)  # strip punctuation/quotes/etc.
    s = re.sub(r"\s+", " ", s).strip()
    return s


def plot_monthly_counts(df: pd.DataFrame, out_path: Path) -> None:
    df = df.copy()
    df["month"] = pd.to_datetime(df["created_utc"], unit="s", utc=True).dt.to_period("M")
    monthly = df.groupby("month").size()

    fig, ax = plt.subplots(figsize=(12, 4.5))
    monthly.plot(kind="line", ax=ax, marker="o", markersize=3)
    ax.set_title("Filtered r/antiwork posts per month (boss/manager/supervisor/team-lead, titles+bodies)")
    ax.set_ylabel("Posts")
    ax.set_xlabel("Month")
    ax.grid(True, alpha=0.3)

    # Annotate window boundaries
    for boundary_label, boundary_period in [
        ("Y1->Y2", pd.Period("2022-03", freq="M")),
        ("Y2->Y3", pd.Period("2023-03", freq="M")),
        ("Y3->Y4", pd.Period("2024-03", freq="M")),
    ]:
        ax.axvline(boundary_period.ordinal, color="red", linestyle="--", alpha=0.4, linewidth=1)
        ax.annotate(boundary_label, xy=(boundary_period.ordinal, ax.get_ylim()[1] * 0.95),
                    fontsize=8, color="red", ha="center")

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  wrote {out_path}")


def plot_term_frequency(df: pd.DataFrame, out_path: Path) -> None:
    """Per-month rate of each filter term in titles+bodies. Multi-match counts each."""
    df = df.copy()
    df["month"] = pd.to_datetime(df["created_utc"], unit="s", utc=True).dt.to_period("M")

    text = (df["title"].fillna("") + " " + df["body"].fillna("")).str.lower()
    df["has_boss"] = text.str.contains(r"\bboss(?:es)?\b", regex=True, na=False)
    df["has_manager"] = text.str.contains(r"\bmanager(?:s)?\b", regex=True, na=False)
    df["has_supervisor"] = text.str.contains(r"\bsupervisor(?:s)?\b", regex=True, na=False)
    df["has_team_lead"] = text.str.contains(r"\bteam[\s\-]+lead(?:er)?(?:s)?\b", regex=True, na=False)

    monthly_counts = df.groupby("month")[["has_boss", "has_manager", "has_supervisor", "has_team_lead"]].sum()

    fig, ax = plt.subplots(figsize=(12, 4.5))
    monthly_counts.plot(ax=ax, marker="o", markersize=2.5, linewidth=1.2)
    ax.set_title("Posts containing each filter term, by month")
    ax.set_ylabel("Posts containing term")
    ax.set_xlabel("Month")
    ax.grid(True, alpha=0.3)
    ax.legend(["boss(es)", "manager(s)", "supervisor(s)", "team lead(er)(s)"], loc="upper right")
    ax.set_yscale("log")

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  wrote {out_path}")


def plot_window_distribution(df: pd.DataFrame, out_path: Path) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))

    rolling = df["rolling_window"].value_counts().sort_index()
    rolling.plot(kind="bar", ax=axes[0], color="steelblue")
    axes[0].set_title("Rolling Mar–Feb windows (PRIMARY)")
    axes[0].set_ylabel("Posts")
    axes[0].tick_params(axis="x", rotation=0)
    for i, v in enumerate(rolling.values):
        axes[0].text(i, v + 200, f"{v:,}", ha="center", fontsize=9)

    cal = df["calendar_window"].value_counts().sort_index()
    cal.plot(kind="bar", ax=axes[1], color="darkorange")
    axes[1].set_title("Calendar-year windows (SECONDARY, with partials)")
    axes[1].set_ylabel("Posts")
    axes[1].tick_params(axis="x", rotation=15)
    for i, v in enumerate(cal.values):
        axes[1].text(i, v + 200, f"{v:,}", ha="center", fontsize=9)

    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    print(f"  wrote {out_path}")


def author_uniqueness(df: pd.DataFrame) -> None:
    print("\n=== Author uniqueness ===")
    n_posts = len(df)
    n_authors = df["author"].nunique(dropna=False)
    n_deleted = (df["author"] == "[deleted]").sum()
    n_known = df.loc[df["author"] != "[deleted]", "author"].nunique()

    top = df["author"].value_counts().head(10)

    print(f"  posts: {n_posts:,}")
    print(f"  unique authors (incl. [deleted]): {n_authors:,}")
    print(f"  posts with [deleted] author: {n_deleted:,} ({n_deleted / n_posts:.1%})")
    print(f"  unique non-deleted authors: {n_known:,}")
    print(f"  posts per non-deleted author (mean): {(n_posts - n_deleted) / max(n_known, 1):.2f}")
    print(f"\n  Top 10 prolific authors:")
    for author, count in top.items():
        print(f"    {author}: {count:,}")


def reconcile_against_csv(df: pd.DataFrame, csv_path: Path) -> None:
    print("\n=== Reconciliation against original 6,132-row CSV ===")
    csv_df = pd.read_csv(csv_path, encoding="latin-1", header=None, names=["text"])
    print(f"  Loaded {len(csv_df):,} rows from {csv_path.name}")

    csv_df["norm"] = csv_df["text"].astype(str).map(_normalize_for_match)
    csv_normalized = set(csv_df["norm"])

    y1 = df[df["rolling_window"] == "Y1_2021-22"]
    print(f"  Y1 (2021-22) corpus titles: {len(y1):,}")

    y1_norms = y1["title"].fillna("").map(_normalize_for_match)
    y1_set = set(y1_norms)

    overlap = csv_normalized & y1_set
    n_csv_matched = sum(1 for n in csv_df["norm"] if n in y1_set)
    print(f"  CSV rows that exact-match a Y1 title (after normalization): {n_csv_matched:,} of {len(csv_df):,} ({n_csv_matched / len(csv_df):.1%})")
    print(f"  Distinct normalized titles in CSV: {len(csv_normalized):,}")
    print(f"  Distinct normalized titles in Y1: {len(y1_set):,}")
    print(f"  Distinct titles in both: {len(overlap):,}")

    # Y1 titles that the original analysis WOULD have caught (filter on title only)
    title_filter_match = y1["title"].fillna("").apply(lambda s: bool(FILTER_PATTERN.search(s))).sum()
    print(f"\n  Of Y1 corpus, posts whose TITLE alone matches the filter: {title_filter_match:,} ({title_filter_match / len(y1):.1%})")
    print(f"  Of Y1 corpus, posts kept only because BODY matches filter: {len(y1) - title_filter_match:,} ({(len(y1) - title_filter_match) / len(y1):.1%})")
    print(f"\n  Note: original analysis used title-only filter on ~6,132 posts. We have {title_filter_match:,} title-matching posts in Y1.")
    print(f"  Reconciliation rate (CSV -> Y1 title-matching subset): {n_csv_matched:,} / {len(csv_df):,} = {n_csv_matched / len(csv_df):.1%}")

    # Sample 5 CSV rows that DIDN'T match — for investigation
    unmatched = csv_df[~csv_df["norm"].isin(y1_set)].head(5)
    if not unmatched.empty:
        print(f"\n  Sample 5 CSV rows that did NOT match any Y1 title (truncated to 120 chars):")
        for _, row in unmatched.iterrows():
            print(f"    {row['text'][:120]!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2 sanity checks + CSV reconciliation")
    parser.add_argument("--parquet", default="data/processed/posts_2021-03_to_2025-02.parquet")
    parser.add_argument("--csv", default="Post Content.csv")
    parser.add_argument("--out-dir", default="outputs/figures")
    args = parser.parse_args()

    parquet_path = Path(args.parquet)
    csv_path = Path(args.csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(parquet_path)
    print(f"Loaded {len(df):,} posts from {parquet_path}")
    print(f"Columns: {list(df.columns)}")

    print("\n=== Plots ===")
    plot_monthly_counts(df, out_dir / "01_monthly_counts.png")
    plot_term_frequency(df, out_dir / "02_term_frequency.png")
    plot_window_distribution(df, out_dir / "03_window_distribution.png")

    author_uniqueness(df)
    reconcile_against_csv(df, csv_path)


if __name__ == "__main__":
    main()
