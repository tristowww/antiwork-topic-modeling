"""BERTopic primary topic-modeling pipeline.

Per the locked Phase 4b decision (see PROJECT.md): all-MiniLM-L6-v2
embeddings + UMAP + HDBSCAN + BERTopic representation models. The larger
all-mpnet-base-v2 model is reserved for a stratified subsample sanity check.

Inputs: data/processed/posts_preprocessed.parquet (we use the original
title + body text for embeddings; embedding models work better on
near-raw text than on lemmatized output).

Usage:
    python -m src.bertopic_primary fit-full     # fit on full corpus
    python -m src.bertopic_primary fit-windows  # fit per rolling window
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd
from bertopic import BERTopic
from bertopic.representation import KeyBERTInspired, MaximalMarginalRelevance
from hdbscan import HDBSCAN
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer, ENGLISH_STOP_WORDS
from umap import UMAP

DEFAULT_PREPROCESSED = "data/processed/posts_preprocessed.parquet"
DEFAULT_OUT_DIR = "outputs"
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_SEED = 29

# These terms are part of the sampling frame rather than the substantive topic
# signal. Removing them from BERTopic's representation vectorizer keeps labels
# focused on what differentiates topics: pay, scheduling, COVID, resignation,
# surveillance, PIPs, and so on. The embeddings still see the original text.
DOMAIN_STOP_WORDS = {
    "boss",
    "bosses",
    "manage",
    "manager",
    "managers",
    "management",
    "supervise",
    "supervisor",
    "supervisors",
    "lead",
    "leader",
    "leaders",
    "job",
    "jobs",
    "work",
    "worked",
    "working",
    "works",
}

DOCUMENT_TOPIC_COLUMNS = [
    "id",
    "created_utc",
    "rolling_window",
    "calendar_window",
    "calendar_window_complete",
    "title",
]

logger = logging.getLogger(__name__)


def _clean_reddit_placeholders(s: str) -> str:
    """Strip Reddit's '[deleted]' and '[removed]' placeholders. Returns empty string for non-strings."""
    if not isinstance(s, str):
        return ""
    return s.replace("[deleted]", "").replace("[removed]", "").strip()


def prepare_documents(df: pd.DataFrame, *, text_mode: str = "title_body") -> pd.DataFrame:
    """Clean placeholders, select analysis text, and keep metadata aligned.

    Rows whose combined cleaned text is empty are dropped. Returning a DataFrame
    instead of a bare list lets us export per-document topic assignments for
    monthly trend lines and validation samples.
    """
    titles = df["title"].fillna("").astype(str).map(_clean_reddit_placeholders)
    bodies = df["body"].fillna("").astype(str).map(_clean_reddit_placeholders)
    if text_mode == "title_body":
        combined = (titles + " " + bodies).str.strip()
    elif text_mode == "title":
        combined = titles.str.strip()
    else:
        raise ValueError(f"Unsupported text mode: {text_mode!r}")
    docs_df = df.copy()
    docs_df["_doc_text"] = combined
    return docs_df[docs_df["_doc_text"].str.len() > 0].reset_index(drop=True)


def join_text(df: pd.DataFrame) -> list[str]:
    """Backward-compatible helper that returns only document strings."""
    return prepare_documents(df)["_doc_text"].tolist()


def make_embedding_model(model_name: str = EMBEDDING_MODEL_NAME) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def make_umap(seed: int = DEFAULT_SEED) -> UMAP:
    return UMAP(
        n_neighbors=15,
        n_components=5,
        min_dist=0.0,
        metric="cosine",
        random_state=seed,
    )


def make_hdbscan(min_cluster_size: int = 50) -> HDBSCAN:
    return HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )


def make_vectorizer() -> CountVectorizer:
    """Stopword-aware vectorizer for cleaner topic representations.

    BERTopic's default CountVectorizer keeps stopwords. Without filtering,
    generic words and sampling-frame terms dominate topic representations and
    obscure content terms, which then breaks Jaccard alignment between topics.
    min_df=2 drops singleton terms.
    """
    stop_words = sorted(set(ENGLISH_STOP_WORDS) | DOMAIN_STOP_WORDS)
    return CountVectorizer(stop_words=stop_words, min_df=2, ngram_range=(1, 1))


def make_representation_models() -> dict:
    """Per-topic representation strategies. KeyBERTInspired provides semantic
    keyword extraction; MMR diversifies the resulting term lists."""
    return {
        "KeyBERT": KeyBERTInspired(),
        "MMR": MaximalMarginalRelevance(diversity=0.3),
    }


def make_model(
    *,
    min_cluster_size: int = 50,
    seed: int = DEFAULT_SEED,
    embedding_model_name: str = EMBEDDING_MODEL_NAME,
) -> BERTopic:
    return BERTopic(
        embedding_model=make_embedding_model(embedding_model_name),
        umap_model=make_umap(seed=seed),
        hdbscan_model=make_hdbscan(min_cluster_size=min_cluster_size),
        vectorizer_model=make_vectorizer(),
        representation_model=make_representation_models(),
        calculate_probabilities=False,
        verbose=True,
    )


