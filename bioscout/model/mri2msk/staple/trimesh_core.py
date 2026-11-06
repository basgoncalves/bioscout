"""Triangulation core: a minimal stand-in for MATLAB's ``triangulation`` object
plus the GIBOC-core ``Tri*`` mesh functions used by STAPLE.

Faces and vertex ids are 0-based here (MATLAB is 1-based). Missing neighbours
are -1 (MATLAB uses NaN).
"""
from __future__ import annotations

from functools import cached_property

import numpy as np
from scipy.spatial import ConvexHull, cKDTree


def normalize(v):
    v = np.asarray(v, float)
    if v.ndim == 1:
        return v / np.linalg.norm(v)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


# =========================================================================== Tri object
class Tri:
    """Lightweight triangulation (points (N,3), faces (M,3) int, 0-based)."""

    def __init__(self, points, faces):
        self.points = np.ascontiguousarray(points, dtype=float)
        self.faces = np.ascontiguousarray(faces, dtype=np.int64).reshape(-1, 3)

    def __len__(self):
        return len(self.faces)

    # ------------------------------------------------------------- per-face
    @cached_property
    def _cross(self):
        p = self.points
        f = self.faces
        return np.cross(p[f[:, 1]] - p[f[:, 0]], p[f[:, 2]] - p[f[:, 0]])

    @cached_property
    def face_normals(self):
        return normalize(self._cross)

    @cached_property
    def face_areas(self):
        return 0.5 * np.linalg.norm(self._cross, axis=1)

    @cached_property
    def incenter(self):
        """Inscribed-circle centres (MATLAB ``incenter``)."""
        p, f = self.points, self.faces
        A, B, C = p[f[:, 0]], p[f[:, 1]], p[f[:, 2]]
        a = np.linalg.norm(B - C, axis=1)[:, None]
        b = np.linalg.norm(C - A, axis=1)[:, None]
        c = np.linalg.norm(A - B, axis=1)[:, None]
        return (a * A + b * B + c * C) / (a + b + c)

    # ------------------------------------------------------------- adjacency
    @cached_property
    def _edge_data(self):
        """Undirected edge key per (face, local edge opposite vertex j)."""
        f = self.faces
        # edge opposite vertex j joins vertices (j+1, j+2)
        e = np.stack([np.stack([f[:, 1], f[:, 2]], 1),
                      np.stack([f[:, 2], f[:, 0]], 1),
                      np.stack([f[:, 0], f[:, 1]], 1)], axis=1)  # (M,3,2)
        es = np.sort(e, axis=2).reshape(-1, 2)
        return e, es

    @cached_property
    def neighbors(self):
        """(M,3) face ids across each edge (opposite vertex j), -1 if none."""
        _, es = self._edge_data
        m = len(self.faces)
        key = es[:, 0] * (len(self.points) + 1) + es[:, 1]
        order = np.argsort(key, kind="stable")
        ks = key[order]
        nb = -np.ones(3 * m, dtype=np.int64)
        same = np.nonzero(ks[1:] == ks[:-1])[0]
        a, b = order[same], order[same + 1]
        nb[a] = b // 3
        nb[b] = a // 3
        return nb.reshape(m, 3)

    @cached_property
    def free_boundary(self):
        """Directed boundary edges (K,2) in face orientation."""
        e, _ = self._edge_data
        mask = (self.neighbors == -1).reshape(-1)
        return e.reshape(-1, 2)[mask]

    @cached_property
    def _vertex_faces_csr(self):
        f = self.faces.reshape(-1)
        order = np.argsort(f, kind="stable")
        counts = np.bincount(f, minlength=len(self.points))
        ptr = np.concatenate([[0], np.cumsum(counts)])
        return ptr, order // 3

    def vertex_attachments(self, vids) -> np.ndarray:
        """Unique face ids attached to vertex ids."""
        ptr, fid = self._vertex_faces_csr
        vids = np.atleast_1d(np.asarray(vids, dtype=np.int64))
        if vids.size == 0:
            return np.zeros(0, np.int64)
        parts = [fid[ptr[v]:ptr[v + 1]] for v in vids]
        return np.unique(np.concatenate(parts))

    def face_neighbors_of(self, fids) -> np.ndarray:
        nb = self.neighbors[np.atleast_1d(fids)].reshape(-1)
        return np.unique(nb[nb >= 0])

    @cached_property
    def vertex_normals(self):
        """Area-weighted vertex normals (MATLAB ``vertexNormal``)."""
        vn = np.zeros_like(self.points)
        for j in range(3):
            np.add.at(vn, self.faces[:, j], self._cross)
        n = np.linalg.norm(vn, axis=1, keepdims=True)
        n[n == 0] = 1
        return vn / n

    @cached_property
    def kdtree(self):
        return cKDTree(self.points)

    def nearest_neighbor(self, pts) -> np.ndarray:
        return self.kdtree.query(np.atleast_2d(pts))[1]


