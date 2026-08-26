# Writing Handoff: Candidate Theme Analysis

Updated 2026-07-23. This packet is the current evidence base for drafting the
results and discussion. It is intentionally written to distinguish observed
candidate-theme patterns from claims outside this exploratory paper's evidence.

## One-sentence result

Across 97,254 filtered r/antiwork posts from March 2021 through February 2025,
a finalized exploratory map of 27 BERTopic clusters shows a shift away from
COVID-centered health and safety discussion and toward scheduling and time-off
discussion, while compensation, career precarity, and recruitment remain
substantial throughout the period.

## What was analyzed

- Population: 97,254 filtered posts from r/antiwork, March 2021 through
  February 2025, using the existing management-related filter.
- Model: the v2 full-corpus BERTopic assignments, with 199 non-outlier clusters
  and 37,536 assigned posts (38.6% of the full corpus).
- Codebook: 27 included clusters from the 30 largest clusters were grouped into
  nine candidate themes. Three clusters are excluded because they are generic,
  deleted, or community-meta content.
- Analytic coverage: the included candidate themes contain 18,506 posts, or
  19.0% of all filtered posts and 49.3% of posts assigned to a non-outlier
  BERTopic cluster.

The codebook is a documented exploratory interpretation of cluster terms and
sampled posts. It is not a claim that the remaining corpus has no relevant content.

## Results that can be written now

| Candidate theme | Y1 2021-22 | Y4 2024-25 | Change | Safe result language |
|---|---:|---:|---:|---|
| Health safety and attendance | 4.97% | 2.50% | -2.47 pp | Declined substantially, driven in part by the early COVID/illness cluster; not absent in the later period. |
| Scheduling hours and time off | 1.71% | 3.20% | +1.49 pp | Increased across the four rolling windows and becomes the largest mapped candidate theme in Y4. |
| Workplace authority and interpersonal conflict | 0.74% | 2.06% | +1.32 pp | Increased in the mapped performance-review and interpersonal-conflict clusters; retain the broad theme label and codebook scope caveat. |
| Compensation and pay rights | 3.52% | 3.04% | -0.48 pp | Remained one of the most prevalent mapped themes in every window, despite a moderate decline from its Y2 high. |
| Recruitment and labor market | 1.98% | 2.33% | +0.35 pp | Remained a persistent candidate theme, with a modest net increase. |
| Work arrangements and control | 1.01% | 1.35% | +0.34 pp | Remained present; the raw remote/RTO cluster shows a late-2024 increase worth describing descriptively. |
| Career precarity and exit | 2.54% | 2.47% | -0.07 pp | Remained stable at the candidate-theme level. |
| Collective worker power and rights | 0.82% | 0.42% | -0.40 pp | Declined after the earlier unionization peak in this mapped subset. |
| Service work and tips | 1.32% | 0.93% | -0.39 pp | Declined in the mapped subset; the retained tipping cluster includes some lexical false positives, as documented in the codebook. |

All shares use every filtered post in the same rolling window as denominator.
They are descriptive prevalence estimates for the mapped subset, not causal
effects and not complete-theme prevalence estimates for the entire corpus.

## Figures and tables for the draft

1. `outputs/v2_clean_min25/figures/monthly_assignment_coverage.png`
   - Method/results caveat figure. Show early because it establishes that raw
     BERTopic clusters cover only 33.1% to 44.0% of posts by month.
2. `outputs/v2_clean_min25/figures/candidate_theme_monthly_prevalence.png`
   - Main candidate-theme trend figure. Nine small multiples, three-month
     smoothing, denominator is all filtered posts.
3. `outputs/v2_clean_min25/figures/candidate_theme_rolling_window_prevalence.png`
   - Compact window-to-window comparison for a Results section or slide.
4. `outputs/v2_clean_min25/analysis/candidate_theme_summary.csv`
   - Exact counts, coverage, and peaks for a table or appendix.
5. `planning/CANDIDATE_THEME_CODEBOOK.csv`
   - Audit trail for every included and excluded raw cluster.

## Suggested results structure

1. **Model coverage and codebook scope.** State the full-corpus size, 38.6%
   non-outlier assignment rate, and candidate-theme coverage. This keeps the
   evidence boundary visible before thematic claims.
2. **A changing health and time-off pattern.** Describe the sharp early
   COVID-centered health/safety concentration and the later rise of scheduling,
   PTO, vacation, and break-related clusters.
3. **Persistent economic and career concerns.** Describe compensation, career
   precarity/exit, and recruitment as present across all four windows. Avoid
   describing this as an unchanged social condition; it is persistence in the
   mapped discussion.
4. **Workplace control and collective action.** Discuss remote/RTO, worker
   power, and interpersonal authority as separate candidate streams, retaining
   the codebook scope caveat where relevant.
5. **Limitations.** Explain the outlier rate, incomplete codebook coverage,
   text-mode sensitivity, filtered sampling frame, and absence of sentiment
   measurement.

## Language to avoid

- "The theme disappeared" or "workers stopped discussing X."
- "The prevalence of all work problems rose or fell."
- Causal claims about policy, labor-market changes, or the pandemic.
- Any sentiment conclusion. Sentiment is out of scope for this exploratory paper.
- Calling the current map a final taxonomy or calling LLM labels ground truth.

## Before a final paper draft

1. Extend the codebook beyond the 30 largest clusters or run a targeted saved-
   model sensitivity analysis if the paper needs claims beyond the mapped 19.0%
   of the corpus.
2. Preserve all current figures and CSVs as the versioned evidence set for this
   draft cycle.
