"""Main figure: rain, cold and heat effects by year (all locations), 95% intervals.

Usage: python 08_figure.py <project_dir>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

root = Path(sys.argv[1])
res = root / "results"
yr = pd.read_csv(res / "effects_by_year.csv")

BLUE, SURFACE, INK, INK2, GRID = "#2a78d6", "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK})

panels = [
    ("rain", "Wet day (2 mm or more) vs dry day", "Change in daytime bikes (%)"),
    ("cold", "Cold: each degree warmer, 0 to 15 °C", "Change per °C (%)"),
    ("heat", "Heat: each degree warmer, above 25 °C", "Change per °C (%)"),
]
fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.4), facecolor=SURFACE)
for ax, (k, title, ylab) in zip(axes, panels):
    s = yr[yr["effect"] == k].sort_values("year")
    x = s["year"].to_numpy()
    est = 100 * (np.exp(s["est"]) - 1)
    lo = 100 * (np.exp(s["est"] - 1.96 * s["se"]) - 1)
    hi = 100 * (np.exp(s["est"] + 1.96 * s["se"]) - 1)
    ax.set_facecolor(SURFACE)
    ax.axvspan(2019.5, 2021.5, color="#efeeea", zorder=0, lw=0)
    ax.axhline(0, color=INK2, lw=0.8, zorder=1)
    ax.vlines(x, lo, hi, color=BLUE, lw=1.6, zorder=2)
    ax.plot(x, est, "o", color=BLUE, ms=5.5, mec=SURFACE, mew=1.2, zorder=3)
    ax.set_title(title, fontsize=9.5, loc="left", color=INK, pad=8)
    ax.set_ylabel(ylab, color=INK2)
    ax.set_xticks([2011, 2014, 2017, 2020, 2023, 2026])
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ymin, ymax = ax.get_ylim()
    ax.text(2020.5, ymax - 0.04 * (ymax - ymin), "pandemic", ha="center", va="top", fontsize=7.5, color=INK2)
fig.text(0.01, 0.01, "Zurich bicycle counters (all locations), 6:00 to 20:00. Dots: estimate for each year. Lines: 95% intervals. "
         "Weather: MeteoSwiss Zürich/Fluntern. 2026 runs to 22 November.", fontsize=7.5, color=INK2)
fig.tight_layout(rect=(0, 0.05, 1, 1))
for ext in ("png", "pdf"):
    fig.savefig(res / f"fig_effects_by_year.{ext}", dpi=200, facecolor=SURFACE)
print("saved", res / "fig_effects_by_year.png")
