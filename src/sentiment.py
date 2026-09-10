"""Context-aware, whole-corpus sentiment scoring for r/antiwork posts.

This module uses a supervised RoBERTa classifier, not a lexicon method. It
scores each non-empty title-plus-body post with negative, neutral, and positive
posterior probabilities, then exports aggregate results and a local-only
per-post audit file. The labels describe whole-post expressed polarity; they
are not target-specific management sentiment and are not human ground truth.

Usage:
    python -m src.sentiment --overwrite
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import onnxruntime
from tqdm import tqdm
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer


DEFAULT_MODEL = "cardiffnlp/twitter-roberta-base-sentiment-latest"
# Pin the model revision used to generate the published aggregate estimates.
DEFAULT_REVISION = "3216a57f2a0d9c45a2e6c20157c20c49fb4bf9c7"
DEFAULT_INPUT = "data/processed/posts_2021-03_to_2025-02.parquet"
DEFAULT_OUTPUT = "outputs/sentiment/twitter_roberta_base_sentiment_latest"
DEFAULT_ONNX_DIR = "outputs/sentiment/model_cache/twitter_roberta_base_sentiment_latest_onnx"
LABEL_ORDER = ("negative", "neutral", "positive")


def clean_social_text(value: object) -> str:
    """Clean archive placeholders and apply the model card's social-text normalization."""
    text = str(value or "")
    text = text.replace("[deleted]", "").replace("[removed]", "")
    normalized = []
    for token in text.split():
        if token.startswith("@") and len(token) > 1:
            normalized.append("@user")
        elif token.startswith("http"):
            normalized.append("http")
        else:
            normalized.append(token)
    return " ".join(normalized).strip()


def prepare_posts(posts: pd.DataFrame) -> pd.DataFrame:
    """Construct the near-raw title-plus-body field and retain only audit metadata."""
    titles = posts["title"].map(clean_social_text)
    bodies = posts["body"].map(clean_social_text)
    prepared = posts[[
        "id",
        "created_utc",
        "rolling_window",
        "calendar_window",
        "calendar_window_complete",
    ]].copy()
    prepared["text"] = (titles + " " + bodies).str.strip()
    return prepared[prepared["text"].str.len() > 0].reset_index(drop=True)


def _load_model(model_name: str, revision: str, onnx_dir: Path, threads: int):
    """Load the cached ONNX model or export the pinned PyTorch checkpoint once."""
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    if onnx_dir.exists() and any(onnx_dir.iterdir()):
        tokenizer = AutoTokenizer.from_pretrained(onnx_dir)
        model = ORTModelForSequenceClassification.from_pretrained(
            onnx_dir,
            provider="CPUExecutionProvider",
            session_options=options,
        )
        exported = False
    else:
        tokenizer = AutoTokenizer.from_pretrained(model_name, revision=revision)
        model = ORTModelForSequenceClassification.from_pretrained(
            model_name,
            revision=revision,
            export=True,
            provider="CPUExecutionProvider",
            session_options=options,
        )
        onnx_dir.mkdir(parents=True, exist_ok=True)
        tokenizer.save_pretrained(onnx_dir)
        model.save_pretrained(onnx_dir)
        exported = True
    labels = {int(key): str(value).lower() for key, value in model.config.id2label.items()}
    if tuple(labels[index] for index in sorted(labels)) != LABEL_ORDER:
        raise ValueError(f"Expected labels {LABEL_ORDER}; found {labels}")
    return tokenizer, model, labels, exported


