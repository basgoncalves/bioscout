"""Tests for pure geometry helpers (numpy only — no opensim/tps needed)."""
import numpy as np
import pytest

from bioscout.tps_personalise import geometry as g


def test_rotation_matrix_is_orthonormal():
    R = g.rotation_matrix([0, 0, 1], np.pi / 3)
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-12)
    assert np.isclose(np.linalg.det(R), 1.0)


def test_rotation_matrix_90deg_about_z():
    R = g.rotation_matrix([0, 0, 1], np.pi / 2)
    assert np.allclose(R @ np.array([1, 0, 0]), [0, 1, 0], atol=1e-12)


def test_kabsch_recovers_known_rotation_and_translation():
    rng = np.random.default_rng(0)
    src = rng.normal(size=(10, 3))
    R_true = g.rotation_matrix([1, 2, 3], 0.7)
    t_true = np.array([5.0, -2.0, 1.0])
    tgt = (R_true @ src.T).T + t_true
    R, t = g.kabsch(src, tgt)
    assert np.allclose(R, R_true, atol=1e-9)
    assert np.allclose(t, t_true, atol=1e-9)
    assert np.allclose((R @ src.T).T + t, tgt, atol=1e-9)


def test_kabsch_is_reflection_safe():
    # a degenerate/near-reflection case should still return a proper rotation
    src = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], float)
    tgt = src[:, [1, 0, 2]]  # swap x,y -> reflection-ish
    R, _ = g.kabsch(src, tgt)
    assert np.isclose(np.linalg.det(R), 1.0, atol=1e-9)


def test_plane_normal_unit_and_perpendicular():
    n = g.plane_normal([1, 0, 0], [0, 0, 0], [0, 1, 0])
    assert np.isclose(np.linalg.norm(n), 1.0)
    assert np.allclose(np.abs(n), [0, 0, 1])


def test_point_distance_to_vector():
    d = g.point_distance_to_vector(np.array([0, 3, 0]), np.array([1, 0, 0]))
    assert np.isclose(d, 3.0)


def test_project_point_to_vector():
    p = g.project_point_to_vector(np.array([2, 3, 0]), np.array([1, 0, 0]))
    assert np.allclose(p, [2, 0, 0])


def test_rmse_zero_for_identical():
    a = np.arange(9).reshape(3, 3).astype(float)
    assert g.rmse(a, a) == 0.0


def test_axes_rotation_signature_backcompat():
    src = np.eye(3) * 10
    tgt = src + 5
    R, t, cf, cs = g.axes_rotation(tgt, src)  # map src onto tgt(=first)
    assert R.shape == (3, 3)
    assert t.shape == (3,)