def fit_and_export(
    docs: list[str],
    *,
    label: str,
    out_dir: Path,
    min_cluster_size: int = 50,
    seed: int = DEFAULT_SEED,
    embedding_model_name: str = EMBEDDING_MODEL_NAME,
    save_model: bool = False,
    doc_metadata: pd.DataFrame | None = None,
) -> tuple[BERTopic, list[int]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    model = make_model(
        min_cluster_size=min_cluster_size,
        seed=seed,
        embedding_model_name=embedding_model_name,
    )
    topics, _ = model.fit_transform(docs)

    topic_info = model.get_topic_info()
    topic_info_path = out_dir / f"bertopic_{label}_topic_info.csv"
    topic_info.to_csv(topic_info_path, index=False)

    rows = []
    for tid in topic_info["Topic"]:
        if tid == -1:
            continue
        terms = [w for w, _ in model.get_topic(tid)[:15]]
        rows.append({
            "topic": tid,
            "size": int(topic_info.loc[topic_info["Topic"] == tid, "Count"].values[0]),
            "name": str(topic_info.loc[topic_info["Topic"] == tid, "Name"].values[0]),
            "top_terms": " ".join(terms),
        })
    topics_df = pd.DataFrame(rows)
    topics_path = out_dir / f"bertopic_{label}_topics.csv"
    topics_df.to_csv(topics_path, index=False)

    if doc_metadata is not None:
        cols = [c for c in DOCUMENT_TOPIC_COLUMNS if c in doc_metadata.columns]
        doc_topics = doc_metadata[cols].copy()
        doc_topics["topic"] = topics
        doc_topics_path = out_dir / f"bertopic_{label}_document_topics.csv"
        doc_topics.to_csv(doc_topics_path, index=False)
        print(f"  wrote {doc_topics_path}")

    if save_model:
        model_path = out_dir / f"bertopic_{label}_model"
        model.save(
            str(model_path),
            serialization="safetensors",
            save_ctfidf=True,
            save_embedding_model=embedding_model_name,
        )
        print(f"  wrote {model_path}")

    print(f"  wrote {topic_info_path}")
    print(f"  wrote {topics_path}")
    print(f"  topics found: {len(topics_df)}  (excluding outlier topic -1)")

    return model, topics


def cmd_fit_full(args) -> None:
    out_dir = Path(args.out_dir)
    df = pd.read_parquet(args.parquet)
    print(f"Loaded {len(df):,} posts")

    docs_df = prepare_documents(df, text_mode=args.text_mode)
    docs = docs_df["_doc_text"].tolist()
    print(f"Text mode: {args.text_mode}")
    print(f"Embedding model: {args.embedding_model}")
    print(f"Min cluster size: {args.min_cluster_size}")
    print(f"After [deleted]/[removed] cleanup: {len(docs):,} non-empty docs")

    fit_and_export(
        docs,
        label="full",
        out_dir=out_dir,
        min_cluster_size=args.min_cluster_size,
        seed=args.seed,
        embedding_model_name=args.embedding_model,
        save_model=args.save_model,
        doc_metadata=docs_df,
    )


def cmd_fit_window(args) -> None:
    """Fit BERTopic on a single named rolling window."""
    out_dir = Path(args.out_dir)
    df = pd.read_parquet(args.parquet)
    win_df = df[df["rolling_window"] == args.window].reset_index(drop=True)
    if win_df.empty:
        raise SystemExit(f"No posts found for window {args.window!r}")
    print(f"=== {args.window}: {len(win_df):,} posts ===")
    docs_df = prepare_documents(win_df, text_mode=args.text_mode)
    docs = docs_df["_doc_text"].tolist()
    print(f"After [deleted]/[removed] cleanup: {len(docs):,} non-empty docs")
    fit_and_export(
        docs,
        label=args.window,
        out_dir=out_dir,
        min_cluster_size=args.min_cluster_size,
        seed=args.seed,
        embedding_model_name=args.embedding_model,
        save_model=args.save_model,
        doc_metadata=docs_df,
    )


def cmd_fit_windows(args) -> None:
    out_dir = Path(args.out_dir)
    df = pd.read_parquet(args.parquet)
    print(f"Loaded {len(df):,} posts")

    for window_label in ["Y1_2021-22", "Y2_2022-23", "Y3_2023-24", "Y4_2024-25"]:
        win_df = df[df["rolling_window"] == window_label].reset_index(drop=True)
        if win_df.empty:
            print(f"\n  skipping {window_label} (no posts)")
            continue
        print(f"\n=== {window_label}: {len(win_df):,} posts ===")
        docs_df = prepare_documents(win_df, text_mode=args.text_mode)
        docs = docs_df["_doc_text"].tolist()
        print(f"After [deleted]/[removed] cleanup: {len(docs):,} non-empty docs")
        fit_and_export(
            docs,
            label=window_label,
            out_dir=out_dir,
            min_cluster_size=args.min_cluster_size,
            seed=args.seed,
            embedding_model_name=args.embedding_model,
            save_model=args.save_model,
            doc_metadata=docs_df,
        )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="BERTopic primary pipeline")
    p.add_argument("--parquet", default=DEFAULT_PREPROCESSED)
    p.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    p.add_argument("--min-cluster-size", type=int, default=50)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--embedding-model", default=EMBEDDING_MODEL_NAME)
    p.add_argument("--text-mode", choices=("title_body", "title"), default="title_body")
    p.add_argument("--save-model", action="store_true", help="Persist the fitted BERTopic model for audit and post-hoc analysis")

    sub = p.add_subparsers(dest="cmd", required=True)
    p_full = sub.add_parser("fit-full", help="Fit BERTopic on full corpus")
    p_full.set_defaults(func=cmd_fit_full)

    p_win = sub.add_parser("fit-windows", help="Fit BERTopic per rolling window")
    p_win.set_defaults(func=cmd_fit_windows)

    p_w1 = sub.add_parser("fit-window", help="Fit BERTopic on a single rolling window")
    p_w1.add_argument("--window", required=True, help="Window label e.g. Y1_2021-22")
    p_w1.set_defaults(func=cmd_fit_window)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
