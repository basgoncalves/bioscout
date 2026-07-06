"""Pure-numpy cylinder geometry (no OpenSim dependency).

Ported from the MATLAB helpers `eulerXYZToRotationMatrix` and
`projectPointOutsideCylinder`. The cylinder axis is the local Z axis, matching
OpenSim's WrapCylinder convention.
"""
from __future__ import annotations

import numpy as np


def euler_xyz_to_rotation_matrix(rx: float, ry: float, rz: float) -> np.ndarray:
    """XYZ body-fixed Euler angles (radians) -> 3x3 rotation matrix.

    Matches OpenSim's ``xyz_body_rotation`` convention for wrap objects:
    R = Rx @ Ry @ Rz.
    """
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)

    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rx @ Ry @ Rz


def radial_distance(pt_body: np.ndarray, R_cyl: np.ndarray, t_cyl: np.ndarray) -> float:
    """Radial distance of a point (in the wrap body's frame) from the cylinder axis."""
    pt_cyl = R_cyl.T @ (np.asarray(pt_body, float) - np.asarray(t_cyl, float))
    return float(np.hypot(pt_cyl[0], pt_cyl[1]))


def project_point_outside_cylinder(
    pt_body: np.ndarray,
    R_cyl: np.ndarray,
    t_cyl: np.ndarray,
    radius: float,
    margin: float,
):
    """Project a point (in the wrap body's frame) radially outside a cylinder.

    Returns ``(is_inside, pt_body_new, displacement_mm, r_point)``.
    If the point is already outside ``radius + margin`` it is returned unchanged.
    """
    pt_body = np.asarray(pt_body, float)
    t_cyl = np.asarray(t_cyl, float)

    pt_cyl = R_cyl.T @ (pt_body - t_cyl)
    r_point = float(np.hypot(pt_cyl[0], pt_cyl[1]))

    is_inside = r_point < (radius + margin)
    pt_body_new = pt_body.copy()
    displacement_mm = 0.0

    if is_inside:
        pt_cyl_new = pt_cyl.copy()
        if r_point < 1e-10:
            # On the axis: push out along local X by an arbitrary but valid direction.
            pt_cyl_new[0] = radius + margin
        else:
            scale = (radius + margin) / r_point
            pt_cyl_new[0] = pt_cyl[0] * scale
            pt_cyl_new[1] = pt_cyl[1] * scale
        pt_body_new = R_cyl @ pt_cyl_new + t_cyl
        displacement_mm = float(np.linalg.norm(pt_body_new - pt_body) * 1000.0)

    return is_inside, pt_body_new, displacement_mm, r_point
