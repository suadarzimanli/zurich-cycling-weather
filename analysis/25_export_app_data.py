"""Export compact data files for the web app (app/data).

- locations.json   every counter with its own rain effect (descriptive, all years of that counter)
- series/<id>.json daily daytime counts and daytime rain for each counter
- effects.json     yearly weather effects, the pre-specified tests and the extended results
- calculator.json  period-model weather coefficients (9 city locations) with their covariance
- forecast.json    forecasting scores and daily forecasts for the test period
- boundaries.json  city districts and canton outline in WGS84
Usage: python 25_export_app_data.py <project_dir>
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from analysis import fit
from blockpois import blockpois

root = Path(sys.argv[1])
der = root / "data" / "derived"
res = root / "results"
out = root / "docs" / "data"
(out / "series").mkdir(parents=True, exist_ok=True)
to_wgs = Transformer.from_crs(2056, 4326, always_xy=True)
WEATHER = ["light", "wet", "t_lt5", "t_5_15", "t_15_25", "t_gt25", "sun_h"]
HOL = ["public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]
DAY0 = pd.Timestamp("2010-01-01")
wx = pd.read_parquet(der / "weather_stations_daily.parquet")
cal = pd.read_parquet(der / "calendar_daily.parquet")
t0 = time.time()


def clean(o):
    """Replace NaN and infinity with None so the files are valid JSON."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


def prep(d):
    d = d[d["keep"]].copy()
    d = d.merge(wx, left_on=["wx_station", "date"], right_on=["station", "date"]).dropna(subset=["rain_day", "tmax", "sun_day"])
    d = d.merge(cal, on="date", how="left")
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
    d["loc"] = d["loc"].astype(str)
    return d


def own_rain_effect(d):
    if len(d) < 120 or d["wet"].sum() < 15:
        return None
    G = d[WEATHER + HOL]
    G = G.loc[:, G.std() > 0]
    try:
        r = blockpois(d["y"], G.to_numpy(), None, d["loc"], d["fe1"], d["dow"], d["week"], names=list(G.columns))
    except Exception:
        return None
    b, se = float(r["beta"]["wet"]), float(np.sqrt(r["vcov"].loc["wet", "wet"]))
    return {"pct": round(100 * (np.exp(b) - 1), 1), "lo": round(100 * (np.exp(b - 1.96 * se) - 1), 1),
            "hi": round(100 * (np.exp(b + 1.96 * se) - 1), 1)}


# ---------------- tables per counter type ----------------
gj = json.loads((root / "data" / "raw" / "zurich_stations" / "standorte.geojson").read_text(encoding="utf-8"))
meta = pd.DataFrame([{**f["properties"], "E": f["geometry"]["coordinates"][0], "N": f["geometry"]["coordinates"][1]} for f in gj["features"]])

c = pd.read_parquet(der / "counts_daily.parquet")
c = c[c["complete"]].rename(columns={"velo_day": "y"})
c["wx_station"] = "SMA"
ped = pd.read_parquet(der / "ped_daily.parquet")
car = pd.read_parquet(der / "car_daily.parquet")
can = pd.read_parquet(der / "canton_daily_clean.parquet")
carmeta = pd.read_parquet(root / "data" / "raw" / "zurich_cars" / "sid_dav_verkehrszaehlung_miv_od2031_alle_jahre.parquet",
                          columns=["MSID", "MSName", "ZSName", "Achse", "Richtung", "EKoord", "NKoord"]).drop_duplicates("MSID", keep="last").set_index("MSID")

groups = [
    ("bike", "City bike counter", c, lambda loc: meta[meta["abkuerzung"] == loc].iloc[-1]["bezeichnung"],
     lambda loc: to_wgs.transform(*c[c["loc"] == loc].iloc[-1][["E", "N"]].to_numpy())),
    ("walk", "Pedestrian counter", ped, lambda loc: meta[meta["abkuerzung"] == loc].iloc[-1]["bezeichnung"],
     lambda loc: to_wgs.transform(*meta[meta["abkuerzung"] == loc].iloc[-1][["E", "N"]].to_numpy())),
    ("car", "Car measuring point", car, lambda loc: f"{carmeta.loc[loc, 'ZSName']} ({carmeta.loc[loc, 'Richtung']})",
     lambda loc: to_wgs.transform(carmeta.loc[loc, "EKoord"], carmeta.loc[loc, "NKoord"])),
    ("canton", "Canton bike counter", can, lambda loc: f"{can[can['loc'] == loc].iloc[-1]['gemeinde']} (station {loc[1:]})",
     lambda loc: (float(can[can["loc"] == loc].iloc[-1]["lon"]), float(can[can["loc"] == loc].iloc[-1]["lat"]))),
]

locations = []
for kind, label, df, namef, xyf in groups:
    P = prep(df)
    for loc, d in P.groupby("loc"):
        lon, lat = xyf(loc)
        eff = own_rain_effect(d)
        sid = f"{kind}_{loc}".replace("/", "_")
        s = d.sort_values("date")
        rec = {"id": sid, "type": kind, "label": label, "name": str(namef(loc)), "lat": round(float(lat), 6), "lon": round(float(lon), 6),
               "first": str(s["date"].min().date()), "last": str(s["date"].max().date()), "days": int(len(s)),
               "mean": int(round(s["y"].mean())), "rain": eff, "weather_station": str(s["wx_station"].mode().iloc[0])}
        locations.append(rec)
        series = {"id": sid, "day0": str(DAY0.date()),
                  "d": ((s["date"] - DAY0).dt.days).astype(int).tolist(),
                  "y": s["y"].astype(int).tolist(),
                  "r": (s["rain_day"] * 10).round().astype(int).tolist()}
        (out / "series" / f"{sid}.json").write_text(json.dumps(series, separators=(",", ":")))
    print(f"[{time.time() - t0:.0f}s] {kind}: {P['loc'].nunique()} locations", flush=True)
