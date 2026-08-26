"""Filter raw r/antiwork JSONL to the four management terms, dedup, bucket.

Reads every ``data/raw/*.jsonl`` file, applies the boss/manager/supervisor/
team-lead filter on title OR body, dedupes on ``id``, drops out-of-span
posts, attaches window labels, and writes a single parquet to
``data/processed/posts_2021-03_to_2025-02.parquet``.

The filter regex matches the original R-pipeline terms with optional
plurals: boss(es), manager(s), supervisor(s), team lead(er)(s).

Usage:
    python -m src.filter
    python -m src.filter --raw-dir data/raw --out data/processed/posts.parquet
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from src.windows import (
    assign_calendar_window,
    assign_rolling_window,
    in_total_span,
)

# Plurals + "team lead(er)(s)" handled inline. Word-boundary on both ends.
FILTER_PATTERN = re.compile(
    r"\b(?:boss(?:es)?|manager(?:s)?|supervisor(?:s)?|team[\s\-]+lead(?:er)?(?:s)?)\b",
    re.IGNORECASE,
)

# Schema kept in the final parquet
KEEP_FIELDS = (
    "id",
    "created_utc",
    "subreddit",
    "title",
    "selftext",
    "author",
    "score",
    "num_comments",
    "removed_by_category",
    "edited",
)

logger = logging.getLogger(__name__)


def _row_matches(post: dict) -> bool:
    title = post.get("title") or ""
    body = post.get("selftext") or ""
    return bool(FILTER_PATTERN.search(title) or FILTER_PATTERN.search(body))


def load_filtered_posts(raw_dir: Path) -> pd.DataFrame:
    """Load all data/raw/*.jsonl, apply filter, dedup, attach windows."""
    files = sorted(raw_dir.glob("*.jsonl"))
    if not files:
        raise FileNotFoundError(f"No .jsonl files in {raw_dir}")

    rows: list[dict] = []
    seen_ids: set[str] = set()
    n_total = 0
    n_dropped_dupe = 0
    n_dropped_filter = 0
    n_dropped_span = 0

    for path in tqdm(files, desc="reading raw"):
        with path.open(encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                n_total += 1
                post = json.loads(line)

                pid = post.get("id")
                if pid in seen_ids:
                    n_dropped_dupe += 1
                    continue

                ts = post.get("created_utc")
                if ts is None or not in_total_span(int(ts)):
                    n_dropped_span += 1
                    continue

                if not _row_matches(post):
                    n_dropped_filter += 1
                    continue

                seen_ids.add(pid)
                rows.append({k: post.get(k) for k in KEEP_FIELDS})

    logger.info(
        "filter pass: total=%d kept=%d dropped_filter=%d dropped_dupe=%d dropped_span=%d",
        n_total, len(rows), n_dropped_filter, n_dropped_dupe, n_dropped_span,
    )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.rename(columns={"selftext": "body"})

    df["rolling_window"] = df["created_utc"].astype(int).map(assign_rolling_window)
    df["calendar_window"] = df["created_utc"].astype(int).map(
        lambda ts: assign_calendar_window(ts, include_partials=True)
    )
    df["calendar_window_complete"] = df["created_utc"].astype(int).map(
        lambda ts: assign_calendar_window(ts, include_partials=False)
    )

    df["created_utc"] = df["created_utc"].astype("int64")
    df["score"] = pd.to_numeric(df["score"], errors="coerce").fillna(0).astype("int64")
    df["num_comments"] = pd.to_numeric(df["num_comments"], errors="coerce").fillna(0).astype("int64")
    for col in ("title", "body", "author", "subreddit", "removed_by_category"):
        df[col] = df[col].astype("string")

    # Reddit's `edited` is either `False` (never edited) or a Unix timestamp.
    # Normalize to nullable Int64: timestamp if edited, NA if not.
    def _norm_edited(v):
        if v is True or v is False or v is None:
            return pd.NA
        try:
            return int(v)
        except (TypeError, ValueError):
            return pd.NA

    df["edited"] = df["edited"].apply(_norm_edited).astype("Int64")

    df = df.sort_values("created_utc").reset_index(drop=True)
    return df


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Filter & bucket raw r/antiwork JSONL")
    parser.add_argument("--raw-dir", default="data/raw", help="Input directory of monthly JSONL")
    parser.add_argument(
        "--out",
        default="data/processed/posts_2021-03_to_2025-02.parquet",
        help="Output parquet path",
    )
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    df = load_filtered_posts(raw_dir)
    df.to_parquet(out, index=False, compression="snappy")

    print(f"\nWrote {len(df):,} posts -> {out}")
    print(f"  Date range: {df['created_utc'].min()} .. {df['created_utc'].max()}  (epoch seconds)")
    print(f"  Rolling-window distribution:")
    print(df["rolling_window"].value_counts(dropna=False).to_string())
    print(f"  Calendar-window distribution (with partials):")
    print(df["calendar_window"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
