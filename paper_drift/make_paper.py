"""Build main.tex of the drift working paper from main_template.tex, filling every number from results/drift/.

Usage: <torch312 python> make_paper.py      (then: latexmk -pdf main.tex)
"""
import json
import shutil
from pathlib import Path

import pandas as pd

here = Path(__file__).resolve().parent
res = here.parent / "results" / "drift"
R = json.loads((res / "drift_results.json").read_text())
S = json.loads((res / "check_same_counters.json").read_text())
cells = pd.read_csv(res / "drift_cells.csv")
pred = pd.read_parquet(res / "drift_predictions.parquet")


def pt(x):
    """A share as percentage points with a proper minus sign, e.g. $-4.5$."""
    v = round(100 * x, 1)
    return f"$-{abs(v):.1f}$" if v < 0 else f"$+{v:.1f}$" if v > 0 else "$0.0$"


def ci(pair):
    return f"{pt(pair[0])} to {pt(pair[1])}"


def ratio(x):
    return f"{x:.2f}"


T = R["tests"]
vals = {}
for h in ("H1", "H2", "H3", "H4"):
    vals[f"{h}pt"], vals[f"{h}ci"] = pt(T[h]["estimate"]), ci(T[h]["ci95"])
    vals[f"{h}ok"] = "supported" if T[h]["supported"] else "not supported"
for s in ("frozen_W1", "frozen_W2", "frozen_W3", "frozen_W4", "yearly"):
    vals[f"S_{s}"], vals[f"S_{s}_ci"] = pt(S[s]["estimate"]), ci(S[s]["ci95"])
vals["S_diffW2"], vals["S_diffW2_ci"] = pt(S["frozen_W1_minus_frozen_W2"]["estimate"]), ci(S["frozen_W1_minus_frozen_W2"]["ci95"])
vals["S_diffW3"], vals["S_diffW3_ci"] = pt(S["frozen_W1_minus_frozen_W3"]["estimate"]), ci(S["frozen_W1_minus_frozen_W3"]["ci95"])

w1late = cells[(cells["strategy"] == "frozen_W1") & (cells["test_year"] >= 2022)]["wet_day_bias"]
vals["W1lo"], vals["W1hi"] = pt(w1late.min()), pt(w1late.max())
D = R["described_pooled"]
vals["nwet_late"], vals["ndry_late"] = f"{D['yearly_late']['n_wet']:,}", f"{D['yearly_late']['n_dry']:,}"
for k in ("frozen_W2_late", "frozen_W3_late"):
    vals[k], vals[k + "_ci"] = pt(D[k]["estimate"]), ci(D[k]["ci95"])

A = R["accuracy_vs_last_week"]
rows = []
names = {"frozen_W1": "Frozen, trained 2011--2013", "frozen_W2": "Frozen, trained 2014--2016",
         "frozen_W3": "Frozen, trained 2017--2019", "frozen_W4": "Frozen, trained 2022--2024$^{a}$",
         "yearly": "Retrained every year"}
for s, label in names.items():
    e, l = A.get(f"{s} | 2014-2019"), A.get(f"{s} | 2022-2026")
    fmt = lambda d: " & ".join(ratio(d[k]) for k in ("all", "wet", "dry")) if d else "-- & -- & --"
    rows.append(f"{label} & {fmt(e)} & {fmt(l)} \\\\")
# the 2022-2024 model is only tested in 2025-2026: the yearly retrained model on the same two years, for comparison
y2 = pred[(pred["strategy"] == "yearly") & pred["year"].isin([2025, 2026])]
k = {"all": y2, "wet": y2[y2["rain"] >= 2], "dry": y2[y2["rain"] < 0.1]}
yr = {kk: float((h["pred"] - h["y"]).abs().sum() / (h["lag7"] - h["y"]).abs().sum()) for kk, h in k.items()}
rows.append(f"Retrained every year, 2025--2026 only$^{{a}}$ & -- & -- & -- & {ratio(yr['all'])} & {ratio(yr['wet'])} & {ratio(yr['dry'])} \\\\")
vals["acc_rows"] = "\n".join(rows)
vals["accW1"], vals["accW2"], vals["accW3"] = (ratio(A[f"frozen_{w} | 2022-2026"]["all"]) for w in ("W1", "W2", "W3"))
vals["accY"] = ratio(A["yearly | 2022-2026"]["all"])
vals["accW4"], vals["accY2526"] = ratio(A["frozen_W4 | 2022-2026"]["all"]) if "frozen_W4 | 2022-2026" in A else "--", ratio(yr["all"])

E = R["earlier_models_wet_day_bias_19_counters"]
vals["E_gwn"], vals["E_rnn"], vals["E_lgbm"] = pt(E["pred_gwn_wx"]), pt(E["pred_rnn_wx"]), pt(E["pred_lgbm_wx"])
M = R["models"]
vals["W1counters"] = str(len(M["frozen_W1"]["counters"]))
vals["code14"] = f"{R['checks']['code14_reference']:+.4f}"

t = (here / "main_template.tex").read_text(encoding="utf-8")
for key, v in vals.items():
    t = t.replace(f"<<{key}>>", v)
missing = [line for line in t.splitlines() if "<<" in line]
assert not missing, missing[:3]
(here / "main.tex").write_text(t, encoding="utf-8", newline="\n")
(here / "figures").mkdir(exist_ok=True)
shutil.copy(res / "fig_drift.pdf", here / "figures" / "fig_drift.pdf")
print("main.tex written with", len(vals), "filled values")
