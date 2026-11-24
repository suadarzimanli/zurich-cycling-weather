"""Scoring helpers for the forecasting part."""
import numpy as np
import pandas as pd


def newey_west_t(x, lags=7):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    m = x.mean()
    e = x - m
    s = e @ e / n
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        s += 2 * w * (e[L:] @ e[:-L]) / n
    se = np.sqrt(s / n)
    return m, se, m / se, n


def score(df, model_col, base_col="pred_lastweek"):
    """MAE ratio against the base, and a Diebold-Mariano test on daily mean loss differences."""
    from scipy.stats import norm
    e_m = (df[model_col] - df["y"]).abs()
    e_b = (df[base_col] - df["y"]).abs()
    ratio = e_m.sum() / e_b.sum()
    daily = (e_m - e_b).groupby(df["date"]).mean()
    m, se, t, n = newey_west_t(daily.to_numpy())
    return {"mae": float(e_m.mean()), "mae_ratio": float(ratio), "dm_mean_diff": float(m),
            "dm_t": float(t), "dm_p": float(2 * norm.sf(abs(t))), "days": int(n)}
