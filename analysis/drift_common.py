"""Shared helpers for the drift checks: the wet-day bias estimator (identical to 40_drift_forecast.py) and a
bootstrap of test weeks."""
import numpy as np


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


def prep(x):
    x = x.copy()
    x["kind"] = np.where(x["rain"] >= 2, "wet", np.where(x["rain"] < 0.1, "dry", "light"))
    x = x[x["kind"] != "light"].copy()
    x["wet_i"] = (x["kind"] == "wet").astype(float)
    x["ym"] = x["date"].dt.strftime("%Y-%m")
    if "rel" not in x:
        x["rel"] = (x["pred"] - x["y"]) / x["y"]
    return x


def gap(x):
    return gap_arrays(x["wet_i"].to_numpy(float), x["rel"].to_numpy(float), x["ym"].to_numpy(), x["loc"].to_numpy())


def bootstrap(sets, weeks, draws, seed):
    """The same resampled weeks for every set, so differences between sets can be read off directly."""
    arr = {k: (v["wet_i"].to_numpy(float), v["rel"].to_numpy(float), v["ym"].to_numpy(), v["loc"].to_numpy(),
               {w: np.flatnonzero(v["week"].to_numpy() == w) for w in v["week"].unique()}) for k, v in sets.items()}
    rng = np.random.default_rng(seed)
    out = {k: np.empty(draws) for k in sets}
    for i in range(draws):
        draw = rng.choice(weeks, len(weeks), replace=True)
        for k, (wet, rel, ym, lc, idx) in arr.items():
            rows = [idx[w] for w in draw if w in idx]
            out[k][i] = gap_arrays(*(a[np.concatenate(rows)] for a in (wet, rel, ym, lc))) if rows else np.nan
    return out
