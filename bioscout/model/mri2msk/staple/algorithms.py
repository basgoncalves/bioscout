"""STAPLE joint coordinate systems used by MRI2MSK step 1.

Ported from STAPLE (Modenese & Renault 2021, CC BY-NC 4.0) / GIBOC-core:

* ``staple_pelvis``  -> JCS.ground_pelvis   (STAPLE_pelvis.m + pelvis_guess_CS.m)
* ``kai2014_tibia``  -> JCS.knee_<side>      (Kai2014_tibia.m)
* ``giboc_femur``    -> JCS.hip_<side>       (GIBOC_femur.m, 'ellipsoids')

All return ``(origin (3,), V (3,3))`` in the mesh units (mm), V columns = X, Y, Z.
"""
from __future__ import annotations

import warnings

import numpy as np
from scipy.spatial import ConvexHull, cKDTree

from . import fitting as fit
from .trimesh_core import (Tri, coeff_morpho, cut_long_bone_mesh, in_polygon,
                           largest_edge_conv_hull, normalize, pca_coeff, plan_polygon_area,
                           tri_change_cs, tri_close_mesh, tri_dilate_mesh,
                           tri_fill_planar_holes, tri_inertia_ppties, tri_keep_largest_patch,
                           tri_open_mesh, tri_plan_intersect, tri_reduce_mesh,
                           tri_slice_obj_along_axis, tri_unite)


def side_sign(side: str) -> int:
    return 1 if side.lower().startswith("r") else -1


# =========================================================================== PELVIS
def pelvis_guess_cs(pelvis: Tri):
    V_all, center, *_ = tri_inertia_ppties(pelvis)
    Z0 = V_all[:, 0]
    hull = ConvexHull(pelvis.points)
    K = hull.simplices
    P = pelvis.points
    areas = 0.5 * np.linalg.norm(np.cross(P[K[:, 1]] - P[K[:, 0]], P[K[:, 2]] - P[K[:, 0]]), axis=1)
    big = K[int(np.argmax(areas))]
    # keep hull orientation (outward) for the face normal, like MATLAB convhull
    tri_pts = P[big]
    n = normalize(np.cross(tri_pts[1] - tri_pts[0], tri_pts[2] - tri_pts[0]))
    if np.dot(n, tri_pts.mean(0) - P[hull.vertices].mean(0)) < 0:
        tri_pts = tri_pts[[0, 2, 1]]
        n = -n
    largest = Tri(tri_pts, [[0, 1, 2]])

    ind_x = int(np.argmax(np.abs(V_all.T @ n)))
    X0 = V_all[:, ind_x]
    anterior = largest.incenter[0] - center
    X0 = normalize(np.sign(anterior @ X0) * X0)
    Y0t = normalize(np.cross(Z0, X0))

    # MATLAB passes [X0,Y0,Z0]' as V -> Pts*[X0 Y0 Z0]'  (kept literally)
    inert = tri_change_cs(pelvis, np.column_stack([X0, Y0t, Z0]).T, center)
    py, pz = inert.points[:, 1], inert.points[:, 2]
    spanY = abs(py.max()) + abs(py.min())
    spanZ = abs(pz.max()) + abs(pz.min())
    if spanY > spanZ:
        i1, i2 = int(np.argmax(py)), int(np.argmin(py))
    else:
        i1, i2 = int(np.argmax(pz)), int(np.argmin(pz))
    P3 = (P[i1] + P[i2]) / 2
    upw_ini = normalize(P3 - center)
    upw = upw_ini - (upw_ini @ X0) * X0
    ind_z = int(np.argmax(np.abs(V_all.T @ upw)))
    Z0 = V_all[:, ind_z]
    Z0 = np.sign(upw @ Z0) * Z0
    R = np.column_stack([X0, Z0, np.cross(X0, Z0)])
    return R, largest


def cs_pelvis_isb(RASIS, LASIS, RPSIS, LPSIS):
    Z = normalize(RASIS - LASIS)
    px = normalize((RASIS + LASIS) / 2 - (RPSIS + LPSIS) / 2)
    Y = normalize(np.cross(Z, px))
    X = normalize(np.cross(Y, Z))
    return np.column_stack([X, Y, Z])


