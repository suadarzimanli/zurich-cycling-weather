"""Graph WaveNet and the same-input RNN (no graph), two weather versions, seeds 1-3.

Settings from FORECAST_DETAILS_2026-11-24.md (including its addendum). One run per call,
so runs can go in parallel. Run with the torch312 environment.

Usage: python 11_forecast_gnn.py <project_dir> <gwn|rnn> <wx|nowx> <seed> <threads>
"""
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from tsl.nn.models import GraphWaveNetModel, RNNModel


root = Path(sys.argv[1])
KIND, WEATHER, SEED, THREADS = sys.argv[2], sys.argv[3] == "wx", int(sys.argv[4]), int(sys.argv[5])
fdir = root / "data" / "forecast"
runs = root / "results" / "forecast" / "runs"
runs.mkdir(parents=True, exist_ok=True)
torch.set_num_threads(THREADS)

WINDOW, BATCH, LR, MAX_EPOCHS, PATIENCE = 28, 32, 1e-3, 200, 20
TRAIN_END, VAL_END = pd.Timestamp("2025-04-30"), pd.Timestamp("2025-05-31")
START = pd.Timestamp("2022-01-01")

p = pd.read_parquet(fdir / "panel.parquet")
nodes = json.loads((fdir / "nodes.json").read_text())["test_nodes"]
p = p[p["loc"].isin(nodes) & (p["date"] >= START)]
dates = pd.date_range(START, p["date"].max(), freq="D")
N, T = len(nodes), len(dates)

Y = p.pivot(index="date", columns="loc", values="y").reindex(index=dates, columns=nodes)
L = np.log1p(Y.to_numpy())
M = ~np.isnan(L)
tr_rows = dates <= TRAIN_END
n_train = M[tr_rows].sum(axis=0)
# Deviation from the details file (documented): a location with fewer than 30 training
# days cannot be standardized on training data alone. For such locations the scaling
# uses all data before the test period (up to 31 May 2025). No test data is used.
pre_test = dates <= VAL_END
mu = np.where(n_train >= 30, np.nanmean(np.where(tr_rows[:, None], L, np.nan), axis=0),
              np.nanmean(np.where(pre_test[:, None], L, np.nan), axis=0))
sd = np.where(n_train >= 30, np.nanstd(np.where(tr_rows[:, None], L, np.nan), axis=0),
              np.nanstd(np.where(pre_test[:, None], L, np.nan), axis=0))
print("training days per location:", dict(zip(nodes, n_train.tolist())))
print("scaled with pre-test data instead of training data:", [n for n, k in zip(nodes, n_train) if k < 30])
Z = np.where(M, (L - mu) / sd, 0.0)
assert np.isfinite(mu).all() and np.isfinite(sd).all() and (sd > 0).all()

day = p.drop_duplicates("date").set_index("date").reindex(dates)
cal = [np.eye(7)[day["dow"].to_numpy().astype(int)],
       np.sin(2 * np.pi * day["month"].to_numpy()[:, None] / 12), np.cos(2 * np.pi * day["month"].to_numpy()[:, None] / 12),
       day[["public_holiday", "school_holiday", "sechselaeuten", "knabenschiessen"]].to_numpy()]
CAL = np.concatenate(cal, axis=1)
wx = day[["light", "wet", "tmax", "sun_h"]].to_numpy().astype(float)
wmu, wsd = np.nanmean(wx[tr_rows], axis=0), np.nanstd(wx[tr_rows], axis=0)
wmu[:2], wsd[:2] = 0, 1  # rain classes stay 0/1
WX = np.nan_to_num((wx - wmu) / wsd)
# covariates of the NEXT day, so the last input step carries the target day
U_cal = np.vstack([CAL[1:], CAL[-1:]])
U_wx = np.vstack([WX[1:], WX[-1:]])

# graph: Gaussian kernel on straight-line distance, 5 nearest neighbours per node
xy = p.drop_duplicates("loc").set_index("loc").loc[nodes, ["E", "N"]].to_numpy()
D = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1))
sigma = D[np.triu_indices(N, 1)].std()
src, dst, wts = [], [], []
for i in range(N):
    for j in np.argsort(D[i])[1:6]:
        src.append(j); dst.append(i); wts.append(np.exp(-(D[i, j] / sigma) ** 2))
