"""Check added after the results, rule fixed in docs/CHECK_OFFPEAK_PROPORTIONAL_2026-11-25.md (check B)
before it was run: did leisure-type routes weaken more than commuter-type routes also in proportional terms?

Same model as 29_route_type.py. The estimator also returns each location's own wet-day effect (its value in
2011, the start of the trend) and the covariance of all coefficients. For each group:
  start level            = simple mean of the locations' own wet-day effects
  proportional change    = trend per decade of the wet-day effect / |start level|
Intervals by the delta method.

Usage: python 31_route_type_proportional.py <project_dir>
"""
import json
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from blockpois import blockpois

here = Path(__file__).resolve().parent
root = Path(sys.argv[1])
g = runpy.run_path(str(here / "29_route_type.py"), run_name="route_type")
d, G, group, WEATHER, r0 = g["d"], g["G"], g["group"], g["WEATHER"], g["r"]

stored = json.loads((root / "results" / "review_checks" / "route_type.json").read_text())
assert abs(r0["beta"]["wet:trend:leisure"] - stored["rain_trend_leisure"]["est"]) < 1e-9, "default estimator changed"
assert abs(r0["beta"]["wet:trend:commuter"] - stored["rain_trend_commuter"]["est"]) < 1e-9, "default estimator changed"

r = blockpois(d["y"], G.to_numpy(), d[WEATHER].to_numpy(), d["loc"], d["fe1"], d["dow"], d["week"],
              names=list(G.columns), full=True, local_names=WEATHER)
b, V = r["beta_full"], r["vcov_full"]
gl = list(G.columns)
dev_b = float(np.abs(r["beta"] - r0["beta"]).max())
dev_v = float(np.abs(V.loc[gl, gl].to_numpy() - r0["vcov"].to_numpy()).max() / np.abs(r0["vcov"].to_numpy()).max())
print(f"full covariance reproduces the original: max coefficient difference {dev_b:.1e}, "
      f"max relative covariance difference {dev_v:.1e}")
assert dev_b < 1e-10 and dev_v < 1e-6


def delta(f, eps=1e-6):
    """value, standard error and gradient of f(b) by central differences."""
    x0 = b.to_numpy()
    val = f(x0)
    grad = np.zeros_like(x0)
    for i in range(len(x0)):
        if not np.any(f_uses[i]):
            continue
        h = eps * max(1.0, abs(x0[i]))
        xp, xm = x0.copy(), x0.copy()
        xp[i] += h
        xm[i] -= h
        grad[i] = (f(xp) - f(xm)) / (2 * h)
    se = float(np.sqrt(grad @ V.to_numpy() @ grad))
    return {"est": float(val), "se": se, "ci95": [float(val - 1.96 * se), float(val + 1.96 * se)]}


idx = {k: i for i, k in enumerate(b.index)}
locs = {grp: [f"{loc}:wet" for loc in sorted(group.index[group == grp])] for grp in ("commuter", "leisure")}
f_uses = np.zeros(len(b), bool)
for grp in ("commuter", "leisure"):
    f_uses[idx[f"wet:trend:{grp}"]] = True
    for k in locs[grp]:
        f_uses[idx[k]] = True


def level(x, grp):
    return np.mean([x[idx[k]] for k in locs[grp]])


def prop(x, grp):
    return x[idx[f"wet:trend:{grp}"]] / abs(level(x, grp))


res = {"n": int(r["n"]), "locations": int(r["locations"]), "check_full_vs_original": {"max_coef_diff": dev_b, "max_rel_vcov_diff": dev_v}}
for grp in ("commuter", "leisure"):
    res[f"start_level_{grp}"] = delta(lambda x, grp=grp: level(x, grp))
    res[f"trend_{grp}"] = delta(lambda x, grp=grp: x[idx[f"wet:trend:{grp}"]])
    res[f"proportional_change_{grp}"] = delta(lambda x, grp=grp: prop(x, grp))
res["proportional_leisure_minus_commuter"] = delta(lambda x: prop(x, "leisure") - prop(x, "commuter"))
res["local_wet_effects"] = {k.split(":")[0]: float(b[k]) for grp in locs for k in locs[grp]}

for key, x in res.items():
    if isinstance(x, dict) and "est" in x:
        print(f"{key:40s} {x['est']:+.4f} [{x['ci95'][0]:+.4f}, {x['ci95'][1]:+.4f}]")
for grp in ("commuter", "leisure"):
    lv = res[f"start_level_{grp}"]["est"]
    print(f"  {grp}: wet day in 2011 {100 * (np.exp(lv) - 1):.1f}%")
out = root / "results" / "review_checks"
(out / "route_type_proportional.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
print("written", out / "route_type_proportional.json")
