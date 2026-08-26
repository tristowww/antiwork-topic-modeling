"""spaCy-based preprocessing for the r/antiwork corpus.

Lemmatizes (NOT stems), removes stopwords + punct + numbers, drops the four
search-term lemmas plus 'work' / 'job', and removes 'team lead' / 'team leader'
two-token phrases.

Diverges from the original R quanteda+Porter pipeline; see
planning/PREPROCESSING.md for the rationale per choice.

Usage:
    python -m src.preprocess
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd
import spacy
from spacy.language import Language
from spacy.tokens import Doc
from tqdm import tqdm

# Search-term lemmas + 'work' / 'job' — same intent as the original R pipeline,
# but expressed as lemmas (boss, manager, manage, supervisor, supervise) rather
# than stems (boss, manag, supervisor).
BLOCKED_LEMMAS: set[str] = {
    "boss",
    "manager",
    "manage",
    "supervisor",
    "supervise",
    "job",
    "work",
}

# Two-token phrases to drop after tokenization. Original R script handled these
# via quanteda phrase matching after stemming; we apply post-lemmatization.
BLOCKED_PHRASES: set[tuple[str, str]] = {
    ("team", "lead"),
    ("team", "leader"),
}


def _drop_blocked_phrases(tokens: list[str]) -> list[str]:
    if len(tokens) < 2:
        return tokens
    keep = [True] * len(tokens)
    i = 0
    while i < len(tokens) - 1:
        if (tokens[i], tokens[i + 1]) in BLOCKED_PHRASES:
            keep[i] = keep[i + 1] = False
            i += 2
        else:
            i += 1
    return [t for t, k in zip(tokens, keep) if k]


def make_nlp() -> Language:
    """Load spaCy en_core_web_sm with parser/ner disabled (lemma-only path)."""
    return spacy.load("en_core_web_sm", disable=["parser", "ner"])


def preprocess_doc(doc: Doc) -> list[str]:
    tokens: list[str] = []
    for tok in doc:
        if tok.is_stop or tok.is_punct or tok.is_space or tok.like_num:
            continue
        lemma = tok.lemma_.lower().strip()
        if not lemma or not lemma.isalpha():
            continue
        if lemma in BLOCKED_LEMMAS:
            continue
        tokens.append(lemma)
    return _drop_blocked_phrases(tokens)


def preprocess_series(
    texts: pd.Series,
    nlp: Language,
    *,
    batch_size: int = 256,
    desc: str = "spacy",
) -> list[list[str]]:
    """Run nlp.pipe() over a Series and return per-row token lists."""
    n = len(texts)

    def _iter_strings():
        for v in texts:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                yield ""
            else:
                yield str(v)

    out: list[list[str]] = []
    for doc in tqdm(nlp.pipe(_iter_strings(), batch_size=batch_size), total=n, desc=desc):
        out.append(preprocess_doc(doc))
    return out


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Preprocess corpus with spaCy lemmatization")
    parser.add_argument(
        "--in",
        dest="in_path",
        default="data/processed/posts_2021-03_to_2025-02.parquet",
    )
    parser.add_argument(
        "--out",
        default="data/processed/posts_preprocessed.parquet",
    )
    args = parser.parse_args()

    in_path = Path(args.in_path)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(in_path)
    print(f"Loaded {len(df):,} posts from {in_path}")

    nlp = make_nlp()
    print(f"spaCy pipeline: {nlp.pipe_names}")

    df["tokens_title"] = preprocess_series(df["title"], nlp, desc="title")
    df["tokens_body"] = preprocess_series(df["body"], nlp, desc="body ")

    df["text_lemmatized_title"] = df["tokens_title"].apply(lambda toks: " ".join(toks))
    df["text_lemmatized_body"] = df["tokens_body"].apply(lambda toks: " ".join(toks))

    keep_cols = [
        "id",
        "created_utc",
        "rolling_window",
        "calendar_window",
        "calendar_window_complete",
        "title",
        "body",
        "tokens_title",
        "tokens_body",
        "text_lemmatized_title",
        "text_lemmatized_body",
    ]
    out_df = df[keep_cols].copy()

    out_df.to_parquet(out_path, index=False, compression="snappy")

    print(f"\nWrote {len(out_df):,} preprocessed posts -> {out_path}")
    print(f"  Avg title tokens after preprocessing: {out_df['tokens_title'].str.len().mean():.1f}")
    print(f"  Avg body tokens after preprocessing:  {out_df['tokens_body'].str.len().mean():.1f}")
    print(f"  Posts with empty title tokens: {(out_df['tokens_title'].str.len() == 0).sum():,}")
    print(f"  Posts with empty body tokens:  {(out_df['tokens_body'].str.len() == 0).sum():,}")


if __name__ == "__main__":
    main()
