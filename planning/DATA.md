# DATA.md — Inventory of `Post Content.csv`

Inventoried 2026-04-26. Phase 1 deliverable.

## File

- Path: `Post Content.csv` (project root)
- Size: 528,603 bytes (~516 KB)
- Encoding: **latin-1** (CP1252 also works). UTF-8 fails — there are smart-quote bytes (e.g. `0x9d`) that suggest a Windows / Excel export.
- Header: **no header row**. First line is data. Read with `pd.read_csv(..., encoding='latin-1', header=None, names=['text'])`.

## Shape

- **6,132 rows** — matches the SIOP poster's claim exactly.
- **1 column** — post text only. Nothing else.

## Content type

These are **post titles**, not bodies. Strong evidence:

| Statistic | Value |
|---|---|
| Max length | 307 chars |
| 99th percentile | 287 chars |
| 95th percentile | 202 chars |
| Median | 71 chars |
| 10th percentile | 31 chars |
| Min length | 8 chars |
| Rows > 300 chars | 8 (CSV-quoting artifacts) |
| Rows > 1000 chars | 0 |

Reddit's title cap is 300 characters. Bodies regularly exceed several thousand. The shape of this distribution is unambiguously titles. Confirms what the SIOP paper says.

## Filter status

Pre-filtered to the four management terms, but with ~1.4% apparent leakage (likely case-sensitive or different word-boundary rules in the original R pipeline).

| Filter term | Rows containing it | % of corpus |
|---|---|---|
| boss | 4,008 | 65.4% |
| manager | 1,850 | 30.2% |
| supervisor | 272 | 4.4% |
| team lead | 19 | 0.3% |
| **Any of the four** | **6,048** | **98.6%** |

(Rows can match multiple terms, so the per-term counts overlap.)

## What's missing — important

The CSV contains **no metadata at all**:

- No `id` (Reddit base36 post ID)
- No `created_utc` timestamp
- No `author`
- No `score` or `num_comments`
- No subreddit (assumed r/antiwork from project context)

This has a direct consequence for Phase 2.

## Implication for Phase 2 reconciliation

The ROADMAP currently calls for: *"Reconcile against original 6,132-row CSV: confirm overlap on `id` for the Mar 2021–Feb 2022 window. If overlap is < 90%, investigate before proceeding."*

That cannot be done as written — the CSV has no IDs. The reconciliation must be by **fuzzy title-text match** against Arctic Shift's r/antiwork titles in Mar 2021 – Feb 2022, filtered to the four terms.

Recommended approach:
- Pull r/antiwork titles from Arctic Shift for Mar 2021 – Feb 2022 with the same four-term filter
- For each CSV row, compute best-match similarity (Levenshtein, or normalized exact match after lowercasing + whitespace normalization) against the Arctic Shift candidate set
- Threshold at ≥0.95 similarity for a "match"

Expected match rate: **≥90%**. Below that, investigate before proceeding. Misses are expected from:
- Post-archive title edits by authors
- Posts deleted before Arctic Shift snapshotted them
- The 1.4% filter leakage (those rows won't match a re-filtered re-pull)

## Provenance (best guess)

The file is undocumented. Most likely:
- Exported from Excel after the original R pipeline (`stab4_wNgrams-nBossYjob (new timeframe).R`) produced its filtered subset
- The R pipeline presumably had access to dates and IDs that did not survive into the CSV export
- Latin-1 encoding + smart-quote artifacts are consistent with an Excel "Save As CSV" operation on Windows

If this matters for reproducibility, look for a sibling R workspace file (`.RData`) or an intermediate parquet/RDS file that may still have IDs.
