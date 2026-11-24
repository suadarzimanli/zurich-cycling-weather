"""Combine the network runs (mean over seeds 1-3) with the tree models and score everything.

Usage: python 12_forecast_scores.py <project_dir>
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from fc_common import score

root = Path(sys.argv[1])
res = root / "results" / "forecast"
runs = res / "runs"
ev = pd.read_parquet(res / "pred_trees.parquet")
training = {}

for kind in ("gwn", "rnn"):
    for v in ("wx", "nowx"):
        name = f"pred_{kind}_{v}"
        seeds = []
        for s in (1, 2, 3):
            meta = json.loads((runs / f"{name}_s{s}.json").read_text())
            arr = np.load(runs / f"{name}_s{s}.npy")
            training[f"{name}_s{s}"] = meta["info"]
            long = pd.DataFrame(arr, index=pd.to_datetime(meta["test_dates"]), columns=meta["nodes"]).stack()
            long = long.rename(f"{name}_s{s}").rename_axis(["date", "loc"]).reset_index()
            ev = ev.merge(long, on=["date", "loc"], how="left")
            seeds.append(f"{name}_s{s}")
        ev[name] = ev[seeds].mean(axis=1)

cols = [c for c in ev.columns if c.startswith("pred_")]
assert ev[cols].notna().all().all(), "missing predictions on the evaluation set"

scores = {}
for col in ("pred_lastweek", "pred_lgbm_wx", "pred_lgbm_nowx", "pred_gwn_wx", "pred_gwn_nowx", "pred_rnn_wx", "pred_rnn_nowx"):
    scores[col] = score(ev, col)
for v in ("wx", "nowx"):
    scores[f"graph_vs_nograph_{v}"] = score(ev, f"pred_gwn_{v}", base_col=f"pred_rnn_{v}")
    scores[f"graph_vs_lgbm_{v}"] = score(ev, f"pred_gwn_{v}", base_col=f"pred_lgbm_{v}")
    for k in ("gwn", "rnn"):
        for s in (1, 2, 3):
            scores[f"pred_{k}_{v}_s{s}"] = score(ev, f"pred_{k}_{v}_s{s}")
scores["training"] = training
ev.to_parquet(res / "pred_all.parquet", index=False)
(res / "scores_all.json").write_text(json.dumps(scores, indent=2))
tab = pd.DataFrame({k: v for k, v in scores.items() if k != "training"}).T[["mae", "mae_ratio", "dm_t", "dm_p"]]
print(tab.round(4).to_string())
print(pd.DataFrame(training).T.to_string())
