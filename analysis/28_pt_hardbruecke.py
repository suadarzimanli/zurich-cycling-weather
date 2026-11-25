"""Check added after the results: do public transport passengers rise or fall on wet days?

Data: 5-minute people counts at the VBZ stop Hardbrücke (City of Zurich open data), reliable from
mid-January 2024 (earlier counts are documented as faulty). Compared on the same days with the two
bicycle counters on the Hardbrücke (Hardbrücke Nord and Süd).

Outcomes (daytime 6:00-20:00):
  pt_vbz : people boarding or leaving VBZ trams and buses at the stop (In + Out, both platforms)
  pt_sbb : people walking between the stop and the S-Bahn station (In + Out, both sides)
  bike   : the two Hardbrücke bicycle counters
Same model as the main analysis (month and weekday effects, holidays, weather from Fluntern),
estimated jointly so that the difference between modes accounts for shared weather days.

Usage: python 28_pt_hardbruecke.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from blockpois import blockpois

root = Path(sys.argv[1])
raw = root / "data" / "raw" / "vbz_hardbruecke"
der = root / "data" / "derived"
START, END = pd.Timestamp("2024-01-16"), pd.Timestamp("2026-11-22")
WEATHER = ["light", "wet", "t_lt5", "t_5_15", "t_15_25", "t_gt25", "sun_h"]
HOL = ["public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]

v = pd.concat([pd.read_parquet(f) for f in sorted(raw.glob("*.parquet"))], ignore_index=True)
v["Name"] = v["Name"].str.lower().str.strip()
v = v.drop_duplicates(["Timestamp", "Name"])
v["date"] = v["Timestamp"].dt.normalize()
v["hour"] = v["Timestamp"].dt.hour
v = v[(v["hour"] >= 6) & (v["hour"] < 20) & (v["date"] >= START) & (v["date"] <= END)]
v["n"] = v["In"] + v["Out"]
lines = {"pt_vbz": ["ost-vbz total", "west-vbz total"], "pt_sbb": ["ost-sbb total", "west-sbb total"]}
rows = []
for name, ls in lines.items():
    s = v[v["Name"].isin(ls)]
    g = s.groupby(["date", "Name"]).agg(slots=("n", "size"), n=("n", "sum")).reset_index()
    ok = g[g["slots"] >= 160].groupby("date").filter(lambda x: len(x) == len(ls))  # both platforms nearly complete
    d = ok.groupby("date")["n"].sum().rename("y").reset_index()
    d["loc"] = name
    rows.append(d)
pt = pd.concat(rows, ignore_index=True)

# same cleaning rule as for the counters
pt = pt.sort_values(["loc", "date"]).reset_index(drop=True)
pt["ym"] = pt["date"].dt.to_period("M").astype(str)
med = pt.groupby(["loc", "ym"])["y"].transform("median")
same = (pt["loc"] == pt["loc"].shift()) & (pt["y"] == pt["y"].shift()) & ((pt["date"] - pt["date"].shift()).dt.days == 1)
run = (~same).cumsum()
stuck = pt.groupby(run)["y"].transform("size") >= 3
pt["keep"] = (pt["y"] > 0) & (pt["y"] >= 0.05 * med) & (pt["y"] <= 5 * med) & ~stuck
pt = pt[pt["keep"]]
pt["device"] = pt["loc"]

c = pd.read_parquet(der / "counts_daily.parquet")
bk = c[c["complete"] & c["keep"] & c["loc"].isin(["VZS_HARN", "VZS_HARS"]) & (c["date"] >= START) & (c["date"] <= END)]
bk = bk.rename(columns={"velo_day": "y"})[["loc", "device", "date", "y"]]
bk["device"] = bk["device"].astype(str)

wx = pd.read_parquet(der / "weather_stations_daily.parquet")
wx = wx[wx["station"] == "SMA"].drop(columns="station")
cal = pd.read_parquet(der / "calendar_daily.parquet")


def prep(d, dataset):
    d = d.merge(wx, on="date").dropna(subset=["rain_day", "tmax", "sun_day"]).merge(cal, on="date", how="left")
    r, t = d["rain_day"], d["tmax"]
    d["light"] = ((r >= 0.1) & (r < 2)).astype(float)
    d["wet"] = (r >= 2).astype(float)
    d["t_lt5"] = np.minimum(t, 5.0)
    d["t_5_15"] = np.clip(t - 5, 0, 10)
    d["t_15_25"] = np.clip(t - 15, 0, 10)
    d["t_gt25"] = np.maximum(t - 25, 0)
    d["sun_h"] = d["sun_day"] / 60
    d["fe1"] = d["device"].astype(str) + "_" + d["date"].dt.strftime("%Y-%m")
    iso = d["date"].dt.isocalendar()
    d["week"] = iso["year"].astype(str) + "-" + iso["week"].astype(str)
    for h in HOL:
        d[h] = d[h].astype(float)
    d["dataset"] = dataset
    d["loc"] = d["loc"].astype(str)
    return d


D = pd.concat([prep(pt[pt["loc"] == "pt_vbz"], "pt_vbz"), prep(pt[pt["loc"] == "pt_sbb"], "pt_sbb"), prep(bk, "bike")], ignore_index=True)
common = set(D[D["dataset"] == "pt_vbz"]["date"]) & set(D[D["dataset"] == "bike"]["date"])
D = D[D["date"].isin(common)]
G = {}
for ds in ("pt_vbz", "pt_sbb", "bike"):
    m = (D["dataset"] == ds).to_numpy().astype(float)
    for w in WEATHER:
        G[f"{w}:{ds}"] = D[w].to_numpy() * m
    for h in HOL:
        G[f"{h}:{ds}"] = D[h].to_numpy() * m
G = pd.DataFrame(G)
G = G.loc[:, G.std() > 0]
r = blockpois(D["y"], G.to_numpy(), None, D["loc"], D["fe1"], D["dow"], D["week"], names=list(G.columns))


def lin(w):
    a = pd.Series(0.0, index=r["beta"].index)
    for k, x in w.items():
        a[k] = x
    est, se = float(a @ r["beta"]), float(np.sqrt(a @ r["vcov"] @ a))
    return {"est": est, "ci95": [est - 1.96 * se, est + 1.96 * se], "pct": 100 * (np.exp(est) - 1),
            "pct_ci": [100 * (np.exp(est - 1.96 * se) - 1), 100 * (np.exp(est + 1.96 * se) - 1)]}


res = {"days": int(D[D["dataset"] == "pt_vbz"]["date"].nunique()),
       "wet_days": int(D[(D["dataset"] == "pt_vbz") & (D["wet"] == 1)]["date"].nunique()),
       "period": [str(min(common).date()), str(max(common).date())],
       "mean_daytime": {ds: int(D[D["dataset"] == ds]["y"].mean()) for ds in ("pt_vbz", "pt_sbb", "bike")}}
for ds in ("pt_vbz", "pt_sbb", "bike"):
    res[f"wet_{ds}"] = lin({f"wet:{ds}": 1})
res["wet_pt_vbz_minus_bike"] = lin({"wet:pt_vbz": 1, "wet:bike": -1})
print(f"days {res['days']} ({res['wet_days']} wet), {res['period'][0]} to {res['period'][1]} | mean daytime counts {res['mean_daytime']}")
for k in ("wet_pt_vbz", "wet_pt_sbb", "wet_bike", "wet_pt_vbz_minus_bike"):
    x = res[k]
    print(f"{k:24s} {x['est']:+.4f} [{x['ci95'][0]:+.4f}, {x['ci95'][1]:+.4f}]  = {x['pct']:+.1f}% [{x['pct_ci'][0]:+.1f}%, {x['pct_ci'][1]:+.1f}%]")
out = root / "results" / "review_checks"
out.mkdir(parents=True, exist_ok=True)
(out / "pt_hardbruecke.json").write_text(json.dumps(res, indent=2, default=float))
