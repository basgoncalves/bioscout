"""Mesh I/O and pure-numpy transform helpers (no OpenSim dependency).

Port of the helper functions at the bottom of MRI2MSK.m.

Conventions kept from MATLAB:
* Vertex arrays are (N, 3) row vectors. MATLAB's ``V * R`` (rows times R) is
  therefore ``V @ R`` here.
* Single points/vectors passed to :func:`apply_transform` are 1-D (3,) arrays and
  are rotated as column vectors, i.e. ``R @ v`` (MATLAB ``R*v``).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import ConvexHull
from scipy.spatial.distance import pdist


# --------------------------------------------------------------------------- STL I/O
def load_stl(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Return (vertices (N,3), faces (M,3)) of an STL. Replaces GIBBON import_STL."""
    mesh = trimesh.load_mesh(str(path), process=False)
    return np.asarray(mesh.vertices, dtype=float), np.asarray(mesh.faces, dtype=int)


def save_stl(path: str | Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Write a binary STL. Replaces MATLAB stlwrite(triangulation(...))."""
    trimesh.Trimesh(vertices=vertices, faces=faces, process=False).export(str(path))


def max_extent(vertices: np.ndarray) -> float:
    """Largest pairwise distance between vertices (MATLAB ``max(pdist(V))``).

    Computed on the convex hull, which gives the exact same maximum but avoids the
    O(N^2) memory of a full pdist on a dense MRI mesh.
    """
    try:
        hull = vertices[ConvexHull(vertices).vertices]
    except Exception:  # degenerate geometry - fall back to brute force
        hull = vertices
    return float(pdist(hull).max())


def max_extent_subsampled(vertices: np.ndarray, n: int = 10000) -> float:
    """Mirror of MATLAB ``pdist(V(floor(1:size(V,1)/10000:end),:))``.

    The MATLAB code subsamples to ~10k vertices before pdist. The exact hull method
    is used here because it is both faster and not approximate; the result may
    differ from the MATLAB value by a fraction of a percent.
    """
    return max_extent(vertices)


def downsample_mesh(vertices: np.ndarray, faces: np.ndarray, n_vertices: int = 10000):
    """Quadric decimation to ~n_vertices (MATLAB ``reducepatch``).

    Uses trimesh's ``simplify_quadric_decimation`` (needs ``fast-simplification``).
    The target is expressed in faces (~2x vertices for a closed mesh).
    """
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.merge_vertices()  # STL stores 3 vertices per face; weld them first
    if len(mesh.vertices) <= n_vertices:
        return np.asarray(mesh.vertices), np.asarray(mesh.faces)
    target_faces = int(2 * n_vertices)
    simplified = mesh.simplify_quadric_decimation(face_count=target_faces)
    return np.asarray(simplified.vertices), np.asarray(simplified.faces)


# --------------------------------------------------------------------------- rotations
def rotation_y(theta: float) -> np.ndarray:
    """Rotation about the Y (long) axis, radians."""
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]])


def rotation_xyz_body(rx: float, ry: float, rz: float) -> np.ndarray:
    """Body-fixed XYZ rotation as used by OpenSim wrap objects (Rx @ Ry @ Rz)."""
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rx @ Ry @ Rz


def xyz_body_from_matrix(R: np.ndarray) -> tuple[float, float, float]:
    """Inverse of :func:`rotation_xyz_body` (same formulas as the MATLAB code)."""
    ry = float(np.arcsin(np.clip(R[0, 2], -1.0, 1.0)))
    rx = float(np.arctan2(-R[1, 2], R[2, 2]))
    rz = float(np.arctan2(-R[0, 1], R[0, 0]))
    return rx, ry, rz


def apply_transform(v, R: np.ndarray, pivot, restore_translation: bool) -> np.ndarray:
    """``R @ (v - pivot)`` (+ pivot if ``restore_translation``)."""
    v = np.asarray(v, dtype=float).reshape(3)
    pivot = np.asarray(pivot, dtype=float).reshape(3)
    out = R @ (v - pivot)
    return out + pivot if restore_translation else out


def calc_angle_2d(u, v) -> float:
    """Signed angle (deg) from 2-D vector u to v."""
    u = np.asarray(u, float) / np.linalg.norm(u)
    v = np.asarray(v, float) / np.linalg.norm(v)
    cross_z = u[0] * v[1] - u[1] * v[0]
    return float(np.degrees(np.arctan2(cross_z, np.dot(u, v))))


# --------------------------------------------------------------------------- OBJ files
def rotate_obj_file(input_file, output_file, R, pivot, restore_translation: bool) -> None:
    """Rotate vertices ('v') and normals ('vn') of a Wavefront OBJ; copy other lines."""
    pivot = np.asarray(pivot, float).reshape(3)
    with open(input_file, "r") as fin, open(output_file, "w") as fout:
        for line in fin:
            stripped = line.strip()
            if stripped.startswith("v "):
                vals = np.array(stripped.split()[1:4], dtype=float)
                n = apply_transform(vals, R, pivot, restore_translation)
                fout.write(f"v {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
            elif stripped.startswith("vn "):
                try:
                    vals = np.array(stripped.split()[1:4], dtype=float)
                except ValueError:
                    continue
                if vals.size == 3 and not np.isnan(vals).any():
                    n = R @ vals
                    fout.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")
            else:
                fout.write(line.rstrip("\n") + "\n")
