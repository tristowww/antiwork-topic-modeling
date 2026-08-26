# Robustness Record

Updated 2026-07-24. These checks support the current exploratory paper. They
do not turn the model into a causal or complete-corpus measurement.

## Frozen-corpus audit

- The filtered and preprocessed inputs each contain 97,254 unique post ids, and
  their id sets are identical.
- Every retained post matches the management-term filter when it is re-applied.
- 11,214 posts have a deleted or removed title or body field. The primary
  pipeline strips those placeholders but retains any remaining title or body
  text.
- The audit records exact normalized duplicate-text counts separately for all
  rows and non-placeholder rows in
  `outputs/v2_clean_min25/analysis/robustness/data_quality_audit.json`.
- 1,127 non-placeholder rows (1.2% of the corpus) have exact normalized-text
  duplicates. The primary corpus is deduplicated by Reddit id, not by text, so
  this small residual duplication is disclosed rather than silently removed
  after the primary model was frozen.

## Cross-window alignment

The existing greedy top-term Jaccard matches were rerun alongside a one-to-one
maximum-Jaccard assignment. The one-to-one result is the conservative result:

| Window comparison | Unique matches at Jaccard >= 0.20 | Mean unique Jaccard |
|---|---:|---:|
| Y1 to Y2 | 46/81 (56.8%) | 0.318 |
| Y2 to Y3 | 45/64 (70.3%) | 0.366 |
| Y3 to Y4 | 33/38 (86.8%) | 0.414 |
| Y1 to Y4 | 26/38 (68.4%) | 0.330 |

These figures are a term-overlap diagnostic, not proof that a substantive theme
persisted. The paper should anchor prevalence claims in the full-corpus
codebook trends and use per-window alignment only as supporting context.

## Seed stability

Using the same deterministic 10,000-post stratified sample (2,500 posts per
rolling window), three UMAP seeds with the unchanged MiniLM and HDBSCAN settings
produced assigned rates from 40.6% to 43.3% and 37 to 41 non-outlier clusters.
Across seed pairs, inlier-membership Jaccard was 0.772 to 0.806, all-document
adjusted Rand index was 0.721 to 0.770, and adjusted Rand index among jointly
assigned documents was 0.900 to 0.966.

This supports the conclusion that the primary configuration has stable
partitions when the input text is held fixed. It does not remove the primary
model's 61.4% outlier limitation.

## Text-mode sensitivity

The same 10,000 posts were clustered from titles only. Its within-method seed
stability was also strong, but title-only assigned 58.2% to 62.7% of documents,
compared with 40.6% to 43.3% for title-plus-body. At seed 29, the two text modes
shared only 41.2% inlier membership Jaccard and had adjusted Rand index 0.098
over all documents (0.419 among jointly assigned documents).

Body text therefore materially changes the discovered partition. The paper
will define title-plus-body as its primary data representation and report this
as a sensitivity limitation, not claim that the title-only model reproduces the
same themes.

## Deferred alternate-encoder check

An `all-mpnet-base-v2` sanity check on the same 4,000-post stratified sample
was attempted on 2026-07-24 but did not complete within the 15-minute CPU
runtime bound and produced no cache or metrics artifact. It is therefore not
reported as evidence. The completed robustness evidence for this paper is the
corpus audit, unique alignment, MiniLM multi-seed stability, and title-only
sensitivity. A future compute-resourced run may add the encoder comparison.

## Reporting decision

Use the 27-cluster, nine-theme codebook for the primary descriptive trends. It
covers 18,506 posts, 19.0% of the full filtered corpus and 49.3% of assigned
posts. State that scope prominently, report no sentiment results, and avoid
claims about the full unfiltered r/antiwork conversation.
