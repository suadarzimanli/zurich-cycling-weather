"""Coverage of the Canton of Zurich bike counts (2016-2025). No weather is used.

Builds data/derived/canton_daily.parquet: one row per station and day, daytime 6:00-20:00
local time, summed over lanes and directions, with the number of hours present.

Usage: python 18_inventory_canton.py <project_dir>
"""
import sys
from pathlib import Path

import pandas as pd

root = Path(sys.argv[1])
raw = root / "data" / "raw" / "canton_counts"
der = root / "data" / "derived"
cols = ["zeit_von", "gemeinde_name", "raumplanungsregion_name", "anzahl_velos", "spur_richtung", "messstelle_id",
        "messstelle_laengengrad_WGS84", "messstelle_breitengrad_WGS84"]
parts = []
for f in sorted(raw.glob("KTZH_00003062_*.csv")):
    d = pd.read_csv(f, usecols=cols)
    parts.append(d)
    print(f.name, len(d), "rows | offsets:", d["zeit_von"].str[-3:].value_counts().to_dict())
d = pd.concat(parts, ignore_index=True)
# time stamps carry their UTC offset; convert to Zurich local time
t = pd.to_datetime(d["zeit_von"] + ":00", format="%Y-%m-%dT%H:%M:%S%z", utc=True).dt.tz_convert("Europe/Zurich").dt.tz_localize(None)
d["t"] = t
dup = d.duplicated(["messstelle_id", "spur_richtung", "t"]).sum()
print("duplicate station-lane-hour rows:", int(dup))
d = d.drop_duplicates(["messstelle_id", "spur_richtung", "t"])
d["date"] = d["t"].dt.normalize()
d["hour"] = d["t"].dt.hour
day = d[(d["hour"] >= 6) & (d["hour"] < 20)]
lanes = d.groupby("messstelle_id")["spur_richtung"].nunique().rename("n_lanes")
g = day.groupby(["messstelle_id", "date"])
daily = pd.DataFrame({"velo_day": g["anzahl_velos"].sum(), "lane_hours": g.size()}).reset_index()
daily = daily.merge(lanes, left_on="messstelle_id", right_index=True)
daily["complete"] = daily["lane_hours"] == 14 * daily["n_lanes"]
info = d.groupby("messstelle_id").agg(gemeinde=("gemeinde_name", "last"), region=("raumplanungsregion_name", "last"),
                                      lon=("messstelle_laengengrad_WGS84", "last"), lat=("messstelle_breitengrad_WGS84", "last"))
daily = daily.merge(info, left_on="messstelle_id", right_index=True)
daily.to_parquet(der / "canton_daily.parquet", index=False)

c = daily[daily["complete"]]
c = c.assign(year=c["date"].dt.year)
cov = c.groupby(["messstelle_id", "year"]).size().unstack(fill_value=0)
good = cov >= 300
print("stations:", cov.shape[0], "| with >=300 complete daytime days per year:\n", good.sum(axis=0).to_string())
print("complete days with zero bikes:", int((c["velo_day"] == 0).sum()), "of", len(c))
early = good.reindex(columns=range(2016, 2020), fill_value=False).sum(axis=1)
late = good.reindex(columns=range(2022, 2026), fill_value=False).sum(axis=1)
both = cov.index[(early >= 2) & (late >= 2)]
print("stations with >=2 good years in 2016-2019 and in 2022-2025:", len(both))
print(info.loc[both].groupby("region").size().to_string())
