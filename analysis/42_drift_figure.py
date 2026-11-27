"""Figure for the drift paper: wet-day bias by test year for every training strategy (left) and the pooled
2022-2026 estimates on the same six counters with 95% intervals (right).

Usage: <torch312 python> 42_drift_figure.py <project_dir>
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

root = Path(sys.argv[1])
res = root / "results" / "drift"
cells = pd.read_csv(res / "drift_cells.csv")
same = json.loads((res / "check_same_counters.json").read_text())

# palette slots 1-4 of the validated chart palette (as in 23_paper_figures.py), ink for the retrained model
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
STYLE = {
    "frozen_W1": ("Frozen, trained 2011–2013", "#2a78d6", "o"),
    "frozen_W2": ("Frozen, trained 2014–2016", "#eb6834", "s"),
    "frozen_W3": ("Frozen, trained 2017–2019", "#1baf7a", "D"),
    "frozen_W4": ("Frozen, trained 2022–2024", "#eda100", "^"),
    "yearly": ("Retrained every year", INK, "o"),
}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK})

fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.2, 3.9), facecolor=SURF, gridspec_kw={"width_ratios": [1.75, 1]})
ax.axhline(0, color=INK2, lw=0.8, zorder=1)
for a in (ax, bx):
    a.set_facecolor(SURF)
    a.grid(axis="y", color=GRID, lw=0.6)
    a.spines[["top", "right"]].set_visible(False)

ax.axvspan(2019.5, 2021.5, color="#efeeea", lw=0, zorder=0)
ax.text(2020.5, 14.5, "pandemic\n(not used)", ha="center", va="top", fontsize=7, color=INK2)
for s, (label, col, mk) in STYLE.items():
    g = cells[cells["strategy"] == s].sort_values("test_year")
    for part in (g[g["test_year"] <= 2019], g[g["test_year"] >= 2022]):  # no line across the pandemic gap
        if len(part):
            ax.plot(part["test_year"], 100 * part["wet_day_bias"], marker=mk, color=col, lw=1.6 if s != "yearly" else 1.2,
                    ls="-" if s != "yearly" else "--", ms=4.5, mec=SURF, mew=0.8, zorder=3,
                    label=label if part is not None and part.index[0] == g.index[0] else None)
ax.set_xticks([2014, 2016, 2018, 2022, 2024, 2026])
ax.set_ylim(-16, 16)
ax.set_ylabel("Wet-day bias (percentage points)", color=INK2)
ax.set_xlabel("Test year", color=INK2)
ax.set_title("a  Wet-day bias in each test year (11 counters)", loc="left", fontsize=8.5, color=INK)

order = ["frozen_W1", "frozen_W2", "frozen_W3", "frozen_W4", "yearly"]
for i, s in enumerate(order):
    label, col, mk = STYLE[s]
    est, (lo, hi) = 100 * same[s]["estimate"], [100 * v for v in same[s]["ci95"]]
    y = len(order) - 1 - i
    bx.hlines(y, lo, hi, color=col, lw=1.6, zorder=2)
    bx.plot(est, y, mk, color=col, ms=5.5, mec=SURF, mew=0.9, zorder=3)
    bx.text(hi + 0.8, y, f"{est:+.1f}", va="center", fontsize=7.5, color=INK)
bx.set_yticks(range(len(order)))
bx.set_yticklabels(["Retrained every year", "Frozen 2022–2024", "Frozen 2017–2019", "Frozen 2014–2016",
                    "Frozen 2011–2013"], fontsize=7.5)
bx.set_xlim(-16, 19)
bx.axvline(0, color=INK2, lw=0.8)
bx.grid(axis="y", visible=False)
bx.grid(axis="x", color=GRID, lw=0.6)
bx.set_xlabel("Wet-day bias, 2022–2026 (points)", color=INK2)
bx.set_title("b  2022–2026, same 6 counters", loc="left", fontsize=8.5, color=INK)

handles, labels = ax.get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", ncol=3, frameon=False, fontsize=7.2)
fig.tight_layout(rect=(0, 0.11, 1, 1))
for ext in ("pdf", "png"):
    fig.savefig(res / f"fig_drift.{ext}", dpi=220, facecolor=SURF)
print("figure written")
