# Findings: v2 exploratory BERTopic run

Updated 2026-07-22. This supersedes the 2026-05-05 narrative. It records what
the current run supports and what it does not support.

## Technical summary

The current full-corpus BERTopic run covers 97,254 filtered r/antiwork posts
from March 2021 through February 2025. It produces 199 non-outlier clusters,
but assigns only 37,536 posts (38.6%) to them. The remaining 59,718 posts
(61.4%) are HDBSCAN outliers.

This is enough to create an interpretable review packet and identify candidate
clusters. It is not enough to make strong claims about a topic "disappearing,"
about change in the complete conversation, or about sentiment.

## Verified descriptive results

- Assignments are complete and one-to-one: all 97,254 corpus post ids appear
  exactly once in `bertopic_full_document_topics.csv`.
- Assignment coverage varies from 33.1% (May 2021) to 44.0% (December 2022).
  Every raw-cluster time series must therefore be interpreted with the coverage
  figure beside it.
- The most frequent interpretable clusters include hiring/interviews (2,170
  assigned posts), pay raises/salary (1,737), COVID/illness (1,329),
  paycheck/payroll (1,130), remote/RTO (963), scheduling (661), PTO (655), and
  unionization (614).
- Selected raw-cluster trends show meaningful descriptive patterns. The COVID
  cluster peaks early, the remote/RTO cluster rises again late in 2024, and the
  pay-raise cluster is strongest in 2021-22. These are prompts for a
  documented exploratory theme analysis, not causal or definitive topic-evolution
  claims.

## Cross-window comparison

The greedy Jaccard alignment remains a discovery diagnostic, not a persistence
measure. A one-to-one maximum-Jaccard matching now provides the conservative
comparison: 56.8% of Y1 topics have a unique Y2 match at Jaccard >= 0.20; the
equivalent rates are 70.3% for Y2 to Y3, 86.8% for Y3 to Y4, and 68.4% of Y4
topics for Y1 to Y4. These results still use top-term overlap rather than
document-level semantic correspondence, so they provide supporting context only.

## Robustness checks

The frozen-corpus audit confirms 97,254 matching unique ids across filtered and
preprocessed inputs and a 100% re-applied filter match rate. Three UMAP seeds
on the same 10,000-post stratified sample show stable title-plus-body partitions
(joint-inlier adjusted Rand index 0.900 to 0.966). Title-only clustering is also
internally stable, but it changes the partition materially: seed-29 agreement
with title-plus-body is 0.098 adjusted Rand index across all documents. The
paper therefore defines title-plus-body as the primary representation and
reports title-only divergence as a sensitivity limitation. Exact metrics and
data-quality detail are in `planning/ROBUSTNESS.md`.

## Provisional theme-map result

The finalized exploratory codebook maps 27 of the 30 largest clusters into nine
themes. It covers 18,506 posts (19.0% of the full corpus and 49.3% of assigned
posts). Within that mapped subset, health safety and attendance falls from 4.97%
of Y1 posts to 2.50% of Y4 posts, while scheduling hours and time off rises from
1.71% to 3.20%. Compensation and pay rights remains substantial in all four
windows, and career precarity and exit is broadly stable.

These are descriptive candidate-theme results, not complete-corpus or causal
claims. The map and writing-ready evidence are in
`planning/CANDIDATE_THEME_CODEBOOK.csv`,
`outputs/v2_clean_min25/analysis/candidate_theme_*.csv`, and
`planning/WRITING_HANDOFF.md`.

## Not yet supported

- A claim that a topic or theme persisted, emerged, or faded in the complete
  r/antiwork conversation.
- A sentiment result. No VADER output should be generated or presented.
- A causal explanation for month-to-month movement.
- A final named-theme taxonomy. Current labels are BERTopic cluster labels.

## Evidence artifacts

- `outputs/v2_clean_min25/analysis/analysis_metrics.json`
- `outputs/v2_clean_min25/analysis/topic_overview.csv`
- `outputs/v2_clean_min25/analysis/topic_review_posts.csv`
- `outputs/v2_clean_min25/analysis/monthly_assignment_coverage.csv`
- `outputs/v2_clean_min25/analysis/monthly_anchor_topic_prevalence.csv`
- `outputs/v2_clean_min25/figures/monthly_assignment_coverage.png`
- `outputs/v2_clean_min25/figures/monthly_anchor_topic_prevalence.png`

## Interpretation rule

Use the current outputs as the finalized evidence set for an exploratory paper.
Sentiment is outside the paper's scope; any later expansion beyond the current
codebook coverage should be treated as a new analysis phase. See
`planning/NEXT_STEPS.md`.