def staple_pelvis(pelvis: Tri, side="r"):
    """Returns (origin, V, landmarks) for JCS.ground_pelvis."""
    _, center, *_ = tri_inertia_ppties(pelvis)
    R, largest = pelvis_guess_cs(pelvis)
    pis = tri_change_cs(pelvis, R, center)

    proj = (largest.points - center) @ R[:, 2]
    I = np.argsort(np.abs(proj), kind="stable")
    asi = I[1:3]
    SYMP = largest.points[I[0]]
    RASIS = largest.points[asi[proj[asi] > 0]][0]
    LASIS = largest.points[asi[proj[asi] < 0]][0]

    def psis(zsign):
        q = pis.points
        nodes = np.nonzero((q[:, 0] < 0) & (q[:, 1] > 0) & (zsign * q[:, 2] > 0))[0]
        sub = tri_reduce_mesh(pelvis, None, nodes)
        return sub.points[int(np.argmin(sub.points @ R[:, 0]))]

    RPSIS, LPSIS = psis(+1), psis(-1)
    if np.linalg.norm(RASIS - LASIS) < np.linalg.norm(RPSIS - LPSIS):
        warnings.warn("Inter-ASIS distance is shorter than inter-PSIS distance. Check manually.")
    origin = (RASIS + LASIS) / 2
    V = cs_pelvis_isb(RASIS, LASIS, RPSIS, LPSIS)
    BL = dict(RASI=RASIS, LASI=LASIS, RPSI=RPSIS, LPSI=LPSIS, SYMP=SYMP)
    return origin, V, BL


# =========================================================================== TIBIA (Kai2014)
def tibia_guess_cs(tibia: Tri):
    V_all, *_ = tri_inertia_ppties(tibia)
    Z0 = V_all[:, 0]
    proj = tibia.points @ Z0
    alt = np.linspace(proj.min() + 0.5, proj.max() - 0.5, 100)
    area = np.zeros(len(alt))
    for k, a in enumerate(alt):
        curves, _ = tri_plan_intersect(tibia, Z0, -a)
        area[k] = max([plan_polygon_area(c.pts) for c in curves] + [0])
    i = int(np.argmax(area)) + 1  # MATLAB 1-based index vs it=100
    if i > 0.66 * len(alt):
        return Z0
    if i < 0.33 * len(alt):
        return -Z0
    warnings.warn("Identification of the initial distal-proximal tibia axis went wrong.")
    return Z0


def tibia_identify_lateral_direction(dist_tib: Tri, Z0):
    _, cdist, *_ = tri_inertia_ppties(dist_tib)
    d = cdist @ Z0
    curves, _ = tri_plan_intersect(dist_tib, Z0, -d)
    if len(curves) > 2:
        raise RuntimeError(f"{len(curves)} section areas in distal tibia (expected tibia [+fibula]).")
    just_tibia = len(curves) != 2
    i = int(np.argmax(dist_tib.points @ -Z0))
    most_distal = dist_tib.points[i]
    if just_tibia:
        U = cdist - most_distal
    else:
        c1, c2 = curves
        diff = c2.pts.mean(0) - c1.pts.mean(0)
        U = diff if c1.area > c2.area else -diff
    return U, most_distal, just_tibia


def kai2014_tibia(tibia: Tri, side="r", slice_thickness=1.0):
    """Returns (origin, V) of JCS.knee_<side>."""
    sgn = side_sign(side)
    V_all = pca_coeff(tibia.points)
    U_d2p = tibia_guess_cs(tibia)
    prox, dist = cut_long_bone_mesh(tibia, U_d2p)
    Y0 = V_all[:, 0]
    Y0 = np.sign((prox.points.mean(0) - dist.points.mean(0)) @ Y0) * Y0

    *_, alt_max = tri_slice_obj_along_axis(tibia, Y0, slice_thickness)
    curves, _ = tri_plan_intersect(tibia, Y0, -alt_max)
    if len(curves) > 2:
        raise RuntimeError(f"{len(curves)} section areas at the largest tibial slice.")
    sect = max(curves, key=lambda c: c.area)
    pc = sect.pts @ V_all
    E = fit.fit_ellipse(pc[:, 1], pc[:, 2])
    if E["a"] > E["b"]:
        Zel = V_all @ np.array([0, np.cos(E["phi"]), -np.sin(E["phi"])])
    else:
        Zel = V_all @ np.array([0, np.sin(E["phi"]), np.cos(E["phi"])])
    center_ellipse = V_all @ np.array([pc[:, 0].mean(), E["X0_in"], E["Y0_in"]])

    U, _, _ = tibia_identify_lateral_direction(dist, Y0)
    U = sgn * U
    Z0t = normalize(U - (U @ Y0) * Y0)
    Zel = np.sign(Z0t @ Zel) * Zel

    Y = normalize(Y0)
    Z = normalize(Zel)
    X = normalize(np.cross(Y, Z))
    Ydp = normalize(np.cross(Z, X))
    return center_ellipse, np.column_stack([X, Ydp, Z])


