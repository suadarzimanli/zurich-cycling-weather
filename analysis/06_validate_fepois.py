"""Check fepois against statsmodels (explicit group dummies) on a small subset.

Usage: python 06_validate_fepois.py <project_dir>
"""
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm

from design import WEATHER, controls, load
from fepois import fepois

d = load(sys.argv[1])
s = d[d["loc"].isin(["VZS_LUXG", "VZS_MYTH"]) & (d["year"] == 2015)].copy()
ctrl = controls(s)
ctrl = ctrl.loc[:, ctrl.std() > 0]
X = pd.concat([s[WEATHER], ctrl], axis=1)
names = list(X.columns)

r = fepois(s["y"], X.to_numpy(), s["fe_group"], s["week"], names=names)

dum = pd.get_dummies(s["fe_group"], dtype=float)
Xs = pd.concat([X, dum], axis=1)
m = sm.GLM(s["y"], Xs, family=sm.families.Poisson()).fit(
    cov_type="cluster", cov_kwds={"groups": pd.factorize(s["week"])[0], "use_correction": False}, tol=1e-12)
b_sm = m.params[r["beta"].index]
se_sm = np.sqrt(np.diag(m.cov_params().loc[r["beta"].index, r["beta"].index]))
se_me = np.sqrt(np.diag(r["vcov_raw"]))
print("n", r["n"], "| groups", r["groups"], "| clusters", r["clusters"], "| iterations", r["iterations"], "| dropped", r["dropped"])
print("max |beta difference|:", float(np.max(np.abs(r["beta"] - b_sm))))
print("max relative SE difference:", float(np.max(np.abs(se_me / se_sm - 1))))
print(pd.DataFrame({"fepois": r["beta"][WEATHER], "statsmodels": b_sm[WEATHER],
                    "se_fepois": se_me[:len(WEATHER)], "se_statsmodels": se_sm[:len(WEATHER)]}).round(6).to_string())
assert np.max(np.abs(r["beta"] - b_sm)) < 1e-6
assert np.max(np.abs(se_me / se_sm - 1)) < 1e-4
print("VALIDATION PASSED")
