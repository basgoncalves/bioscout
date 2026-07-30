"""Tests for the TPS wrapper.

No longer skipped when the third-party ``tps`` package is missing: the wrapper
falls back to the bundled pure-numpy backend, so these run everywhere.
"""
import numpy as np
import pandas as pd
import pytest

from bioscout.tps_personalise.tps import OneBodyTPS, _thin_plate_spline_class

tps_pkg = _thin_plate_spline_class()


def _cube_df():
    pts = np.array([
        [0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
        [1, 1, 0], [1, 0, 1], [0, 1, 1], [1, 1, 1],
    ], float)
    names = [f"m{i}" for i in range(len(pts))]
    return pd.DataFrame(pts, columns=["r", "a", "s"], index=names)


def test_identity_transform_recovers_points():
    df = _cube_df()
    tps = OneBodyTPS("pelvis", alpha=0.0).fit(df, df)
    out = tps.transform_points(df)
    assert np.allclose(out, df[["r", "a", "s"]].to_numpy(), atol=1e-6)


def test_translation_transform():
    src = _cube_df()
    tgt = src.copy()
    tgt[["r", "a", "s"]] += np.array([2.0, -1.0, 0.5])
    tps = OneBodyTPS("femur_r", alpha=0.0).fit(src, tgt)
    out = tps.transform_points(src)
    assert np.allclose(out, tgt[["r", "a", "s"]].to_numpy(), atol=1e-4)


def test_requires_fit_first():
    tps = OneBodyTPS("x")
    with pytest.raises(RuntimeError):
        tps.transform_points(np.zeros((3, 3)))


def test_too_few_landmarks_raises():
    df = _cube_df().iloc[:3]
    with pytest.raises(ValueError):
        OneBodyTPS("x").fit(df, df)


def test_shape_mismatch_raises():
    src = _cube_df()
    tgt = _cube_df().iloc[:-1]
    with pytest.raises(ValueError):
        OneBodyTPS("x").fit(src, tgt)
