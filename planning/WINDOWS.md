# WINDOWS.md — Locked window definitions

Locked 2026-04-26. Phase 1 deliverable.

This file is the **single source of truth** for which posts go in which bucket. All downstream code (`src/scrape.py`, `src/preprocess.py`, all topic-modeling notebooks) must use these definitions verbatim.

## Time semantics

- **Timestamp source:** Reddit's `created_utc` (Unix seconds since epoch, UTC by definition)
- **Comparison timezone:** UTC (no DST conversion, no local-time bucketing — Reddit doesn't store posts in user-local time anyway)
- **Interval convention:** half-open `[start, end)` — start inclusive, end exclusive
- **Why half-open:** unambiguous at boundaries; a post created at `2022-03-01T00:00:00Z` belongs to Y2, never to Y1
- **Date format in code:** ISO 8601 with explicit `Z` suffix (e.g., `2021-03-01T00:00:00Z`)

## Scheme A — Rolling March–Feb (PRIMARY)

Matches the original 2023 SIOP poster exactly. Four complete one-year windows, no partials.

| Window | Label | Start (inclusive) | End (exclusive) | Days |
|---|---|---|---|---|
| Y1 | 2021–22 | 2021-03-01T00:00:00Z | 2022-03-01T00:00:00Z | 365 |
| Y2 | 2022–23 | 2022-03-01T00:00:00Z | 2023-03-01T00:00:00Z | 365 |
| Y3 | 2023–24 | 2023-03-01T00:00:00Z | 2024-03-01T00:00:00Z | 366 |
| Y4 | 2024–25 | 2024-03-01T00:00:00Z | 2025-03-01T00:00:00Z | 365 |

Total span: **1,461 days** (exactly 4 years).

Y1 is the **replication target** — its topic structure should be compared directly to the original six SIOP themes (Scheduling, Holidays, Leaving, COVID-19, Desires, Compensation).

## Scheme B — Calendar year (SECONDARY / robustness)

Used only for cross-year comparison figures and the appendix. Three **complete** calendar years are the comparison set.

| Year | Start (inclusive) | End (exclusive) | Days | Status |
|---|---|---|---|---|
| 2021 | 2021-03-01T00:00:00Z | 2022-01-01T00:00:00Z | 306 | **Partial** (no Jan–Feb 2021 data) |
| 2022 | 2022-01-01T00:00:00Z | 2023-01-01T00:00:00Z | 365 | Complete |
| 2023 | 2023-01-01T00:00:00Z | 2024-01-01T00:00:00Z | 365 | Complete |
| 2024 | 2024-01-01T00:00:00Z | 2025-01-01T00:00:00Z | 366 | Complete |
| 2025 | 2025-01-01T00:00:00Z | 2025-03-01T00:00:00Z | 59 | **Partial** (Jan–Feb only) |

### Partial-bucket policy

- **Default:** drop the partial 2021 and 2025 buckets from any cross-year comparison or figure. Only 2022 / 2023 / 2024 are reported in the calendar-year secondary analysis.
- **Rationale:** comparing topic prevalence across vastly different sample windows (306-day vs 365-day vs 59-day) introduces artifacts that swamp the signal we care about.
- **Override:** if a robustness check explicitly wants to include partials, label them clearly as "Mar–Dec 2021" and "Jan–Feb 2025" in figures (never bare "2021" or "2025").

## Implementation contract

Any code that buckets posts must follow this contract:

```python
# Pseudocode — to be implemented in src/windows.py once skeleton lands
from datetime import datetime, timezone

ROLLING_WINDOWS = [
    ("Y1_2021-22", datetime(2021, 3, 1, tzinfo=timezone.utc), datetime(2022, 3, 1, tzinfo=timezone.utc)),
    ("Y2_2022-23", datetime(2022, 3, 1, tzinfo=timezone.utc), datetime(2023, 3, 1, tzinfo=timezone.utc)),
    ("Y3_2023-24", datetime(2023, 3, 1, tzinfo=timezone.utc), datetime(2024, 3, 1, tzinfo=timezone.utc)),
    ("Y4_2024-25", datetime(2024, 3, 1, tzinfo=timezone.utc), datetime(2025, 3, 1, tzinfo=timezone.utc)),
]

CALENDAR_WINDOWS_COMPLETE = [
    ("CY_2022", datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2023, 1, 1, tzinfo=timezone.utc)),
    ("CY_2023", datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)),
    ("CY_2024", datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2025, 1, 1, tzinfo=timezone.utc)),
]

CALENDAR_WINDOWS_INCLUDING_PARTIALS = [
    ("CY_2021_partial", datetime(2021, 3, 1, tzinfo=timezone.utc), datetime(2022, 1, 1, tzinfo=timezone.utc)),
    *CALENDAR_WINDOWS_COMPLETE,
    ("CY_2025_partial", datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 3, 1, tzinfo=timezone.utc)),
]
```

## Out-of-window data

The Arctic Shift pull will collect everything Mar 2021 – Feb 2025 inclusive. Posts whose `created_utc` falls outside `[2021-03-01T00:00:00Z, 2025-03-01T00:00:00Z)` are **not used** in any analysis. They are kept in `data/raw/` for provenance but excluded from `data/processed/posts_2021-03_to_2025-02.parquet`.

## Sanity check at end of Phase 2

Once the corpus is built, confirm:

- Every row in `data/processed/posts_2021-03_to_2025-02.parquet` falls into exactly one rolling window
- Every row falls into exactly one calendar window (which may be a "partial" bucket)
- No posts have `created_utc` outside the total span