edge_index = torch.tensor([src, dst])
edge_weight = torch.tensor(wts, dtype=torch.float32)

X = np.stack([Z, M.astype(float)], axis=-1)  # [T, N, 2]
assert np.isfinite(X).all() and np.isfinite(U_cal).all() and np.isfinite(U_wx).all()
targets = np.arange(WINDOW, T)
tdates = dates[targets]
split = {"train": targets[tdates <= TRAIN_END], "val": targets[(tdates > TRAIN_END) & (tdates <= VAL_END)],
         "test": targets[tdates > VAL_END]}
split["train"] = split["train"][M[split["train"]].any(axis=1)]
print("nodes", N, "| days", T, "| train/val/test targets", {k: len(v) for k, v in split.items()})

Xt = torch.tensor(X, dtype=torch.float32)
Zt = torch.tensor(Z, dtype=torch.float32)
Mt = torch.tensor(M)


def batch(idx, U):
    w = torch.stack([Xt[i - WINDOW:i] for i in idx])
    u = torch.stack([U[i - WINDOW:i] for i in idx])
    return w, u, Zt[idx].unsqueeze(-1), Mt[idx].unsqueeze(-1)


def run(kind, weather, seed):
    torch.manual_seed(seed)
    np.random.seed(seed)
    U = torch.tensor(np.concatenate([U_cal, U_wx], 1) if weather else U_cal, dtype=torch.float32)
    if kind == "gwn":
        model = GraphWaveNetModel(input_size=2, output_size=1, horizon=1, exog_size=U.shape[1], n_nodes=N,
                                  n_layers=5, dilation=2, dilation_mod=5, hidden_size=32, ff_size=64)
        assert model.receptive_field >= WINDOW
        fwd = lambda w, u: model(w, edge_index, edge_weight, u=u)
    else:
        model = RNNModel(input_size=2, output_size=1, horizon=1, exog_size=U.shape[1])
        fwd = lambda w, u: model(w, u=u)
    opt = torch.optim.Adam(model.parameters(), lr=LR)

    def masked_mae(idx):
        model.eval()
        with torch.no_grad():
            w, u, y, m = batch(idx, U)
            yh = fwd(w, u)[:, 0]
            return (yh - y).abs()[m].mean().item(), yh[..., 0].numpy()

    best, best_state, bad = np.inf, None, 0
    for ep in range(MAX_EPOCHS):
        model.train()
        perm = np.random.permutation(split["train"])
        for k in range(0, len(perm), BATCH):
            w, u, y, m = batch(perm[k:k + BATCH], U)
            yh = fwd(w, u)[:, 0]
            loss = (yh - y).abs()[m].mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
        v, _ = masked_mae(split["val"])
        if not np.isfinite(v):
            raise RuntimeError(f"non-finite validation loss at epoch {ep}")
        if v < best - 1e-6:
            best, best_state, bad = v, copy.deepcopy(model.state_dict()), 0
        else:
            bad += 1
            if bad >= PATIENCE:
                break
        if ep % 10 == 0:
            print(f"epoch {ep} val {v:.4f} best {best:.4f} [{time.time() - t0:.0f}s]", flush=True)
    model.load_state_dict(best_state)
    _, zh = masked_mae(split["test"])
    pred = np.expm1(zh * sd + mu)  # [test days, N]
    return pred, {"val_mae_scaled": best, "epochs": ep + 1}


t0 = time.time()
name = f"pred_{KIND}_{'wx' if WEATHER else 'nowx'}_s{SEED}"
pred, info = run(KIND, WEATHER, SEED)
info["seconds"] = round(time.time() - t0)
np.save(runs / f"{name}.npy", pred)
meta = {"name": name, "info": info, "nodes": nodes, "test_dates": [str(d.date()) for d in dates[split["test"]]]}
(runs / f"{name}.json").write_text(json.dumps(meta, indent=2))
print("done", name, info, flush=True)
