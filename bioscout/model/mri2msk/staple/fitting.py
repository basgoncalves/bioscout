"""Fitting routines from GIBOC-core/SubFunctions/FittingFun (+ LSGE lsplane)."""
from __future__ import annotations

import warnings

import numpy as np
from scipy.optimize import curve_fit


def sphere_fit(X):
    """Algebraic sphere fit (sphereFit.m). Returns centre (3,), radius, error dist."""
    X = np.asarray(X, float)
    m = X.mean(axis=0)
    Xc = X - m
    A = np.array([
        [np.mean(X[:, 0] * Xc[:, 0]), 2 * np.mean(X[:, 0] * Xc[:, 1]), 2 * np.mean(X[:, 0] * Xc[:, 2])],
        [0, np.mean(X[:, 1] * Xc[:, 1]), 2 * np.mean(X[:, 1] * Xc[:, 2])],
        [0, 0, np.mean(X[:, 2] * Xc[:, 2])],
    ])
    A = A + A.T
    sq = np.sum(X ** 2, axis=1)
    B = np.array([np.mean(sq * Xc[:, i]) for i in range(3)])
    c = np.linalg.solve(A, B)
    d2 = np.sum((X - c) ** 2, axis=1)
    r = np.sqrt(np.mean(d2))
    return c, r, d2 - r ** 2


def ellipsoid_fit(X):
    """Unconstrained ellipsoid fit (ellipsoid_fit.m, equals='')."""
    x, y, z = X[:, 0], X[:, 1], X[:, 2]
    D = np.column_stack([x * x + y * y - 2 * z * z, x * x + z * z - 2 * y * y,
                         2 * x * y, 2 * x * z, 2 * y * z, 2 * x, 2 * y, 2 * z, np.ones_like(x)])
    d2 = x * x + y * y + z * z
    u = np.linalg.solve(D.T @ D, D.T @ d2)
    v = np.zeros(10)
    v[0] = u[0] + u[1] - 1
    v[1] = u[0] - 2 * u[1] - 1
    v[2] = u[1] - 2 * u[0] - 1
    v[3:] = u[2:]
    A = np.array([[v[0], v[3], v[4], v[6]], [v[3], v[1], v[5], v[7]],
                  [v[4], v[5], v[2], v[8]], [v[6], v[7], v[8], v[9]]])
    center = -np.linalg.solve(A[:3, :3], v[6:9])
    T = np.eye(4)
    T[3, :3] = center
    R = T @ A @ T.T
    evals, evecs = np.linalg.eig(R[:3, :3] / -R[3, 3])
    radii = np.sqrt(1 / np.abs(evals)) * np.sign(evals)
    return center, radii, evecs


def fit_ellipse(x, y):
    """Least-squares ellipse fit (fit_ellipse.m by O. Gal). Returns a dict."""
    tol = 1e-3
    x = np.asarray(x, float).ravel()
    y = np.asarray(y, float).ravel()
    mx, my = x.mean(), y.mean()
    x = x - mx
    y = y - my
    X = np.column_stack([x ** 2, x * y, y ** 2, x, y])
    a, b, c, d, e = np.linalg.solve((X.T @ X).T, X.sum(axis=0))
    if min(abs(b / a), abs(b / c)) > tol:
        phi = 0.5 * np.arctan(b / (c - a))
        cp, sp = np.cos(phi), np.sin(phi)
        a, b, c, d, e = (a * cp ** 2 - b * cp * sp + c * sp ** 2, 0.0,
                         a * sp ** 2 + b * cp * sp + c * cp ** 2,
                         d * cp - e * sp, d * sp + e * cp)
        mx, my = cp * mx - sp * my, sp * mx + cp * my
    else:
        phi = 0.0
        cp, sp = 1.0, 0.0
    if a * c <= 0:
        raise RuntimeError("fit_ellipse: did not locate an ellipse")
    if a < 0:
        a, c, d, e = -a, -c, -d, -e
    X0 = mx - d / 2 / a
    Y0 = my - e / 2 / c
    F = 1 + d ** 2 / (4 * a) + e ** 2 / (4 * c)
    a, b = np.sqrt(F / a), np.sqrt(F / c)
    R = np.array([[cp, sp], [-sp, cp]])
    X0_in, Y0_in = R @ np.array([X0, Y0])
    th = np.linspace(0, 2 * np.pi, 1000)
    data = R @ np.vstack([X0 + a * np.cos(th), Y0 + b * np.sin(th)])
    return dict(a=a, b=b, phi=phi, X0=X0, Y0=Y0, X0_in=X0_in, Y0_in=Y0_in,
                long_axis=2 * max(a, b), short_axis=2 * min(a, b), data=data)


def lsplane(X):
    """Least-squares plane: (centroid (3,), unit normal (3,))."""
    x0 = X.mean(axis=0)
    _, S, Vt = np.linalg.svd(X - x0, full_matrices=False)
    return x0, Vt[np.argmin(S)]


def _gauss2(x, a1, b1, c1, a2, b2, c2):
    return a1 * np.exp(-((x - b1) / c1) ** 2) + a2 * np.exp(-((x - b2) / c2) ** 2)


def _gauss_lin(x, a1, b1, c1, d, e):
    return a1 * np.exp(-((x - b1) / c1) ** 2) + d * x + e


def fit_csa(Z, Area):
    """fitCSA.m: locate diaphysis/epiphysis transition from cross-section areas."""
    Z = np.asarray(Z, float)
    Area = np.asarray(Area, float)
    Z0 = Z.mean()
    Z = Z - Z0
    Area = Area / Area.mean()
    imax = int(np.argmax(Area))
    AreaMax = Area[imax]
    orient = -1 if Z[imax] < Z.mean() else 1
    p0 = [AreaMax, Z[imax], 20, Area.mean(), Z.mean(), 75]
    lb = [-np.inf, -np.inf, 0, -np.inf, -np.inf, 0]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        p1, _ = curve_fit(_gauss2, Z, Area, p0=p0, bounds=(lb, np.inf), maxfev=20000)
        p2, _ = curve_fit(_gauss_lin, Z, Area, p0=[p1[0], p1[1], p1[2], 0, Z.mean()], maxfev=20000)
    a1, b1, c1, d, e = p2
    c1 = abs(c1)  # c enters squared; MATLAB may return either sign
    dist2lin = Area - (d * Z + e)
    Zkept = Z[np.abs(dist2lin) < abs(0.1 * np.median(Area))][2:-2]
    z_start_dia = Zkept.max() if orient == -1 else Zkept.min()
    z_end_dia = b1 - 3 * orient * c1
    z_epi = Z0 + b1 - 1.5 * orient * c1
    return Z0 + np.array([z_start_dia, z_end_dia]), z_epi, orient