def predict_posts(
    prepared: pd.DataFrame,
    *,
    model_name: str,
    revision: str,
    batch_size: int,
    max_length: int,
    threads: int,
    onnx_dir: Path,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Score all prepared posts and return labels, posterior probabilities, and diagnostics."""
    tokenizer, model, labels, exported = _load_model(model_name, revision, onnx_dir, threads)

    texts = prepared["text"].tolist()
    token_lengths = np.fromiter(
        (len(ids) for ids in tokenizer(texts, add_special_tokens=True).input_ids),
        dtype=np.int32,
        count=len(texts),
    )
    probabilities: list[np.ndarray] = []
    for start in tqdm(range(0, len(texts), batch_size), desc="RoBERTa sentiment", unit="batch"):
        batch_texts = texts[start : start + batch_size]
        inputs = tokenizer(
            batch_texts,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="np",
        )
        logits = model(**inputs).logits
        logits = np.asarray(logits)
        shifted = logits - logits.max(axis=1, keepdims=True)
        scores = np.exp(shifted) / np.exp(shifted).sum(axis=1, keepdims=True)
        probabilities.append(scores)

    scores = np.concatenate(probabilities, axis=0)
    label_names = [labels[index] for index in range(scores.shape[1])]
    result = prepared.drop(columns="text").copy()
    for index, label in enumerate(label_names):
        result[f"p_{label}"] = scores[:, index]
    top_index = scores.argmax(axis=1)
    result["sentiment_label"] = [labels[int(index)] for index in top_index]
    result["max_probability"] = scores.max(axis=1)
    result["input_tokens"] = token_lengths
    result["truncated"] = token_lengths > max_length
    metadata = {
        "model": model_name,
        "revision": revision,
        "execution_engine": "ONNX Runtime CPUExecutionProvider",
        "onnxruntime_version": onnxruntime.__version__,
        "transformers_version": __import__("transformers").__version__,
        "max_length": max_length,
        "batch_size": batch_size,
        "threads": threads,
        "onnx_cache": str(onnx_dir),
        "onnx_exported_this_run": exported,
        "labels": label_names,
    }
    return result, metadata


def summarize(results: pd.DataFrame, *, total_input_posts: int, metadata: dict[str, object]) -> dict[str, object]:
    hard_counts = results["sentiment_label"].value_counts().reindex(LABEL_ORDER, fill_value=0)
    probability_means = {label: float(results[f"p_{label}"].mean()) for label in LABEL_ORDER}
    return {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "interpretation": "Whole-post expressed polarity estimated by a pretrained social-media RoBERTa classifier; not human-validated or target-specific management sentiment.",
        "input_posts": int(total_input_posts),
        "scored_posts": int(len(results)),
        "empty_after_placeholder_cleanup": int(total_input_posts - len(results)),
        "hard_label_counts": {label: int(hard_counts[label]) for label in LABEL_ORDER},
        "hard_label_shares": {label: float(hard_counts[label] / len(results)) for label in LABEL_ORDER},
        "mean_posterior_probability": probability_means,
        "mean_max_probability": float(results["max_probability"].mean()),
        "low_confidence_share_under_0_60": float((results["max_probability"] < 0.60).mean()),
        "truncated_posts": int(results["truncated"].sum()),
        "truncated_share": float(results["truncated"].mean()),
        "input_token_mean": float(results["input_tokens"].mean()),
        "input_token_p95": float(results["input_tokens"].quantile(0.95)),
        "model": metadata,
    }


def aggregate(results: pd.DataFrame, group_column: str) -> pd.DataFrame:
    records = []
    for group, frame in results.dropna(subset=[group_column]).groupby(group_column, sort=True):
        row: dict[str, object] = {group_column: group, "posts": int(len(frame))}
        for label in LABEL_ORDER:
            row[f"{label}_count"] = int((frame["sentiment_label"] == label).sum())
            row[f"{label}_hard_share"] = float((frame["sentiment_label"] == label).mean())
            row[f"{label}_mean_probability"] = float(frame[f"p_{label}"].mean())
        row["mean_max_probability"] = float(frame["max_probability"].mean())
        row["truncated_share"] = float(frame["truncated"].mean())
        records.append(row)
    return pd.DataFrame(records)


def plot_rolling_window(rolling: pd.DataFrame, path: Path) -> None:
    colors = {"negative": "#B35A27", "neutral": "#8FA6B8", "positive": "#3B7D5A"}
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for label in LABEL_ORDER:
        axes[0].plot(rolling["rolling_window"], rolling[f"{label}_hard_share"] * 100, marker="o", linewidth=2.2, color=colors[label], label=label.title())
        axes[1].plot(rolling["rolling_window"], rolling[f"{label}_mean_probability"] * 100, marker="o", linewidth=2.2, color=colors[label], label=label.title())
    axes[0].set_title("Hard-label distribution", loc="left", fontweight="bold")
    axes[1].set_title("Mean posterior distribution", loc="left", fontweight="bold")
    for axis in axes:
        axis.set_ylim(0, 100)
        axis.set_ylabel("Share of scored posts")
        axis.yaxis.set_major_formatter("{x:.0f}%")
        axis.grid(axis="y", alpha=0.25)
        axis.spines[["top", "right"]].set_visible(False)
        axis.legend(frameon=False, ncol=3, loc="upper center")
    fig.suptitle("Whole-corpus RoBERTa sentiment by rolling window", x=0.08, ha="left", fontweight="bold", fontsize=14)
    fig.text(0.08, 0.02, "Context-aware model estimates of whole-post polarity, not human-validated or target-specific management sentiment.", fontsize=8.5, color="#475569")
    fig.tight_layout(rect=[0, 0.06, 1, 0.92])
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the r/antiwork corpus with a contextual RoBERTa sentiment classifier.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--out-dir", default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--revision", default=DEFAULT_REVISION)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--threads", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument("--onnx-dir", default=DEFAULT_ONNX_DIR)
    parser.add_argument("--limit", type=int, help="Optional diagnostic-only cap; omit for the full corpus.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    started = time.perf_counter()

    out_dir = Path(args.out_dir)
    if out_dir.exists() and any(out_dir.iterdir()) and not args.overwrite:
        raise FileExistsError(f"{out_dir} already contains outputs; pass --overwrite to replace this run.")
    out_dir.mkdir(parents=True, exist_ok=True)
    posts = pd.read_parquet(args.input)
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be positive.")
        posts = posts.head(args.limit).copy()
    prepared = prepare_posts(posts)
    results, metadata = predict_posts(
        prepared,
        model_name=args.model,
        revision=args.revision,
        batch_size=args.batch_size,
        max_length=args.max_length,
        threads=args.threads,
        onnx_dir=Path(args.onnx_dir),
    )
    summary = summarize(results, total_input_posts=len(posts), metadata=metadata)
    summary["run_duration_seconds"] = round(time.perf_counter() - started, 3)
    rolling = aggregate(results, "rolling_window")
    monthly_input = results.assign(month=pd.to_datetime(results["created_utc"], unit="s", utc=True).dt.strftime("%Y-%m"))
    monthly = aggregate(monthly_input, "month")
    results.to_parquet(out_dir / "sentiment_post_labels.parquet", index=False, compression="snappy")
    rolling.to_csv(out_dir / "sentiment_by_rolling_window.csv", index=False)
    monthly.to_csv(out_dir / "sentiment_by_month.csv", index=False)
    (out_dir / "sentiment_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    plot_rolling_window(rolling, out_dir / "sentiment_by_rolling_window.png")
    print(json.dumps(summary, indent=2))
    print(f"Wrote {out_dir}")


if __name__ == "__main__":
    main()
