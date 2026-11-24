"""Poisson regression with two fixed effects nested in locations, shared ("global")
regressors and location-specific ("local") regressors. Built for large panels.

Model: log E[y] = fe1 + fe2 + G b + L_loc c_loc, where fe1 and fe2 are fixed effects whose
groups lie inside one location (for example counter x month and location x weekday).
Estimated by IRLS (as in ppmlhdfe). At each step the working variable and the regressors
are demeaned within each location by weighted alternating projections over fe1 and fe2,
and the local coefficients are concentrated out with a Schur complement.
Standard errors for b are cluster-robust with a G/(G-1) correction, using the regressors
after removing fixed effects and local regressors (Frisch-Waugh).
"""
import numpy as np
import pandas as pd
import scipy.sparse as sp


def _drop_zero_groups(y, *codes):
    keep = np.ones(len(y), bool)
    while True:
        changed = False
        for c in codes:
            s = np.bincount(c[keep], weights=y[keep], minlength=c.max() + 1)
            bad = keep & (s[c] <= 0)
            if bad.any():
                keep &= ~bad
                changed = True
        if not changed:
            return keep


class _Block:
    def __init__(self, idx, f1, f2):
        self.idx = idx
        a = pd.factorize(f1)[0]
        b = pd.factorize(f2)[0]
        n = len(idx)
        self.D1 = sp.csr_matrix((np.ones(n), (np.arange(n), a)), shape=(n, a.max() + 1))
        self.D2 = sp.csr_matrix((np.ones(n), (np.arange(n), b)), shape=(n, b.max() + 1))

    def demean(self, w, M, tol=1e-11, maxit=10000):
        M = M.copy()
        s1 = self.D1.T @ w
        s2 = self.D2.T @ w
        for _ in range(maxit):
            m1 = (self.D1.T @ (w[:, None] * M)) / s1[:, None]
            M -= self.D1 @ m1
            m2 = (self.D2.T @ (w[:, None] * M)) / s2[:, None]
            M -= self.D2 @ m2
            if np.abs(m2).max() < tol:
                return M
        raise RuntimeError("demeaning did not converge")


def blockpois(y, G, L, loc, fe1, fe2, clusters, names=None, maxit=200, tol=1e-10):
    y = np.asarray(y, float)
    G = np.asarray(G, float)
    L = None if L is None else np.asarray(L, float)
    loc = np.asarray(loc)
    c1 = pd.factorize(pd.Series(loc).astype(str) + "|" + pd.Series(np.asarray(fe1)).astype(str))[0]
    c2 = pd.factorize(pd.Series(loc).astype(str) + "|" + pd.Series(np.asarray(fe2)).astype(str))[0]
    keep = _drop_zero_groups(y, c1, c2)
    y, G, loc, c1, c2 = y[keep], G[keep], loc[keep], c1[keep], c2[keep]
    L = None if L is None else L[keep]
    cl = pd.factorize(np.asarray(clusters)[keep])[0]
    n, kg = G.shape
    kl = 0 if L is None else L.shape[1]
    lc = pd.factorize(loc)[0]
    order = np.argsort(lc, kind="stable")
    bounds = np.searchsorted(lc[order], np.arange(lc.max() + 2))
    blocks = [_Block(order[bounds[i]:bounds[i + 1]], c1[order[bounds[i]:bounds[i + 1]]], c2[order[bounds[i]:bounds[i + 1]]])
              for i in range(lc.max() + 1)]

    ybar = np.array([y[b.idx].mean() for b in blocks])
    mu = (y + ybar[lc]) / 2
    eta = np.log(mu)
    dev_old = np.inf
    bg = np.zeros(kg)

    def solve_step(w, z):
        S = np.zeros((kg, kg))
        r = np.zeros(kg)
        store = []
        for b in blocks:
            i = b.idx
            cols = [z[i, None], G[i]] + ([L[i]] if kl else [])
            Mt = b.demean(w[i], np.hstack(cols))
            zt, Gt = Mt[:, 0], Mt[:, 1:1 + kg]
            Lt = Mt[:, 1 + kg:] if kl else None
            wi = w[i]
            S += (Gt * wi[:, None]).T @ Gt
            r += (Gt * wi[:, None]).T @ zt
            if kl:
                A = (Lt * wi[:, None]).T @ Lt
                B = (Gt * wi[:, None]).T @ Lt
                c = (Lt * wi[:, None]).T @ zt
                Ainv = np.linalg.pinv(A)
                S -= B @ Ainv @ B.T
                r -= B @ Ainv @ c
                store.append((Ainv, B, c))
            else:
                store.append(None)
            b.zt, b.Gt, b.Lt = zt, Gt, Lt
        return S, r, store

    for it in range(maxit):
        z = eta + (y - mu) / mu
        w = mu
        S, r, store = solve_step(w, z)
        bg = np.linalg.solve(S, r)
        e = np.empty(n)
        for b, st in zip(blocks, store):
            res = b.zt - b.Gt @ bg
            if kl:
                Ainv, B, c = st
                bl = Ainv @ (c - B.T @ bg)
                res -= b.Lt @ bl
            e[b.idx] = res
        eta = z - e
        mu = np.exp(eta)
        with np.errstate(divide="ignore", invalid="ignore"):
            dev = 2 * np.sum(np.where(y > 0, y * np.log(y / mu), 0) - (y - mu))
        if abs(dev_old - dev) / max(abs(dev), 0.1) < tol:
            break
        dev_old = dev
    else:
        raise RuntimeError("IRLS did not converge")

    # variance with the final weights
    w = mu
    S, _, store = solve_step(w, np.zeros(n))
    C = cl.max() + 1
    scores = np.zeros((C, kg))
    for b, st in zip(blocks, store):
        Gb = b.Gt
        if kl:
            Ainv, B, _ = st
            Gb = Gb - b.Lt @ (Ainv @ B.T)
        s = Gb * (y[b.idx] - mu[b.idx])[:, None]
        np.add.at(scores, cl[b.idx], s)
    Sinv = np.linalg.inv(S)
    V = Sinv @ (scores.T @ scores) @ Sinv * C / (C - 1)
    names = names if names is not None else list(range(kg))
    return {"beta": pd.Series(bg, index=names), "vcov": pd.DataFrame(V, index=names, columns=names),
            "n": n, "clusters": C, "locations": len(blocks), "iterations": it + 1, "deviance": dev}
