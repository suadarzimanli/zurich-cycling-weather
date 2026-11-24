"""Coverage of the new data for the extended plan (pedestrians and cars). No weather is used.

Usage: python 16_inventory_new.py <project_dir>
"""
import json
import sys
from pathlib import Path

import pandas as pd

root = Path(sys.argv[1])
raw = root / "data" / "raw"
out = root / "data" / "inventory"
pd.set_option("display.width", 220)

# ---------- pedestrians ----------
cols = ["FK_STANDORT", "DATUM", "VELO_IN", "VELO_OUT", "FUSS_IN", "FUSS_OUT"]
pq = pd.read_parquet(raw / "zurich_counts" / "verkehrszaehlungen_werte_fussgaenger_velo_alle_jahre.parquet", columns=cols)
c26 = pd.read_csv(raw / "zurich_counts" / "2026_verkehrszaehlungen_werte_fussgaenger_velo.csv", usecols=cols)
v = pd.concat([pq[pq["DATUM"] < "2026-01-01"], c26], ignore_index=True)
has_bike = v.groupby("FK_STANDORT")[["VELO_IN", "VELO_OUT"]].apply(lambda x: x.notna().any().any())
f = v[v["FUSS_IN"].notna() | v["FUSS_OUT"].notna()].copy()
f["DATUM"] = pd.to_datetime(f["DATUM"], format="%Y-%m-%dT%H:%M")
f = f.drop_duplicates(["FK_STANDORT", "DATUM"])
f["date"] = f["DATUM"].dt.normalize()
f = f[(f["DATUM"].dt.hour >= 6) & (f["DATUM"].dt.hour < 20)]
day = f.groupby(["FK_STANDORT", "date"]).size().rename("slots").reset_index()
day = day[day["slots"] == 56]
day["year"] = day["date"].dt.year
gj = json.loads((raw / "zurich_stations" / "standorte.geojson").read_text(encoding="utf-8"))
meta = pd.DataFrame([f_["properties"] for f_ in gj["features"]]).set_index("id1")
day["loc"] = day["FK_STANDORT"].map(meta["abkuerzung"])
day["name"] = day["FK_STANDORT"].map(meta["bezeichnung"])
day["bike_counter_at_site"] = day["FK_STANDORT"].map(has_bike)
cov = day.groupby(["loc", "year"]).size().unstack(fill_value=0)
good = cov >= 300
print("pedestrian locations:", cov.shape[0], "| with >=300 complete daytime days, per year:")
print(good.sum(axis=0).to_string())
site = day.groupby("loc").agg(name=("name", "first"), first=("date", "min"), last=("date", "max"),
                              good_years=("year", lambda s: int((s.value_counts() >= 300).sum())),
                              bike_counter_at_site=("bike_counter_at_site", "max"))
print(site.sort_values("first").to_string())
for a, b in ((2015, 2018), (2016, 2019)):
    early = good.reindex(columns=range(a, b + 1), fill_value=False).sum(axis=1)
    late = good.reindex(columns=range(2022, 2026), fill_value=False).sum(axis=1)
    both = sorted(cov.index[(early >= 2) & (late >= 2)])
    print(f"pedestrian locations with >=2 good years in {a}-{b} and in 2022-2025: {len(both)}")
cov.to_csv(out / "pedestrian_complete_days_by_location_year.csv")

# ---------- cars ----------
car = pd.read_parquet(raw / "zurich_cars" / "sid_dav_verkehrszaehlung_miv_od2031_alle_jahre.parquet",
                      columns=["MSID", "ZSID", "ZSName", "Achse", "Richtung", "EKoord", "NKoord", "MessungDatZeit",
                               "AnzFahrzeuge", "AnzFahrzeugeStatus"])
print("\ncar rows", len(car), "| status shares:\n", car["AnzFahrzeugeStatus"].value_counts(normalize=True).round(4).to_string())
print("count values when status is Fehlend:", car.loc[car["AnzFahrzeugeStatus"] == "Fehlend", "AnzFahrzeuge"].describe()[["count", "mean", "max"]].to_dict())
car["t"] = pd.to_datetime(car["MessungDatZeit"].str[:19])
print("time range:", car["t"].min(), car["t"].max(), "| example stamp:", car["MessungDatZeit"].iloc[0])
car = car[(car["t"].dt.hour >= 6) & (car["t"].dt.hour < 20) & (car["AnzFahrzeugeStatus"] == "Gemessen")]
car["date"] = car["t"].dt.normalize()
cd = car.groupby(["MSID", "date"]).size().rename("hours").reset_index()
cd = cd[cd["hours"] == 14]
cd["year"] = cd["date"].dt.year
ccov = cd.groupby(["MSID", "year"]).size().unstack(fill_value=0)
cgood = ccov >= 300
print("car measuring points:", ccov.shape[0], "| with >=300 fully measured daytime days, per year:")
print(cgood.sum(axis=0).to_string())
early = cgood.reindex(columns=range(2012, 2015), fill_value=False).sum(axis=1)
late = cgood.reindex(columns=range(2022, 2026), fill_value=False).sum(axis=1)
print("car measuring points with >=2 good years in 2012-2014 and in 2022-2025:", int(((early >= 2) & (late >= 2)).sum()))
print("counting stations (ZSID) among them:", car[car["MSID"].isin(ccov.index[(early >= 2) & (late >= 2)])]["ZSID"].nunique())
ccov.to_csv(out / "car_full_days_by_point_year.csv")
