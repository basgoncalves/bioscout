"""Automatic landmark generation for the OpenSim Creator Mesh Warper.

Idea: after step 1 the participant bone is already in the OpenSim frame and
scaled to the base bone, so both meshes almost overlap. We

1. pick ``n`` well-spread landmarks on the base mesh (farthest-point sampling),
2. register base -> participant with Coherent Point Drift (affine, then
   non-rigid; Myronenko & Song 2010),
3. push the base landmarks through that deformation and snap them onto the
   participant surface,
4. write ``base_<bone>.csv`` / ``participant_<bone>.csv`` in the Mesh Warper
   format (``name,x,y,z``).

Pure numpy/scipy, no extra dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from . import geometry as geo


# =========================================================================== CSV I/O
def read_landmarks_csv(path) -> tuple[list[str], np.ndarray]:
    names, pts = [], []
    for line in Path(path).read_text().splitlines()[1:]:
        if line.strip():
            n, x, y, z = line.split(",")[:4]
            names.append(n.strip())
            pts.append([float(x), float(y), float(z)])
    return names, np.array(pts)


def write_landmarks_csv(path, names, pts) -> None:
    lines = ["name,x,y,z"] + [f"{n},{p[0]:.6f},{p[1]:.6f},{p[2]:.6f}" for n, p in zip(names, pts)]
    Path(path).write_text("\n".join(lines) + "\n")


# =========================================================================== sampling
def mesh_points(vertices, faces, n, seed=0):
    """Area-uniform random surface samples (deterministic seed)."""
    rng = np.random.default_rng(seed)
    v0, v1, v2 = vertices[faces[:, 0]], vertices[faces[:, 1]], vertices[faces[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    idx = rng.choice(len(faces), size=n, p=area / area.sum())
    r1, r2 = rng.random(n), rng.random(n)
    s = np.sqrt(r1)
    return (1 - s)[:, None] * v0[idx] + (s * (1 - r2))[:, None] * v1[idx] + (s * r2)[:, None] * v2[idx]


def farthest_point_sampling(pts, n):
    """``n`` well-spread points; starts at the point farthest from the centroid."""
    pts = np.asarray(pts, float)
    n = min(n, len(pts))
    sel = [int(np.argmax(np.linalg.norm(pts - pts.mean(0), axis=1)))]
    d = np.linalg.norm(pts - pts[sel[0]], axis=1)
    for _ in range(n - 1):
        i = int(np.argmax(d))
        sel.append(i)
        d = np.minimum(d, np.linalg.norm(pts - pts[i], axis=1))
    return np.array(sel)


# =========================================================================== CPD
def _sigma2(X, Y):
    D, M = X.shape[0], Y.shape[0]
    return np.sum((X[None] - Y[:, None]) ** 2) / (D * M * 3) if D * M < 4e6 else \
        np.mean(np.sum((X[np.random.default_rng(0).choice(D, 2000)][None] -
                        Y[np.random.default_rng(1).choice(M, 2000)][:, None]) ** 2, -1)) / 3


def _estep(X, TY, s2, w):
    """Posterior P (M,N) of GMM centroids TY generating points X."""
    M, N = TY.shape[0], X.shape[0]
    d2 = np.sum((X[None, :, :] - TY[:, None, :]) ** 2, axis=2)
    P = np.exp(-d2 / (2 * s2))
    c = (2 * np.pi * s2) ** 1.5 * w / (1 - w) * M / N
    den = P.sum(0, keepdims=True) + c
    return P / np.maximum(den, 1e-300)


def cpd_affine(X, Y, w=0.1, iters=60, tol=1e-6):
    """Affine CPD. Returns (B (3,3), t (3,)) so that Y -> Y @ B.T + t."""
    B, t = np.eye(3), np.zeros(3)
    s2 = _sigma2(X, Y)
    for _ in range(iters):
        TY = Y @ B.T + t
        P = _estep(X, TY, s2, w)
        Np = P.sum()
        mux = (P.sum(0) @ X) / Np
        muy = (P.sum(1) @ Y) / Np
        Xh, Yh = X - mux, Y - muy
        A = Xh.T @ P.T @ Yh
        YPY = (Yh * P.sum(1)[:, None]).T @ Yh
        B = A @ np.linalg.inv(YPY)
        t = mux - B @ muy
        s2_old = s2
        s2 = (np.sum(P.sum(0) * np.sum(Xh * Xh, 1)) - np.trace(A @ B.T)) / (Np * 3)
        s2 = max(s2, 1e-10)
        if abs(s2_old - s2) < tol:
            break
    return B, t


def cpd_deformable(X, Y, beta=2.0, lam=2.0, w=0.1, iters=80, tol=1e-6):
    """Non-rigid CPD (motion coherence). Returns (W (M,3), beta) with
    T(Y) = Y + G(Y,Y) W, G = exp(-|yi-yj|^2 / (2 beta^2))."""
    M = Y.shape[0]
    G = np.exp(-np.sum((Y[None] - Y[:, None]) ** 2, -1) / (2 * beta ** 2))
    W = np.zeros((M, 3))
    s2 = _sigma2(X, Y)
    for _ in range(iters):
        TY = Y + G @ W
        P = _estep(X, TY, s2, w)
        P1, Pt1 = P.sum(1), P.sum(0)
        Np = P1.sum()
        PX = P @ X
        A = np.diag(P1) @ G + lam * s2 * np.eye(M)
        W = np.linalg.solve(A, PX - np.diag(P1) @ Y)
        TY = Y + G @ W
        s2_old = s2
        s2 = (np.sum(Pt1 * np.sum(X * X, 1)) - 2 * np.sum(PX * TY) + np.sum(P1 * np.sum(TY * TY, 1))) / (Np * 3)
        s2 = max(s2, 1e-10)
        if abs(s2_old - s2) < tol:
            break
    return W


@dataclass
class Registration:
    """Base -> participant mapping in normalised coordinates."""
    c: np.ndarray        # normalisation centre
    s: float             # normalisation scale
    B: np.ndarray
    t: np.ndarray
    Y: np.ndarray        # affine-transformed, normalised base control points
    W: np.ndarray
    beta: float

    def __call__(self, pts):
        q = (np.asarray(pts, float) - self.c) / self.s
        q = q @ self.B.T + self.t
        G = np.exp(-np.sum((q[:, None] - self.Y[None]) ** 2, -1) / (2 * self.beta ** 2))
        q = q + G @ self.W
        return q * self.s + self.c


def register(base_v, base_f, part_v, part_f, n_points=1500, beta=3.0, lam=3.0, seed=0):
    """CPD registration of the base surface onto the participant surface."""
    Ys = mesh_points(base_v, base_f, n_points, seed)
    Xs = mesh_points(part_v, part_f, n_points, seed + 1)
    c = Xs.mean(0)
    s = np.sqrt(np.mean(np.sum((Xs - c) ** 2, 1)))
    X, Y = (Xs - c) / s, (Ys - c) / s
    B, t = cpd_affine(X, Y)
    Ya = Y @ B.T + t
    W = cpd_deformable(X, Ya, beta=beta, lam=lam)
    return Registration(c, s, B, t, Ya, W, beta)


# =========================================================================== main API
def snap_to_surface(pts, vertices, faces, n_dense=60000, seed=2):
    """Closest point on the mesh (dense surface sampling + vertices)."""
    cloud = np.vstack([vertices, mesh_points(vertices, faces, n_dense, seed)])
    _, i = cKDTree(cloud).query(pts)
    return cloud[i]


def auto_landmarks(base_stl, participant_stl, n_landmarks=25, base_landmarks=None, n_points=1500):
    """Return (names, base_pts, participant_pts) for one bone.

    ``base_landmarks``: optional (names, pts) to reuse instead of sampling.
    """
    bv, bf = geo.load_stl(base_stl)
    pv, pf = geo.load_stl(participant_stl)
    if base_landmarks is None:
        cand = np.vstack([bv, mesh_points(bv, bf, 20000, seed=3)])
        base_pts = cand[farthest_point_sampling(cand, n_landmarks)]
        names = [f"landmark_{i}" for i in range(len(base_pts))]
    else:
        names, base_pts = base_landmarks
    reg = register(bv, bf, pv, pf, n_points=n_points)
    part_pts = snap_to_surface(reg(base_pts), pv, pf)
    return names, base_pts, part_pts


def auto_landmarks_for_participant(info: dict, counts: dict[str, int], log=print) -> None:
    """Generate and write CSVs for every bone in ``info`` (from
    ``pipeline.prepare_mesh_warper_files``). ``counts`` maps bone -> n landmarks."""
    for key, d in info.items():
        n = int(counts.get(key, 25))
        names, b, p = auto_landmarks(d["source"], d["destination"], n)
        write_landmarks_csv(d["base_csv"], names, b)
        write_landmarks_csv(d["participant_csv"], names, p)
        shift = np.linalg.norm(p - b, axis=1) * 1000
        log(f"[auto-landmarks] {key}: {len(names)} landmarks, base->participant shift "
            f"mean {shift.mean():.1f} mm, max {shift.max():.1f} mm")
