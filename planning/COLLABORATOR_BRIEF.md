# Antiwork topic modeling: current findings and decisions

## Bottom line

We have a reproducible, exploratory topic-modeling baseline over 97,254
management-related r/antiwork posts from March 2021 through February 2025. It
reveals several interpretable candidate clusters, but only 38.6% of posts are
assigned to a non-outlier cluster. This is an exploratory topic-prevalence
study: it will use a documented codebook, coverage-aware trends, and robustness
checks. It will not present a sentiment overlay.

## What the current run shows

| Measure | Current result | Meaning |
|---|---:|---|
| Filtered corpus | 97,254 posts | Complete analysis population |
| Monthly periods | 48 | March 2021 to February 2025 |
| Non-outlier BERTopic clusters | 199 | Exploratory candidate clusters |
| Assigned posts | 37,536 (38.6%) | The part currently covered by named clusters |
| HDBSCAN outliers | 59,718 (61.4%) | A coverage limitation, not a substantive theme |
| Assignment coverage by month | 33.1% to 44.0% | Raw prevalence comparisons need this context |

The larger, readable clusters include hiring/interviews, pay raises and salary,
COVID/illness, paychecks, remote/RTO, resignation, scheduling, PTO, and
unionization. The two attached figures make the pattern concrete:

- `outputs/v2_clean_min25/figures/monthly_assignment_coverage.png`
- `outputs/v2_clean_min25/figures/monthly_anchor_topic_prevalence.png`

Examples of descriptive patterns worth discussing: the COVID cluster peaks in
early 2021-22; the remote/RTO cluster rises again late in 2024; the pay-raise
cluster is stronger in 2021-22 than at the end of the period. These are
candidate interpretations only. They do not establish causes or complete-theme
prevalence.

## Candidate theme analysis now available

A finalized exploratory codebook maps 27 of the 30 largest clusters into nine
candidate themes. It covers 18,506 posts: 19.0% of the full filtered corpus and
49.3% of non-outlier topic assignments. The three excluded clusters are generic,
deleted, or community-meta content. This is enough for an evidence-bounded
writing story, not a complete taxonomy of the corpus.

- Health safety and attendance falls from 4.97% of filtered posts in Y1 to
  2.50% in Y4, primarily because the early COVID cluster contracts.
- Scheduling hours and time off rises from 1.71% to 3.20%, becoming the largest
  mapped candidate theme in Y4.
- Compensation and pay rights remains substantial in every window, moving from
  3.52% in Y1 to 3.04% in Y4 after a Y2 high.
- Career precarity and exit stays near 2.5%, while recruitment remains present
  and collective-worker-power discussion declines within the mapped subset.

Use `planning/WRITING_HANDOFF.md` for approved phrasing, exact evidence, and
the limits that need to travel with these results.

## What we should not claim yet

- That a theme disappeared, emerged, or persisted in the full conversation.
- That negative sentiment increased or decreased.
- That a monthly topic change is causal.
- That BERTopic's raw labels are the final analytic themes.

The previous greedy cross-window term-overlap alignment is directionally useful,
but it allows many source clusters to map to the same target cluster. It needs
unique or bidirectional matching and codebook finalization before it supports a
longitudinal persistence claim.

## Decisions for this meeting

1. **Coverage strategy:** Keep the current model as exploratory discovery and
   make the 19.0% all-post theme-map coverage visible in results.
2. **Robustness interpretation:** Treat unique Jaccard alignment as a
   conservative persistence diagnostic and title-only divergence as a stated
   text-length sensitivity, not as disconfirmation of the defined primary model.
3. **Writing boundary:** Keep the manuscript descriptive and exploratory:
   topic prevalence, persistence, emergence, and bounded interpretations, not
   sentiment, causal mechanisms, or a complete taxonomy of r/antiwork.

## Immediate deliverables

- `outputs/v2_clean_min25/analysis/topic_review_posts.csv`: 120 deterministic
  review posts from the 30 largest clusters.
- `outputs/v2_clean_min25/analysis/topic_overview.csv`: cluster sizes, terms,
  coverage, and peaks.
- `planning/CANDIDATE_THEME_CODEBOOK.csv`: the finalized exploratory raw-cluster map.
- `outputs/v2_clean_min25/figures/candidate_theme_monthly_prevalence.png` and
  `candidate_theme_rolling_window_prevalence.png`: writing-ready trend figures.
- `planning/WRITING_HANDOFF.md`: the narrative, results table, and caveats for
  a draft handoff.
- `planning/ROBUSTNESS.md`: corpus audit, seed stability, text-mode sensitivity,
  and cross-window alignment results.

## Recommendation

Approve the exploratory analysis path: finalized codebook, coverage-aware trend
results, and robustness checks. Keep v2 as the exploratory baseline while we
decide whether a coverage-sensitive BERTopic refit adds enough value to justify
it. This path makes the evidence transparent without claiming validated
sentiment or a definitive taxonomy.
