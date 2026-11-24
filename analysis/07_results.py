"""Main results: weather effects by year, the three prediction tests, and the checks.

Usage: python 07_results.py <project_dir>
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import by_year, pct, period_test, save_json
from design import load

root = Path(sys.argv[1])
res = root / "results"
res.mkdir(exist_ok=True)
core = json.loads((root / "data" / "derived" / "sample_definitions.json").read_text())["period_comparison_locations"]
t0 = time.time()

# ---------- main: by year, all locations ----------
d = load(root)
print("main sample: location-days", len(d), "| locations", d["loc"].nunique(), "| years", d["year"].min(), "-", d["year"].max())
yr, r = by_year(d)
yr.to_csv(res / "effects_by_year.csv", index=False)
print("fit: n", r["n"], "groups", r["groups"], "clusters", r["clusters"], "iterations", r["iterations"], "dropped", r["dropped"])
tab = yr.pivot(index="year", columns="effect", values="est")
se = yr.pivot(index="year", columns="effect", values="se")
show = pd.DataFrame({
    "rain_%": pct(tab["rain"]).round(1), "rain_se": se["rain"].round(3),
    "cold_%/degC": pct(tab["cold"]).round(2), "cold_se": se["cold"].round(4),
    "heat_%/degC": pct(tab["heat"]).round(2), "heat_se": se["heat"].round(4),
    "days": yr.groupby("year")["n_days"].first()})
print(show.to_string())
print(f"[{time.time() - t0:.0f}s]")


def report(name, o):
    print(f"\n--- {name}: location-days {o['n']}, locations {o['locations']}, weeks {o['clusters']}")
    for k in ("rain", "cold", "heat"):
        x = o[k]
        print(f"{k:5s} early {x['early']:+.4f} ({x['early_se']:.4f})  late {x['late']:+.4f} ({x['late_se']:.4f})  "
              f"change {x['change']:+.4f} [{x['change'] - 1.96 * x['change_se']:+.4f}, {x['change'] + 1.96 * x['change_se']:+.4f}]  "
              f"shrink {x['shrink']:+.3f} ({x['shrink_se']:.3f})  early CI excludes 0: {x['early_ci_excludes_zero']}")
    for k in ("cold", "heat"):
        v, s = o[f"{k}_minus_rain_shrink"], o[f"{k}_minus_rain_shrink_se"]
        print(f"shrink({k}) - shrink(rain) = {v:+.3f} [{v - 1.96 * s:+.3f}, {v + 1.96 * s:+.3f}]")


out = {}
# ---------- predictions 1 and 2 ----------
out["P1_P2_core"] = period_test(d, core)
report("Predictions 1 and 2 (9 locations, daytime)", out["P1_P2_core"])

# ---------- prediction 3: weekday rush hours ----------
dr = d[(d["dow"] < 5) & (~d["public_holiday"])].copy()
dr["y"] = (dr["velo_am"] + dr["velo_pm"]).astype(float)
out["P3_core_rush"] = period_test(dr, core)
report("Prediction 3 (9 locations, weekday rush hours)", out["P3_core_rush"])
print(f"[{time.time() - t0:.0f}s]")

# ---------- checks ----------
out["check_all_locations"] = period_test(d)
report("Check: all locations", out["check_all_locations"])
out["check_affoltern"] = period_test(load(root, station="reh"), core)
report("Check: Affoltern weather", out["check_affoltern"])
out["check_no_cleaning"] = period_test(load(root, cleaning=False), core)
report("Check: no cleaning rule", out["check_no_cleaning"])
out["check_daily_rain"] = period_test(load(root, rain_col="rain_daily_6utc"), core)
report("Check: MeteoSwiss daily rain (6 to 6 UTC)", out["check_daily_rain"])
save_json(out, res / "prediction_tests.json")
print(f"\n[{time.time() - t0:.0f}s] done")