# =========================================================================== loading
def load_tri(path) -> Tri:
    """Load an STL like MATLAB ``stlread`` (merge identical vertices) + TriFixNormals."""
    import trimesh
    m = trimesh.load_mesh(str(path), process=False)
    v = np.asarray(m.vertices, float)
    f = np.asarray(m.faces, np.int64)
    uniq, first, inv = np.unique(v, axis=0, return_index=True, return_inverse=True)
    order = np.argsort(first)                # keep first-occurrence order
    remap = np.empty(len(order), np.int64)
    remap[order] = np.arange(len(order))
    tri = Tri(uniq[order], remap[inv.reshape(-1)][f])
    return tri_fix_normals(tri)


def tri_fix_normals(tri: Tri) -> Tri:
    nodes, el = tri.points, tri.faces
    normals = tri.face_normals
    n = max(500, len(nodes))
    idx = np.round(np.linspace(0, len(normals) - 1, n)).astype(int)
    p0 = nodes[el[idx, 0]]
    vol0 = ConvexHull(p0).volume
    vol1 = ConvexHull(p0 + 5 * normals[idx]).volume
    if vol1 < vol0:
        el = el[:, [0, 2, 1]]
    return Tri(nodes, el)


# =========================================================================== mesh ops
def tri_reduce_mesh(tri: Tri, elmts_kept=None, nodes_kept=None) -> Tri:
    """TriReduceMesh: keep faces (or faces attached to nodes / nearest nodes of points)."""
    if nodes_kept is not None:
        nk = np.asarray(nodes_kept)
        if nk.ndim == 2 or (nk.dtype.kind == "f" and np.any(np.mod(nk, 1))):
            ids = np.unique(tri.nearest_neighbor(nk))
        else:
            ids = nk.astype(np.int64).reshape(-1)
        elmts_kept = tri.vertex_attachments(ids)
    elmts_kept = np.atleast_1d(np.asarray(elmts_kept, dtype=np.int64))
    sub = tri.faces[elmts_kept]
    nodes = np.unique(sub)
    remap = -np.ones(len(tri.points), np.int64)
    remap[nodes] = np.arange(len(nodes))
    return Tri(tri.points[nodes], remap[sub])


def tri_unite(a: Tri, b: Tri) -> Tri:
    return Tri(np.vstack([a.points, b.points]), np.vstack([a.faces, b.faces + len(a.points)]))


def _matching_vertex_ids(sup: Tri, pts: np.ndarray) -> np.ndarray:
    """Ids of ``sup.points`` that exactly equal any row of ``pts`` (MATLAB intersect rows)."""
    lut = {r.tobytes(): i for i, r in enumerate(sup.points)}
    ids = {lut[r.tobytes()] for r in np.asarray(pts, float) if r.tobytes() in lut}
    return np.array(sorted(ids), dtype=np.int64)


def tri_dilate_mesh(sup: Tri, tin: Tri, nb) -> Tri:
    nb = int(np.ceil(nb))
    ia = _matching_vertex_ids(sup, tin.points)
    ok = sup.vertex_attachments(ia)
    cur = ok
    for _ in range(nb):
        cur = sup.face_neighbors_of(cur)
        ok = np.union1d(ok, cur)
    return tri_reduce_mesh(sup, ok)


def tri_erode_mesh(tin: Tri, nb) -> Tri:
    nb = int(np.ceil(nb))
    border_nodes = np.unique(tin.free_boundary)
    border = np.nonzero(np.isin(tin.faces, border_nodes).any(axis=1))[0]
    cur = border
    for _ in range(max(nb - 1, 0)):
        cur = tin.face_neighbors_of(cur)
        border = np.union1d(border, cur)
    keep = np.ones(len(tin.faces), bool)
    keep[border] = False
    return tri_reduce_mesh(tin, np.nonzero(keep)[0])


def tri_open_mesh(sup: Tri, tin: Tri, nb) -> Tri:
    return tri_dilate_mesh(sup, tri_erode_mesh(tin, nb), nb)


