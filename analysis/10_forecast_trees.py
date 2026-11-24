"""Last-week baseline, LightGBM (two weather versions) and the drift test.

Usage: python 10_forecast_trees.py <project_dir>
"""
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from fc_common import score

root = Path(sys.argv[1])
fdir = root / "data" / "forecast"
res = root / "results" / "forecast"
res.mkdir(parents=True, exist_ok=True)
p = pd.read_parquet(fdir / "panel.parquet")
TRAIN_END = pd.Timestamp("2025-05-31")

CAL = ["dow", "month", "public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]
LAGS = ["lag1", "lag7", "lag14", "mean7"]
WX = ["light", "wet", "tmax", "sun_h"]
PARAMS = dict(objective="regression", n_estimators=500, learning_rate=0.05, num_leaves=31,
              min_child_samples=50, verbose=-1, random_state=2026, n_jobs=8)

p["loc_cat"] = pd.Categorical(p["loc"])


def fit_predict(train, test, weather):
    feats = ["loc_cat"] + CAL + LAGS + (WX if weather else [])
    tr = train[train["y"].notna()]
    m = lgb.LGBMRegressor(**PARAMS)
    m.fit(tr[feats], np.log1p(tr["y"]), categorical_feature=["loc_cat"])
    return np.expm1(m.predict(test[feats]))


ev = p[p["eval"]].copy()
ev["pred_lastweek"] = ev["lag7"]
train_all = p[p["date"] <= TRAIN_END]
ev["pred_lgbm_wx"] = fit_predict(train_all, ev, True)
ev["pred_lgbm_nowx"] = fit_predict(train_all, ev, False)

out = {"eval_rows": len(ev), "locations": int(ev["loc"].nunique()), "days": int(ev["date"].nunique())}
for col in ("pred_lastweek", "pred_lgbm_wx", "pred_lgbm_nowx"):
    out[col] = score(ev, col)
print(json.dumps(out, indent=2))

# ---- drift test ----
old_locs = set(p.loc[(p["date"].dt.year <= 2015) & p["y"].notna(), "loc"])
dl = sorted(old_locs & set(ev["loc"]))
print("drift-test locations:", dl)
train_old = p[(p["date"].dt.year >= 2011) & (p["date"].dt.year <= 2015) & p["loc"].isin(dl)]
d = ev[ev["loc"].isin(dl)].copy()
d["pred_old"] = fit_predict(train_old, d, True)
d["pred_new"] = d["pred_lgbm_wx"]
d["rel_old"] = (d["pred_old"] - d["y"]) / d["y"]
d["rel_new"] = (d["pred_new"] - d["y"]) / d["y"]
d["kind"] = np.where(d["rain"] >= 2, "wet", np.where(d["rain"] < 0.1, "dry", "light"))
d["week"] = d["date"].dt.isocalendar()["year"].astype(str) + "-" + d["date"].dt.isocalendar()["week"].astype(str)


def gap(x, col):
    return x.loc[x["kind"] == "wet", col].mean() - x.loc[x["kind"] == "dry", col].mean()


rng = np.random.default_rng(2026)
weeks = d["week"].unique()
by_week = {w: x for w, x in d.groupby("week")}
boot = {"rel_old": [], "rel_new": []}
for _ in range(2000):
    s = pd.concat([by_week[w] for w in rng.choice(weeks, len(weeks), replace=True)])
    for col in boot:
        boot[col].append(gap(s, col))
drift = {}
for col, name in (("rel_old", "old_model_2011_2015"), ("rel_new", "full_model_reference")):
    est = gap(d, col)
    lo, hi = np.nanpercentile(boot[col], [2.5, 97.5])
    drift[name] = {"wet_minus_dry": float(est), "ci95": [float(lo), float(hi)],
                   "mean_rel_error_wet": float(d.loc[d["kind"] == "wet", col].mean()),
                   "mean_rel_error_dry": float(d.loc[d["kind"] == "dry", col].mean())}
drift["n_wet"] = int((d["kind"] == "wet").sum())
drift["n_dry"] = int((d["kind"] == "dry").sum())
drift["locations"] = dl
out["drift"] = drift
print(json.dumps(drift, indent=2))
ev.to_parquet(res / "pred_trees.parquet", index=False)
(res / "scores_trees.json").write_text(json.dumps(out, indent=2))
