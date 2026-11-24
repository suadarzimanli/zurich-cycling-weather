"""Check 2: does the drift result survive comparing wet and dry days within the same month?

Refits the 2011-2015 LightGBM exactly as in 10_forecast_trees.py (same data, settings, seed),
confirms that the original result is reproduced, then compares wet and dry days within
each calendar month of the test period and within each location (regression with
month and location fixed effects). Interval: bootstrap of test weeks (2,000 draws, seed 2026).

Usage: python 14_check_drift_months.py <project_dir>   (torch312 environment, as for 10)
"""
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

root = Path(sys.argv[1])
fdir = root / "data" / "forecast"
res = root / "results" / "forecast"
p = pd.read_parquet(fdir / "panel.parquet")
ev = pd.read_parquet(res / "pred_trees.parquet")

CAL = ["dow", "month", "public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]
LAGS = ["lag1", "lag7", "lag14", "mean7"]
WX = ["light", "wet", "tmax", "sun_h"]
PARAMS = dict(objective="regression", n_estimators=500, learning_rate=0.05, num_leaves=31,
              min_child_samples=50, verbose=-1, random_state=2026, n_jobs=8)
p["loc_cat"] = pd.Categorical(p["loc"])
ev["loc_cat"] = pd.Categorical(ev["loc"], categories=p["loc_cat"].cat.categories)
feats = ["loc_cat"] + CAL + LAGS + WX

old_locs = set(p.loc[(p["date"].dt.year <= 2015) & p["y"].notna(), "loc"])
dl = sorted(old_locs & set(ev["loc"]))
train_old = p[(p["date"].dt.year >= 2011) & (p["date"].dt.year <= 2015) & p["loc"].isin(dl) & p["y"].notna()]
m = lgb.LGBMRegressor(**PARAMS)
m.fit(train_old[feats], np.log1p(train_old["y"]), categorical_feature=["loc_cat"])
d = ev[ev["loc"].isin(dl)].copy()
d["rel_old"] = (np.expm1(m.predict(d[feats])) - d["y"]) / d["y"]
d["rel_new"] = (d["pred_lgbm_wx"] - d["y"]) / d["y"]
d["kind"] = np.where(d["rain"] >= 2, "wet", np.where(d["rain"] < 0.1, "dry", "light"))
d = d[d["kind"] != "light"].copy()
d["wet_i"] = (d["kind"] == "wet").astype(float)
d["ym"] = d["date"].dt.strftime("%Y-%m")
iso = d["date"].dt.isocalendar()
d["week"] = iso["year"].astype(str) + "-" + iso["week"].astype(str)

raw_gap = d.loc[d["wet_i"] == 1, "rel_old"].mean() - d.loc[d["wet_i"] == 0, "rel_old"].mean()
print(f"reproduced original gap (old model): {raw_gap:+.5f}   (original run: -0.07698)")
assert abs(raw_gap - (-0.07698422742829868)) < 1e-6, "refit did not reproduce the original model"


def within_gap(x, col):
    """Wet-minus-dry coefficient from least squares with month and location dummies."""
    X = pd.concat([x[["wet_i"]], pd.get_dummies(x["ym"], dtype=float),
                   pd.get_dummies(x["loc"], drop_first=True, dtype=float)], axis=1).to_numpy()
    b = np.linalg.lstsq(X, x[col].to_numpy(), rcond=None)[0]
    return float(b[0])


rng = np.random.default_rng(2026)
weeks = d["week"].unique()
by_week = {k: g for k, g in d.groupby("week")}
out = {"locations": dl, "n_wet": int(d["wet_i"].sum()), "n_dry": int((1 - d["wet_i"]).sum())}
for col, name in (("rel_old", "old_model_2011_2015"), ("rel_new", "full_model_reference")):
    est = within_gap(d, col)
    boot = []
    for _ in range(2000):
        s = pd.concat([by_week[k] for k in rng.choice(weeks, len(weeks), replace=True)], ignore_index=True)
        boot.append(within_gap(s, col))
    lo, hi = np.percentile(boot, [2.5, 97.5])
    out[name] = {"within_month_wet_minus_dry": est, "ci95": [float(lo), float(hi)]}
    print(f"{name}: wet minus dry within month and location {est:+.4f} [{lo:+.4f}, {hi:+.4f}]")
print("original (no month adjustment): old model -0.0770 [-0.1303, -0.0204], reference +0.0141 [-0.0354, +0.0699]")
(root / "results" / "check_drift_months.json").write_text(json.dumps(out, indent=2))
