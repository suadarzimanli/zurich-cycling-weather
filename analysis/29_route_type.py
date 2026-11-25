"""Check added after the results (docs/CHECK_ROUTE_TYPE_2026-11-25.md, fixed before running):
did the rain effect weaken on commuter-type routes, on leisure-type routes, or on both?

Locations are split at the median of the weekend ratio (mean daytime count on Saturdays and Sundays
divided by the mean on working days that are not public holidays, all kept days, without 2020-2021).
Then the trend design of question 1 is estimated with a separate trend per decade for each group.

Usage: python 29_route_type.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from blockpois import blockpois

root = Path(sys.argv[1])
der = root / "data" / "derived"
WEATHER = ["light", "wet", "t_lt5", "t_5_15", "t_15_25", "t_gt25", "sun_h"]
HOL = ["public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]

wx = pd.read_parquet(der / "weather_stations_daily.parquet")
cal = pd.read_parquet(der / "calendar_daily.parquet")
c = pd.read_parquet(der / "counts_daily.parquet")
c = c[c["complete"] & c["keep"]].rename(columns={"velo_day": "y"})
c = c[~c["date"].dt.year.isin([2020, 2021]) & (c["date"].dt.year >= 2011)]

# ---- classification: counts and calendar only ----
k = c.merge(cal[["date", "public_holiday", "dow"]], on="date", how="left")
wkday = k[(k["date"].dt.dayofweek < 5) & (k["public_holiday"] == 0)]
wkend = k[k["date"].dt.dayofweek >= 5]
ratio = (wkend.groupby("loc")["y"].mean() / wkday.groupby("loc")["y"].mean()).rename("weekend_ratio")
med = ratio.median()
group = pd.Series(np.where(ratio <= med, "commuter", "leisure"), index=ratio.index, name="group")
names = c.groupby("loc")["name"].last()
tab = pd.concat([ratio, group, names], axis=1).sort_values("weekend_ratio")
print(f"median weekend ratio {med:.3f}")
print(tab.to_string())


# ---- trend design of question 1, separate trends by group ----
def prep(df):
    d = df.copy()
    d["wx_station"] = "SMA"
    d = d.merge(wx, left_on=["wx_station", "date"], right_on=["station", "date"], how="inner")
    d = d.dropna(subset=["rain_day", "tmax", "sun_day"]).merge(cal, on="date", how="left")
    r, t = d["rain_day"], d["tmax"]
    d["light"] = ((r >= 0.1) & (r < 2)).astype(float)
    d["wet"] = (r >= 2).astype(float)
    d["t_lt5"] = np.minimum(t, 5.0)
    d["t_5_15"] = np.clip(t - 5, 0, 10)
    d["t_15_25"] = np.clip(t - 15, 0, 10)
    d["t_gt25"] = np.maximum(t - 25, 0)
    d["sun_h"] = d["sun_day"] / 60
    d["year"] = d["date"].dt.year
    d["trend"] = (d["year"] - 2011) / 10
    d["fe1"] = d["device"].astype(str) + "_" + d["date"].dt.strftime("%Y-%m")
    iso = d["date"].dt.isocalendar()
    d["week"] = iso["year"].astype(str) + "-" + iso["week"].astype(str)
    d["loc"] = d["loc"].astype(str)
    for h in HOL:
        d[h] = d[h].astype(float)
    return d


d = prep(c)
d["dataset"] = d["loc"].map(group)
G = {}
for ds in ("commuter", "leisure"):
    m = (d["dataset"] == ds).to_numpy().astype(float)
    for v in WEATHER:
        G[f"{v}:trend:{ds}"] = d[v].to_numpy() * d["trend"].to_numpy() * m
    for h in HOL:
        G[f"{h}:{ds}"] = d[h].to_numpy() * m
G = pd.DataFrame(G)
G = G.loc[:, G.std() > 0]
r = blockpois(d["y"], G.to_numpy(), d[WEATHER].to_numpy(), d["loc"], d["fe1"], d["dow"], d["week"], names=list(G.columns))


def lin(w):
    a = pd.Series(0.0, index=r["beta"].index)
    for key, x in w.items():
        a[key] = x
    est, se = float(a @ r["beta"]), float(np.sqrt(a @ r["vcov"] @ a))
    return {"est": est, "se": se, "ci95": [est - 1.96 * se, est + 1.96 * se]}


res = {"median_weekend_ratio": float(med), "n": int(r["n"]), "locations": int(r["locations"]),
       "groups": {g: sorted(group.index[group == g].tolist()) for g in ("commuter", "leisure")},
       "weekend_ratio": {loc: float(x) for loc, x in ratio.items()},
       "rain_trend_commuter": lin({"wet:trend:commuter": 1}),
       "rain_trend_leisure": lin({"wet:trend:leisure": 1}),
       "rain_trend_commuter_minus_leisure": lin({"wet:trend:commuter": 1, "wet:trend:leisure": -1})}
print(f"n {res['n']}, locations {res['locations']} (commuter {len(res['groups']['commuter'])}, leisure {len(res['groups']['leisure'])})")
for key in ("rain_trend_commuter", "rain_trend_leisure", "rain_trend_commuter_minus_leisure"):
    x = res[key]
    print(f"{key:36s} {x['est']:+.4f} [{x['ci95'][0]:+.4f}, {x['ci95'][1]:+.4f}]")
out = root / "results" / "review_checks"
(out / "route_type.json").write_text(json.dumps(res, indent=2))
