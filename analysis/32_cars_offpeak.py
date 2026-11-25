"""Check added after the results, rule fixed in docs/CHECK_OFFPEAK_PROPORTIONAL_2026-11-25.md (check A)
before it was run: is car traffic higher on wet days outside the peak hours, when most roads are not full?

Same 134 measuring points, years and days as question 4 (22_extended_results.py). Two hour bands from the
hourly counts (the hour stamp is the start of the hour):
  off-peak  9:00-16:00 on every day
  peak      7:00-9:00 and 16:00-19:00 on working days (Monday to Friday, not a public holiday)
Both bands in one period model, each with its own weather terms by period and its own holiday terms.

Usage: python 32_cars_offpeak.py <project_dir>
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
WEATHER = ["light", "wet", "t_lt5", "t_5_15", "t_15_25", "t_gt25", "sun_h"]
HOL = ["public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]
t0 = time.time()

wx = pd.read_parquet(der / "weather_stations_daily.parquet")
cal = pd.read_parquet(der / "calendar_daily.parquet")
cd = pd.read_parquet(der / "car_daily.parquet")


def car_points(cd):  # as in 22_extended_results.py
    c = cd.copy()
    c["year"] = c["date"].dt.year
    cy = c.groupby(["loc", "year"]).size().unstack(fill_value=0) >= 300
    e = cy.reindex(columns=range(2012, 2015), fill_value=False).sum(axis=1)
    l = cy.reindex(columns=range(2022, 2026), fill_value=False).sum(axis=1)
    return sorted(cy.index[(e >= 2) & (l >= 2)])


pts = car_points(cd)
assert len(pts) == 134, len(pts)
days = cd[cd["loc"].isin(pts) & cd["keep"]][["loc", "date"]]
days = days[days["date"].dt.year.isin(list(range(2012, 2015)) + list(range(2022, 2027)))]

# hourly counts of these points, same reading as 20_build_extended.py
car = pd.read_parquet(root / "data" / "raw" / "zurich_cars" / "sid_dav_verkehrszaehlung_miv_od2031_alle_jahre.parquet",
                      columns=["MSID", "MessungDatZeit", "AnzFahrzeuge", "AnzFahrzeugeStatus"],
                      filters=[("MSID", "in", pts)])
car["t"] = pd.to_datetime(car["MessungDatZeit"].str[:19])
car = car.drop_duplicates(["MSID", "t"])
hr = car["t"].dt.hour
car["date"] = car["t"].dt.normalize()
car["band"] = np.select([(hr >= 9) & (hr < 16), hr.isin([7, 8, 16, 17, 18])], ["offpeak", "peak"], "")
car = car[car["band"] != ""]
car["measured"] = car["AnzFahrzeugeStatus"] == "Gemessen"
bands = car.groupby(["MSID", "date", "band"]).agg(y=("AnzFahrzeuge", "sum"), hours=("measured", "sum")).reset_index()
bands = bands.rename(columns={"MSID": "point"}).merge(days.rename(columns={"loc": "point"}), on=["point", "date"])
need = {"offpeak": 7, "peak": 5}
assert (bands["hours"] == bands["band"].map(need)).all(), "a kept day has an unmeasured hour"
print(f"[{time.time() - t0:.0f}s] hourly counts read: {len(bands)} point-day-bands", flush=True)

d = bands.merge(cal, on="date", how="left")
working = (d["date"].dt.dayofweek < 5) & (d["public_holiday"] == 0)
d = d[(d["band"] == "offpeak") | working].copy()

d["wx_station"] = "SMA"
d = d.merge(wx, left_on=["wx_station", "date"], right_on=["station", "date"], how="inner")
d = d.dropna(subset=["rain_day", "tmax", "sun_day"])
r_, t_ = d["rain_day"], d["tmax"]
d["light"] = ((r_ >= 0.1) & (r_ < 2)).astype(float)
d["wet"] = (r_ >= 2).astype(float)
d["t_lt5"] = np.minimum(t_, 5.0)
d["t_5_15"] = np.clip(t_ - 5, 0, 10)
d["t_15_25"] = np.clip(t_ - 15, 0, 10)
d["t_gt25"] = np.maximum(t_ - 25, 0)
d["sun_h"] = d["sun_day"] / 60
d["year"] = d["date"].dt.year
d["period"] = np.where(d["year"] <= 2014, "early", "late")
d["loc"] = d["point"].astype(str) + "|" + d["band"]
d["fe1"] = d["loc"] + "_" + d["date"].dt.strftime("%Y-%m")
iso = d["date"].dt.isocalendar()
d["week"] = iso["year"].astype(str) + "-" + iso["week"].astype(str)
for h in HOL:
    d[h] = d[h].astype(float)

G = {}
for band in ("offpeak", "peak"):
    mb = (d["band"] == band).to_numpy().astype(float)
    for p in ("early", "late"):
        m = mb * (d["period"] == p).to_numpy()
        for v in WEATHER:
            G[f"{v}:{p}:{band}"] = d[v].to_numpy() * m
    for h in HOL:
        G[f"{h}:{band}"] = d[h].to_numpy() * mb
G = pd.DataFrame(G)
G = G.loc[:, G.std() > 0]
r = blockpois(d["y"], G.to_numpy(), None, d["loc"], d["fe1"], d["dow"], d["week"], names=list(G.columns))
b, V = r["beta"], r["vcov"]
print(f"[{time.time() - t0:.0f}s] model done: n {r['n']}, point-bands {r['locations']}", flush=True)


def lin(w):
    a = pd.Series(0.0, index=b.index)
    for k, x in w.items():
        a[k] = x
    est, se = float(a @ b), float(np.sqrt(a @ V @ a))
    return {"est": est, "se": se, "ci95": [est - 1.96 * se, est + 1.96 * se], "pct": 100 * (np.exp(est) - 1)}


res = {"n": int(r["n"]), "point_bands": int(r["locations"]), "points": len(pts),
       "days_by_band": d.groupby("band").size().to_dict(), "wet_days_by_band": d[d["wet"] == 1].groupby("band").size().to_dict()}
for band in ("offpeak", "peak"):
    for p in ("early", "late"):
        res[f"wet_{band}_{p}"] = lin({f"wet:{p}:{band}": 1})
for p in ("early", "late"):
    res[f"wet_offpeak_minus_peak_{p}"] = lin({f"wet:{p}:offpeak": 1, f"wet:{p}:peak": -1})
for key, x in res.items():
    if isinstance(x, dict) and "est" in x:
        print(f"{key:32s} {x['est']:+.4f} [{x['ci95'][0]:+.4f}, {x['ci95'][1]:+.4f}]  ({x['pct']:+.1f}%)")
out = root / "results" / "review_checks"
(out / "cars_offpeak.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
print(f"written {out / 'cars_offpeak.json'} [{time.time() - t0:.0f}s]")
