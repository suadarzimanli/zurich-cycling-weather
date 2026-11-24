"""Check blockpois against the validated fepois (which uses explicit weekday dummies).

(a) No local regressors: the frozen prediction-1 test on the 9 locations.
(b) With local regressors: weather x location as local terms, on a small subset.
Usage: python 21_validate_blockpois.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from blockpois import blockpois
from design import WEATHER, controls, load, weather_by
from fepois import fepois

root = Path(sys.argv[1])
core = json.loads((root / "data" / "derived" / "sample_definitions.json").read_text())["period_comparison_locations"]
HOL = ["public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]
d = load(root)

# (a)
a = d[d["loc"].isin(core) & d["year"].isin([2011, 2012, 2013, 2014, 2022, 2023, 2024, 2025, 2026])].copy()
a["period"] = np.where(a["year"] <= 2014, "early", "late")
W = weather_by(a, "period")
ref = fepois(a["y"], pd.concat([W, controls(a)], axis=1).to_numpy(), a["fe_group"], a["week"],
             names=list(W.columns) + list(controls(a).columns))
G = pd.concat([W, a[HOL].astype(float)], axis=1)
new = blockpois(a["y"], G.to_numpy(), None, a["loc"], a["fe_group"], a["dow"], a["week"], names=list(G.columns))
cols = list(W.columns) + HOL
db = (new["beta"][cols] - ref["beta"][cols]).abs().max()
ds = (np.sqrt(np.diag(new["vcov"].loc[cols, cols])) / np.sqrt(np.diag(ref["vcov"].loc[cols, cols])) - 1).__abs__().max()
print(f"(a) max |beta diff| {db:.2e} | max relative SE diff {ds:.2e} | iterations {new['iterations']}")
print("    wet early/late:", round(new["beta"]["wet:early"], 5), round(new["beta"]["wet:late"], 5), "(frozen result -0.4072 / -0.3393)")

# (b)
b = d[d["loc"].isin(["VZS_LUXG", "VZS_MYTH", "VZS_SCHE"]) & d["year"].isin([2015, 2016])].copy()
b["is2016"] = (b["year"] == 2016).astype(float)
Lloc = pd.DataFrame({f"{v}:{l}": b[v] * (b["loc"] == l) for l in sorted(b["loc"].unique()) for v in WEATHER}, index=b.index)
Wt = pd.DataFrame({f"{v}:2016": b[v] * b["is2016"] for v in WEATHER}, index=b.index)
C = controls(b)
C = C.loc[:, C.std() > 0]
ref = fepois(b["y"], pd.concat([Lloc, Wt, C], axis=1).to_numpy(), b["fe_group"], b["week"],
             names=list(Lloc.columns) + list(Wt.columns) + list(C.columns))
G = pd.concat([Wt, b[HOL].astype(float)], axis=1)
G = G.loc[:, G.std() > 0]
new = blockpois(b["y"], G.to_numpy(), b[WEATHER].to_numpy(), b["loc"], b["fe_group"], b["dow"], b["week"], names=list(G.columns))
cols = list(G.columns)
db = (new["beta"][cols] - ref["beta"][cols]).abs().max()
ds = (np.sqrt(np.diag(new["vcov"].loc[cols, cols])) / np.sqrt(np.diag(ref["vcov"].loc[cols, cols])) - 1).__abs__().max()
print(f"(b) max |beta diff| {db:.2e} | max relative SE diff {ds:.2e} | iterations {new['iterations']}")
assert db < 1e-6 and ds < 1e-4
print("VALIDATION PASSED")
