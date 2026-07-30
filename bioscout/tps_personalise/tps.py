"""Thin-plate-spline transform for a single body.

Refactor of the original ``OneBodyTPS`` class. Key changes:
  * the ``tps`` dependency is imported lazily, so the package imports cleanly in
    a plain numpy/pandas environment (and tests can monkeypatch it),
  * no work in ``__init__`` beyond storing inputs; fitting is explicit via
    :meth:`fit`, transforms via the ``transform_*`` methods (no hidden side
    effects on construction),
  * accepts plain numpy arrays *or* DataFrames with ``['r','a','s']`` columns,
  * type hints + docstrings.

The spline is fit on **bone landmarks** (source = generic/scaled model space,
target = subject MRI space) and then applied to every other point set attached
to that body (muscle path points, skin markers, wrapping-surface points,
full bone meshes).
"""
from __future__ import annotations

from typing import Optional, Sequence

import numpy as np
import pandas as pd

Array = np.ndarray
_RAS = ["r", "a", "s"]


def _as_points(data) -> Array:
    """Return an (N,3) float array from an array-like or an r/a/s DataFrame."""
    if isinstance(data, pd.DataFrame):
        return data[_RAS].to_numpy(dtype=float)
    return np.asarray(data, dtype=float)


def _thin_plate_spline_class():
    """Return the TPS implementation to use.

    Prefers the ``thin-plate-spline`` package when installed (so results match
    anyone running the standalone tool), and otherwise falls back to the
    bundled pure-numpy implementation. The two are mathematically identical;
    the fallback exists so bioscout has no hard third-party TPS dependency.
    """
    try:
        from tps import ThinPlateSpline  # type: ignore
        return ThinPlateSpline
    except Exception:
        from ._tps_backend import ThinPlateSpline
        return ThinPlateSpline


class OneBodyTPS:
    """Fit a TPS on one body's bone landmarks and apply it to other point sets."""

    def __init__(self, body_name: str, alpha: float = 0.002):
        self.name = body_name
        self.alpha = alpha
        self._spline = None  # created on fit()

    # ------------------------------------------------------------------ fit
    def fit(
        self,
        source_bone,
        target_bone,
        exclude: Optional[Sequence[str]] = None,
    ) -> "OneBodyTPS":
        """Fit the spline mapping ``source_bone`` landmarks onto ``target_bone``.

        If DataFrames are passed, ``exclude`` may name index labels (markers) to
        leave out of the fit (e.g. unreliable landmarks); the index order of the
        two frames must correspond.
        """
        ThinPlateSpline = _thin_plate_spline_class()

        if isinstance(source_bone, pd.DataFrame) and exclude:
            include = [i for i in source_bone.index if i not in set(exclude)]
            src = source_bone.loc[include, _RAS].to_numpy(dtype=float)
            tgt = target_bone.loc[include, _RAS].to_numpy(dtype=float)
        else:
            src = _as_points(source_bone)
            tgt = _as_points(target_bone)

        if src.shape != tgt.shape:
            raise ValueError(
                f"[{self.name}] source/target landmark shapes differ: "
                f"{src.shape} vs {tgt.shape}"
            )
        if src.shape[0] < 4:
            raise ValueError(
                f"[{self.name}] need >=4 landmarks for a stable TPS, got {src.shape[0]}"
            )

        self._spline = ThinPlateSpline(alpha=self.alpha)
        self._spline.fit(src, tgt)
        return self

    @property
    def is_fitted(self) -> bool:
        return self._spline is not None

    def _check(self) -> None:
        if self._spline is None:
            raise RuntimeError(f"[{self.name}] call fit() before transforming")

    # -------------------------------------------------------------- transform
    def transform_points(self, points) -> Array:
        """Apply the fitted spline to an (N,3) array or r/a/s DataFrame."""
        self._check()
        return self._spline.transform(_as_points(points))

    def transform_surface(self, polydata):
        """Apply the spline to a ``pyvista.PolyData`` mesh, returning a new mesh."""
        self._check()
        import pyvista as pv  # lazy import
        pts = self._spline.transform(np.asarray(polydata.points))
        return pv.PolyData(pts, polydata.faces)

    def transform_wraps(self, wrap_df: pd.DataFrame):
        """Transform wrapping-surface defining points.

        ``wrap_df`` must have ``radius_point``, ``axis_point`` and
        ``translation`` columns (each an array-like of 3 floats). Returns
        ``[radius_points, axis_points, translations]`` after transformation.
        """
        self._check()
        n = len(wrap_df)
        stacked = np.concatenate([
            np.array([np.asarray(x, float) for x in wrap_df["radius_point"]]),
            np.array([np.asarray(x, float) for x in wrap_df["axis_point"]]),
            np.array([np.asarray(x, float) for x in wrap_df["translation"]]),
        ])
        out = self._spline.transform(stacked)
        radius, axis, translation = np.split(out, [n, 2 * n])
        return [radius, axis, translation]
