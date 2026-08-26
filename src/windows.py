"""Window bucketing per planning/WINDOWS.md.

Two schemes:
- Rolling Mar–Feb (PRIMARY): four complete one-year windows matching the
  original SIOP poster's Mar 2021 – Feb 2022 frame.
- Calendar year (SECONDARY): three complete years (2022, 2023, 2024) plus
  optional partial 2021 / 2025 buckets for robustness checks.

All boundaries are half-open `[start, end)` in UTC.
"""
from __future__ import annotations

from datetime import datetime, timezone

# (label, start_inclusive_utc, end_exclusive_utc)
ROLLING_WINDOWS: list[tuple[str, datetime, datetime]] = [
    ("Y1_2021-22", datetime(2021, 3, 1, tzinfo=timezone.utc), datetime(2022, 3, 1, tzinfo=timezone.utc)),
    ("Y2_2022-23", datetime(2022, 3, 1, tzinfo=timezone.utc), datetime(2023, 3, 1, tzinfo=timezone.utc)),
    ("Y3_2023-24", datetime(2023, 3, 1, tzinfo=timezone.utc), datetime(2024, 3, 1, tzinfo=timezone.utc)),
    ("Y4_2024-25", datetime(2024, 3, 1, tzinfo=timezone.utc), datetime(2025, 3, 1, tzinfo=timezone.utc)),
]

CALENDAR_WINDOWS_COMPLETE: list[tuple[str, datetime, datetime]] = [
    ("CY_2022", datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2023, 1, 1, tzinfo=timezone.utc)),
    ("CY_2023", datetime(2023, 1, 1, tzinfo=timezone.utc), datetime(2024, 1, 1, tzinfo=timezone.utc)),
    ("CY_2024", datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2025, 1, 1, tzinfo=timezone.utc)),
]

CALENDAR_WINDOWS_INCLUDING_PARTIALS: list[tuple[str, datetime, datetime]] = [
    ("CY_2021_partial", datetime(2021, 3, 1, tzinfo=timezone.utc), datetime(2022, 1, 1, tzinfo=timezone.utc)),
    *CALENDAR_WINDOWS_COMPLETE,
    ("CY_2025_partial", datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 3, 1, tzinfo=timezone.utc)),
]

TOTAL_SPAN_START = datetime(2021, 3, 1, tzinfo=timezone.utc)
TOTAL_SPAN_END = datetime(2025, 3, 1, tzinfo=timezone.utc)


def _epoch(dt: datetime) -> int:
    return int(dt.timestamp())


def _assign(created_utc: int, scheme: list[tuple[str, datetime, datetime]]) -> str | None:
    for label, start, end in scheme:
        if _epoch(start) <= created_utc < _epoch(end):
            return label
    return None


def assign_rolling_window(created_utc: int) -> str | None:
    """Return the rolling window label for a Unix-epoch timestamp, or None if outside the total span."""
    return _assign(created_utc, ROLLING_WINDOWS)


def assign_calendar_window(created_utc: int, include_partials: bool = True) -> str | None:
    """Return the calendar-year window label for a Unix-epoch timestamp.

    By default returns labels for partial 2021 / 2025 buckets too. Pass
    ``include_partials=False`` to restrict to the three complete years
    (2022, 2023, 2024) — which is the recommended default for the
    secondary analysis figures.
    """
    scheme = CALENDAR_WINDOWS_INCLUDING_PARTIALS if include_partials else CALENDAR_WINDOWS_COMPLETE
    return _assign(created_utc, scheme)


def in_total_span(created_utc: int) -> bool:
    """True if the timestamp falls within the locked Mar 2021 – Feb 2025 span."""
    return _epoch(TOTAL_SPAN_START) <= created_utc < _epoch(TOTAL_SPAN_END)
