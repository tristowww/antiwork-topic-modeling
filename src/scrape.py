"""Arctic Shift API client for r/antiwork.

Pulls posts in a date range, paginated, rate-limited, with per-month JSONL
caching so partial pulls are resumable. See planning/SCRAPING.md for the
contract this implements.

Usage:
    python -m src.scrape --start 2021-03-01 --end 2025-03-01

Or programmatically:
    from src.scrape import scrape_range
    counts = scrape_range(start, end, Path("data/raw"))
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import requests
from tqdm import tqdm

ARCTIC_SHIFT_BASE = "https://arctic-shift.photon-reddit.com"
SUBREDDIT = "antiwork"
PAGE_LIMIT = 100
RATE_LIMIT_SEC = 1.0
REQUEST_TIMEOUT = 30
RETRY_COUNT = 3
RETRY_BACKOFF_SEC = 2.0

logger = logging.getLogger(__name__)


def _fetch_page(params: dict) -> list[dict]:
    last_err: Exception | None = None
    for attempt in range(RETRY_COUNT):
        try:
            resp = requests.get(
                f"{ARCTIC_SHIFT_BASE}/api/posts/search",
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except (requests.RequestException, ValueError) as e:
            last_err = e
            if attempt < RETRY_COUNT - 1:
                sleep_for = RETRY_BACKOFF_SEC ** attempt
                logger.warning("Arctic Shift request failed (%s); retrying in %.1fs", e, sleep_for)
                time.sleep(sleep_for)
    raise RuntimeError(f"Arctic Shift request failed after {RETRY_COUNT} retries") from last_err


def fetch_window(after_epoch: int, before_epoch: int) -> Iterator[dict]:
    """Yield r/antiwork posts in [after_epoch, before_epoch) using cursor pagination.

    Cursor advances to max(created_utc) of each page. IDs are de-duplicated to
    handle inclusive vs exclusive `after` semantics defensively.
    """
    cursor: int = after_epoch
    seen_ids: set[str] = set()

    while True:
        params = {
            "subreddit": SUBREDDIT,
            "after": cursor,
            "before": before_epoch,
            "limit": PAGE_LIMIT,
            "sort": "asc",
        }
        posts = _fetch_page(params)
        if not posts:
            return

        new_in_page = 0
        for post in posts:
            pid = post.get("id")
            if pid is None or pid in seen_ids:
                continue
            seen_ids.add(pid)
            new_in_page += 1
            yield post

        if new_in_page == 0:
            # The page was entirely duplicates — pagination stuck, terminate.
            return

        cursor = max(p["created_utc"] for p in posts)
        time.sleep(RATE_LIMIT_SEC)


def _month_bounds(year: int, month: int) -> tuple[int, int]:
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(year, month + 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp()), int(end.timestamp())


def scrape_month(year: int, month: int, out_dir: Path) -> int:
    """Scrape one month of r/antiwork to data/raw/<YYYY-MM>.jsonl. Idempotent."""
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{year:04d}-{month:02d}.jsonl"
    if out_path.exists():
        with out_path.open(encoding="utf-8") as f:
            return sum(1 for _ in f)

    after_epoch, before_epoch = _month_bounds(year, month)
    tmp_path = out_path.with_suffix(".jsonl.tmp")
    n = 0
    with tmp_path.open("w", encoding="utf-8") as f:
        for post in fetch_window(after_epoch, before_epoch):
            f.write(json.dumps(post, ensure_ascii=False) + "\n")
            n += 1
    tmp_path.replace(out_path)
    return n


def _iter_months(start: datetime, end: datetime) -> Iterator[tuple[int, int]]:
    cur = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
    end_anchor = datetime(end.year, end.month, 1, tzinfo=timezone.utc)
    while cur < end_anchor:
        yield cur.year, cur.month
        cur = datetime(cur.year + (1 if cur.month == 12 else 0),
                       1 if cur.month == 12 else cur.month + 1,
                       1, tzinfo=timezone.utc)


def scrape_range(start: datetime, end: datetime, out_dir: Path) -> dict[str, int]:
    """Scrape every month-bucket in [start, end). Returns {YYYY-MM: post_count}."""
    counts: dict[str, int] = {}
    months = list(_iter_months(start, end))
    for year, month in tqdm(months, desc="months"):
        counts[f"{year:04d}-{month:02d}"] = scrape_month(year, month, out_dir)
    return counts


def _parse_iso_utc(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def main() -> None:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Scrape r/antiwork via Arctic Shift")
    parser.add_argument("--start", default="2021-03-01", help="Inclusive start (YYYY-MM-DD)")
    parser.add_argument("--end", default="2025-03-01", help="Exclusive end (YYYY-MM-DD)")
    parser.add_argument("--out-dir", default="data/raw", help="Output directory for monthly JSONL")
    args = parser.parse_args()

    start = _parse_iso_utc(args.start)
    end = _parse_iso_utc(args.end)
    out_dir = Path(args.out_dir)

    counts = scrape_range(start, end, out_dir)
    total = sum(counts.values())
    print(f"\n{total:,} posts saved across {len(counts)} months -> {out_dir}/")
    if counts:
        first = min(counts)
        last = max(counts)
        print(f"  {first}: {counts[first]:,} posts")
        print(f"  {last}: {counts[last]:,} posts")


if __name__ == "__main__":
    main()
