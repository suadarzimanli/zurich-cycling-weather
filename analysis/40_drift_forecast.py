"""Drift study: frozen versus yearly retrained forecasting models (docs/DRIFT_PLAN_2026-11-27.md, frozen).

Trains LightGBM exactly as code/10_forecast_trees.py on the windows of the plan, forecasts every later test year,
and estimates the wet-day bias (wet-minus-dry relative error within year-month and counter, as in
code/14_check_drift_months.py) with a bootstrap of test weeks. Writes results/drift/.

The fixed-effects regression is solved from its normal equations built with bincount (exact, fast). Two checks run
first: it equals a dense least-squares fit, and it reproduces the stored result of code/14 on the same inputs.

Usage: <torch312 python> 40_drift_forecast.py <project_dir>
"""
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

root = Path(sys.argv[1])
out = root / "results" / "drift"
out.mkdir(parents=True, exist_ok=True)

LOCS = ["VZS_BUCH", "VZS_HOFW", "VZS_LANN", "VZS_LIMC", "VZS_LUXG", "VZS_MILI", "VZS_MUEH", "VZS_MYTH",
        "VZS_SCHE", "VZS_SIHL", "VZS_TOED"]
CAL = ["dow", "month", "public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]
LAGS = ["lag1", "lag7", "lag14", "mean7"]
WX = ["light", "wet", "tmax", "sun_h"]
FEATS = ["loc_cat"] + CAL + LAGS + WX
PARAMS = dict(objective="regression", n_estimators=500, learning_rate=0.05, num_leaves=31,
              min_child_samples=50, verbose=-1, random_state=2026, n_jobs=8)
PANDEMIC = {2020, 2021}
TEST_YEARS = [2014, 2015, 2016, 2017, 2018, 2019, 2022, 2023, 2024, 2025, 2026]
WINDOWS = {"W1": (2011, 2013), "W2": (2014, 2016), "W3": (2017, 2019), "W4": (2022, 2024)}
MIN_TRAIN_DAYS = 200
B, SEED = 2000, 2026
LATE = [2022, 2023, 2024, 2025, 2026]
EARLY = [2014, 2015, 2016]


# ---------- the wet-day bias estimator ----------
def gap_arrays(wet, rel, ym, lc):
    """OLS coefficient of wet in rel ~ wet + year-month FE + counter FE (first counter dropped), via normal equations."""
    _, ymi = np.unique(ym, return_inverse=True)
    _, lci = np.unique(lc, return_inverse=True)
    K, J = ymi.max() + 1, lci.max() + 1
    P = 1 + K + (J - 1)
    A, v = np.zeros((P, P)), np.zeros(P)
    A[0, 0], v[0] = wet.sum(), (wet * rel).sum()
    s = np.bincount(ymi, wet, K)
    A[0, 1:1 + K] = A[1:1 + K, 0] = s
    A[1 + np.arange(K), 1 + np.arange(K)] = np.bincount(ymi, minlength=K)
    v[1:1 + K] = np.bincount(ymi, rel, K)
    if J > 1:
        m = lci > 0
        lj = lci[m] - 1
        s = np.bincount(lj, wet[m], J - 1)
        A[0, 1 + K:] = A[1 + K:, 0] = s
        A[1 + K + np.arange(J - 1), 1 + K + np.arange(J - 1)] = np.bincount(lj, minlength=J - 1)
        cross = np.bincount(ymi[m] * (J - 1) + lj, minlength=K * (J - 1)).reshape(K, J - 1)
        A[1:1 + K, 1 + K:], A[1 + K:, 1:1 + K] = cross, cross.T
        v[1 + K:] = np.bincount(lj, rel[m], J - 1)
    return float(np.linalg.lstsq(A, v, rcond=None)[0][0])


def gap_dense(x):
    """Reference implementation, as in code/14_check_drift_months.py."""
    X = pd.concat([x[["wet_i"]], pd.get_dummies(x["ym"], dtype=float),
                   pd.get_dummies(x["loc"], drop_first=True, dtype=float)], axis=1).to_numpy()
    return float(np.linalg.lstsq(X, x["rel"].to_numpy(), rcond=None)[0][0])


def gap(x):
    return gap_arrays(x["wet_i"].to_numpy(float), x["rel"].to_numpy(float), x["ym"].to_numpy(), x["loc"].to_numpy())


def prep(x):
    x = x.copy()
    x["kind"] = np.where(x["rain"] >= 2, "wet", np.where(x["rain"] < 0.1, "dry", "light"))
    x = x[x["kind"] != "light"].copy()
    x["wet_i"] = (x["kind"] == "wet").astype(float)
    x["ym"] = x["date"].dt.strftime("%Y-%m")
    return x


# check 1: reproduce code/14 (full model, 11 counters, earlier test period) with both implementations
ref = json.loads((root / "results" / "check_drift_months.json").read_text())["full_model_reference"]["within_month_wet_minus_dry"]
e14 = prep(pd.read_parquet(root / "results" / "forecast" / "pred_trees.parquet").query("loc in @LOCS"))
e14["rel"] = (e14["pred_lgbm_wx"] - e14["y"]) / e14["y"]
g_fast, g_dense = gap(e14), gap_dense(e14)
print(f"check: code/14 stored {ref:+.10f} | dense {g_dense:+.10f} | fast {g_fast:+.10f}")
assert abs(g_dense - ref) < 1e-9 and abs(g_fast - ref) < 1e-9, "estimator does not reproduce code/14"

# ---------- models ----------
p = pd.read_parquet(root / "data" / "forecast" / "panel.parquet")
p = p[p["loc"].isin(LOCS)].copy()
p["year"] = p["date"].dt.year
p = p[~p["year"].isin(PANDEMIC)]
p["loc_cat"] = pd.Categorical(p["loc"], categories=LOCS)
counted = p[p["y"].notna()]
evalrows = p[p["y"].notna() & p["lag7"].notna() & p["year"].isin(TEST_YEARS)]


def fit(train):
    m = lgb.LGBMRegressor(**PARAMS)
    m.fit(train[FEATS], np.log1p(train["y"]), categorical_feature=["loc_cat"])
    return m


def eligible(train):
    n = train.groupby("loc")["y"].count()
    return sorted(n[n >= MIN_TRAIN_DAYS].index)


preds, models_info = [], {}
for name, (a, b) in WINDOWS.items():
    train = counted[(counted["year"] >= a) & (counted["year"] <= b)]
    locs = eligible(train)
    m = fit(train[train["loc"].isin(locs)])
    test = evalrows[(evalrows["year"] > b) & evalrows["loc"].isin(locs)].copy()
    test["pred"] = np.expm1(m.predict(test[FEATS]))
    test["strategy"], test["train_end"] = f"frozen_{name}", b
    preds.append(test)
    models_info[f"frozen_{name}"] = {"train_years": [a, b], "train_rows": int(len(train)), "counters": locs}
    print(f"frozen {name} {a}-{b}: {len(train)} training rows, {len(locs)} counters, {len(test)} test rows")
for t in TEST_YEARS:
    train = counted[counted["year"] < t]
    locs = eligible(train)
    m = fit(train[train["loc"].isin(locs)])
    test = evalrows[(evalrows["year"] == t) & evalrows["loc"].isin(locs)].copy()
    test["pred"] = np.expm1(m.predict(test[FEATS]))
    test["strategy"], test["train_end"] = "yearly", t - 1
    preds.append(test)
    models_info[f"yearly_{t}"] = {"train_years": [int(train["year"].min()), t - 1], "train_rows": int(len(train)),
                                  "counters": locs}
    print(f"yearly retrained for {t}: {len(train)} training rows, {len(locs)} counters, {len(test)} test rows")

d = pd.concat(preds, ignore_index=True)
d["rel"] = (d["pred"] - d["y"]) / d["y"]
d["kind"] = np.where(d["rain"] >= 2, "wet", np.where(d["rain"] < 0.1, "dry", "light"))
iso = d["date"].dt.isocalendar()
d["week"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
d["age"] = d["year"] - d["train_end"]
d.drop(columns=["loc_cat"]).to_parquet(out / "drift_predictions.parquet", index=False)
c = prep(d)

# ---------- tests ----------
def subset(strats, years):
    return c[c["strategy"].isin(strats) & c["year"].isin(years)]


sets = {"H1_frozen_W1W2_late": subset(["frozen_W1", "frozen_W2"], LATE), "yearly_late": subset(["yearly"], LATE),
        "H3_frozen_W1_early": subset(["frozen_W1"], EARLY), "yearly_early": subset(["yearly"], EARLY)}
for s in ("W1", "W2", "W3", "W4"):
    sets[f"frozen_{s}_late"] = subset([f"frozen_{s}"], LATE)

point = {}
for k, v in sets.items():
    point[k] = gap(v)
    assert abs(point[k] - gap_dense(v)) < 1e-8, f"fast and dense estimates differ for {k}"  # check 2

arr = {k: dict(wet=v["wet_i"].to_numpy(float), rel=v["rel"].to_numpy(float), ym=v["ym"].to_numpy(),
               lc=v["loc"].to_numpy(), idx={w: np.flatnonzero(v["week"].to_numpy() == w) for w in v["week"].unique()})
       for k, v in sets.items()}
rng = np.random.default_rng(SEED)
all_weeks = np.array(sorted(c["week"].unique()))
boot = {k: np.empty(B) for k in sets}
for i in range(B):
    draw = rng.choice(all_weeks, len(all_weeks), replace=True)
    for k, a in arr.items():
        rows = [a["idx"][w] for w in draw if w in a["idx"]]
        if not rows:
            boot[k][i] = np.nan
            continue
        r = np.concatenate(rows)
        boot[k][i] = gap_arrays(a["wet"][r], a["rel"][r], a["ym"][r], a["lc"][r])


def ci(x):
    lo, hi = np.nanpercentile(x, [2.5, 97.5])
    return [float(lo), float(hi)]


tests = {
    "H1": {"what": "wet-day bias, frozen W1 and W2 pooled, test years 2022-2026", "prediction": "interval below 0",
           "estimate": point["H1_frozen_W1W2_late"], "ci95": ci(boot["H1_frozen_W1W2_late"])},
    "H2": {"what": "frozen W1 and W2 (pooled) minus yearly retrained, 2022-2026", "prediction": "interval below 0",
           "estimate": point["H1_frozen_W1W2_late"] - point["yearly_late"],
           "ci95": ci(boot["H1_frozen_W1W2_late"] - boot["yearly_late"])},
    "H3": {"what": "placebo: frozen W1 minus yearly retrained, 2014-2016", "prediction": "interval includes 0",
           "estimate": point["H3_frozen_W1_early"] - point["yearly_early"],
           "ci95": ci(boot["H3_frozen_W1_early"] - boot["yearly_early"])},
    "H4": {"what": "wet-day bias, yearly retrained, 2022-2026", "prediction": "interval includes 0",
           "estimate": point["yearly_late"], "ci95": ci(boot["yearly_late"])},
}
for v in tests.values():
    lo, hi = v["ci95"]
    v["supported"] = bool(hi < 0) if v["prediction"] == "interval below 0" else bool(lo <= 0 <= hi)
described = {k: {"estimate": point[k], "ci95": ci(boot[k]), "n_wet": int(sets[k]["wet_i"].sum()),
                 "n_dry": int((1 - sets[k]["wet_i"]).sum())} for k in sets}

# ---------- described ----------
cells = []
for (s, yr), g in c.groupby(["strategy", "year"]):
    cells.append({"strategy": s, "test_year": int(yr), "age": int(g["age"].iloc[0]), "wet_day_bias": gap(g),
                  "n_wet": int(g["wet_i"].sum()), "n_dry": int((1 - g["wet_i"]).sum())})
pd.DataFrame(cells).to_csv(out / "drift_cells.csv", index=False)

acc = {}
for per, yrs in (("2014-2019", [2014, 2015, 2016, 2017, 2018, 2019]), ("2022-2026", LATE)):
    for s, g in d[d["year"].isin(yrs)].groupby("strategy"):
        acc[f"{s} | {per}"] = {kind: float((h["pred"] - h["y"]).abs().sum() / (h["lag7"] - h["y"]).abs().sum())
                               for kind, h in (("all", g), ("wet", g[g["kind"] == "wet"]), ("dry", g[g["kind"] == "dry"]))}

e = prep(pd.read_parquet(root / "results" / "forecast" / "pred_all.parquet"))
earlier = {col: gap(e.assign(rel=(e[col] - e["y"]) / e["y"]))
           for col in ("pred_lgbm_wx", "pred_gwn_wx", "pred_rnn_wx")}

res = {"plan": "docs/DRIFT_PLAN_2026-11-27.md (frozen 2026-11-27 15:05:30 +0100)",
       "checks": {"code14_reference": ref, "dense": g_dense, "fast": g_fast},
       "tests": tests, "described_pooled": described, "accuracy_vs_last_week": acc,
       "earlier_models_wet_day_bias_19_counters": earlier, "models": models_info,
       "bootstrap": {"draws": B, "seed": SEED, "unit": "ISO week"}}
(out / "drift_results.json").write_text(json.dumps(res, indent=2))
for k, v in tests.items():
    print(f"{k}: {v['estimate']:+.4f} [{v['ci95'][0]:+.4f}, {v['ci95'][1]:+.4f}]  prediction: {v['prediction']}  -> "
          f"{'supported' if v['supported'] else 'NOT supported'}")
for k in ("frozen_W1_late", "frozen_W2_late", "frozen_W3_late", "frozen_W4_late"):
    print(f"described {k}: {point[k]:+.4f} {ci(boot[k])}")
print("earlier models, wet-day bias (19 counters):", {k: round(v, 4) for k, v in earlier.items()})
