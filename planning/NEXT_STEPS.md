# Next steps

Updated 2026-07-24. This is the active execution plan.

## Current state

- The corpus is complete: 577,190 raw posts and 97,254 filtered posts spanning
  March 2021 through February 2025.
- The v2 BERTopic run is complete in `outputs/v2_clean_min25/`: clean
  representation stopwords, per-document assignments, per-window fits,
  alignments, and exploratory monthly outputs.
- The v2 model is exploratory because it assigns 38.6% of posts to a non-outlier
  cluster. The coverage limitation is measured and visible, not hidden.
- The finalized exploratory codebook maps 27 of the 30 largest clusters into
  nine themes, covering 18,506 posts (19.0% of all filtered posts and 49.3% of
  assigned posts).
- Corpus audit, unique cross-window alignment, multi-seed stability, and
  titles-only sensitivity outputs are complete in `planning/ROBUSTNESS.md`.
- The current paper is explicitly exploratory. It does not include an LLM or
  lexical sentiment overlay because no human reference set is available.

## The right path forward

1. **Freeze the exploratory evidence set.** Preserve the current codebook,
   figures, CSVs, and robustness artifacts. Do not rerun the primary model just
   to improve a chart or lower the outlier rate.
2. **Draft the paper from bounded claims.** Use the writing handoff for the
   Method, Results, and limitations structure; report all-post denominators,
   assignment coverage, text-mode sensitivity, and the filtered sampling frame.
3. **Use the collaborator meeting for interpretation and writing.** Present the
   completed analysis, robustness record, figures, and draft claims. Do not ask
   the collaborator to make unfinished analytic decisions.
4. **Treat any expanded-model work as optional follow-up.** A saved-model refit,
   larger codebook, or external TopicGPT comparison is only needed if the paper
   later requires claims beyond the mapped 19.0% of the corpus.

## What to do with the collaborator now

1. Review [the writing handoff](WRITING_HANDOFF.md), the codebook, and
   `planning/ROBUSTNESS.md` before discussing narrative framing.
2. Review the bounded claims, especially the 38.6% non-outlier assignment rate,
   the 19.0% all-post theme-map coverage, and title-only sensitivity.
3. Use the meeting to discuss findings and writing implications, not to make
   uncompleted analytic decisions.

## Local commands

Regenerate the collaborator outputs after any v2 output change:

```powershell
.\.venv\Scripts\python.exe -m src.collaborator_analysis --out-dir outputs/v2_clean_min25
```

The command creates or refreshes the review files, coverage and anchor-cluster
figures, and deterministic future-sentiment samples. It does not call an LLM
or send data outside the workspace.

## What not to do

- Do not run VADER or an unvalidated LLM as a placeholder sentiment score.
- Do not present greedy Jaccard alignment as proof that a theme disappeared.
- Do not convert outliers into a substantive category.
