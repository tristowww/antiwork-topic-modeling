"""Build aggregate-only visuals for the collaborator analysis brief."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "v2_clean_min25"
ANALYSIS_DIR = OUT_DIR / "analysis"
FIGURE_DIR = OUT_DIR / "figures"

NAVY = "#1F4E79"
MUTED = "#52616B"
GRID = "#D9E0E5"
PANEL = "#F7F9FA"


def build_key_theme_trends() -> Path:
    monthly = pd.read_csv(ANALYSIS_DIR / "candidate_theme_monthly_prevalence.csv", parse_dates=["month"])
    themes = [
        ("Health safety and attendance", "Health, safety, attendance", "#A55A44"),
        ("Scheduling hours and time off", "Scheduling and time off", "#2B6B84"),
        ("Compensation and pay rights", "Compensation and pay", "#667B3E"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(8, 3.7), sharey=True)
    for axis, (theme, label, color) in zip(axes, themes):
        series = monthly.loc[monthly["candidate_theme"].eq(theme)].sort_values("month")
        values = series["three_month_share_all_posts"] * 100
        axis.plot(series["month"], values, color=color, linewidth=2.2)
        axis.scatter(series["month"], values, color=color, s=8, zorder=3)
        axis.set_title(label, loc="left", fontsize=9.5, fontweight="bold", color="#22313F", pad=8)
        axis.set_ylim(0, 6.5)
        axis.yaxis.set_major_formatter("{x:.0f}%")
        axis.xaxis.set_major_locator(mdates.YearLocator())
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        axis.grid(axis="y", color=GRID, linewidth=0.8)
        axis.spines[["top", "right"]].set_visible(False)
        axis.spines[["left", "bottom"]].set_color("#8B98A3")
        axis.tick_params(labelsize=8, color="#8B98A3")
    axes[0].set_ylabel("Share of all filtered posts", fontsize=8.6, color="#22313F")
    fig.text(0.01, 0.01, "Three-month rolling shares; denominator is all filtered posts each month. The reviewed theme map covers 19.0% of the corpus.", fontsize=8, color=MUTED)
    fig.tight_layout(rect=[0, 0.08, 1, 1])
    path = FIGURE_DIR / "brief_key_theme_monthly_trends.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def build_method_flow() -> Path:
    fig, axis = plt.subplots(figsize=(7.5, 2.6))
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    boxes = [
        ("Collection", "Public posts\nMar 2021 to Feb 2025"),
        ("Filter and\ndeduplicate", "Management terms\n97,254 unique posts"),
        ("Model", "Title plus body\nBERTopic model"),
        ("Review and\nestimate", "27 clusters\nNine themes\nRolling shares"),
    ]
    width, height, y = 0.205, 0.58, 0.21
    starts = [0.02, 0.27, 0.52, 0.77]
    for index, (x, (title, detail)) in enumerate(zip(starts, boxes)):
        fill = "#E8EEF3" if index in (1, 3) else PANEL
        axis.add_patch(Rectangle((x, y), width, height, facecolor=fill, edgecolor="#9AA9B5", linewidth=0.9))
        axis.text(x + width / 2, y + height * 0.70, title, ha="center", va="center", fontsize=9.2, fontweight="bold", color=NAVY, linespacing=1.15, wrap=True)
        axis.text(x + width / 2, y + height * 0.31, detail, ha="center", va="center", fontsize=7.8, color="#344454", linespacing=1.3, wrap=True)
        if index < len(boxes) - 1:
            axis.add_patch(FancyArrowPatch((x + width + 0.008, 0.5), (starts[index + 1] - 0.008, 0.5), arrowstyle="-|>", mutation_scale=10, linewidth=1.0, color="#6D7E8B"))
    path = FIGURE_DIR / "brief_collection_to_results_flow.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    print(build_method_flow())
    print(build_key_theme_trends())


if __name__ == "__main__":
    main()
