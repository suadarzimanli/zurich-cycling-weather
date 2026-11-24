"""Join the three tables and build the regressors exactly as in ANALYSIS_DETAILS_2026-11-24.md."""
from pathlib import Path

import numpy as np
import pandas as pd

WEATHER = ["light", "wet", "t_lt5", "t_5_15", "t_15_25", "t_gt25", "sun_h"]


def load(root, station="sma", rain_col="rain_day", outcome="velo_day", cleaning=True):
    der = Path(root) / "data" / "derived"
    c = pd.read_parquet(der / "counts_daily.parquet")
    w = pd.read_parquet(der / "weather_daily.parquet")
    k = pd.read_parquet(der / "calendar_daily.parquet")
    c = c[c["complete"]]
    if cleaning:
        c = c[c["keep"]]
    d = c.merge(w, on="date", how="left").merge(k, on="date", how="left")
    d = d[(d["date"] >= "2011-01-01") & (d["date"] <= "2026-11-22")]
    rain = d[f"{station}_{rain_col}"]
    tmax = d[f"{station}_tmax"]
    sun = d[f"{station}_sun_day"]
    d = d[rain.notna() & tmax.notna() & sun.notna()].copy()
    rain = d[f"{station}_{rain_col}"]
    tmax = d[f"{station}_tmax"]
    d["light"] = ((rain >= 0.1) & (rain < 2)).astype(float)
    d["wet"] = (rain >= 2).astype(float)
    d["t_lt5"] = np.minimum(tmax, 5.0)
    d["t_5_15"] = np.clip(tmax - 5, 0, 10)
    d["t_15_25"] = np.clip(tmax - 15, 0, 10)
    d["t_gt25"] = np.maximum(tmax - 25, 0)
    d["sun_h"] = d[f"{station}_sun_day"] / 60.0
    d["y"] = d[outcome].astype(float)
    d["fe_group"] = d["device"].astype(str) + "_" + d["date"].dt.strftime("%Y-%m")
    iso = d["date"].dt.isocalendar()
    d["week"] = iso["year"].astype(str) + "-" + iso["week"].astype(str)
    d["year"] = d["date"].dt.year
    return d


def controls(d):
    """Location x weekday dummies (Monday reference) and the holiday terms."""
    cols = {}
    for loc in sorted(d["loc"].unique()):
        isloc = (d["loc"] == loc).to_numpy()
        for dow in range(1, 7):
            cols[f"dow{dow}_{loc}"] = (isloc & (d["dow"] == dow).to_numpy()).astype(float)
    for h in ("public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"):
        cols[h] = d[h].astype(float).to_numpy()
    return pd.DataFrame(cols, index=d.index)


def weather_by(d, key):
    """Weather terms interacted with a period label (for example the year)."""
    cols = {}
    for lab in sorted(d[key].unique()):
        m = (d[key] == lab).to_numpy().astype(float)
        for v in WEATHER:
            cols[f"{v}:{lab}"] = d[v].to_numpy() * m
    return pd.DataFrame(cols, index=d.index)


def effects(beta, V, lab):
    """Rain, cold and heat effects for one period label, with standard errors (delta method)."""
    out = {}
    a = pd.Series(0.0, index=beta.index)
    a[f"wet:{lab}"] = 1
    out["rain"] = a
    a = pd.Series(0.0, index=beta.index)
    a[f"t_lt5:{lab}"] = 5 / 15
    a[f"t_5_15:{lab}"] = 10 / 15
    out["cold"] = a
    a = pd.Series(0.0, index=beta.index)
    a[f"t_gt25:{lab}"] = 1
    out["heat"] = a
    res = {}
    for k, a in out.items():
        est = float(a @ beta)
        se = float(np.sqrt(a @ V @ a))
        res[k] = (est, se, a)
    return res