# =========================================================================== FEMUR (GIBOC)
def femur_guess_cs(femur: Tri):
    V_all, center, *_ = tri_inertia_ppties(femur)
    Z0 = V_all[:, 0]
    P = femur.points - center
    Pd = (P @ V_all) @ np.diag([1, 2, 1]) @ V_all.T
    fem = Tri(Pd + center, femur.faces)
    epi1, epi2 = cut_long_bone_mesh(fem, Z0, 0.05)
    proj = fem.points @ Z0
    L = proj.max() - proj.min()
    t1 = tri_fill_planar_holes(tri_reduce_mesh(fem, np.nonzero(fem.incenter @ Z0 < proj.max() - 0.2 * L)[0]))
    t2 = tri_fill_planar_holes(tri_reduce_mesh(t1, np.nonzero(t1.incenter @ Z0 > proj.min() + 0.2 * L)[0]))
    Vd, cd, *_ = tri_inertia_ppties(t2)
    Zd = Vd[:, 0]
    _, ce1, *_ = tri_inertia_ppties(epi1)
    _, ce2, *_ = tri_inertia_ppties(epi2)
    d1 = np.linalg.norm(np.cross(ce1 - cd, Zd))
    d2 = np.linalg.norm(np.cross(ce2 - cd, Zd))
    U = ce2 - ce1 if d1 < d2 else ce1 - ce2
    if abs(d1 - d2) / (d1 + d2) < 0.2:
        warnings.warn("Femur epiphyses similarly distant from diaphysis axis; Z0 may be wrong.")
    return np.sign(U @ Z0) * Z0


def giboc_fit_sphere_fem_head(prox: Tri, cs: dict, cm: float):
    Z0 = cs["Z0"]
    i_top = int(np.argmax(prox.incenter @ Z0))
    ids = np.concatenate([[i_top], prox.neighbors[i_top][prox.neighbors[i_top] >= 0]])
    patch_top = tri_dilate_mesh(prox, tri_reduce_mesh(prox, ids), 40 * cm)
    OT = patch_top.points.mean(0) - cs["CenterVol"]
    cs["Y0"] = normalize(np.cross(np.cross(Z0, OT), Z0))
    i_mm = int(np.argmax(prox.incenter @ cs["Y0"]))
    ids = np.concatenate([[i_mm], prox.neighbors[i_mm][prox.neighbors[i_mm] >= 0]])
    patch_mm = tri_dilate_mesh(prox, tri_reduce_mesh(prox, ids), 40 * cm)
    head0 = tri_unite(patch_mm, patch_top)
    _, radius, _ = fit.sphere_fit(head0.points)
    dil = tri_dilate_mesh(prox, head0, round(1.5 * radius * cm))
    c_fh, r_dil, _ = fit.sphere_fit(dil.points)
    v = dil.incenter - c_fh
    nrm = v / np.linalg.norm(v, axis=1, keepdims=True)
    cond1 = np.sum(nrm * dil.face_normals, axis=1) > 0.975
    cond2 = np.abs(np.linalg.norm(dil.incenter - c_fh, axis=1) - radius) < 0.1 * radius
    single = False
    if np.sum(cond1 & cond2) > 20:
        applied = cond1 & cond2
    else:
        single, applied = True, cond1
    head = tri_reduce_mesh(dil, np.nonzero(applied)[0])
    if single:
        head = tri_keep_largest_patch(head)
    head = tri_open_mesh(prox, head, 3 * cm)
    c_fh, r, _ = fit.sphere_fit(head.points)
    cs["CenterFH_Renault"] = c_fh
    cs["RadiusFH_Renault"] = r
    return cs, head


