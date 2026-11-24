"""Model runs shared by the result scripts (definitions in ANALYSIS_DETAILS_2026-11-24.md)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from design import WEATHER, controls, effects, load, weather_by
from fepois import fepois

EARLY = range(2011, 2015)
LATE = range(2022, 2027)


def fit(d, key):
    W = weather_by(d, key)
    C = controls(d)
    X = pd.concat([W, C], axis=1)
    return fepois(d["y"], X.to_numpy(), d["fe_group"], d["week"], names=list(X.columns))


def by_year(d):
    r = fit(d, "year")
    rows = []
    for y in sorted(d["year"].unique()):
        e = effects(r["beta"], r["vcov"], y)
        for k, (est, se, _) in e.items():
            rows.append({"year": y, "effect": k, "est": est, "se": se, "n_days": int((d["year"] == y).sum())})
    return pd.DataFrame(rows), r


def period_test(d, locs=None):
    """Early (2011-2014) against late (2022-2026). Returns a dict with all prediction quantities."""
    if locs is not None:
        d = d[d["loc"].isin(locs)]
    d = d[d["year"].isin(list(EARLY) + list(LATE))].copy()
    d["period"] = np.where(d["year"].isin(list(EARLY)), "early", "late")
    r = fit(d, "period")
    b, V = r["beta"], r["vcov"]
    ee, el = effects(b, V, "early"), effects(b, V, "late")
    out = {"n": r["n"], "clusters": r["clusters"], "locations": int(d["loc"].nunique())}
    for k in ("rain", "cold", "heat"):
        E, seE, aE = ee[k]
        L, seL, aL = el[k]
        a = aL - aE
        out[k] = {"early": E, "early_se": seE, "late": L, "late_se": seL,
                  "change": L - E, "change_se": float(np.sqrt(a @ V @ a))}
        # shrinkage 1 - L/E, gradient in beta space by the delta method
        grad = -(1 / E) * aL + (L / E ** 2) * aE
        out[k]["shrink"] = 1 - L / E
        out[k]["shrink_grad"] = grad
        out[k]["shrink_se"] = float(np.sqrt(grad @ V @ grad))
        out[k]["early_ci_excludes_zero"] = abs(E) > 1.96 * seE
    for k in ("cold", "heat"):
        g = out[k]["shrink_grad"] - out["rain"]["shrink_grad"]
        out[f"{k}_minus_rain_shrink"] = out[k]["shrink"] - out["rain"]["shrink"]
        out[f"{k}_minus_rain_shrink_se"] = float(np.sqrt(g @ V @ g))
    for k in ("rain", "cold", "heat"):
        del out[k]["shrink_grad"]
    return out


def pct(b):
    return 100 * (np.exp(b) - 1)


def save_json(obj, path):
    def conv(o):
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        if isinstance(o, np.bool_):
            return bool(o)
        raise TypeError(type(o))
    Path(path).write_text(json.dumps(obj, indent=2, default=conv), encoding="utf-8")
