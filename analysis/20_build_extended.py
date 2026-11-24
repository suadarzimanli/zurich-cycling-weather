"""Daily tables for the extended plan: city pedestrians, city cars, canton bikes.

Same rules as the bike table: daytime 6:00-20:00 local time, complete days only, and the
same cleaning flags (zero, below 5% or above 5x the location-month median, 3+ identical
days in a row). Canton weather: nearest station below 650 m with complete weather that day.

Usage: python 20_build_extended.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1])
raw = root / "data" / "raw"
der = root / "data" / "derived"


def clean_flags(d, loc="loc", device="device", value="y"):
    d = d.sort_values([device, "date"]).reset_index(drop=True)
    d["ym"] = d["date"].dt.to_period("M").astype(str)
    med = d.groupby([loc, "ym"])[value].transform("median")
    d["flag_zero"] = d[value] == 0
    d["flag_low"] = d[value] < 0.05 * med
    d["flag_high"] = d[value] > 5 * med
    new_run = (d[device] != d[device].shift()) | (d[value] != d[value].shift()) | ((d["date"] - d["date"].shift()).dt.days != 1)
    run = new_run.cumsum()
    d["flag_stuck"] = d.groupby(run)[value].transform("size") >= 3
    d["keep"] = ~d[["flag_zero", "flag_low", "flag_high", "flag_stuck"]].any(axis=1)
    return d


# ---------------- city pedestrians ----------------
cols = ["FK_STANDORT", "DATUM", "FUSS_IN", "FUSS_OUT"]
pq = pd.read_parquet(raw / "zurich_counts" / "verkehrszaehlungen_werte_fussgaenger_velo_alle_jahre.parquet", columns=cols)
c26 = pd.read_csv(raw / "zurich_counts" / "2026_verkehrszaehlungen_werte_fussgaenger_velo.csv", usecols=cols)
v = pd.concat([pq[pq["DATUM"] < "2026-01-01"], c26], ignore_index=True).dropna(subset=["FUSS_IN", "FUSS_OUT"], how="all")
v["DATUM"] = pd.to_datetime(v["DATUM"], format="%Y-%m-%dT%H:%M")
v = v.drop_duplicates(["FK_STANDORT", "DATUM"])
has_in = v.groupby("FK_STANDORT")["FUSS_IN"].apply(lambda s: s.notna().mean() > 0.5)
has_out = v.groupby("FK_STANDORT")["FUSS_OUT"].apply(lambda s: s.notna().mean() > 0.5)
v["ok"] = ((~v["FK_STANDORT"].map(has_in)) | v["FUSS_IN"].notna()) & ((~v["FK_STANDORT"].map(has_out)) | v["FUSS_OUT"].notna())
v["n"] = v["FUSS_IN"].fillna(0).astype("int64") + v["FUSS_OUT"].fillna(0).astype("int64")
v["date"] = v["DATUM"].dt.normalize()
h = v["DATUM"].dt.hour
v = v[(h >= 6) & (h < 20)]
g = v.groupby(["FK_STANDORT", "date"])
ped = pd.DataFrame({"slots_ok": g["ok"].sum(), "y": g["n"].sum()}).reset_index()
ped = ped[ped["slots_ok"] == 56]
gj = json.loads((raw / "zurich_stations" / "standorte.geojson").read_text(encoding="utf-8"))
meta = pd.DataFrame([f["properties"] for f in gj["features"]]).set_index("id1")
ped["loc"] = ped["FK_STANDORT"].map(meta["abkuerzung"])
ped["name"] = ped["FK_STANDORT"].map(meta["bezeichnung"])
excluded = {"FZS_LANN", "FZS_LANS", "FZS_MYTH", "FZS_MILI", "FZS_LIMM", "FZS_KLOE"}
ped = ped[ped["loc"].str.startswith("FZS_") & ~ped["loc"].isin(excluded)].rename(columns={"FK_STANDORT": "device"})
ped = clean_flags(ped)
ped["wx_station"] = "SMA"
ped.to_parquet(der / "ped_daily.parquet", index=False)
print("pedestrians: locations", ped["loc"].nunique(), "| complete days", len(ped), "| kept", int(ped["keep"].sum()),
      "| locations:", sorted(ped["loc"].unique()))

# ---------------- city cars ----------------
car = pd.read_parquet(raw / "zurich_cars" / "sid_dav_verkehrszaehlung_miv_od2031_alle_jahre.parquet",
                      columns=["MSID", "ZSID", "MessungDatZeit", "AnzFahrzeuge", "AnzFahrzeugeStatus"])
car["t"] = pd.to_datetime(car["MessungDatZeit"].str[:19])  # local wall time
car = car[(car["t"].dt.hour >= 6) & (car["t"].dt.hour < 20)]
car["date"] = car["t"].dt.normalize()
car["measured"] = car["AnzFahrzeugeStatus"] == "Gemessen"
car = car.drop_duplicates(["MSID", "t"])
g = car.groupby(["MSID", "date"])
cd = pd.DataFrame({"hours_measured": g["measured"].sum(), "y": g["AnzFahrzeuge"].sum(), "ZSID": g["ZSID"].first()}).reset_index()
cd = cd[cd["hours_measured"] == 14].rename(columns={"MSID": "loc"})
cd["device"] = cd["loc"]
cd = clean_flags(cd)
cd["wx_station"] = "SMA"
cd.to_parquet(der / "car_daily.parquet", index=False)
print("cars: points", cd["loc"].nunique(), "| complete days", len(cd), "| kept", int(cd["keep"].sum()))

# ---------------- canton bikes ----------------
k = pd.read_parquet(der / "canton_daily.parquet")
k = k[k["complete"]].rename(columns={"velo_day": "y"})
k["loc"] = "K" + k["messstelle_id"].astype(str)
k["device"] = k["loc"]
k = clean_flags(k)
st = pd.read_csv(raw / "meteoswiss" / "ogd-smn_meta_stations.csv", sep=";", encoding="latin1").set_index("station_abbr")
cand = ["CHZ", "HLL", "KLO", "LAC", "PFA", "REH", "SCM", "SHA", "SMA", "STK", "TAE", "WAE"]
st = st.loc[cand]
wx = pd.read_parquet(der / "weather_stations_daily.parquet")
ok = wx.dropna(subset=["rain_day", "tmax", "sun_day"])[["station", "date"]]
avail = set(zip(ok["station"], ok["date"]))
lat0 = np.radians(47.4)
pos = k.drop_duplicates("loc").set_index("loc")[["lon", "lat"]]
order = {}
for loc, r in pos.iterrows():
    dd = np.hypot((st["station_coordinates_wgs84_lon"] - r["lon"]) * 111.32 * np.cos(lat0),
                  (st["station_coordinates_wgs84_lat"] - r["lat"]) * 110.57)
    order[loc] = list(dd.sort_values().index)
choice = []
for loc, date in zip(k["loc"], k["date"]):
    choice.append(next((s for s in order[loc] if (s, date) in avail), None))
k["wx_station"] = choice
k["wx_is_nearest"] = [c == order[l][0] for c, l in zip(k["wx_station"], k["loc"])]
k.to_parquet(der / "canton_daily_clean.parquet", index=False)
print("canton: stations", k["loc"].nunique(), "| complete days", len(k), "| kept", int(k["keep"].sum()),
      "| days using the nearest weather station:", f"{k['wx_is_nearest'].mean():.1%}",
      "| weather stations used:", k["wx_station"].value_counts().to_dict())
