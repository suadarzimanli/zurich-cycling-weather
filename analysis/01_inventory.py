"""Data inventory only: which bike counters exist, for which years, and how complete.
No weather is joined here and no weather effect is estimated.

Usage: python 01_inventory.py <project_dir>
"""
import json
import sys
from pathlib import Path

import pandas as pd

root = Path(sys.argv[1])
raw = root / "data" / "raw"
out = root / "data" / "inventory"
out.mkdir(parents=True, exist_ok=True)

df = pd.read_parquet(raw / "zurich_counts" / "verkehrszaehlungen_werte_fussgaenger_velo_alle_jahre.parquet")
print("rows", len(df), "columns", list(df.columns))
print(df.dtypes)
print(df.head(3).to_string())

df["DATUM"] = pd.to_datetime(df["DATUM"])
print("date range", df["DATUM"].min(), df["DATUM"].max())

# bike rows only
v = df[df["VELO_IN"].notna() | df["VELO_OUT"].notna()].copy()
v["VELO"] = v["VELO_IN"].fillna(0) + v["VELO_OUT"].fillna(0)
v["date"] = v["DATUM"].dt.normalize()
print("bike rows", len(v), "bike sites (FK_STANDORT)", v["FK_STANDORT"].nunique())

# daily completeness per site: number of 15-min slots per day (96 expected)
slots = v.groupby(["FK_STANDORT", "date"]).size().rename("slots").reset_index()
slots["full_day"] = slots["slots"] >= 92  # allow DST days (92 slots) and a few gaps
slots["year"] = slots["date"].dt.year
cov = slots.groupby(["FK_STANDORT", "year"])["full_day"].sum().unstack(fill_value=0)
cov.to_csv(out / "bike_full_days_by_site_year.csv")

# station metadata
gj = json.loads((raw / "zurich_stations" / "standorte.geojson").read_text(encoding="utf-8"))
meta = pd.DataFrame([f["properties"] for f in gj["features"]])
meta.to_csv(out / "stations_meta.csv", index=False)
bike_meta = meta[meta["velo"] == 1][["id1", "abkuerzung", "bezeichnung", "von", "bis", "korrekturfaktor", "status"]]
print("\nbike stations in metadata:", len(bike_meta))

# summary per site
first = slots.groupby("FK_STANDORT")["date"].agg(["min", "max"])
full = slots.groupby("FK_STANDORT")["full_day"].sum().rename("full_days")
summ = first.join(full).join(bike_meta.set_index("id1")[["abkuerzung", "bezeichnung", "korrekturfaktor"]], how="left")
summ = summ.sort_values("min")
summ.to_csv(out / "bike_sites_summary.csv")
pd.set_option("display.width", 200)
print(summ.to_string())

# how many sites have near-complete data in each year (>= 300 full days)
good = (cov >= 300).sum(axis=0)
print("\nsites with >=300 full days, per year:\n", good.to_string())

# long panels: sites with >=300 full days in at least N years
yrs_good = (cov >= 300).sum(axis=1)
for n in (5, 8, 10, 12, 15):
    print(f"sites with >=300 full days in >= {n} years:", int((yrs_good >= n).sum()))