def giboc_isolate_epiphysis(tri: Tri, Z0, which="distal"):
    areas, alt, *_ = tri_slice_obj_along_axis(tri, Z0, 1.0)
    _, z_epi, _ = fit.fit_csa(alt, areas)
    inc = tri.incenter @ Z0
    keep = inc > z_epi if which == "proximal" else inc < z_epi
    return tri_reduce_mesh(tri, np.nonzero(keep)[0])


def pc_region_growing(pts, seed, r):
    pts = pts.copy()
    seeds = pts[[cKDTree(pts).query(seed)[1]]]
    out = []
    while len(seeds):
        tree = cKDTree(pts)
        idx = np.unique(np.concatenate([np.asarray(i, int) for i in tree.query_ball_point(seeds, r)]))
        seeds = pts[idx]
        out.append(pts[idx])
        pts = np.delete(pts, idx, axis=0)
        if len(pts) == 0:
            break
    return np.vstack(out) if out else np.zeros((0, 3))


def giboc_femur_process_epiphysis(epi: Tri, cs, V_all, edge_thr=0.5, dev_thr=0.75):
    pairs, edges = largest_edge_conv_hull(epi.points)
    fb_nodes = set(np.unique(epi.free_boundary).tolist())
    target = int(np.sum(edges > edge_thr * edges[0]))
    kept = []
    i = 0
    while len(kept) != target and i < len(pairs):
        a, b = pairs[i]
        if a not in fb_nodes and b not in fb_nodes:
            kept.append(i)
        i += 1
    ids = pairs[kept]
    axes = epi.points[ids[:, 0]] - epi.points[ids[:, 1]]
    keep = axes @ cs["Y0"] >= 0
    ids, axes = ids[keep], axes[keep]
    U = normalize(axes)
    keep = np.abs(U @ V_all[:, 1]) >= dev_thr
    ids, U = ids[keep], U[keep]
    good = pc_region_growing(U, normalize(U.mean(0)), 0.1)
    good_set = {r.tobytes() for r in good}
    lia = np.array([r.tobytes() in good_set for r in U])
    ids, U = ids[lia], U[lia]
    orient = np.round(np.mean(np.sign(U @ cs["Y0"])))
    if orient < 0:
        warnings.warn("Unexpected lateral->medial axis orientation of the distal femoral epiphysis.")
        med_lat = (1, 0)
    else:
        med_lat = (0, 1)
    return ids, U, med_lat


def get_condyle_most_prox_point(epi: Tri, cs, trace, U):
    c, nrm = fit.lsplane(trace)
    dmed = -c @ nrm
    on_plan = np.nonzero((np.abs(epi.points @ nrm + dmed) < 2.5) &
                         (epi.points @ cs["Z0"] > np.max(trace @ cs["Z0"] - 2.5)))[0]
    near = epi.kdtree.query_ball_point(trace, 7.5)
    near = np.unique(np.concatenate([np.asarray(n, int) for n in near]))
    iok = np.intersect1d(on_plan, near)
    return epi.points[iok[int(np.argmax(epi.vertex_normals[iok] @ U))]]


def pts_on_condyles_femur(P0, Pepi, cut_angle, inset, dilat):
    E = fit.fit_ellipse(P0[:, 2], P0[:, 0])
    Ux = np.array([np.cos(E["phi"]), -np.sin(E["phi"])])
    Uy = np.array([np.sin(E["phi"]), np.cos(E["phi"])])
    R = np.column_stack([Ux, Uy])
    th = np.linspace(0, 2 * np.pi, 36)
    ell = (R @ np.vstack([E["X0"] + inset * E["a"] * np.cos(th),
                          E["Y0"] + inset * E["b"] * np.sin(th)])).T
    out_elps = ~in_polygon(Pepi[:, 2], Pepi[:, 0], ell[:, 0], ell[:, 1])
    h2 = P0[:, [2, 0]]
    K = ConvexHull(h2).vertices
    hx = h2[K, 0] + dilat * (h2[K, 0] - E["X0_in"])
    hy = h2[K, 1] + dilat * (h2[K, 1] - E["Y0_in"])
    in_ch = in_polygon(Pepi[:, 2], Pepi[:, 0], hx, hy)
    rel = Pepi[:, [2, 0]] - np.array([E["X0_in"], E["Y0_in"]])
    sq = (rel @ Ux) ** 2 + (rel @ Uy) ** 2
    I = int(np.argmax(sq))
    Ue = rel / np.linalg.norm(rel, axis=1, keepdims=True)
    c = np.cos(np.deg2rad(90 - cut_angle))
    if rel[I] @ Uy < 0:
        ext_post = (Ue @ Uy < -c) | ((Ue @ Uy < 0) & (Ue @ Ux > 0))
    else:
        ext_post = (Ue @ Uy > c) | ((Ue @ Uy > 0) & (Ue @ Ux > 0))
    return Pepi[out_elps & in_ch & ~ext_post]


