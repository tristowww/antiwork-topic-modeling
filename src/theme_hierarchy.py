"""Render the reviewed candidate-theme hierarchy with full-corpus cluster sizes.

The figure is a deterministic view of the documented codebook and the existing
BERTopic document assignments. It does not create or reinterpret themes.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import ConnectionPatch


DEFAULT_CODEBOOK = "planning/CANDIDATE_THEME_CODEBOOK.csv"
DEFAULT_ASSIGNMENTS = "outputs/v2_clean_min25/bertopic_full_document_topics.csv"
DEFAULT_OUTPUT = "outputs/v2_clean_min25/figures/reviewed_theme_hierarchy.png"

THEME_COLORS = [
    "#275D8C", "#B35A27", "#3B7D5A", "#7C5A9B", "#9A6A24",
    "#4C7A8D", "#9D4E63", "#637055", "#5E6F91",
]


def load_hierarchy(codebook_path: Path, assignments_path: Path) -> list[tuple[str, int, list[tuple[str, int]]]]:
    with codebook_path.open(newline="", encoding="utf-8") as handle:
        codebook = list(csv.DictReader(handle))
    with assignments_path.open(newline="", encoding="utf-8") as handle:
        counts = Counter(int(row["topic"]) for row in csv.DictReader(handle))

    grouped: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for row in codebook:
        if row["decision"] == "include":
            grouped[row["candidate_theme"]].append((row["candidate_subtheme"], counts[int(row["topic"])]))
    return sorted(
        ((theme, sum(size for _, size in subthemes), sorted(subthemes, key=lambda item: (-item[1], item[0]))) for theme, subthemes in grouped.items()),
        key=lambda item: (-item[1], item[0]),
    )


def render(hierarchy: list[tuple[str, int, list[tuple[str, int]]]], output: Path) -> None:
    rows = [(theme, total, subtheme, size) for theme, total, subthemes in hierarchy for subtheme, size in subthemes]
    fig_height = max(10.0, len(rows) * 0.43 + 2.2)
    fig, axis = plt.subplots(figsize=(12.0, fig_height))
    axis.set_xlim(0, 1)
    axis.set_ylim(len(rows) + 1.2, -1.4)
    axis.axis("off")
    axis.text(0.02, -0.95, "Reviewed candidate-theme hierarchy", fontsize=17, fontweight="bold", color="#17365D")
    axis.text(0.02, -0.34, "Theme totals and subtheme cluster sizes are calculated from full-corpus BERTopic document assignments.", fontsize=9.5, color="#475569")

    row_y = {subtheme: index + 0.5 for index, (_, _, subtheme, _) in enumerate(rows)}
    color_by_theme = {theme: THEME_COLORS[index % len(THEME_COLORS)] for index, (theme, _, _) in enumerate(hierarchy)}
    for index, (theme, total, subtheme, size) in enumerate(rows):
        y = index + 0.5
        color = color_by_theme[theme]
        radius = 0.034 + 0.045 * (size / max(item[3] for item in rows)) ** 0.5
        axis.scatter(0.60, y, s=(radius * 920) ** 2, color=color, alpha=0.9, edgecolor="white", linewidth=0.8, zorder=3)
        axis.text(0.645, y, f"{subtheme}  (n={size:,})", va="center", fontsize=8.7, color="#1F2937")

    for theme, total, subthemes in hierarchy:
        ys = [row_y[subtheme] for subtheme, _ in subthemes]
        center = sum(ys) / len(ys)
        color = color_by_theme[theme]
        axis.text(0.02, center, f"{theme}\n(n={total:,})", va="center", fontsize=9.2, fontweight="bold", color="#17365D")
        axis.plot([0.34, 0.44], [center, center], color=color, linewidth=2.5, solid_capstyle="round")
        for y in ys:
            connection = ConnectionPatch((0.44, center), (0.60, y), "data", "data", axesA=axis, axesB=axis, color=color, linewidth=0.9, alpha=0.62)
            axis.add_artist(connection)

    axis.text(0.02, len(rows) + 0.8, "Included clusters only: 27 clusters, 18,506 posts (19.0% of the filtered corpus). Node area scales with cluster n. This is a documented candidate map, not a complete taxonomy.", fontsize=8.5, color="#475569")
    fig.tight_layout(pad=0.5)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the reviewed theme-to-subtheme hierarchy.")
    parser.add_argument("--codebook", default=DEFAULT_CODEBOOK)
    parser.add_argument("--assignments", default=DEFAULT_ASSIGNMENTS)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    hierarchy = load_hierarchy(Path(args.codebook), Path(args.assignments))
    render(hierarchy, Path(args.output))
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