def tri_close_mesh(sup: Tri, tin: Tri, nb) -> Tri:
    return tri_erode_mesh(tri_dilate_mesh(sup, tin, nb), nb)


def tri_connected_patch(tri: Tri, pts) -> Tri:
    nodes = np.unique(tri.nearest_neighbor(pts))
    cur = tri.vertex_attachments(nodes)
    conn = cur
    while True:
        prev = len(conn)
        cur = tri.face_neighbors_of(cur)
        conn = np.union1d(conn, cur)
        if len(conn) == prev:
            break
    return tri_reduce_mesh(tri, conn)


def boundary_loops(tri: Tri) -> list[np.ndarray]:
    """Closed boundary loops as lists of directed edges (each (k,2))."""
    fb = tri.free_boundary
    if len(fb) == 0:
        return []
    nxt = {}
    for k, (a, b) in enumerate(fb):
        nxt.setdefault(int(a), []).append(k)
    used = np.zeros(len(fb), bool)
    loops = []
    for start in range(len(fb)):
        if used[start]:
            continue
        loop = []
        k = start
        while k is not None and not used[k]:
            used[k] = True
            loop.append(k)
            cand = [c for c in nxt.get(int(fb[k, 1]), []) if not used[c]]
            k = cand[0] if cand else None
        loops.append(fb[loop])
    return loops


def tri_fill_planar_holes(tin: Tri) -> Tri:
    loops = boundary_loops(tin)
    if not loops:
        return tin
    pts = [tin.points]
    faces = [tin.faces]
    n_new = len(tin.points)
    tri_center = tin.points.mean(axis=0)
    for fb in loops:
        hole_pts = tin.points[fb[:, 0]]
        hc = hole_pts.mean(axis=0)
        pts.append(hc[None])
        new = np.column_stack([fb, np.full(len(fb), n_new)])
        allp = np.vstack(pts)
        U = normalize(hc - tri_center)
        nrm = normalize(np.cross(allp[new[:, 1]] - allp[new[:, 0]], allp[new[:, 2]] - allp[new[:, 0]]))
        if np.mean(nrm @ U) < 0:
            new = np.column_stack([fb[:, 0], np.full(len(fb), n_new), fb[:, 1]])
        faces.append(new)
        n_new += 1
    return Tri(np.vstack(pts), np.vstack(faces))


def tri_keep_largest_patch(tin: Tri) -> Tri:
    tin2 = tri_erode_mesh(tin, 1)
    loops = boundary_loops(tin2)
    if len(loops) > 1:
        best, best_area = None, -1.0
        for fb in loops:
            patch = tri_connected_patch(tin, tin2.points[fb[:, 0]])
            area = patch.face_areas.sum()
            if area > best_area:
                best, best_area = patch, area
        return best
    return tri_dilate_mesh(tin, tin2, 1)


# =========================================================================== inertia
def tri_inertia_ppties(tri: Tri):
    """TriInertiaPpties: (eigVecs, CenterVol(3,), InertiaMatrix, D(eigvals), mass)."""
    pc = tri.points.mean(axis=0)
    P = tri.points - pc
    f = tri.faces
    P1, P2, P3 = P[f[:, 0]], P[f[:, 1]], P[f[:, 2]]
    d = np.cross(P2 - P1, P3 - P1)

    def sub(w0, w1, w2):
        t0 = w0 + w1
        f1 = t0 + w2
        t1 = w0 * w0
        t2 = t1 + w1 * t0
        f2 = t2 + w2 * f1
        f3 = w0 * t1 + w1 * t2 + w2 * f2
        g0 = f2 + w0 * (f1 + w0)
        g1 = f2 + w1 * (f1 + w1)
        g2 = f2 + w2 * (f1 + w2)
        return f1, f2, f3, g0, g1, g2

    x0, x1, x2 = P1[:, 0], P2[:, 0], P3[:, 0]
    y0, y1, y2 = P1[:, 1], P2[:, 1], P3[:, 1]
    z0, z1, z2 = P1[:, 2], P2[:, 2], P3[:, 2]
    f1x, f2x, f3x, g0x, g1x, g2x = sub(x0, x1, x2)
    _, f2y, f3y, g0y, g1y, g2y = sub(y0, y1, y2)
    _, f2z, f3z, g0z, g1z, g2z = sub(z0, z1, z2)
    d0, d1, d2 = d[:, 0], d[:, 1], d[:, 2]
    intg = np.array([
        np.sum(d0 * f1x), np.sum(d0 * f2x), np.sum(d1 * f2y), np.sum(d2 * f2z),
        np.sum(d0 * f3x), np.sum(d1 * f3y), np.sum(d2 * f3z),
        np.sum(d0 * (y0 * g0x + y1 * g1x + y2 * g2x)),
        np.sum(d1 * (z0 * g0y + z1 * g1y + z2 * g2y)),
        np.sum(d2 * (x0 * g0z + x1 * g1z + x2 * g2z)),
    ]) * np.array([1 / 6, 1 / 24, 1 / 24, 1 / 24, 1 / 60, 1 / 60, 1 / 60, 1 / 120, 1 / 120, 1 / 120])
    mass = intg[0]
    c = intg[1:4] / mass
    I = np.zeros((3, 3))
    I[0, 0] = intg[5] + intg[6] - mass * (c[1] ** 2 + c[2] ** 2)
    I[1, 1] = intg[4] + intg[6] - mass * (c[2] ** 2 + c[0] ** 2)
    I[2, 2] = intg[4] + intg[5] - mass * (c[0] ** 2 + c[1] ** 2)
    I[0, 1] = I[1, 0] = -(intg[7] - mass * c[0] * c[1])
    I[1, 2] = I[2, 1] = -(intg[8] - mass * c[1] * c[2])
    I[2, 0] = I[0, 2] = -(intg[9] - mass * c[2] * c[0])
    evals, evecs = np.linalg.eigh(I)
    return evecs, c + pc, I, evals, mass


