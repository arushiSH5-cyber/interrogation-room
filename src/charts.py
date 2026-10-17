"""Charts for the report (matplotlib, saved as PNG under results/)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")                     # draw to files, no window needed
import matplotlib.pyplot as plt  # noqa: E402

# Colour roles (validated categorical palette, light mode).
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
LABELS = {"prolog": "Prolog checker", "judge": "LLM judge", "detective": "Pure-LLM detective"}


def _style(ax, title: str) -> None:
    ax.set_title(title, loc="left", color=INK, fontsize=12, pad=12)
    ax.set_facecolor(SURFACE)
    ax.set_ylim(0, 118)
    ax.set_yticks(range(0, 101, 20))
    ax.set_ylabel("percent", color=MUTED)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0)


def _label_bars(ax, bars, tops=None) -> None:
    """Value label above each bar (or above its error bar, if given)."""
    for bar, top in zip(bars, tops or [b.get_height() for b in bars]):
        ax.annotate(f"{bar.get_height():.0f}%", (bar.get_x() + bar.get_width() / 2, top),
                    ha="center", va="bottom", xytext=(0, 3), textcoords="offset points",
                    color=INK, fontsize=9)


def plot_summary(summary: list[dict], out_dir: Path) -> list[Path]:
    """Two charts: detection vs false alarms, and culprit accuracy."""
    names = [LABELS[s["detector"]] for s in summary]
    x = range(len(summary))
    paths = []

    # 1. Lie-detection rate vs false-alarm rate (same unit, one axis).
    fig, ax = plt.subplots(figsize=(7, 4), facecolor=SURFACE)
    width = 0.36
    det = [100 * s["lie_detection_rate"] for s in summary]
    fa = [100 * s["false_alarm_rate"] for s in summary]
    err = [[100 * (s["lie_detection_rate"] - s["lie_detection_ci_low"]) for s in summary],
           [100 * (s["lie_detection_ci_high"] - s["lie_detection_rate"]) for s in summary]]
    b1 = ax.bar([i - width / 2 - 0.01 for i in x], det, width, color=BLUE,
                label="Lie detection rate (culprit flagged)", yerr=err,
                error_kw={"ecolor": MUTED, "elinewidth": 1, "capsize": 3})
    b2 = ax.bar([i + width / 2 + 0.01 for i in x], fa, width, color=ORANGE,
                label="False-alarm rate (innocents flagged)")
    _label_bars(ax, b1, [100 * s["lie_detection_ci_high"] for s in summary])
    _label_bars(ax, b2)
    ax.set_xticks(list(x), names, color=INK)
    _style(ax, f"Catching the liar across {summary[0]['mysteries']} mysteries")
    ax.legend(frameon=False, loc="upper right", fontsize=9, labelcolor=INK)
    fig.tight_layout()
    paths.append(out_dir / "detection_vs_false_alarms.png")
    fig.savefig(paths[-1], dpi=200)
    plt.close(fig)

    # 2. Naming the murderer (single series, no legend needed).
    fig, ax = plt.subplots(figsize=(7, 3.6), facecolor=SURFACE)
    bars = ax.bar(list(x), [100 * s["culprit_accuracy"] for s in summary], 0.5, color=BLUE)
    _label_bars(ax, bars)
    ax.set_xticks(list(x), names, color=INK)
    _style(ax, "Murderer named correctly")
    fig.tight_layout()
    paths.append(out_dir / "culprit_accuracy.png")
    fig.savefig(paths[-1], dpi=200)
    plt.close(fig)
    return paths
