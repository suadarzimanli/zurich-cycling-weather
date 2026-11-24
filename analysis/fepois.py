"""Poisson regression with one high-dimensional fixed effect, concentrated out.

For a given beta, the group effect has the closed form
    alpha_g = log(sum_g y) - log(sum_g exp(x'beta)),
so only beta is solved by Newton steps. Standard errors are cluster-robust,
using the regressors after removing their mu-weighted group means
(the effective score for beta), with a G/(G-1) correction.
"""
import numpy as np
import pandas as pd


def _group_sum(codes, w, n_groups):
    return np.bincount(codes, weights=w, minlength=n_groups)


def fepois(y, X, groups, clusters, names=None, maxit=50, tol=1e-9):
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    groups = pd.factorize(np.asarray(groups))[0]
    clusters = np.asarray(clusters)

    # groups where every outcome is zero carry no information
    gy = _group_sum(groups, y, groups.max() + 1)
    keep = gy[groups] > 0
    y, X, clusters = y[keep], X[keep], clusters[keep]
    g = pd.factorize(groups[keep])[0]
    cl = pd.factorize(clusters)[0]
    n, k = X.shape
    G = g.max() + 1
    sy = _group_sum(g, y, G)

    # drop regressors with no variation inside any group
    def within_var(col):
        m = _group_sum(g, col, G) / np.bincount(g, minlength=G)
        return np.abs(col - m[g]).max()
    ok = np.array([within_var(X[:, j]) > 1e-12 for j in range(k)])
    dropped = [names[j] if names is not None else j for j in range(k) if not ok[j]]
    X = X[:, ok]
    names = [nm for nm, o in zip(names, ok) if o] if names is not None else None
    k = X.shape[1]

    def mu_ll(beta):
        eta = X @ beta
        mx = np.full(G, -np.inf)
        np.maximum.at(mx, g, eta)
        e = np.exp(eta - mx[g])
        se = _group_sum(g, e, G)
        logmu = (eta - mx[g]) - np.log(se)[g] + np.log(sy)[g]
        mu = np.exp(logmu)
        ll = np.sum(y * logmu - mu)
        return mu, ll

    beta = np.zeros(k)
    mu, ll = mu_ll(beta)
    for it in range(maxit):
        sm = _group_sum(g, mu, G)
        xbar = np.column_stack([_group_sum(g, mu * X[:, j], G) for j in range(k)]) / sm[:, None]
        Xt = X - xbar[g]
        grad = Xt.T @ (y - mu)
        H = (Xt * mu[:, None]).T @ Xt
        step = np.linalg.solve(H, grad)
        t = 1.0
        while True:
            mu_new, ll_new = mu_ll(beta + t * step)
            if ll_new >= ll - 1e-12 or t < 1e-6:
                break
            t /= 2
        beta = beta + t * step
        mu, ll_change = mu_new, ll_new - ll
        ll = ll_new
        if np.max(np.abs(t * step)) < tol:
            break
    else:
        raise RuntimeError("fepois did not converge")

    sm = _group_sum(g, mu, G)
    xbar = np.column_stack([_group_sum(g, mu * X[:, j], G) for j in range(k)]) / sm[:, None]
    Xt = X - xbar[g]
    H = (Xt * mu[:, None]).T @ Xt
    Hinv = np.linalg.inv(H)
    s = Xt * (y - mu)[:, None]
    C = cl.max() + 1
    S = np.column_stack([_group_sum(cl, s[:, j], C) for j in range(k)])
    V = Hinv @ (S.T @ S) @ Hinv * C / (C - 1)
    return {
        "beta": pd.Series(beta, index=names),
        "vcov": pd.DataFrame(V, index=names, columns=names),
        "n": n, "groups": G, "clusters": C, "iterations": it + 1, "dropped": dropped,
        "vcov_raw": pd.DataFrame(Hinv @ (S.T @ S) @ Hinv, index=names, columns=names),
    }
