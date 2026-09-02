"""Independently verify the frozen analysis artifacts used in the handoff brief.

This script intentionally recomputes reported counts and prevalence from the
saved corpus, document-topic assignments, and reviewed candidate-theme codebook.
It does not refit BERTopic or overwrite analysis outputs.

Run with:
    .venv\\Scripts\\python.exe scripts\\validate_handoff.py
"""
from __future__ import annotations

import json
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.filter import FILTER_PATTERN


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "v2_clean_min25"
EXPECTED_WINDOWS = ["Y1_2021-22", "Y2_2022-23", "Y3_2023-24", "Y4_2024-25"]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def as_ids(frame: pd.DataFrame) -> set[str]:
    return set(frame["id"].astype(str))


def normalized(values: pd.Series) -> pd.Series:
    """Compare nullable values without losing the distinction from text data."""
    return values.astype("string").fillna("__NA__")


def main(rebuilt_filter: Path | None = None) -> None:
    filtered = pd.read_parquet(ROOT / "data" / "processed" / "posts_2021-03_to_2025-02.parquet")
    preprocessed = pd.read_parquet(ROOT / "data" / "processed" / "posts_preprocessed.parquet")
    document_topics = pd.read_csv(OUT_DIR / "bertopic_full_document_topics.csv")
    codebook = pd.read_csv(ROOT / "planning" / "CANDIDATE_THEME_CODEBOOK.csv")
    saved_window = pd.read_csv(OUT_DIR / "analysis" / "candidate_theme_window_prevalence.csv")
    saved_coverage = pd.read_csv(OUT_DIR / "analysis" / "monthly_assignment_coverage.csv")

    for name, frame in {
        "filtered corpus": filtered,
        "preprocessed corpus": preprocessed,
        "document topics": document_topics,
    }.items():
        require(not frame["id"].duplicated().any(), f"{name} contains duplicate post ids")

    require(len(filtered) == 97_254, f"unexpected filtered corpus size: {len(filtered):,}")
    require(as_ids(filtered) == as_ids(preprocessed), "filtered and preprocessed corpus IDs differ")
    require(as_ids(preprocessed) == as_ids(document_topics), "preprocessed and document-topic IDs differ")

    if rebuilt_filter is not None:
        rebuilt = pd.read_parquet(rebuilt_filter)
        require(not rebuilt["id"].duplicated().any(), "rebuilt corpus contains duplicate post ids")
        require(as_ids(filtered) == as_ids(rebuilt), "raw rebuild and frozen filtered corpus IDs differ")
        comparison_columns = [
            "id", "created_utc", "subreddit", "title", "body", "author", "score",
            "num_comments", "removed_by_category", "edited", "rolling_window",
            "calendar_window", "calendar_window_complete",
        ]
        left = filtered.sort_values("id").reset_index(drop=True)
        right = rebuilt.sort_values("id").reset_index(drop=True)
        mismatches = {
            column: int((normalized(left[column]) != normalized(right[column])).sum())
            for column in comparison_columns
        }
        require(not any(mismatches.values()), f"raw rebuild field mismatches: {mismatches}")

    timestamps = pd.to_datetime(filtered["created_utc"], unit="s", utc=True)
    require(timestamps.min() >= pd.Timestamp("2021-03-01", tz="UTC"), "corpus starts before 2021-03-01")
    require(timestamps.max() < pd.Timestamp("2025-03-01", tz="UTC"), "corpus extends past 2025-02")
    filter_text = filtered["title"].fillna("").astype(str) + " " + filtered["body"].fillna("").astype(str)
    require(filter_text.map(lambda text: bool(FILTER_PATTERN.search(text))).all(), "a corpus row fails the stated filter")

    document_topics["topic"] = document_topics["topic"].astype(int)
    assigned = document_topics[document_topics["topic"].ne(-1)]
    require(len(assigned) == 37_536, f"unexpected assigned-post count: {len(assigned):,}")
    require(document_topics["topic"].nunique() - 1 == 199, "unexpected non-outlier topic count")

    included = codebook[codebook["decision"].eq("include")].copy()
    require(not codebook["topic"].duplicated().any(), "candidate codebook has duplicate topics")
    require(len(included) == 27, f"unexpected included topic count: {len(included)}")
    mapped = document_topics.merge(included, on="topic", how="inner", validate="many_to_one")
    require(len(mapped) == 18_506, f"unexpected mapped-post count: {len(mapped):,}")
    require(mapped["candidate_theme"].nunique() == 9, "unexpected candidate-theme count")

    expected_window = (
        document_topics.groupby("rolling_window", as_index=False).size().rename(columns={"size": "total_posts"})
        .merge(
            mapped.groupby(["rolling_window", "candidate_theme"], as_index=False)
            .size()
            .rename(columns={"size": "post_count"}),
            on="rolling_window",
            how="left",
        )
    )
    expected_window["share_all_posts"] = expected_window["post_count"] / expected_window["total_posts"]
    expected_window = expected_window.sort_values(["rolling_window", "candidate_theme"]).reset_index(drop=True)
    saved_window = saved_window.sort_values(["rolling_window", "candidate_theme"]).reset_index(drop=True)
    require(expected_window[["rolling_window", "candidate_theme", "post_count", "total_posts"]].equals(
        saved_window[["rolling_window", "candidate_theme", "post_count", "total_posts"]]
    ), "saved window counts do not match recomputation")
    require(np.allclose(expected_window["share_all_posts"], saved_window["share_all_posts"]), "saved window prevalence does not match recomputation")
    require(saved_window["rolling_window"].drop_duplicates().tolist() == EXPECTED_WINDOWS, "rolling windows are incomplete or out of order")

    document_topics["month"] = pd.to_datetime(document_topics["created_utc"], unit="s", utc=True).dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    expected_coverage = document_topics.groupby("month", as_index=False).agg(
        total_posts=("id", "size"),
        assigned_posts=("topic", lambda values: int((values != -1).sum())),
    )
    expected_coverage["outlier_posts"] = expected_coverage["total_posts"] - expected_coverage["assigned_posts"]
    expected_coverage["assigned_rate"] = expected_coverage["assigned_posts"] / expected_coverage["total_posts"]
    expected_coverage["outlier_rate"] = expected_coverage["outlier_posts"] / expected_coverage["total_posts"]
    expected_coverage = expected_coverage.sort_values("month").reset_index(drop=True)
    saved_coverage["month"] = pd.to_datetime(saved_coverage["month"])
    saved_coverage = saved_coverage.sort_values("month").reset_index(drop=True)
    require(expected_coverage[["month", "total_posts", "assigned_posts", "outlier_posts"]].equals(
        saved_coverage[["month", "total_posts", "assigned_posts", "outlier_posts"]]
    ), "saved monthly assignment counts do not match recomputation")
    require(np.allclose(expected_coverage[["assigned_rate", "outlier_rate"]], saved_coverage[["assigned_rate", "outlier_rate"]]), "saved monthly assignment rates do not match recomputation")

    receipt = {
        "status": "pass",
        "filtered_posts": len(filtered),
        "assigned_posts": len(assigned),
        "assigned_rate": len(assigned) / len(document_topics),
        "non_outlier_topics": int(document_topics["topic"].nunique() - 1),
        "included_topics": len(included),
        "mapped_posts": len(mapped),
        "mapped_corpus_rate": len(mapped) / len(document_topics),
        "mapped_assigned_rate": len(mapped) / len(assigned),
        "candidate_themes": int(mapped["candidate_theme"].nunique()),
        "raw_filter_rebuild_checked": rebuilt_filter is not None,
        "windows": EXPECTED_WINDOWS,
        "checks": [
            "corpus IDs remain one-to-one through preprocessing and document assignments",
            "date range and stated text filter hold for every retained post",
            "headline clustering and codebook counts match",
            "window prevalence and monthly assignment coverage reproduce from source artifacts",
        ],
    }
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rebuilt-filter",
        type=Path,
        help="Optional parquet rebuilt from data/raw with src.filter for a field-level comparison.",
    )
    args = parser.parse_args()
    main(args.rebuilt_filter)
