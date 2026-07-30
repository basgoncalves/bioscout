"""Pure-numpy thin-plate-spline, used when the ``thin-plate-spline`` package is absent.

The original package depended on ``thin-plate-spline`` (import name ``tps``) for a
single class with two methods. That is a hard pip dependency for ~40 lines of
linear algebra, and it is not always installable in the locked-down conda envs
these simulations run in. This module reimplements it exactly so
``bioscout.tps_personalise`` has no third-party TPS dependency at all; the
external package is still preferred when installed, so results are unchanged for
anyone who already has it.

Formulation (standard 3-D TPS, identical to the upstream package):

    K_ij = ||x_i - x_j||                      (U(r) = r is the 3-D kernel)
    [K + alpha*I   P] [W]   [Y]
    [P^T           0] [A] = [0]  ,  P = [1 | X]

    f(x) = [1 | x] A + U(||x - X||) W
"""
from __future__ import annotations

import numpy as np

__all__ = ["ThinPlateSpline"]


def _cdist(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Pairwise Euclidean distances without a scipy dependency."""
    diff = a[:, None, :] - b[None, :, :]
    return np.sqrt(np.einsum("ijk,ijk->ij", diff, diff))


class ThinPlateSpline:
    """Drop-in replacement for ``tps.ThinPlateSpline``.

    Parameters
    ----------
    alpha : float
        Ridge regularisation added to the kernel diagonal. ``0`` interpolates
        the landmarks exactly; larger values smooth the warp. The project
        default (0.002) comes from the original notebooks.
    """

    def __init__(self, alpha: float = 0.0):
        self.alpha = float(alpha)
        self.control_points: np.ndarray | None = None
        self.parameters: np.ndarray | None = None

    # ------------------------------------------------------------------ fit
    def fit(self, X: np.ndarray, Y: np.ndarray) -> "ThinPlateSpline":
        X = np.asarray(X, dtype=float)
        Y = np.asarray(Y, dtype=float)
        if X.ndim != 2 or Y.ndim != 2:
            raise ValueError("X and Y must be 2-D (n_points, n_dims)")
        if X.shape[0] != Y.shape[0]:
            raise ValueError(
                f"X and Y must have the same number of points, got "
                f"{X.shape[0]} and {Y.shape[0]}"
            )
        n, d = X.shape

        K = _cdist(X, X)
        if self.alpha:
            K = K + self.alpha * np.eye(n)
        P = np.hstack([np.ones((n, 1)), X])                   # (n, d+1)

        A = np.zeros((n + d + 1, n + d + 1))
        A[:n, :n] = K
        A[:n, n:] = P
        A[n:, :n] = P.T

        b = np.zeros((n + d + 1, Y.shape[1]))
        b[:n] = Y

        # lstsq (not solve) so a rank-deficient landmark set degrades to the
        # least-squares warp instead of raising LinAlgError.
        self.parameters = np.linalg.lstsq(A, b, rcond=None)[0]
        self.control_points = X
        return self

    # ------------------------------------------------------------ transform
    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.parameters is None or self.control_points is None:
            raise RuntimeError("fit() must be called before transform()")
        X = np.asarray(X, dtype=float)
        n_c = self.control_points.shape[0]
        K = _cdist(X, self.control_points)
        P = np.hstack([np.ones((X.shape[0], 1)), X])
        return K @ self.parameters[:n_c] + P @ self.parameters[n_c:]
