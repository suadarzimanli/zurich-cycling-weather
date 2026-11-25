"""Checks added after the results, in response to likely reviewer questions (not in the locked plans).

A. Did wet days become milder or differently timed? Distribution of rain amount and rain hours on wet days, by period.
B. Rain intensity classes (2-5, 5-10, 10+ mm): change in each class, and a wet-day effect that holds the
   early-period mix of intensities fixed in both periods.
C. Rain hours and rain in commute hours added as controls.
D. Wind speed added as a control.
E. Standard errors clustered by month instead of week (prediction 1, question 1, question 2).

Weather: Zürich/Fluntern ten-minute values. Daytime = 6:00-20:00 local time.
Usage: python 26_review_checks.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from blockpois import blockpois

root = Path(sys.argv[1])
raw = root / "data" / "raw" / "meteoswiss"
der = root / "data" / "derived"
out = root / "results" / "review_checks"
out.mkdir(parents=True, exist_ok=True)
HOL = ["public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]
TEMP = ["t_lt5", "t_5_15", "t_15_25", "t_gt25"]

# ---------- extra daily weather from ten-minute data ----------
files = [raw / f"ogd-smn_sma_t_{s}.csv" for s in ("historical_2010-2019", "historical_2020-2029", "recent")]
w = pd.concat([pd.read_csv(f, sep=";", usecols=["reference_timestamp", "rre150z0", "fkl010z0"]) for f in files])
w["utc_end"] = pd.to_datetime(w["reference_timestamp"], format="%d.%m.%Y %H:%M")
w = w.drop_duplicates("utc_end")
w["start"] = (w["utc_end"] - pd.Timedelta(minutes=10)).dt.tz_localize("UTC").dt.tz_convert("Europe/Zurich").dt.tz_localize(None)
w["date"] = w["start"].dt.normalize()
w["hour"] = w["start"].dt.hour
d = w[(w["hour"] >= 6) & (w["hour"] < 20)]
hourly = d.groupby(["date", "hour"])["rre150z0"].sum(min_count=1).reset_index()
extra = pd.DataFrame({
    "rain_hours": hourly.assign(r=hourly["rre150z0"] >= 0.1).groupby("date")["r"].sum(),
    "max_hour_rain": hourly.groupby("date")["rre150z0"].max(),
    "commute_rain": d[d["hour"].isin([7, 8, 16, 17, 18])].groupby("date")["rre150z0"].sum(min_count=1),
    "wind": d.groupby("date")["fkl010z0"].mean(),
}).reset_index()
extra.to_parquet(der / "weather_extra_sma.parquet", index=False)

wx = pd.read_parquet(der / "weather_stations_daily.parquet")
wx = wx[wx["station"] == "SMA"].drop(columns="station")
cal = pd.read_parquet(der / "calendar_daily.parquet")


def prep(df, cleaning=True):
    d = df.copy()
    if cleaning:
        d = d[d["keep"]]
    d = d.merge(wx, on="date").merge(extra, on="date").dropna(subset=["rain_day", "tmax", "sun_day", "wind"])
    d = d.merge(cal, on="date", how="left")
    r, t = d["rain_day"], d["tmax"]
    d["light"] = ((r >= 0.1) & (r < 2)).astype(float)
    d["wet"] = (r >= 2).astype(float)
    d["wet_2_5"] = ((r >= 2) & (r < 5)).astype(float)
    d["wet_5_10"] = ((r >= 5) & (r < 10)).astype(float)
    d["wet_10"] = (r >= 10).astype(float)
    d["commute_wet"] = (d["commute_rain"] >= 0.5).astype(float)
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
    d["month"] = d["date"].dt.strftime("%Y-%m")
    for h in HOL:
        d[h] = d[h].astype(float)
    d["loc"] = d["loc"].astype(str)
    return d


c = pd.read_parquet(der / "counts_daily.parquet")
c = c[c["complete"]].rename(columns={"velo_day": "y"})
core = json.loads((der / "sample_definitions.json").read_text())["period_comparison_locations"]
B = prep(c)
P9 = B[B["loc"].isin(core) & B["year"].isin([2011, 2012, 2013, 2014, 2022, 2023, 2024, 2025, 2026])].copy()
P9["period"] = np.where(P9["year"] <= 2014, "early", "late")
R = {}


def period_fit(d, weather, cluster="week"):
    G = {}
    for p in ("early", "late"):
        m = (d["period"] == p).to_numpy().astype(float)
        for v in weather:
            G[f"{v}:{p}"] = d[v].to_numpy() * m
    for h in HOL:
        G[h] = d[h].to_numpy()
    G = pd.DataFrame(G)
    return blockpois(d["y"], G.to_numpy(), None, d["loc"], d["fe1"], d["dow"], d[cluster], names=list(G.columns))


def lin(r, w):
    a = pd.Series(0.0, index=r["beta"].index)
    for k, v in w.items():
        a[k] = v
    est = float(a @ r["beta"])
    se = float(np.sqrt(a @ r["vcov"] @ a))
    return {"est": est, "se": se, "ci95": [est - 1.96 * se, est + 1.96 * se]}


def show(label, x):
    print(f"{label:62s} {x['est']:+.4f} [{x['ci95'][0]:+.4f}, {x['ci95'][1]:+.4f}]", flush=True)


# ---------- A. did wet days change? ----------
wd = P9.drop_duplicates("date")
wd = wd[wd["wet"] == 1]
desc = wd.groupby("period").agg(wet_days=("date", "size"), mean_rain=("rain_day", "mean"), median_rain=("rain_day", "median"),
                                 mean_rain_hours=("rain_hours", "mean"), share_commute_wet=("commute_wet", "mean"),
                                 share_10mm=("wet_10", "mean"), share_2_5mm=("wet_2_5", "mean"))
R["A_wet_day_mix"] = desc.round(3).to_dict(orient="index")
print("A. wet days by period (Fluntern, days present in the 9-location sample):\n", desc.round(2).to_string())

# ---------- main (reproduce) ----------
BASE = ["light", "wet"] + TEMP + ["sun_h"]
r0 = period_fit(P9, BASE)
R["main_change"] = lin(r0, {"wet:late": 1, "wet:early": -1})
show("Main result reproduced: change in wet-day effect", R["main_change"])

# ---------- B. intensity classes ----------
INT = ["light", "wet_2_5", "wet_5_10", "wet_10"] + TEMP + ["sun_h"]
r1 = period_fit(P9, INT)
shares = wd[wd["period"] == "early"][["wet_2_5", "wet_5_10", "wet_10"]].mean()
shares = shares / shares.sum()
for k in ("wet_2_5", "wet_5_10", "wet_10"):
    R[f"B_change_{k}"] = lin(r1, {f"{k}:late": 1, f"{k}:early": -1})
    show(f"B. change in effect of {k}", R[f"B_change_{k}"])
R["B_change_fixed_mix"] = lin(r1, {**{f"{k}:late": shares[k] for k in shares.index}, **{f"{k}:early": -shares[k] for k in shares.index}})
R["B_early_mix_shares"] = shares.round(3).to_dict()
show("B. change in wet-day effect, early intensity mix held fixed", R["B_change_fixed_mix"])

# ---------- C. rain hours and commute rain ----------
r2 = period_fit(P9, BASE + ["rain_hours", "commute_wet"])
R["C_change_with_hours_commute"] = lin(r2, {"wet:late": 1, "wet:early": -1})
show("C. change in wet-day effect, with rain hours and commute rain", R["C_change_with_hours_commute"])

# ---------- D. wind ----------
r3 = period_fit(P9, BASE + ["wind"])
R["D_change_with_wind"] = lin(r3, {"wet:late": 1, "wet:early": -1})
R["D_wind_effect_early"] = lin(r3, {"wind:early": 1})
show("D. change in wet-day effect, with wind", R["D_change_with_wind"])
show("D. wind effect per m/s, early period", R["D_wind_effect_early"])

# ---------- E. clustering by month ----------
r4 = period_fit(P9, BASE, cluster="month")
R["E_change_month_clusters"] = lin(r4, {"wet:late": 1, "wet:early": -1})
show("E. prediction 1, clustered by month", R["E_change_month_clusters"])


def trend_fit(d, datasets, cluster):
    G = {}
    for ds in datasets:
        m = (d["dataset"] == ds).to_numpy().astype(float)
        for v in BASE:
            G[f"{v}:trend:{ds}"] = d[v].to_numpy() * d["trend"].to_numpy() * m
        for h in HOL:
            G[f"{h}:{ds}"] = d[h].to_numpy() * m
    G = pd.DataFrame(G)
    G = G.loc[:, G.std() > 0]
    return blockpois(d["y"], G.to_numpy(), d[BASE].to_numpy(), d["loc"], d["fe1"], d["dow"], d[cluster], names=list(G.columns))


Q1 = B[B["year"].between(2011, 2026) & ~B["year"].isin([2020, 2021])].assign(dataset="bike")
r5 = trend_fit(Q1, ["bike"], "month")
R["E_Q1_trend_month_clusters"] = lin(r5, {"wet:trend:bike": 1})
show("E. question 1 (trend per decade), clustered by month", R["E_Q1_trend_month_clusters"])
ped = pd.read_parquet(der / "ped_daily.parquet")
W = prep(ped).assign(dataset="walk")
yrs = list(range(2014, 2023))
Q2 = pd.concat([B[B["year"].isin(yrs)].assign(dataset="bike"), W[W["year"].isin(yrs)]], ignore_index=True)
Q2 = Q2[~Q2["year"].isin([2020, 2021])]
r6 = trend_fit(Q2, ["bike", "walk"], "month")
R["E_Q2_difference_month_clusters"] = lin(r6, {"wet:trend:bike": 1, "wet:trend:walk": -1})
show("E. question 2 (cycling minus walking), clustered by month", R["E_Q2_difference_month_clusters"])

(out / "review_checks.json").write_text(json.dumps(R, indent=2, default=float))
print("saved", out / "review_checks.json")
