"""Cross-window topic alignment for BERTopic per-window fits.

Loads ``outputs/bertopic_<window>_topics.csv`` for each rolling window
and computes pairwise Jaccard similarity on top-N terms. Reports
best-match tables per window pair and saves alignment heatmaps.

Usage:
    python -m src.topic_alignment
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.optimize import linear_sum_assignment
from spacy.lang.en.stop_words import STOP_WORDS as SPACY_STOPWORDS

WINDOWS = ["Y1_2021-22", "Y2_2022-23", "Y3_2023-24", "Y4_2024-25"]

# Drop stopwords and sampling-frame terms from BERTopic's topic representations
# before Jaccard. This keeps generic corpus terms from inflating match scores
# between unrelated topics.
DOMAIN_NOISE_WORDS: set[str] = {
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

_NOISE_WORDS: set[str] = SPACY_STOPWORDS | {
    # very-short / domain-noisy tokens that show up frequently in BERTopic outputs
    "n", "s", "t", "m", "re", "ve", "ll", "d", "us",
    # bracketed Reddit placeholders (already filtered upstream, defensive)
    "deleted", "removed",
} | DOMAIN_NOISE_WORDS

# Drop topics that have too few content words to compare meaningfully
MIN_CONTENT_TERMS = 3


def _content_terms(top_terms_str: str, top_n: int) -> set[str]:
    """Strip stopwords/short tokens, return top_n content terms as a set."""
    tokens = str(top_terms_str).split()
    content = [t for t in tokens if t.lower() not in _NOISE_WORDS and len(t) > 2]
    return set(content[:top_n])


def load_window_topics(out_dir: Path, window_label: str, top_n: int = 15) -> pd.DataFrame:
    path = out_dir / f"bertopic_{window_label}_topics.csv"
    df = pd.read_csv(path)
    df["term_set"] = df["top_terms"].apply(lambda s: _content_terms(s, top_n))
    df["n_content_terms"] = df["term_set"].apply(len)
    return df


def jaccard_matrix(topics_a: pd.DataFrame, topics_b: pd.DataFrame) -> np.ndarray:
    sets_a = list(topics_a["term_set"])
    sets_b = list(topics_b["term_set"])
    M = np.zeros((len(sets_a), len(sets_b)))
    for i, sa in enumerate(sets_a):
        for j, sb in enumerate(sets_b):
            union = len(sa | sb)
            M[i, j] = len(sa & sb) / max(union, 1)
    return M


def best_match_table(
    topics_a: pd.DataFrame,
    topics_b: pd.DataFrame,
    M: np.ndarray,
    threshold: float = 0.2,
) -> pd.DataFrame:
    rows = []
    for i in range(len(topics_a)):
        j_best = int(np.argmax(M[i]))
        score = float(M[i, j_best])
        rows.append({
            "a_topic": int(topics_a.iloc[i]["topic"]),
            "a_size": int(topics_a.iloc[i]["size"]),
            "a_top_terms": " ".join(str(topics_a.iloc[i]["top_terms"]).split()[:8]),
            "best_match_b": int(topics_b.iloc[j_best]["topic"]),
            "b_top_terms": " ".join(str(topics_b.iloc[j_best]["top_terms"]).split()[:8]),
            "jaccard": round(score, 3),
            "matched": "Y" if score >= threshold else "N",
        })
    return pd.DataFrame(rows).sort_values("jaccard", ascending=False)


def unique_match_table(
    topics_a: pd.DataFrame,
    topics_b: pd.DataFrame,
    M: np.ndarray,
    threshold: float = 0.2,
) -> pd.DataFrame:
    """Return a one-to-one maximum-Jaccard matching between two topic sets.

    Greedy best matches are useful for discovery but allow several source topics
    to claim the same target. The Hungarian assignment gives a conservative
    longitudinal diagnostic by allowing each target topic to be used once.
    """
    rows, cols = linear_sum_assignment(-M)
    records = []
    for i, j in zip(rows, cols):
        score = float(M[i, j])
        records.append({
            "a_topic": int(topics_a.iloc[i]["topic"]),
            "a_size": int(topics_a.iloc[i]["size"]),
            "a_top_terms": " ".join(str(topics_a.iloc[i]["top_terms"]).split()[:8]),
            "unique_match_b": int(topics_b.iloc[j]["topic"]),
            "b_size": int(topics_b.iloc[j]["size"]),
            "b_top_terms": " ".join(str(topics_b.iloc[j]["top_terms"]).split()[:8]),
            "jaccard": round(score, 3),
            "matched": "Y" if score >= threshold else "N",
        })
    return pd.DataFrame(records).sort_values("jaccard", ascending=False)


def plot_heatmap(M: np.ndarray, a_label: str, b_label: str, out_path: Path) -> None:
    fig_w = max(8, min(18, M.shape[1] * 0.18))
    fig_h = max(6, min(18, M.shape[0] * 0.18))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    sns.heatmap(
        M,
        ax=ax,
        cmap="viridis",
        vmin=0,
        vmax=max(0.5, M.max()),
        cbar_kws={"label": "Jaccard (top-15 terms)"},
        xticklabels=list(range(M.shape[1])) if M.shape[1] <= 80 else False,
        yticklabels=list(range(M.shape[0])) if M.shape[0] <= 80 else False,
    )
    ax.set_xlabel(f"{b_label} topic id")
    ax.set_ylabel(f"{a_label} topic id")
    ax.set_title(f"Topic alignment: {a_label} (rows) vs {b_label} (cols)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross-window topic alignment via Jaccard")
    parser.add_argument("--out-dir", default="outputs")
    parser.add_argument("--top-n", type=int, default=15)
    parser.add_argument("--threshold", type=float, default=0.2)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    topics_per_window: dict[str, pd.DataFrame] = {}
    for w in WINDOWS:
        df = load_window_topics(out_dir, w, args.top_n)
        topics_per_window[w] = df
        print(f"  {w}: {len(df)} topics loaded")

    pairs = [
        ("Y1_2021-22", "Y2_2022-23"),
        ("Y2_2022-23", "Y3_2023-24"),
        ("Y3_2023-24", "Y4_2024-25"),
        ("Y1_2021-22", "Y4_2024-25"),
    ]

    for a, b in pairs:
        ta = topics_per_window[a]
        tb = topics_per_window[b]
        M = jaccard_matrix(ta, tb)
        match_df = best_match_table(ta, tb, M, threshold=args.threshold)
        unique_df = unique_match_table(ta, tb, M, threshold=args.threshold)

        csv_path = out_dir / f"alignment_{a}_vs_{b}.csv"
        match_df.to_csv(csv_path, index=False)
        unique_path = out_dir / f"alignment_unique_{a}_vs_{b}.csv"
        unique_df.to_csv(unique_path, index=False)
        fig_path = fig_dir / f"alignment_{a}_vs_{b}.png"
        plot_heatmap(M, a, b, fig_path)

        n_above = int((match_df["jaccard"] >= args.threshold).sum())
        mean_jac = float(match_df["jaccard"].mean())
        n_unique_above = int((unique_df["jaccard"] >= args.threshold).sum())
        mean_unique_jac = float(unique_df["jaccard"].mean())
        print(f"\n  {a} vs {b}:")
        print(f"    {len(match_df)} topics in {a}, {len(tb)} topics in {b}")
        print(f"    Best-match Jaccard >= {args.threshold}: {n_above}/{len(match_df)} ({n_above / max(len(match_df), 1):.1%})")
        print(f"    Mean best-match Jaccard: {mean_jac:.3f}")
        print(f"    Unique Jaccard >= {args.threshold}: {n_unique_above}/{len(unique_df)} ({n_unique_above / max(len(unique_df), 1):.1%})")
        print(f"    Mean unique-match Jaccard: {mean_unique_jac:.3f}")
        print(f"    wrote {csv_path}")
        print(f"    wrote {unique_path}")
        print(f"    wrote {fig_path}")


if __name__ == "__main__":
    main()
