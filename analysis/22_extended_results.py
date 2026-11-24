"""Questions 1-4 of EXTENDED_PLAN_2026-11-24.md, with the planned checks.

Usage: python 22_extended_results.py <project_dir>
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from blockpois import blockpois

root = Path(sys.argv[1])
der = root / "data" / "derived"
out_dir = root / "results" / "extended"
out_dir.mkdir(parents=True, exist_ok=True)
WEATHER = ["light", "wet", "t_lt5", "t_5_15", "t_15_25", "t_gt25", "sun_h"]
HOL = ["public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]
t0 = time.time()

wx = pd.read_parquet(der / "weather_stations_daily.parquet")
cal = pd.read_parquet(der / "calendar_daily.parquet")


def prep(df, dataset, station=None, cleaning=True):
    d = df.copy()
    if cleaning:
        d = d[d["keep"]]
    if station is not None:
        d["wx_station"] = station
    d = d.merge(wx, left_on=["wx_station", "date"], right_on=["station", "date"], how="inner")
    d = d.dropna(subset=["rain_day", "tmax", "sun_day"])
    d = d.merge(cal, on="date", how="left")
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
    d["dataset"] = dataset
    d["loc"] = d["loc"].astype(str)
    for h in HOL:
        d[h] = d[h].astype(float)
    return d


def bikes(cleaning=True, station="SMA"):
    c = pd.read_parquet(der / "counts_daily.parquet")
    c = c[c["complete"]].rename(columns={"velo_day": "y"})
    return prep(c, "bike", station=station, cleaning=cleaning)


def comb(beta, V, w):
    a = pd.Series(0.0, index=beta.index)
    for k, x in w.items():
        a[k] = x
    return float(a @ beta), float(np.sqrt(a @ V @ a)), a


def three(beta, V, fmt):
    """rain, cold, heat effects for coefficient names built by fmt(variable)."""
    return {"rain": comb(beta, V, {fmt("wet"): 1}),
            "cold": comb(beta, V, {fmt("t_lt5"): 5 / 15, fmt("t_5_15"): 10 / 15}),
            "heat": comb(beta, V, {fmt("t_gt25"): 1})}


def trend_model(d, datasets):
    """Each location keeps its own weather effect (local terms). Each data source has its own
    trend per decade in every weather term and its own holiday terms."""
    G = {}
    for ds in datasets:
        m = (d["dataset"] == ds).to_numpy().astype(float)
        for v in WEATHER:
            G[f"{v}:trend:{ds}"] = d[v].to_numpy() * d["trend"].to_numpy() * m
        for h in HOL:
            G[f"{h}:{ds}"] = d[h].to_numpy() * m
    G = pd.DataFrame(G)
    G = G.loc[:, G.std() > 0]
    return blockpois(d["y"], G.to_numpy(), d[WEATHER].to_numpy(), d["loc"], d["fe1"], d["dow"], d["week"], names=list(G.columns))


def period_model(d, early, late):
    d = d[d["year"].isin(list(early) + list(late))].copy()
    d["period"] = np.where(d["year"].isin(list(early)), "early", "late")
    G = {}
    for p in ("early", "late"):
        m = (d["period"] == p).to_numpy().astype(float)
        for v in WEATHER:
            G[f"{v}:{p}"] = d[v].to_numpy() * m
    for h in HOL:
        G[h] = d[h].to_numpy()
    G = pd.DataFrame(G)
    return blockpois(d["y"], G.to_numpy(), None, d["loc"], d["fe1"], d["dow"], d["week"], names=list(G.columns)), d


def fmt_ci(est, se):
    return {"est": est, "se": se, "ci95": [est - 1.96 * se, est + 1.96 * se]}


def drop_years(d, years):
    return d[d["year"].isin(years) & ~d["year"].isin([2020, 2021])]


R = {}


def q1(d, tag):
    s = drop_years(d, range(2011, 2027))
    r = trend_model(s, ["bike"])
    e = three(r["beta"], r["vcov"], lambda v: f"{v}:trend:bike")
    R[tag] = {"n": r["n"], "locations": r["locations"], **{k: fmt_ci(v[0], v[1]) for k, v in e.items()}}
    print(f"[{time.time() - t0:.0f}s] {tag}: n {r['n']}, locations {r['locations']} | trend per decade: "
          + " | ".join(f"{k} {v[0]:+.4f} [{v[0] - 1.96 * v[1]:+.4f}, {v[0] + 1.96 * v[1]:+.4f}]" for k, v in e.items()), flush=True)


def q_stack(d1, d2, years, ds1, ds2, tag):
    s = pd.concat([drop_years(d1, years), drop_years(d2, years)], ignore_index=True)
    r = trend_model(s, [ds1, ds2])
    b, V = r["beta"], r["vcov"]
    e1 = three(b, V, lambda v: f"{v}:trend:{ds1}")
    e2 = three(b, V, lambda v: f"{v}:trend:{ds2}")
    res = {"n": r["n"], "locations": r["locations"]}
    for k in ("rain", "cold", "heat"):
        a = e1[k][2] - e2[k][2]
        diff = float(a @ b)
        se = float(np.sqrt(a @ V @ a))
        res[k] = {ds1: fmt_ci(e1[k][0], e1[k][1]), ds2: fmt_ci(e2[k][0], e2[k][1]), f"{ds1}_minus_{ds2}": fmt_ci(diff, se)}
    R[tag] = res
    x = res["rain"]
    print(f"[{time.time() - t0:.0f}s] {tag}: n {r['n']}, locations {r['locations']} | wet-day trend per decade: "
          f"{ds1} {x[ds1]['est']:+.4f} [{x[ds1]['ci95'][0]:+.4f}, {x[ds1]['ci95'][1]:+.4f}], "
          f"{ds2} {x[ds2]['est']:+.4f} [{x[ds2]['ci95'][0]:+.4f}, {x[ds2]['ci95'][1]:+.4f}], "
          f"difference {x[f'{ds1}_minus_{ds2}']['est']:+.4f} [{x[f'{ds1}_minus_{ds2}']['ci95'][0]:+.4f}, {x[f'{ds1}_minus_{ds2}']['ci95'][1]:+.4f}]", flush=True)


def car_points(cd):
    c = cd.copy()
    c["year"] = c["date"].dt.year
    cy = c.groupby(["loc", "year"]).size().unstack(fill_value=0) >= 300
    e = cy.reindex(columns=range(2012, 2015), fill_value=False).sum(axis=1)
    l = cy.reindex(columns=range(2022, 2026), fill_value=False).sum(axis=1)
    return sorted(cy.index[(e >= 2) & (l >= 2)])


def q4(d, tag):
    r, s = period_model(d, range(2012, 2015), range(2022, 2027))
    b, V = r["beta"], r["vcov"]
    ee = three(b, V, lambda v: f"{v}:early")
    el = three(b, V, lambda v: f"{v}:late")
    res = {"n": r["n"], "locations": r["locations"]}
    for k in ("rain", "cold", "heat"):
        a = el[k][2] - ee[k][2]
        res[k] = {"early": fmt_ci(ee[k][0], ee[k][1]), "late": fmt_ci(el[k][0], el[k][1]),
                  "change": fmt_ci(float(a @ b), float(np.sqrt(a @ V @ a)))}
    R[tag] = res
    x = res["rain"]
    print(f"[{time.time() - t0:.0f}s] {tag}: n {r['n']}, points {r['locations']} | wet-day effect on cars: "
          f"early {x['early']['est']:+.4f} [{x['early']['ci95'][0]:+.4f}, {x['early']['ci95'][1]:+.4f}], "
          f"late {x['late']['est']:+.4f} [{x['late']['ci95'][0]:+.4f}, {x['late']['ci95'][1]:+.4f}], "
          f"change {x['change']['est']:+.4f} [{x['change']['ci95'][0]:+.4f}, {x['change']['ci95'][1]:+.4f}]", flush=True)


# ---------------- main results ----------------
B = bikes()
q1(B, "Q1_bikes_trend")

P = prep(pd.read_parquet(der / "ped_daily.parquet"), "walk", station="SMA")
q_stack(B, P, range(2014, 2023), "bike", "walk", "Q2_bike_vs_walk")

K = prep(pd.read_parquet(der / "canton_daily_clean.parquet"), "canton")
q_stack(K, B, range(2017, 2026), "canton", "bike", "Q3_canton_vs_city_exploratory")

cd = pd.read_parquet(der / "car_daily.parquet")
pts = car_points(cd)
print("car points with >=2 good years in both periods:", len(pts))
Cars = prep(cd[cd["loc"].isin(pts)], "car", station="SMA")
q4(Cars, "Q4_cars_periods")
(out_dir / "extended_results.json").write_text(json.dumps(R, indent=2, default=float))

# ---------------- checks ----------------
Breh = bikes(station="REH")
q1(Breh, "check_Q1_affoltern")
q_stack(Breh, prep(pd.read_parquet(der / "ped_daily.parquet"), "walk", station="REH"), range(2014, 2023), "bike", "walk", "check_Q2_affoltern")
q4(prep(cd[cd["loc"].isin(pts)], "car", station="REH"), "check_Q4_affoltern")
Bnc = bikes(cleaning=False)
q1(Bnc, "check_Q1_no_cleaning")
q_stack(Bnc, prep(pd.read_parquet(der / "ped_daily.parquet"), "walk", station="SMA", cleaning=False), range(2014, 2023), "bike", "walk", "check_Q2_no_cleaning")
q_stack(prep(pd.read_parquet(der / "canton_daily_clean.parquet"), "canton", cleaning=False), Bnc, range(2017, 2026), "canton", "bike", "check_Q3_no_cleaning")
q4(prep(cd[cd["loc"].isin(pts)], "car", station="SMA", cleaning=False), "check_Q4_no_cleaning")
(out_dir / "extended_results.json").write_text(json.dumps(R, indent=2, default=float))

# all car points, trend per decade with each point's own weather effect
CarsAll = prep(cd, "car", station="SMA")
s = drop_years(CarsAll, range(2012, 2027))
r = trend_model(s, ["car"])
e = three(r["beta"], r["vcov"], lambda v: f"{v}:trend:car")
R["check_Q4_all_points_trend"] = {"n": r["n"], "locations": r["locations"], **{k: fmt_ci(v[0], v[1]) for k, v in e.items()}}
print(f"[{time.time() - t0:.0f}s] check_Q4_all_points_trend: n {r['n']}, points {r['locations']} | trend per decade: "
      + " | ".join(f"{k} {v[0]:+.4f} [{v[0] - 1.96 * v[1]:+.4f}, {v[0] + 1.96 * v[1]:+.4f}]" for k, v in e.items()), flush=True)
(out_dir / "extended_results.json").write_text(json.dumps(R, indent=2, default=float))
print(f"done [{time.time() - t0:.0f}s]")
