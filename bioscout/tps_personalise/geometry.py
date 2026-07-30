"""Pure geometric helpers (numpy only).

Ported from the original ``rotation_utils.py`` with no behavioural change, but:
  * no plotting code (moved out of the math layer),
  * no ``print`` side effects (callers get values / use logging),
  * docstrings and type hints,
  * an explicit, tested Kabsch implementation shared by the axis classes.

Every function here is dependency-light and covered by ``tests/test_geometry.py``.
"""
from __future__ import annotations

import math
from typing import Sequence, Tuple

import numpy as np

Array = np.ndarray


def rotation_matrix(axis: Sequence[float], theta: float) -> Array:
    """Rotation matrix for counter-clockwise rotation of ``theta`` radians
    about ``axis`` (Euler-Rodrigues). Identical to the original."""
    axis = np.asarray(axis, dtype=float)
    axis = axis / math.sqrt(np.dot(axis, axis))
    a = math.cos(theta / 2.0)
    b, c, d = -axis * math.sin(theta / 2.0)
    aa, bb, cc, dd = a * a, b * b, c * c, d * d
    bc, ad, ac, ab, bd, cd = b * c, a * d, a * c, a * b, b * d, c * d
    return np.array([
        [aa + bb - cc - dd, 2 * (bc + ad), 2 * (bd - ac)],
        [2 * (bc - ad), aa + cc - bb - dd, 2 * (cd + ab)],
        [2 * (bd + ac), 2 * (cd - ab), aa + dd - bb - cc],
    ])


def kabsch(source: Array, target: Array) -> Tuple[Array, Array]:
    """Best-fit rigid rotation+translation mapping ``source`` onto ``target``.

    Returns ``(R, t)`` such that ``(R @ source_centred.T).T + t ~= target``.
    Reflection-safe (determinant correction). This is the shared core that the
    original duplicated inside ``axes_rotation`` and ``TransformBodyToOsim``.
    """
    source = np.asarray(source, dtype=float)
    target = np.asarray(target, dtype=float)
    c_src = source.mean(axis=0)
    c_tgt = target.mean(axis=0)
    H = (source - c_src).T @ (target - c_tgt)
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:                 # reflection -> fix
        Vt[-1, :] *= -1
        R = Vt.T @ U.T
    t = c_tgt - R @ c_src
    return R, t


def axes_rotation(first: Array, second: Array):
    """Backwards-compatible wrapper around the original ``axes_rotation``.

    Returns ``(R, t, center_first, center_second)`` mapping ``second`` onto
    ``first`` (same signature/semantics as the original function)."""
    first = np.asarray(first, dtype=float)
    second = np.asarray(second, dtype=float)
    center_first = first.mean(axis=0)
    center_second = second.mean(axis=0)
    R, _ = kabsch(second, first)
    new_center_second = np.matmul(R, (second - center_second).T).mean(axis=1)
    t = -new_center_second + center_first
    return R, t, center_first, center_second


def rotate_about_centroid(data: Array, R: Array) -> Array:
    """Centre ``data`` on its centroid then rotate by ``R``."""
    data = np.asarray(data, dtype=float)
    return np.matmul(R, (data - data.mean(axis=0)).T).T


def plane_normal(p1: Array, p2: Array, p3: Array) -> Array:
    """Unit normal of the plane through three points (p2 is the vertex)."""
    v1 = np.asarray(p1) - np.asarray(p2)
    v2 = np.asarray(p3) - np.asarray(p2)
    n = np.cross(v1, v2)
    return n / np.linalg.norm(n)


def point_distance_to_vector(point: Array, vector: Array) -> float:
    """Perpendicular distance from ``point`` to the line through the origin
    along ``vector`` (the vector origin must already be subtracted from point)."""
    return float(np.linalg.norm(np.cross(point, vector)) / np.linalg.norm(vector))


def project_point_to_vector(point: Array, vector: Array) -> Array:
    """Orthogonal projection of ``point`` onto ``vector`` (origin-subtracted)."""
    point = np.asarray(point, dtype=float)
    vector = np.asarray(vector, dtype=float)
    cos_a = np.dot(point, vector) / (np.linalg.norm(point) * np.linalg.norm(vector))
    dist = cos_a * np.linalg.norm(point)
    return dist * vector / np.linalg.norm(vector)


def project_point_to_plane(point: Array, point_on_plane: Array, normal: Array) -> Array:
    """Project ``point`` onto the plane defined by a point and unit normal."""
    diff = np.asarray(point) - np.asarray(point_on_plane)
    return np.asarray(point) - (diff * normal) * normal


def rmse(a: Array, b: Array) -> float:
    """Root-mean-square error between two point sets of equal shape."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return float(np.sqrt(np.mean(np.square(a - b))))
