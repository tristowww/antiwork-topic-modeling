# Antiwork Longitudinal Topic Modeling

## Context

The 2023 SIOP poster (*Themes in Discontent with Management in the Great Resignation: A Social Media Study*, Mitropoulos & Minton) applied LDA to ~6,132 r/antiwork **post titles** from March 2021 – February 2022 filtered on "boss / manager / supervisor / team lead", and identified six themes: Scheduling, Holidays, Leaving, COVID-19, Desires, Compensation. The work was presented as a poster but never published as a peer-reviewed paper.

Three years later, two things have changed:

1. **The Great Resignation ended** — the 2023–2025 labor market normalized. Themes that were COVID-driven (sick-leave communication, holiday staffing during Omicron) should fade if the original signal was real, while structural complaints (compensation, scheduling) should persist. **This is a falsifiable empirical claim — and a publishable one.**
2. **Topic modeling moved on** — embedding-based methods such as BERTopic use semantic document representations rather than only bag-of-words counts. Stem-based preprocessing ("manag", "schedul", "christma") is no longer the standard.

## Goal

Produce a **peer-reviewable paper** that does two things:

1. **Revisits the original 2021–2022 research question with modern methods** — same time window and filter, but an updated semantic topic-modeling pipeline. The original six themes provide historical context, not a required model-replication target.
2. **Extends longitudinally to early 2025** — three additional years (Feb 2022 – Feb 2025), divided into comparable windows, to track which management-discontent themes were transient (COVID-bound) vs. structural.

Target venue: TBD (see Open Questions). Likely *Journal of Business and Psychology*, *Journal of Applied Psychology*, *Computers in Human Behavior*, or back to SIOP as a paper rather than a poster.

## Scope

### In scope

- Re-scrape r/antiwork posts March 2021 – Feb 2025 (titles **and** bodies)
- Same filter terms as original: "boss(es) / manager(s) / supervisor(s) / team lead(ers)"
- Modern preprocessing: lemmatization, noun-phrase detection, no aggressive stemming
- Primary topic model: **BERTopic** with sentence embeddings
- Historical comparison to the original six reported themes without making LDA a required analytic path
- Coherence-score-justified k selection (c_v / NPMI), not eyeballing
- Per-window topic fits + cross-window topic alignment via Jaccard / cosine on top-N terms
- Stability checks (multi-seed runs)
- Prevalence trend lines per theme across the full timeline
- Exploratory review of a documented cluster-to-theme codebook, with coverage and uncertainty reported alongside every result
- No sentiment overlay in the current exploratory paper. A target-aware LLM-assisted sentiment study remains a future extension and will not substitute for human validation; no lexical VADER baseline

### Out of scope (for now)

- Cross-subreddit comparison (r/jobs, r/recruitinghell)
- Author-level demographics or panel-style analysis (Reddit doesn't support it cleanly)
- Causal claims about the labor market — this is a descriptive thematic study

## Key Decisions

| Decision | Choice | Rationale | Status |
|---|---|---|---|
| Time window | Mar 2021 – Feb 2025 (4 yearly windows) | Year 1 = Great Resignation; Year 2 = post-Omicron normalization; Year 3 = "Quiet quitting" / RTO debate; Year 4 = labor cooling | Pending sign-off |
| Corpus | Titles **+** bodies | Bodies were collected but unused in original; cheap leverage on signal | Pending sign-off |
| Primary topic model | BERTopic with **all-MiniLM-L6-v2** embeddings, KeyBERT-inspired keywords, and MMR term diversification. all-mpnet-base-v2 is deferred as a future subsample-only sanity check because it did not finish within the available CPU runtime bound. | The current pipeline uses auditable topic terms and deterministic sampled posts rather than unvalidated external LLM labels. Completed robustness evidence is documented in `planning/ROBUSTNESS.md`. | Updated 2026-07-24 |
| Robustness model | **TopicGPT** (Pham et al., NAACL 2024) secondary run on stratified ~5,000-post subsample (1,250 per rolling window) | Convergence with BERTopic = robustness story; divergence = finding to investigate; demonstrates methodological seriousness against 2024-era LLM topic-modeling SOTA | Decided 2026-04-27 |
| Supplementary model | No LDA analysis is required for the current exploratory paper. The existing historical LDA outputs may be cited only as context for the original study. | Keeps the paper focused on the updated semantic method rather than splitting the evidence across incompatible primary analyses. | Updated 2026-07-24 |
| Preprocessing | Lemmatization (spaCy), no stemming | Cleaner outputs; "manage" reads better than "manag" | Pending sign-off |
| k selection | Coherence-score curve (c_v) across k=2–20 | Removes "I picked it because it looked nice" reviewer attack | Pending sign-off |
| Longitudinal alignment | Per-window topic fit + Jaccard alignment on top-N terms | Simpler than Dynamic Topic Models, defensible, interpretable | Pending sign-off |
| Stack | Python (sentence-transformers + BERTopic + spaCy + gensim for LDA) | BERTopic has no first-class R port | Pending sign-off |
| Project location | `C:\Users\v-tristow\OneDrive\Antiwork Topic Modeling\` (current) | OneDrive sync risk is low without auto-commits; keep where data already lives | Pending sign-off |
| Window scheme | Rolling Mar–Feb (primary, matches original) + calendar year (secondary, robustness) | Rolling preserves continuity with original; calendar bins make cross-year comparison cleaner | Decided 2026-04-25 |
| Scraper | Arctic Shift primary (full 2005-12 → 2026-02 archive, no registration); Academic Torrents per-subreddit split as offline backup; PRAW for spot-check verification of individual post IDs only | Arctic Shift covers the full Mar 2021 – Feb 2025 window in one source with no API limits or approval friction; Pushshift direct is moderator-only and Reddit's researcher program is too slow | Decided 2026-04-25 |
| Authorship | Mitropoulos (1st) & Ristow (2nd) | New paper; Ristow replaces Minton | Decided 2026-04-25 |
| Target venue | IO psychology journal (e.g. *Journal of Business and Psychology*, *Journal of Applied Psychology*, *Personnel Psychology*) | Matches the framing of the original SIOP work; specific journal selection deferred to Phase 6 | Decided 2026-04-25 |
| Sentiment overlay | Deferred from the current exploratory paper | No human reference set is available, so sentiment would be an unvalidated measurement rather than defensible evidence | Updated 2026-07-24 |

### Alternative if a lighter pass is preferred

If full modernization is too ambitious, the **"LDA done right"** alternative is: keep LDA, but add (a) bodies, (b) lemmatization, (c) coherence-justified k, (d) multi-seed stability. Drop BERTopic. Drop alignment to Jaccard-on-LDA-topics-per-window. This is ~60% of the work and ~80% of the publication-readiness.

## Open Questions

All five original open questions resolved 2026-04-25 — see Decisions table. New questions will land here as they emerge.

## Inputs

The following exist in the project folder and inform the work:

- `Post Content.csv` — original 6,132-post corpus (likely bodies; verify)
- `themesMngtGR_MitropoulosMinton.docx` — full SIOP paper (literature review, method, results — reusable for new paper)
- `SIOP 2023 Poster_PrintEdits.pptx` — original poster
- `LDA-*.xlsx` — original topic-term tables for k=3..10
- `stab4_wNgrams-nBossYjob (new timeframe).R` — original analysis script (reference, not reused)
- `Antiwork Plan.docx` — original Part 2 sketch (this project supersedes it)

---
*Created 2026-04-24 from conversation. Pending sign-off on Key Decisions.*