def giboc_femur_artic_surf_full(epi: Tri, cs, cm):
    """GIBOC_femur_ArticSurf with art_surface='full_condyles'. Returns (med, lat) Tri."""
    cut_lat, cut_med, inset, dil = 70, 85, 0.8, 0.025
    V_all, Z0 = cs["V_all"], cs["Z0"]
    ids, U_axes, ml = giboc_femur_process_epiphysis(epi, cs, V_all)
    Pmed = epi.points[ids[:, ml[0]]]
    Plat = epi.points[ids[:, ml[1]]]
    Y1 = normalize(U_axes.sum(0))
    X1 = normalize(np.cross(Y1, Z0))
    Z1 = np.cross(X1, Y1)
    VC = np.column_stack([X1, Y1, Z1])
    n_in = int(np.ceil(len(ids) * 0.5))
    mid_post = np.mean(0.5 * (Pmed[:n_in] + Plat[:n_in]), axis=0)
    mid_epi = epi.points.mean(0)
    X1 = np.sign((mid_epi - mid_post) @ X1) * X1
    U = normalize(3 * Z0 - X1)
    top_med = get_condyle_most_prox_point(epi, cs, Pmed, U)
    top_lat = get_condyle_most_prox_point(epi, cs, Plat, U)
    mid = np.mean(0.5 * (Pmed + Plat), axis=0)
    axis_proj = mid @ VC
    epi2d = epi.points @ VC
    proj_lat = np.vstack([Plat, top_lat, top_lat]) @ VC
    proj_med = np.vstack([Pmed, top_med, top_med]) @ VC
    C1 = epi2d[epi2d[:, 1] - axis_proj[1] < 0]
    C2 = epi2d[epi2d[:, 1] - axis_proj[1] > 0]
    art_lat = pts_on_condyles_femur(proj_lat, C1, cut_lat, inset, dil) @ VC.T
    art_med = pts_on_condyles_femur(proj_med, C2, cut_med, inset, dil) @ VC.T

    def smooth(pts):
        cond = tri_reduce_mesh(epi, None, pts)
        cond2 = tri_close_mesh(epi, cond, 5 * cm)
        return tri_open_mesh(epi, cond2, 15 * cm)

    return smooth(art_med), smooth(art_lat)


def giboc_femur(femur: Tri, side="r"):
    """GIBOC_femur(..., 'ellipsoids'). Returns (origin, V) of JCS.hip_<side>."""
    sgn = side_sign(side)
    U_d2p = femur_guess_cs(femur)
    prox, dist = cut_long_bone_mesh(femur, U_d2p)
    cm = coeff_morpho(femur)
    V_all, center, *_ = tri_inertia_ppties(femur)
    Z0 = V_all[:, 0]
    Z0 = np.sign((prox.points.mean(0) - dist.points.mean(0)) @ Z0) * Z0
    cs = dict(CenterVol=center, V_all=V_all, Z0=Z0)
    cs, _ = giboc_fit_sphere_fem_head(prox, cs, cm)
    epi = giboc_isolate_epiphysis(dist, Z0, "distal")
    med, lat = giboc_femur_artic_surf_full(epi, cs, cm)
    c_lat, *_ = fit.ellipsoid_fit(lat.points)
    c_med, *_ = fit.ellipsoid_fit(med.points)
    knee = 0.5 * (c_med + c_lat)
    Z = normalize(c_lat - c_med) * sgn
    Y = normalize(cs["CenterFH_Renault"] - knee)
    X = normalize(np.cross(Y, Z))
    Zml = normalize(np.cross(X, Y))
    return cs["CenterFH_Renault"], np.column_stack([X, Y, Zml])
