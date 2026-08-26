"""Reproducible robustness checks for the exploratory BERTopic paper.

The primary model remains the full-corpus BERTopic fit. This module adds
transparent checks on the frozen input corpus and on clustering stability across
multiple UMAP random seeds using the same stratified document sample.
"""
from __future__ import annotations

import argparse
import json
import re
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

from src.filter import FILTER_PATTERN


WINDOWS = ("Y1_2021-22", "Y2_2022-23", "Y3_2023-24", "Y4_2024-25")
DEFAULT_PREPROCESSED = "data/processed/posts_preprocessed.parquet"
DEFAULT_SEED = 29
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def _normalized_text(frame: pd.DataFrame) -> pd.Series:
    text = frame["title"].fillna("").astype(str) + " " + frame["body"].fillna("").astype(str)
    return text.str.lower().str.replace(r"\s+", " ", regex=True).str.strip()


def run_data_audit(filtered_path: Path, preprocessed_path: Path, out_dir: Path) -> None:
    raw = pd.read_parquet(filtered_path)
    preprocessed = pd.read_parquet(preprocessed_path)
    if raw["id"].duplicated().any() or preprocessed["id"].duplicated().any():
        raise ValueError("The filtered and preprocessed inputs must both be one row per post id.")
    if set(raw["id"]) != set(preprocessed["id"]):
        raise ValueError("The filtered and preprocessed inputs do not contain the same post ids.")

    text = _normalized_text(raw)
    created = pd.to_datetime(raw["created_utc"], unit="s", utc=True)
    monthly = pd.DataFrame({"month": created.dt.tz_localize(None).dt.to_period("M").astype(str)})
    monthly = monthly.groupby("month", as_index=False).size().rename(columns={"size": "post_count"})

    title = raw["title"].fillna("").astype(str)
    body = raw["body"].fillna("").astype(str)
    placeholder = title.str.contains(r"^\s*\[(?:deleted|removed)\]\s*$", case=False, regex=True) | body.str.contains(
        r"^\s*\[(?:deleted|removed)\]\s*$", case=False, regex=True
    )
    substantive_text = text[~placeholder & text.ne("")]
    metrics = {
        "filtered_posts": int(len(raw)),
        "preprocessed_posts": int(len(preprocessed)),
        "unique_ids": int(raw["id"].nunique()),
        "exact_duplicate_normalized_text_rows": int(text.duplicated(keep=False).sum()),
        "exact_duplicate_normalized_text_groups": int(text[text.duplicated(keep=False)].nunique()),
        "exact_duplicate_nonplaceholder_rows": int(substantive_text.duplicated(keep=False).sum()),
        "exact_duplicate_nonplaceholder_groups": int(substantive_text[substantive_text.duplicated(keep=False)].nunique()),
        "empty_title_rows": int(title.str.strip().eq("").sum()),
        "empty_body_rows": int(body.str.strip().eq("").sum()),
        "deleted_or_removed_field_rows": int(placeholder.sum()),
        "filter_match_rate": round(float((title + " " + body).map(lambda value: bool(FILTER_PATTERN.search(value))).mean()), 6),
        "min_monthly_posts": int(monthly["post_count"].min()),
        "max_monthly_posts": int(monthly["post_count"].max()),
        "median_title_characters": round(float(title.str.len().median()), 1),
        "median_body_characters": round(float(body.str.len().median()), 1),
        "p95_body_characters": round(float(body.str.len().quantile(0.95)), 1),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(out_dir / "data_quality_monthly_volume.csv", index=False)
    (out_dir / "data_quality_audit.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print(f"wrote {out_dir / 'data_quality_monthly_volume.csv'}")
    print(f"wrote {out_dir / 'data_quality_audit.json'}")


def _stable_sample(frame: pd.DataFrame, per_window: int, seed: int) -> pd.DataFrame:
    samples = []
    for window in WINDOWS:
        group = frame[frame["rolling_window"].eq(window)].copy()
        if len(group) < per_window:
            raise ValueError(f"Window {window} has only {len(group)} rows; need {per_window}.")
        key = pd.util.hash_pandas_object(group["id"].astype(str) + f"|stability|{seed}", index=False)
        samples.append(group.assign(_stable_key=key).sort_values("_stable_key").head(per_window))
    return pd.concat(samples, ignore_index=True).drop(columns="_stable_key")


def _cluster_embeddings(embeddings: np.ndarray, seed: int, min_cluster_size: int) -> np.ndarray:
    from src.bertopic_primary import make_hdbscan, make_umap

    reduced = make_umap(seed=seed).fit_transform(embeddings)
    return make_hdbscan(min_cluster_size=min_cluster_size).fit_predict(reduced)


def run_seed_stability(
    preprocessed_path: Path,
    out_dir: Path,
    *,
    per_window: int,
    sample_seed: int,
    seeds: list[int],
    min_cluster_size: int,
    embedding_model_name: str,
    text_mode: str,
) -> None:
    from src.bertopic_primary import make_embedding_model, prepare_documents

    source = pd.read_parquet(preprocessed_path)
    sample = prepare_documents(_stable_sample(source, per_window, sample_seed), text_mode=text_mode)
    cache_dir = out_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = re.sub(r"[^A-Za-z0-9._-]+", "_", embedding_model_name)
    if text_mode == "title_body" and embedding_model_name == EMBEDDING_MODEL_NAME and len(sample) == 10_000:
        prefix = "seed_stability"
    elif text_mode == "title" and embedding_model_name == EMBEDDING_MODEL_NAME and len(sample) == 10_000:
        prefix = "seed_stability_title"
    else:
        prefix = f"seed_stability_{text_mode}_{len(sample)}_{cache_key}"
    embedding_path = cache_dir / f"{prefix}_{len(sample)}_{cache_key}_embeddings.npz"
    sample_path = cache_dir / f"{prefix}_{len(sample)}_sample.csv"
    if embedding_path.exists() and sample_path.exists():
        embeddings = np.load(embedding_path)["embeddings"]
        cached_ids = pd.read_csv(sample_path)["id"].astype(str).tolist()
        if cached_ids != sample["id"].astype(str).tolist():
            raise ValueError("Cached embeddings do not match the deterministic stability sample.")
        print(f"loaded cached embeddings: {embedding_path}")
    else:
        model = make_embedding_model(embedding_model_name)
        embeddings = model.encode(sample["_doc_text"].tolist(), show_progress_bar=True, normalize_embeddings=True)
        np.savez_compressed(embedding_path, embeddings=embeddings)
        sample[["id", "rolling_window", "title"]].to_csv(sample_path, index=False)
        print(f"wrote {embedding_path}")
        print(f"wrote {sample_path}")

    assignments = sample[["id", "rolling_window"]].copy()
    summary_rows = []
    for seed in seeds:
        labels = _cluster_embeddings(embeddings, seed=seed, min_cluster_size=min_cluster_size)
        assignments[f"topic_seed_{seed}"] = labels
        summary_rows.append({
            "seed": seed,
            "documents": int(len(labels)),
            "non_outlier_topics": int(len(set(labels)) - int(-1 in labels)),
            "assigned_rate": float(np.mean(labels != -1)),
            "outlier_rate": float(np.mean(labels == -1)),
        })

    pairwise = []
    for left, right in combinations(seeds, 2):
        a = assignments[f"topic_seed_{left}"].to_numpy()
        b = assignments[f"topic_seed_{right}"].to_numpy()
        joint_inliers = (a != -1) & (b != -1)
        pairwise.append({
            "seed_a": left,
            "seed_b": right,
            "inlier_membership_jaccard": float(np.sum(joint_inliers) / np.sum((a != -1) | (b != -1))),
            "ari_all_documents": float(adjusted_rand_score(a, b)),
            "ari_joint_inliers": float(adjusted_rand_score(a[joint_inliers], b[joint_inliers])) if np.sum(joint_inliers) > 1 else None,
            "joint_inlier_documents": int(np.sum(joint_inliers)),
        })

    assignments.to_csv(out_dir / f"{prefix}_assignments.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(out_dir / f"{prefix}_run_summary.csv", index=False)
    pd.DataFrame(pairwise).to_csv(out_dir / f"{prefix}_pairwise.csv", index=False)
    metrics = {
        "sample_documents": int(len(sample)),
        "documents_per_window": int(per_window),
        "sample_seed": int(sample_seed),
        "clustering_seeds": seeds,
        "min_cluster_size": int(min_cluster_size),
        "embedding_model": embedding_model_name,
        "text_mode": text_mode,
        "runs": summary_rows,
        "pairwise": pairwise,
    }
    (out_dir / f"{prefix}_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))


def compare_text_modes(out_dir: Path, seed: int) -> None:
    """Compare title-only and title-plus-body partitions on shared sample ids."""
    full = pd.read_csv(out_dir / "seed_stability_assignments.csv")[["id", f"topic_seed_{seed}"]]
    title = pd.read_csv(out_dir / "seed_stability_title_assignments.csv")[["id", f"topic_seed_{seed}"]]
    joined = full.merge(title, on="id", suffixes=("_title_body", "_title"), validate="one_to_one")
    a = joined[f"topic_seed_{seed}_title_body"].to_numpy()
    b = joined[f"topic_seed_{seed}_title"].to_numpy()
    joint_inliers = (a != -1) & (b != -1)
    metrics = {
        "seed": seed,
        "shared_documents": int(len(joined)),
        "title_body_assigned_rate": float(np.mean(a != -1)),
        "title_only_assigned_rate": float(np.mean(b != -1)),
        "inlier_membership_jaccard": float(np.sum(joint_inliers) / np.sum((a != -1) | (b != -1))),
        "ari_all_documents": float(adjusted_rand_score(a, b)),
        "ari_joint_inliers": float(adjusted_rand_score(a[joint_inliers], b[joint_inliers])) if np.sum(joint_inliers) > 1 else None,
        "joint_inlier_documents": int(np.sum(joint_inliers)),
    }
    (out_dir / "title_only_vs_title_body_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))


def compare_embedding_models(out_dir: Path, seed: int, left_file: Path, right_file: Path) -> None:
    """Compare two encoder-based partitions on the same sampled document ids."""
    column = f"topic_seed_{seed}"
    left = pd.read_csv(left_file)[["id", column]]
    right = pd.read_csv(right_file)[["id", column]]
    joined = left.merge(right, on="id", suffixes=("_left", "_right"), validate="one_to_one")
    a = joined[f"{column}_left"].to_numpy()
    b = joined[f"{column}_right"].to_numpy()
    joint_inliers = (a != -1) & (b != -1)
    metrics = {
        "seed": seed,
        "left_file": left_file.name,
        "right_file": right_file.name,
        "shared_documents": int(len(joined)),
        "left_assigned_rate": float(np.mean(a != -1)),
        "right_assigned_rate": float(np.mean(b != -1)),
        "inlier_membership_jaccard": float(np.sum(joint_inliers) / np.sum((a != -1) | (b != -1))),
        "ari_all_documents": float(adjusted_rand_score(a, b)),
        "ari_joint_inliers": float(adjusted_rand_score(a[joint_inliers], b[joint_inliers])) if np.sum(joint_inliers) > 1 else None,
        "joint_inlier_documents": int(np.sum(joint_inliers)),
    }
    (out_dir / "embedding_model_sensitivity_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run exploratory-paper robustness checks")
    parser.add_argument("--out-dir", default="outputs/v2_clean_min25/analysis/robustness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit = subparsers.add_parser("data-audit", help="Audit frozen corpus identity and quality")
    audit.add_argument("--filtered", default="data/processed/posts_2021-03_to_2025-02.parquet")
    audit.add_argument("--preprocessed", default=DEFAULT_PREPROCESSED)

    stability = subparsers.add_parser("seed-stability", help="Measure clustering stability across UMAP seeds")
    stability.add_argument("--preprocessed", default=DEFAULT_PREPROCESSED)
    stability.add_argument("--per-window", type=int, default=2500)
    stability.add_argument("--sample-seed", type=int, default=DEFAULT_SEED)
    stability.add_argument("--seeds", type=int, nargs="+", default=[11, 29, 47])
    stability.add_argument("--min-cluster-size", type=int, default=25)
    stability.add_argument("--embedding-model", default=EMBEDDING_MODEL_NAME)
    stability.add_argument("--text-mode", choices=("title_body", "title"), default="title_body")

    compare = subparsers.add_parser("compare-text-modes", help="Compare title-only and title-plus-body partitions")
    compare.add_argument("--seed", type=int, default=DEFAULT_SEED)

    encoder_compare = subparsers.add_parser("compare-embedding-models", help="Compare two encoder partitions")
    encoder_compare.add_argument("--seed", type=int, default=DEFAULT_SEED)
    encoder_compare.add_argument("--left-file", required=True)
    encoder_compare.add_argument("--right-file", required=True)

    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    if args.command == "data-audit":
        run_data_audit(Path(args.filtered), Path(args.preprocessed), out_dir)
    elif args.command == "compare-text-modes":
        compare_text_modes(out_dir, args.seed)
    elif args.command == "compare-embedding-models":
        compare_embedding_models(out_dir, args.seed, Path(args.left_file), Path(args.right_file))
    else:
        run_seed_stability(
            Path(args.preprocessed),
            out_dir,
            per_window=args.per_window,
            sample_seed=args.sample_seed,
            seeds=args.seeds,
            min_cluster_size=args.min_cluster_size,
            embedding_model_name=args.embedding_model,
            text_mode=args.text_mode,
        )


if __name__ == "__main__":
    main()
