# Antiwork Topic Modeling

Exploratory longitudinal topic modeling of management-related r/antiwork posts,
March 2021 through February 2025.

## What this repository contains

- Reproducible Python source for filtering, preprocessing, BERTopic fitting,
  theme trends, cross-window alignment, and robustness checks.
- The finalized exploratory theme codebook and collaborator-facing methods,
  findings, robustness, and writing-handoff documents.
- A dated revised manuscript draft with the updated Method, Results, Discussion,
  Table 1, and two analysis figures in `deliverables/`.
- Selected safe-to-share figures and aggregate CSV outputs.

## Current evidence boundary

The primary analysis uses a full-corpus BERTopic model over 97,254 filtered
posts. The documented 27-cluster theme map covers 18,506 posts, or 19.0% of the
full corpus and 49.3% of non-outlier assignments. Results are descriptive and
exploratory, not causal or complete-corpus prevalence estimates. No sentiment
results are reported.

## Reproduce locally

The raw corpus is deliberately excluded from GitHub. With the authorized local
data present, install dependencies and run the appropriate module:

```powershell
python -m pip install -e ".[nlp,viz]"
python -m src.collaborator_analysis --out-dir outputs/v2_clean_min25
python -m src.theme_trends --out-dir outputs/v2_clean_min25 --codebook planning/CANDIDATE_THEME_CODEBOOK.csv
python -m src.topic_alignment --out-dir outputs/v2_clean_min25 --top-n 15 --threshold 0.2
```

Read [planning/WRITING_HANDOFF.md](planning/WRITING_HANDOFF.md) for the results
that can be drafted and [planning/ROBUSTNESS.md](planning/ROBUSTNESS.md) for
the evidence boundary and sensitivity results.

To rebuild the collaborator brief from the checked-in figures and aggregate
outputs, install the optional document dependency and run:

```powershell
python -m pip install -e ".[docs]"
python scripts/build_collaborator_brief.py
```

The revised manuscript can be rebuilt with the same document dependency:

```powershell
python scripts/build_revised_manuscript.py
```

## Data handling

Raw Reddit data, cached embeddings, sampled post excerpts, virtual
environments, and non-aggregate outputs remain local and are excluded from this
repository.