(out / "locations.json").write_text(json.dumps(clean(locations), separators=(",", ":"), ensure_ascii=False, allow_nan=False), encoding="utf-8")

# ---------------- effects ----------------
yr = pd.read_csv(res / "effects_by_year.csv")
modes = pd.read_csv(res / "extended" / "wet_effect_by_year_three_modes.csv")


def pct_rows(df):
    return [{"year": int(r["year"]), "pct": round(100 * (np.exp(r["est"]) - 1), 2),
             "lo": round(100 * (np.exp(r["est"] - 1.96 * r["se"]) - 1), 2),
             "hi": round(100 * (np.exp(r["est"] + 1.96 * r["se"]) - 1), 2)} for _, r in df.iterrows()]


effects = {
    "cycling_by_year": {k: pct_rows(yr[yr["effect"] == k].sort_values("year")) for k in ("rain", "cold", "heat")},
    "wet_by_year_modes": {k: pct_rows(modes[modes["series"] == k].sort_values("year")) for k in ("cycling", "walking", "cars")},
    "tests": json.loads((res / "prediction_tests.json").read_text()),
    "extended": json.loads((res / "extended" / "extended_results.json").read_text()),
    "device_check": json.loads((res / "check_devices.json").read_text()),
    "year_2019_check": json.loads((res / "check_2018_2019.json").read_text()),
}
(out / "effects.json").write_text(json.dumps(clean(effects), separators=(",", ":"), allow_nan=False))

# ---------------- calculator ----------------
from design import load
core = json.loads((der / "sample_definitions.json").read_text())["period_comparison_locations"]
d = load(root)
d = d[d["loc"].isin(core) & d["year"].isin([2011, 2012, 2013, 2014, 2022, 2023, 2024, 2025, 2026])].copy()
d["period"] = np.where(d["year"] <= 2014, "early", "late")
r = fit(d, "period")
names = [f"{v}:{p}" for p in ("early", "late") for v in WEATHER]
calc = {"names": names, "beta": [float(r["beta"][n]) for n in names],
        "vcov": r["vcov"].loc[names, names].round(10).values.tolist(),
        "note": "Poisson model on the 9 city locations, 2011-2014 (early) and 2022-2026 (late), counter-month and location-weekday effects."}
assert abs(r["beta"]["wet:early"] - (-0.4072)) < 5e-4 and abs(r["beta"]["wet:late"] - (-0.3393)) < 5e-4
(out / "calculator.json").write_text(json.dumps(clean(calc), separators=(",", ":"), allow_nan=False))

# ---------------- forecast ----------------
pa = pd.read_parquet(res / "forecast" / "pred_all.parquet")
sc = json.loads((res / "forecast" / "scores_all.json").read_text())
models = ["pred_lastweek", "pred_lgbm_wx", "pred_lgbm_nowx", "pred_rnn_wx", "pred_rnn_nowx", "pred_gwn_wx", "pred_gwn_nowx"]
nodes = {}
for loc, g in pa.groupby("loc"):
    g = g.sort_values("date")
    nodes[loc] = {"name": str(meta[meta["abkuerzung"] == loc].iloc[-1]["bezeichnung"]),
                  "d": ((g["date"] - DAY0).dt.days).astype(int).tolist(), "y": g["y"].astype(int).tolist(),
                  **{m.replace("pred_", ""): g[m].round().astype(int).tolist() for m in models}}
fc = {"day0": str(DAY0.date()), "scores": {m.replace("pred_", ""): {k: sc[m][k] for k in ("mae", "mae_ratio", "dm_t", "dm_p")} for m in models},
      "graph_test": {v: sc[f"graph_vs_nograph_{v}"] for v in ("wx", "nowx")}, "nodes": nodes}
(out / "forecast.json").write_text(json.dumps(clean(fc), separators=(",", ":"), allow_nan=False))

# ---------------- boundaries ----------------
bd = root / "data" / "raw" / "boundaries"


def to_ll(geom, tol):
    """Simplify in metres (LV95, Douglas-Peucker via shapely), then convert to lat/lon."""
    from shapely.geometry import Polygon
    g = geom["coordinates"]
    polys = [g] if geom["type"] == "Polygon" else g
    outp = []
    for poly in polys:
        ring = np.array(Polygon(np.array(poly[0])[:, :2]).simplify(tol, preserve_topology=True).exterior.coords)
        lon, lat = to_wgs.transform(ring[:, 0], ring[:, 1])
        outp.append([[round(a, 5), round(b, 5)] for a, b in zip(lat, lon)])
    return outp


kreise = json.loads((bd / "stadtkreise.geojson").read_text(encoding="utf-8"))
kanton = json.loads((bd / "kanton_zh.json").read_text(encoding="utf-8"))["results"][0]["geometry"]
bnd = {"districts": [to_ll(f["geometry"], 8) for f in kreise["features"]], "canton": to_ll(kanton, 40)}
print("boundary vertices:", sum(len(r) for d in bnd["districts"] for r in d), "+", sum(len(r) for r in bnd["canton"]))
(out / "boundaries.json").write_text(json.dumps(bnd, separators=(",", ":")))

sizes = {p.name: p.stat().st_size for p in out.glob("*.json")}
print("files:", sizes, "| series files:", len(list((out / "series").glob("*.json"))),
      "| series total MB:", round(sum(p.stat().st_size for p in (out / "series").glob("*.json")) / 1e6, 1))
print(f"done [{time.time() - t0:.0f}s]")