def tri_change_cs(tri: Tri, V, T) -> Tri:
    return Tri((tri.points - np.asarray(T).reshape(3)) @ V, tri.faces)


def coeff_morpho(tri: Tri) -> float:
    mean_edge = np.sqrt(4 / np.sqrt(3) * tri.face_areas.sum() / len(tri.faces))
    return 0.5 / mean_edge


def pca_coeff(X):
    """MATLAB ``pca`` coefficients (columns), sign: largest |component| positive."""
    Xc = X - X.mean(axis=0)
    _, _, Vt = np.linalg.svd(Xc, full_matrices=False)
    V = Vt.T
    idx = np.argmax(np.abs(V), axis=0)
    sgn = np.sign(V[idx, np.arange(V.shape[1])])
    sgn[sgn == 0] = 1
    return V * sgn


# =========================================================================== plane sections
class Curve:
    __slots__ = ("pts", "area", "hole")

    def __init__(self, pts, area):
        self.pts, self.area, self.hole = pts, area, 0


def _plane_basis(n):
    n = normalize(n)
    a = np.array([1.0, 0, 0]) if abs(n[0]) < 0.9 else np.array([0, 1.0, 0])
    u = normalize(np.cross(n, a))
    return u, np.cross(n, u)


def polygon_area(xy):
    x, y = xy[:, 0], xy[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def in_polygon(px, py, vx, vy):
    """Vectorised point-in-polygon (boundary counted as inside, like inpolygon)."""
    px = np.atleast_1d(px)[:, None]
    py = np.atleast_1d(py)[:, None]
    x1, y1 = np.asarray(vx)[None, :], np.asarray(vy)[None, :]
    x2, y2 = np.roll(x1, -1, axis=1), np.roll(y1, -1, axis=1)
    cond = (y1 > py) != (y2 > py)
    with np.errstate(divide="ignore", invalid="ignore"):
        xint = (x2 - x1) * (py - y1) / (y2 - y1) + x1
    inside = np.sum(cond & (px < xint), axis=1) % 2 == 1
    # on-edge check
    cross = (x2 - x1) * (py - y1) - (y2 - y1) * (px - x1)
    within = (np.minimum(x1, x2) - 1e-12 <= px) & (px <= np.maximum(x1, x2) + 1e-12) & \
             (np.minimum(y1, y2) - 1e-12 <= py) & (py <= np.maximum(y1, y2) + 1e-12)
    on_edge = np.any((np.abs(cross) < 1e-9) & within, axis=1)
    return inside | on_edge


def tri_plan_intersect(tri: Tri, n, d):
    """TriPlanIntersect: plane n.x + d = 0. Returns (curves, total_area).

    ``d`` may also be a point on the plane (3,).
    """
    n = normalize(np.asarray(n, float).reshape(3))
    d = np.asarray(d, float)
    if d.size == 3:
        d = -float(d @ n)
    else:
        d = float(d)
    s = tri.points @ n + d
    sg = np.sign(s)
    f = tri.faces
    e, es = tri._edge_data
    e_flat = e.reshape(-1, 2)
    crossing = (sg[e_flat[:, 0]] * sg[e_flat[:, 1]]) < 0
    if not crossing.any():
        return [], 0.0
    key = es[:, 0] * (len(tri.points) + 1) + es[:, 1]
    ukeys, inv = np.unique(key[crossing], return_inverse=True)
    # intersection point per unique crossing edge
    ce = es[crossing]
    first = np.zeros(len(ukeys), np.int64)
    first[inv[::-1]] = np.arange(len(inv))[::-1]
    a, b = ce[first, 0], ce[first, 1]
    t = s[a] / (s[a] - s[b])
    P = tri.points[a] + (tri.points[b] - tri.points[a]) * t[:, None]
    pid = -np.ones(len(key), np.int64)
    pid[np.nonzero(crossing)[0]] = inv
    pid = pid.reshape(-1, 3)
    two = pid[(pid >= 0).sum(axis=1) == 2]
    segs = np.sort(two, axis=1)[:, 1:]  # drop the single -1 per row
    # chain segments into loops
    adj = [[] for _ in range(len(P))]
    for i, (u, v) in enumerate(segs):
        adj[u].append((v, i))
        adj[v].append((u, i))
    used = np.zeros(len(segs), bool)
    curves = []
    for i0 in range(len(segs)):
        if used[i0]:
            continue
        used[i0] = True
        loop = [segs[i0, 0], segs[i0, 1]]
        cur = segs[i0, 1]
        while True:
            nxt = [(v, k) for v, k in adj[cur] if not used[k]]
            if not nxt:
                break
            v, k = nxt[0]
            used[k] = True
            if v == loop[0]:
                break
            loop.append(v)
            cur = v
        curves.append(np.array(loop))
    u, w = _plane_basis(n)
    out = []
    for loop in curves:
        pts = P[loop]
        xy = np.column_stack([pts @ u, pts @ w])
        out.append((Curve(pts, polygon_area(xy)), xy))
    tot = 0.0
    for i, (ci, xyi) in enumerate(out):
        cnt = 0
        for j, (cj, xyj) in enumerate(out):
            if i != j and in_polygon(xyi[0, 0], xyi[0, 1], xyj[:, 0], xyj[:, 1])[0]:
                cnt += 1
        add = 1 - 2 * (cnt % 2)
        ci.hole = -add
        tot += add * ci.area
    return [c for c, _ in out], tot


def tri_slice_obj_along_axis(tri: Tri, axis, step, cut_offset=0.5):
    proj = tri.points @ axis
    alt = np.arange(proj.min() + cut_offset, proj.max() - cut_offset + 1e-9, step)
    areas = np.array([tri_plan_intersect(tri, axis, -a)[1] for a in alt])
    i = int(np.argmax(areas))
    return areas, alt, areas[i], i, alt[i]


def plan_polygon_area(pts):
    """Area returned by PlanPolygonCentroid3D (abs signed area in the curve plane)."""
    if len(pts) < 3:
        return 0.0
    C = np.cov(pts.T)
    _, V = np.linalg.eigh(C)
    xy = (pts - pts.mean(0)) @ V[:, 1:]
    return polygon_area(xy)


def cut_long_bone_mesh(tri: Tri, U0=None, L_ratio=0.33):
    if U0 is None:
        U0 = np.array([0, 0, 1.0])
    V, *_ = tri_inertia_ppties(tri)
    Z0 = V[:, 0]
    Z0 = np.sign(np.dot(U0, Z0)) * Z0
    proj = tri.points @ Z0
    L = proj.max() - proj.min()
    inc = tri.incenter @ Z0
    prox = tri_fill_planar_holes(tri_reduce_mesh(tri, np.nonzero(inc > proj.max() - L_ratio * L)[0]))
    dist = tri_fill_planar_holes(tri_reduce_mesh(tri, np.nonzero(inc < proj.min() + L_ratio * L)[0]))
    return prox, dist


def largest_edge_conv_hull(pts):
    """LargestEdgeConvHull (3-D): all hull-triangle edges sorted by length desc."""
    K = ConvexHull(pts).simplices
    rows = []
    for a, b in ((0, 1), (1, 2), (2, 0)):
        L = np.linalg.norm(pts[K[:, a]] - pts[K[:, b]], axis=1)
        rows.append(np.column_stack([L, K[:, a], K[:, b]]))
    M = np.vstack(rows)
    order = np.argsort(-M[:, 0], kind="stable")
    M = M[order]
    return M[:, 1:].astype(np.int64), M[:, 0]
