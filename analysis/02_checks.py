"""Checks before the plan is registered. Data quality and coverage only.
No count data is joined to weather and no weather effect is estimated.

Usage: python 02_checks.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1])
raw = root / "data" / "raw"
out = root / "data" / "inventory"
out.mkdir(parents=True, exist_ok=True)
pd.set_option("display.width", 220)
pd.set_option("display.max_columns", 40)

print("=== A. Combined parquet vs 2026 yearly CSV (overlap must match)")
pq = pd.read_parquet(raw / "zurich_counts" / "verkehrszaehlungen_werte_fussgaenger_velo_alle_jahre.parquet")
c26 = pd.read_csv(raw / "zurich_counts" / "2026_verkehrszaehlungen_werte_fussgaenger_velo.csv")
for d in (pq, c26):
    d["DATUM"] = pd.to_datetime(d["DATUM"])
key = ["FK_STANDORT", "DATUM"]
cols = ["VELO_IN", "VELO_OUT"]
a = pq[pq["DATUM"] >= "2026-01-01"].dropna(subset=cols, how="all")[key + cols]
b = c26.dropna(subset=cols, how="all")[key + cols]
m = a.merge(b, on=key, how="outer", suffixes=("_pq", "_csv"), indicator=True)
print("parquet 2026 bike rows", len(a), "| csv 2026 bike rows", len(b), "| csv max date", b["DATUM"].max())
ov = m[m["_merge"] == "both"]
print("overlap rows", len(ov), "| only in parquet", int((m["_merge"] == "left_only").sum()),
      "| only in csv before 2026-06-07", int(((m["_merge"] == "right_only") & (m["DATUM"] < "2026-06-07")).sum()))
diff = ((ov["VELO_IN_pq"].fillna(-1) != ov["VELO_IN_csv"].fillna(-1)) | (ov["VELO_OUT_pq"].fillna(-1) != ov["VELO_OUT_csv"].fillna(-1))).sum()
print("overlap rows with different values:", int(diff))

# combined bike data: parquet before 2026 plus the 2026 CSV
v = pd.concat([pq[pq["DATUM"] < "2026-01-01"], c26], ignore_index=True)
v = v.dropna(subset=cols, how="all")[["FK_STANDORT", "DATUM", "VELO_IN", "VELO_OUT"]].copy()
dups = v.duplicated(subset=key).sum()
print("duplicate (site, time) rows:", int(dups))

print("\n=== B. Station metadata match")
gj = json.loads((raw / "zurich_stations" / "standorte.geojson").read_text(encoding="utf-8"))
meta = pd.DataFrame([f["properties"] for f in gj["features"]])
bike_meta = meta[meta["velo"] == 1].set_index("id1")
sites = v["FK_STANDORT"].unique()
missing = [s for s in sites if s not in bike_meta.index]
print("bike sites in data", len(sites), "| not in metadata:", missing)
v["loc"] = v["FK_STANDORT"].map(bike_meta["abkuerzung"])
print("distinct locations (abkuerzung):", v["loc"].nunique())

print("\n=== C. Time stamps and daylight saving (local time expected)")
v["date"] = v["DATUM"].dt.normalize()
for day in ["2024-03-31", "2024-10-27", "2025-03-30", "2025-10-26"]:
    s = v[v["date"] == day].groupby("FK_STANDORT").size()
    print(day, "slots per site: min", s.min(), "median", s.median(), "max", s.max())
# do 15-min stamps start at :00 and how many distinct minute values
print("minute values:", sorted(v["DATUM"].dt.minute.unique()))

print("\n=== D. Daytime coverage (6:00-20:00 = 56 slots) per location and year")
v["hour"] = v["DATUM"].dt.hour
day = v[(v["hour"] >= 6) & (v["hour"] < 20)].copy()
day["velo"] = day["VELO_IN"].fillna(0) + day["VELO_OUT"].fillna(0)
g = day.groupby(["loc", "FK_STANDORT", "date"]).agg(slots=("velo", "size"), velo=("velo", "sum")).reset_index()
g["complete"] = g["slots"] >= 56
g["year"] = g["date"].dt.year
comp = g[g["complete"]]
print("complete daytime location-days:", len(comp), "| of all location-days", len(g))

print("\n=== E. Suspicious values among complete days")
print("days with 0 bikes in 6-20:", int((comp["velo"] == 0).sum()))
# relative to the location's median of the same calendar month and year
comp = comp.copy()
comp["ym"] = comp["date"].dt.to_period("M")
med = comp.groupby(["loc", "FK_STANDORT", "ym"])["velo"].transform("median")
comp["ratio"] = comp["velo"] / med
for thr in (0.05, 0.1, 0.2):
    print(f"days below {thr:.0%} of the location-month median:", int((comp["ratio"] < thr).sum()))
for thr in (3, 5):
    print(f"days above {thr}x the location-month median:", int((comp["ratio"] > thr).sum()))
# runs of identical daily totals (stuck counter)
comp = comp.sort_values(["FK_STANDORT", "date"])
same = comp.groupby("FK_STANDORT")["velo"].diff().eq(0)
print("days with the same total as the previous day:", int(same.sum()))
# 15-min slots with implausibly high values
hi = day[day["velo"] > 1000]
print("15-min slots above 1000 bikes:", len(hi))

print("\n=== F. Locations by period (years with >= 300 complete daytime days)")
cov = comp.groupby(["loc", "year"]).size().unstack(fill_value=0)
goodyrs = cov >= 300
cov.to_csv(out / "daytime_complete_days_by_location_year.csv")
p1 = goodyrs.loc[:, [y for y in range(2010, 2015) if y in goodyrs.columns]].sum(axis=1)
p2 = goodyrs.loc[:, [y for y in range(2022, 2027) if y in goodyrs.columns]].sum(axis=1)
# 2026 is partial: count >= 250 days up to 22 Nov as a good year
if 2026 in cov.columns:
    p2 = p2 + ((cov[2026] >= 250) & ~goodyrs[2026]).astype(int)
tab = pd.DataFrame({"good_years_2010_14": p1, "good_years_2022_26": p2,
                    "days_2010_14": cov.loc[:, [y for y in range(2010, 2015) if y in cov.columns]].sum(axis=1),
                    "days_2022_26": cov.loc[:, [y for y in range(2022, 2027) if y in cov.columns]].sum(axis=1)})
print(tab.sort_values("days_2010_14", ascending=False).to_string())
for k in (1, 2, 3):
    both = tab[(tab.good_years_2010_14 >= k) & (tab.good_years_2022_26 >= k)]
    print(f"locations with >= {k} good years in BOTH periods:", len(both), list(both.index))
print("locations with >= 300 complete days, per year:\n", goodyrs.sum(axis=0).to_string())

print("\n=== G. Weather only (Fluntern, 10-minute data, UTC end-of-interval stamps)")
fs = [raw / "meteoswiss" / f"ogd-smn_sma_t_{s}.csv" for s in ("historical_2010-2019", "historical_2020-2029", "recent")]
w = pd.concat([pd.read_csv(f, sep=";", usecols=["reference_timestamp", "tre200s0", "rre150z0", "sre000z0"]) for f in fs])
w["utc_end"] = pd.to_datetime(w["reference_timestamp"], format="%d.%m.%Y %H:%M")
w = w.drop_duplicates("utc_end").set_index("utc_end").sort_index()
print("10-min rows", len(w), "from", w.index.min(), "to", w.index.max())
print("missing share: temp", round(w["tre200s0"].isna().mean(), 4), "rain", round(w["rre150z0"].isna().mean(), 4), "sun", round(w["sre000z0"].isna().mean(), 4))
# convert end-of-interval UTC to interval start in Zurich local time
start_local = (w.index - pd.Timedelta(minutes=10)).tz_localize("UTC").tz_convert("Europe/Zurich").tz_localize(None)
w = w.reset_index(drop=True)
w["start_local"] = start_local
w["date"] = w["start_local"].dt.normalize()
w["hour"] = w["start_local"].dt.hour
dw = w[(w["hour"] >= 6) & (w["hour"] < 20)].groupby("date").agg(rain=("rre150z0", "sum"), n=("rre150z0", "count"))
tx = w.groupby("date")["tre200s0"].max()
dw = dw.join(tx.rename("tmax"))
dw["year"] = dw.index.year
summ = dw.groupby("year").agg(days=("rain", "size"), wet=("rain", lambda s: int((s >= 2).sum())),
                              dry=("rain", lambda s: int((s < 0.1).sum())),
                              tmax_ge25=("tmax", lambda s: int((s >= 25).sum())),
                              tmax_ge30=("tmax", lambda s: int((s >= 30).sum())),
                              tmax_lt5=("tmax", lambda s: int((s < 5).sum())),
                              incomplete_rain_days=("n", lambda s: int((s < 84).sum())))
print(summ.to_string())

# compare 10-min daytime rain with the daily product (6 UTC to 6 UTC) as a sanity check
dd = pd.concat([pd.read_csv(raw / "meteoswiss" / f, sep=";", usecols=["reference_timestamp", "rre150d0", "tre200dx"])
                for f in ("ogd-smn_sma_d_historical.csv", "ogd-smn_sma_d_recent.csv")])
dd["date"] = pd.to_datetime(dd["reference_timestamp"], format="%d.%m.%Y %H:%M")
dd = dd.drop_duplicates("date").set_index("date")
j = dw.join(dd, how="inner")
j = j[j.index >= "2010-01-01"]
print("days compared", len(j), "| corr(daytime rain, daily rain)", round(j["rain"].corr(j["rre150d0"]), 3),
      "| corr(10-min Tmax, daily Tmax)", round(j["tmax"].corr(j["tre200dx"]), 4),
      "| mean abs diff Tmax", round((j["tmax"] - j["tre200dx"]).abs().mean(), 3))
