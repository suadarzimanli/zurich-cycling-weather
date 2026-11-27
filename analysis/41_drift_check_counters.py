"""Check added AFTER the drift results (not in the frozen plan): is the large wet-day bias of the 2011-2013 model
about the age of the model, or about its smaller set of counters?

The 2011-2013 model covers 6 counters, the later models 11. Here every strategy is compared on the same 6 counters
in the test years 2022-2026, using the predictions saved by 40_drift_forecast.py (no model is retrained).
Interval: bootstrap of test weeks (2,000 draws, seed 2026), as in the plan.

Usage: <torch312 python> 41_drift_check_counters.py <project_dir>
"""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("drift", root / "code" / "drift_common.py")
dc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dc)

res = json.loads((root / "results" / "drift" / "drift_results.json").read_text())
six = res["models"]["frozen_W1"]["counters"]
d = pd.read_parquet(root / "results" / "drift" / "drift_predictions.parquet")
c = dc.prep(d[d["loc"].isin(six) & d["year"].isin([2022, 2023, 2024, 2025, 2026])])

sets = {s: c[c["strategy"] == s] for s in ("frozen_W1", "frozen_W2", "frozen_W3", "frozen_W4", "yearly")}
point = {k: dc.gap(v) for k, v in sets.items()}
boot = dc.bootstrap(sets, np.array(sorted(c["week"].unique())), 2000, 2026)
out = {"counters": six, "test_years": "2022-2026", "added_after_results": True}
for k in sets:
    lo, hi = np.nanpercentile(boot[k], [2.5, 97.5])
    out[k] = {"estimate": point[k], "ci95": [float(lo), float(hi)]}
    print(f"{k:10} on the 6 counters: {point[k]:+.4f} [{lo:+.4f}, {hi:+.4f}]")
for k in ("frozen_W2", "frozen_W3"):
    diff = boot["frozen_W1"] - boot[k]
    lo, hi = np.nanpercentile(diff, [2.5, 97.5])
    out[f"frozen_W1_minus_{k}"] = {"estimate": point["frozen_W1"] - point[k], "ci95": [float(lo), float(hi)]}
    print(f"frozen_W1 minus {k}: {point['frozen_W1'] - point[k]:+.4f} [{lo:+.4f}, {hi:+.4f}]")
(root / "results" / "drift" / "check_same_counters.json").write_text(json.dumps(out, indent=2))
