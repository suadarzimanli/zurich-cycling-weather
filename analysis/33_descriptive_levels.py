"""Descriptive table: how many cyclists, on dry and on wet days, at the nine locations of the period design.

Simple averages, not a model: for each location the mean daytime count (6:00-20:00) of all kept complete days,
of dry days (under 0.1 mm of daytime rain at Fluntern) and of wet days (2 mm or more), in 2011-2014 and 2022-2026.
The table gives the average over the nine locations, so each location counts the same.
Also: growth from 2011-2014 to 2017 measured by the original counters only (none was replaced before 2018),
and the mean temperature and sunshine on dry and wet days.

Usage: python 33_descriptive_levels.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1])
der = root / "data" / "derived"
LOCS = json.loads((der / "sample_definitions.json").read_text(encoding="utf-8"))["period_comparison_locations"]
assert len(LOCS) == 9

c = pd.read_parquet(der / "counts_daily.parquet")
c = c[c["complete"] & c["keep"] & c["loc"].isin(LOCS)].copy()
assert not c.duplicated(["loc", "date"]).any(), "a location has two counters on the same day"
w = pd.read_parquet(der / "weather_daily.parquet")[["date", "sma_rain_day", "sma_tmax", "sma_sun_day"]]
d = c.merge(w, on="date", how="inner")
d["year"] = d["date"].dt.year
d["period"] = np.select([d["year"].between(2011, 2014), d["year"].between(2022, 2026)], ["early", "late"], "")
d["day"] = np.select([d["sma_rain_day"] < 0.1, d["sma_rain_day"] >= 2], ["dry", "wet"], "light")
p = d[d["period"] != ""]


def avg(df):
    """mean per location, then the average over the nine locations."""
    return float(df.groupby("loc")["velo_day"].mean().mean())


res = {"locations": LOCS, "definition": "mean daytime count per location, averaged over the nine locations"}
for per in ("early", "late"):
    s = p[p["period"] == per]
    res[per] = {"all_days": avg(s), "dry_days": avg(s[s["day"] == "dry"]), "wet_days": avg(s[s["day"] == "wet"]),
                "location_days": int(len(s)), "dry_dates": int(s.loc[s["day"] == "dry", "date"].nunique()),
                "wet_dates": int(s.loc[s["day"] == "wet", "date"].nunique())}
    res[per]["wet_minus_dry"] = res[per]["wet_days"] - res[per]["dry_days"]
    res[per]["wet_vs_dry_pct"] = 100 * (res[per]["wet_days"] / res[per]["dry_days"] - 1)
    for k in ("dry", "wet"):
        days = s[s["day"] == k].drop_duplicates("date")
        res[per][f"{k}_tmax_mean"] = float(days["sma_tmax"].mean())
        res[per][f"{k}_sun_hours_mean"] = float(days["sma_sun_day"].mean() / 60)
res["change_pct"] = {k: 100 * (res["late"][k] / res["early"][k] - 1) for k in ("all_days", "dry_days", "wet_days")}
res["change_pct"]["fewer_on_wet_day"] = 100 * (res["late"]["wet_minus_dry"] / res["early"]["wet_minus_dry"] - 1)

# growth before any counter was replaced: same original counters, 2011-2014 against 2017
first = c.sort_values("date").groupby("loc")["device"].first()
o = d[d["device"].astype(str) == d["loc"].map(first).astype(str)]
assert o.loc[o["year"] == 2017, "loc"].nunique() == 9 and o["date"].max() >= pd.Timestamp("2018-01-01")
e = o[o["year"].between(2011, 2014)].groupby("loc")["velo_day"].mean()
y17 = o[o["year"] == 2017].groupby("loc")["velo_day"].mean()
res["original_counters"] = {"mean_2011_2014": float(e.mean()), "mean_2017": float(y17.mean()),
                            "growth_pct": 100 * (y17.mean() / e.mean() - 1),
                            "last_day_of_original_counters": {k: str(v.date()) for k, v in o.groupby("loc")["date"].max().items()}}

e_, l_ = res["early"], res["late"]
print("Daytime cyclists per counter (average over the nine locations)")
print(f"{'':28s} {'2011-2014':>10s} {'2022-2026':>10s} {'change':>8s}")
for k, lab in (("all_days", "All days"), ("dry_days", "Dry days"), ("wet_days", "Wet days")):
    print(f"{lab:28s} {e_[k]:10.0f} {l_[k]:10.0f} {res['change_pct'][k]:+7.0f}%")
print(f"{'Fewer on a wet day':28s} {-e_['wet_minus_dry']:10.0f} {-l_['wet_minus_dry']:10.0f} {res['change_pct']['fewer_on_wet_day']:+7.0f}%")
print(f"wet vs dry, raw: {e_['wet_vs_dry_pct']:.0f}% early, {l_['wet_vs_dry_pct']:.0f}% late")
print(f"wet days: {e_['wet_dates']} early, {l_['wet_dates']} late | dry days: {e_['dry_dates']}, {l_['dry_dates']}")
print(f"weather, dry vs wet days: max temperature {e_['dry_tmax_mean']:.1f} vs {e_['wet_tmax_mean']:.1f} C (early), "
      f"{l_['dry_tmax_mean']:.1f} vs {l_['wet_tmax_mean']:.1f} C (late); sunshine {e_['dry_sun_hours_mean']:.1f} vs "
      f"{e_['wet_sun_hours_mean']:.1f} h (early), {l_['dry_sun_hours_mean']:.1f} vs {l_['wet_sun_hours_mean']:.1f} h (late)")
oc = res["original_counters"]
print(f"original counters: {oc['mean_2011_2014']:.0f} (2011-2014) -> {oc['mean_2017']:.0f} (2017), {oc['growth_pct']:+.0f}%")
(root / "results" / "descriptive_levels.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
print("written results/descriptive_levels.json")
