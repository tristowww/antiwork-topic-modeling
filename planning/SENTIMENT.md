# Whole-Corpus Context-Aware Sentiment Check

## Purpose

This is a separate descriptive check of whether the deliberately
problem-oriented management-term sample is predominantly negative under a
context-aware sentiment model. It does not change the BERTopic theme analysis,
and it is not a target-specific measure of sentiment about management.

## Method

- Unit: one public r/antiwork submission, combining title and body after
  removing archive placeholders.
- Population: all 97,254 posts retained by the existing management-term filter.
- Model: `cardiffnlp/twitter-roberta-base-sentiment-latest` at revision
  `3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7`.
- Labels: negative, neutral, and positive whole-post polarity. The model is a
  social-media RoBERTa classifier trained on 124 million tweets and fine-tuned
  on TweetEval, rather than a lexical VADER-style scorer.
- Inputs: near-raw title plus body. User handles and URLs receive the model
  card's placeholder normalization. The token limit is 512; the run records
  the number and share of posts that are truncated.
- Outputs: hard-label shares, mean posterior probabilities, confidence
  diagnostics, and rolling-window/monthly results. Per-post labels remain local
  because they are derived from the archived post data.
- Execution: ONNX Runtime's CPU provider runs a cached export of the same pinned
  classifier. This accelerates inference only; it is not a second model or a
  separate analytic method.

## Run

```powershell
.\.venv\Scripts\python.exe -m src.sentiment --overwrite
.\.venv\Scripts\python.exe -m src.theme_sentiment
```

## Theme And Longitudinal Analysis

`src.theme_sentiment` joins the fixed post-level probabilities to the
full-corpus BERTopic document assignments and the included 27-cluster,
nine-theme codebook. It exports overall, rolling-window, and monthly estimates
for each reviewed theme, with a three-month negative-probability figure.

Theme sentiment is conditional on assignment to an included candidate-theme
cluster. It must not be confused with theme prevalence: prevalence is the share
of all filtered posts captured by a theme, while sentiment is the model's
whole-post polarity distribution within that theme. Both measures should carry
the codebook's 19.0%-of-corpus coverage limitation.

## Interpretation Boundary

The resulting proportions are model-based estimates of whole-post polarity.
They can provide convergent evidence that this sampling frame is
problem-oriented, but they are not human-validated sentiment labels, do not
identify the target of a post's affect, and cannot establish that any issue is
more important than another. Report both hard-label and probability-weighted
distributions, the confidence diagnostics, and the truncation rate.

## Sources

- Cardiff NLP, Twitter-RoBERTa sentiment model card:
  https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest
- Barbieri et al. (2020), TweetEval:
  https://aclanthology.org/2020.findings-emnlp.148/
