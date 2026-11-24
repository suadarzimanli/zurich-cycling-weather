"""Figures for the main paper.

Fig. 2: wet-day effect by year for cycling, walking and cars (descriptive, not a planned test).
Fig. 3: map of all counting locations and weather stations.
Usage: python 23_paper_figures.py <project_dir>
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon

sys.path.insert(0, str(Path(__file__).parent))
from blockpois import blockpois

root = Path(sys.argv[1])
der = root / "data" / "derived"
fig_dir = root / "paper" / "figures"
fig_dir.mkdir(parents=True, exist_ok=True)

WEATHER = ["light", "wet", "t_lt5", "t_5_15", "t_15_25", "t_gt25", "sun_h"]
HOL = ["public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]
wx = pd.read_parquet(der / "weather_stations_daily.parquet")
cal = pd.read_parquet(der / "calendar_daily.parquet")
BLUE, ORANGE, AQUA, SURF, INK, INK2, GRID = "#2a78d6", "#eb6834", "#1baf7a", "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK})


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
    d["year"] = d["date"].dt.year
    d["fe1"] = d["device"].astype(str) + "_" + d["date"].dt.strftime("%Y-%m")
    iso = d["date"].dt.isocalendar()
    d["week"] = iso["year"].astype(str) + "-" + iso["week"].astype(str)
    for h in HOL:
        d[h] = d[h].astype(float)
    d["loc"] = d["loc"].astype(str)
    return d


def by_year(d):
    G = {}
    for y in sorted(d["year"].unique()):
        m = (d["year"] == y).to_numpy().astype(float)
        for v in WEATHER:
            G[f"{v}:{y}"] = d[v].to_numpy() * m
    for h in HOL:
        G[h] = d[h].to_numpy()
    G = pd.DataFrame(G)
    G = G.loc[:, G.std() > 0]
    r = blockpois(d["y"], G.to_numpy(), None, d["loc"], d["fe1"], d["dow"], d["week"], names=list(G.columns))
    rows = []
    for y in sorted(d["year"].unique()):
        b, se = r["beta"][f"wet:{y}"], np.sqrt(r["vcov"].loc[f"wet:{y}", f"wet:{y}"])
        rows.append({"year": y, "est": b, "se": se, "n": int((d["year"] == y).sum())})
    return pd.DataFrame(rows)


c = pd.read_parquet(der / "counts_daily.parquet")
c = c[c["complete"]].rename(columns={"velo_day": "y"})
c["wx_station"] = "SMA"
bike = by_year(prep(c[(c["date"] >= "2011-01-01")]))
ped = pd.read_parquet(der / "ped_daily.parquet")
walk = by_year(prep(ped[(ped["date"] >= "2014-01-01") & (ped["date"] <= "2022-12-31")]))
car = by_year(prep(pd.read_parquet(der / "car_daily.parquet")))
old = pd.read_csv(root / "results" / "effects_by_year.csv")
old = old[old["effect"] == "rain"].set_index("year")["est"]
print("bike by-year matches the earlier estimator (max diff):", float((bike.set_index("year")["est"] - old).abs().max()))
tab = pd.concat([bike.assign(series="cycling"), walk.assign(series="walking"), car.assign(series="cars")])
tab.to_csv(root / "results" / "extended" / "wet_effect_by_year_three_modes.csv", index=False)

# ---------- Fig. 2 ----------
fig, ax = plt.subplots(figsize=(7.2, 3.6), facecolor=SURF)
ax.set_facecolor(SURF)
ax.axvspan(2019.5, 2021.5, color="#efeeea", lw=0, zorder=0)
ax.axhline(0, color=INK2, lw=0.8, zorder=1)
for s, col, mk, dx in (("cycling", BLUE, "o", -0.18), ("walking", ORANGE, "s", 0.0), ("cars", AQUA, "D", 0.18)):
    t = tab[tab["series"] == s]
    x = t["year"].to_numpy() + dx
    est = 100 * (np.exp(t["est"]) - 1)
    lo = 100 * (np.exp(t["est"] - 1.96 * t["se"]) - 1)
    hi = 100 * (np.exp(t["est"] + 1.96 * t["se"]) - 1)
    ax.vlines(x, lo, hi, color=col, lw=1.4, zorder=2)
    ax.plot(x, est, mk, color=col, ms=5, mec=SURF, mew=1.0, zorder=3, label=s.capitalize())
    ax.annotate(s.capitalize(), (x[-1], est.iloc[-1]), xytext=(6, 0), textcoords="offset points", va="center",
                fontsize=8, color=INK)
ax.text(2020.5, 6, "pandemic", ha="center", va="top", fontsize=7.5, color=INK2)
ax.set_ylabel("Change on a wet day vs a dry day (%)", color=INK2)
ax.set_xticks(range(2011, 2027, 2))
ax.set_xlim(2010.4, 2027.6)
ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)
ax.legend(frameon=False, loc="lower right", ncol=3, fontsize=8)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(fig_dir / f"fig2_wet_by_year_modes.{ext}", dpi=220, facecolor=SURF)
plt.close(fig)

# ---------- Fig. 3 ----------
bd = root / "data" / "raw" / "boundaries"


def polys(geom):
    g = geom["coordinates"]
    if geom["type"] == "Polygon":
        g = [g]
    return [np.array(ring)[:, :2] for poly in g for ring in poly[:1]]


kreise = json.loads((bd / "stadtkreise.geojson").read_text(encoding="utf-8"))
kanton = json.loads((bd / "kanton_zh.json").read_text(encoding="utf-8"))["results"][0]["geometry"]
lake = json.loads((bd / "zurichsee.json").read_text(encoding="utf-8"))["results"][0]["geometry"]
bike_xy = c.groupby("loc")[["E", "N"]].last()
gj = json.loads((root / "data" / "raw" / "zurich_stations" / "standorte.geojson").read_text(encoding="utf-8"))
meta = pd.DataFrame([{**f["properties"], "E": f["geometry"]["coordinates"][0], "N": f["geometry"]["coordinates"][1]} for f in gj["features"]])
ped_xy = meta[meta["abkuerzung"].isin(ped["loc"].unique())].groupby("abkuerzung")[["E", "N"]].last()
carraw = pd.read_parquet(root / "data" / "raw" / "zurich_cars" / "sid_dav_verkehrszaehlung_miv_od2031_alle_jahre.parquet", columns=["MSID", "EKoord", "NKoord"]).drop_duplicates("MSID")
k = pd.read_parquet(der / "canton_daily_clean.parquet").drop_duplicates("loc")
from pyproj import Transformer
tr = Transformer.from_crs(4326, 2056, always_xy=True)
kx, ky = tr.transform(k["lon"].to_numpy(), k["lat"].to_numpy())
stm = pd.read_csv(root / "data" / "raw" / "meteoswiss" / "ogd-smn_meta_stations.csv", sep=";", encoding="latin1").set_index("station_abbr")
used = ["SMA", "REH", "KLO", "PFA", "WAE", "CHZ", "TAE", "SHA"]
stm = stm.loc[used]

fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.4, 3.9), facecolor=SURF, gridspec_kw={"width_ratios": [1.05, 1]})
for ax in (a1, a2):
    ax.set_facecolor(SURF)
    for p in polys(lake):
        ax.add_patch(Polygon(p, closed=True, fc="#dbe8f6", ec="none", zorder=0))
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
for f in kreise["features"]:
    for p in polys(f["geometry"]):
        a1.add_patch(Polygon(p, closed=True, fc="none", ec="#b9b8b2", lw=0.6, zorder=1))
a1.scatter(carraw["EKoord"], carraw["NKoord"], s=7, marker="D", color=AQUA, lw=0, zorder=2, label="Car measuring points")
a1.scatter(ped_xy["E"], ped_xy["N"], s=22, marker="s", color=ORANGE, ec=SURF, lw=0.6, zorder=3, label="Pedestrian counters")
a1.scatter(bike_xy["E"], bike_xy["N"], s=24, marker="o", color=BLUE, ec=SURF, lw=0.6, zorder=4, label="Bike counters")
a1.scatter([stm.loc["SMA", "station_coordinates_lv95_east"]], [stm.loc["SMA", "station_coordinates_lv95_north"]], s=60, marker="*", color=INK, zorder=5, label="Weather station")
a1.set_xlim(2676500, 2690500)
a1.set_ylim(1241000, 1254500)
a1.set_title("(a) City of Zurich", loc="left", fontsize=9)
a1.legend(frameon=False, fontsize=7, loc="lower left", bbox_to_anchor=(-0.02, -0.2), ncol=2)
for p in polys(kanton):
    a2.add_patch(Polygon(p, closed=True, fc="none", ec=INK2, lw=0.8, zorder=1))
for f in kreise["features"]:
    for p in polys(f["geometry"]):
        a2.add_patch(Polygon(p, closed=True, fc="#efeeea", ec="none", zorder=1))
a2.scatter(kx, ky, s=12, marker="o", color=BLUE, ec=SURF, lw=0.4, zorder=3, label="Canton bike counters")
a2.scatter(stm["station_coordinates_lv95_east"], stm["station_coordinates_lv95_north"], s=50, marker="*", color=INK, zorder=4, label="Weather stations")
for ab, r in stm.iterrows():
    a2.annotate(r["station_name"].replace("Zürich / ", ""), (r["station_coordinates_lv95_east"], r["station_coordinates_lv95_north"]),
                xytext=(4, 3), textcoords="offset points", fontsize=6.5, color=INK)
kb = np.vstack(polys(kanton))
a2.set_xlim(kb[:, 0].min() - 2000, kb[:, 0].max() + 2000)
a2.set_ylim(kb[:, 1].min() - 2000, kb[:, 1].max() + 2000)
a2.set_title("(b) Canton of Zurich (city shaded)", loc="left", fontsize=9)
a2.legend(frameon=False, fontsize=7, loc="lower left", bbox_to_anchor=(0, -0.2), ncol=1)
fig.tight_layout()
for ext in ("pdf", "png"):
    fig.savefig(fig_dir / f"fig3_map.{ext}", dpi=220, facecolor=SURF, bbox_inches="tight")
plt.close(fig)
print("figures written to", fig_dir)
