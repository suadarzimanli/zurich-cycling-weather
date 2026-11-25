"""Diagnostics added AFTER seeing the result of 29_route_type.py (not part of its fixed specification).

1. Influence: drop one location at a time and re-estimate the commuter-minus-leisure difference.
2. Trip mix: did the weekend ratio of each group change between 2011-2014 and 2022-2026?
   (A falling weekend ratio on leisure routes would mean more weekday, everyday trips there.)
Counts and calendar only in part 2, no weather.

Usage: python 30_route_type_followup.py <project_dir>
"""
import json
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from blockpois import blockpois

here = Path(__file__).resolve().parent
g = runpy.run_path(str(here / "29_route_type.py"), run_name="route_type")
d, group, k, WEATHER, HOL = g["d"], g["group"], g["k"], g["WEATHER"], g["HOL"]
root = Path(sys.argv[1])


def diff_without(drop):
    s = d[d["loc"] != drop]
    G = {}
    for ds in ("commuter", "leisure"):
        m = (s["dataset"] == ds).to_numpy().astype(float)
        for v in WEATHER:
            G[f"{v}:trend:{ds}"] = s[v].to_numpy() * s["trend"].to_numpy() * m
        for h in HOL:
            G[f"{h}:{ds}"] = s[h].to_numpy() * m
    G = pd.DataFrame(G)
    G = G.loc[:, G.std() > 0]
    r = blockpois(s["y"], G.to_numpy(), s[WEATHER].to_numpy(), s["loc"], s["fe1"], s["dow"], s["week"], names=list(G.columns))
    b, V = r["beta"], r["vcov"]
    out = {}
    for key, w in (("commuter", {"wet:trend:commuter": 1}), ("leisure", {"wet:trend:leisure": 1}),
                   ("diff", {"wet:trend:commuter": 1, "wet:trend:leisure": -1})):
        a = pd.Series(0.0, index=b.index)
        for n, x in w.items():
            a[n] = x
        est, se = float(a @ b), float(np.sqrt(a @ V @ a))
        out[key] = [est, est - 1.96 * se, est + 1.96 * se]
    return out


print("\n1. Drop one location at a time")
loo = {}
for loc in sorted(group.index):
    loo[loc] = diff_without(loc)
    x = loo[loc]
    print(f"  without {loc:9s} ({group[loc]:8s}) commuter {x['commuter'][0]:+.3f} | leisure {x['leisure'][0]:+.3f} | "
          f"difference {x['diff'][0]:+.3f} [{x['diff'][1]:+.3f}, {x['diff'][2]:+.3f}]")
diffs = np.array([v["diff"][0] for v in loo.values()])
uppers = np.array([v["diff"][2] for v in loo.values()])
print(f"  difference ranges from {diffs.min():+.3f} to {diffs.max():+.3f}, upper interval bound at most {uppers.max():+.3f}")

print("\n2. Weekend ratio by period (locations observed in both periods)")
k = k.copy()
k["period"] = np.where(k["date"].dt.year <= 2014, "early", np.where(k["date"].dt.year >= 2022, "late", None))
k = k[k["period"].notna()]
wd = k[(k["date"].dt.dayofweek < 5) & (k["public_holiday"] == 0)].groupby(["loc", "period"])["y"].mean()
we = k[k["date"].dt.dayofweek >= 5].groupby(["loc", "period"])["y"].mean()
rr = (we / wd).unstack().dropna()
rr["group"] = rr.index.map(group)
print(rr.round(3).to_string())
mix = {}
for grp, s in rr.groupby("group"):
    mix[grp] = {"locations": len(s), "early_mean": float(s["early"].mean()), "late_mean": float(s["late"].mean()),
                "share_falling": float((s["late"] < s["early"]).mean())}
    print(f"  {grp}: {len(s)} locations, mean weekend ratio {s['early'].mean():.3f} -> {s['late'].mean():.3f}, "
          f"falling at {int((s['late'] < s['early']).sum())} of {len(s)}")

res = {"leave_one_out": loo, "loo_diff_range": [float(diffs.min()), float(diffs.max())], "loo_max_upper": float(uppers.max()),
       "weekend_ratio_by_period": {loc: {"early": float(r["early"]), "late": float(r["late"]), "group": r["group"]} for loc, r in rr.iterrows()},
       "weekend_ratio_summary": mix}
(root / "results" / "review_checks" / "route_type_followup.json").write_text(json.dumps(res, indent=2))
