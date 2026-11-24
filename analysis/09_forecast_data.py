"""Location-by-day panel for forecasting (FORECAST_DETAILS_2026-11-24.md).

Usage: python 09_forecast_data.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1])
der = root / "data" / "derived"
out = root / "data" / "forecast"
out.mkdir(parents=True, exist_ok=True)

TEST_START, TEST_END = pd.Timestamp("2025-06-01"), pd.Timestamp("2026-11-22")

c = pd.read_parquet(der / "counts_daily.parquet")
c = c[c["keep"]]
# if two devices report on the same location-day (overlap at a device change), keep the newer device
first_day = c.groupby("device")["date"].min().rename("device_start")
c = c.merge(first_day, left_on="device", right_index=True)
n_overlap = int(c.duplicated(["loc", "date"], keep=False).sum())
c = c.sort_values("device_start").drop_duplicates(["loc", "date"], keep="last")
print("location-days with two devices (newer kept):", n_overlap)

locs = sorted(c["loc"].unique())
dates = pd.date_range("2011-01-01", TEST_END, freq="D")
grid = pd.MultiIndex.from_product([locs, dates], names=["loc", "date"]).to_frame(index=False)
p = grid.merge(c[["loc", "date", "velo_day", "E", "N"]], on=["loc", "date"], how="left")
p = p.rename(columns={"velo_day": "y"})
p["y"] = p["y"].astype(float)

w = pd.read_parquet(der / "weather_daily.parquet")
w = w.assign(light=((w["sma_rain_day"] >= 0.1) & (w["sma_rain_day"] < 2)).astype(float),
             wet=(w["sma_rain_day"] >= 2).astype(float),
             tmax=w["sma_tmax"], sun_h=w["sma_sun_day"] / 60, rain=w["sma_rain_day"])
k = pd.read_parquet(der / "calendar_daily.parquet")
p = p.merge(w[["date", "light", "wet", "tmax", "sun_h", "rain"]], on="date", how="left")
p = p.merge(k, on="date", how="left")
for h in ("public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"):
    p[h] = p[h].astype(float)
p["month"] = p["date"].dt.month

# lags relative to the target day (the forecast is made at the end of the day before)
p = p.sort_values(["loc", "date"]).reset_index(drop=True)
g = p.groupby("loc")["y"]
p["lag1"] = g.shift(1)
p["lag7"] = g.shift(7)
p["lag14"] = g.shift(14)


def mean_last7(s):
    # mean of the last 7 non-missing values among the previous 28 days (target day excluded)
    vals = s.shift(1).to_numpy()
    out = np.full(len(vals), np.nan)
    for i in range(len(vals)):
        win = vals[max(0, i - 27): i + 1]
        win = win[~np.isnan(win)]
        if len(win):
            out[i] = win[-7:].mean()
    return out


p["mean7"] = np.concatenate([mean_last7(s) for _, s in p.groupby("loc", sort=True)["y"]])

# coordinates per location (latest device)
xy = c.sort_values("device_start").groupby("loc")[["E", "N"]].last()
p = p.drop(columns=["E", "N"]).merge(xy, left_on="loc", right_index=True, how="left")

test = p[(p["date"] >= TEST_START) & (p["date"] <= TEST_END)]
usable = test.groupby("loc")["y"].count()
nodes = sorted(usable[usable >= 300].index)
p["test_node"] = p["loc"].isin(nodes)
p["eval"] = p["test_node"] & (p["date"] >= TEST_START) & p["y"].notna() & p["lag7"].notna()
p.to_parquet(out / "panel.parquet", index=False)
(out / "nodes.json").write_text(json.dumps({"test_nodes": nodes}, indent=2))
print("test-period usable days per location:\n", usable.sort_values(ascending=False).to_string())
print("test nodes:", len(nodes), nodes)
print("evaluation target days:", int(p["eval"].sum()))
