"""Cross-body wrap penetration fix, driven by coordinate sweeps (no .mot needed).

Ports the MATLAB pipeline's Phase 3 *cross-body point projection*: a path point
on one body can dip inside a wrap cylinder on a different body only at certain
poses, producing a pose-dependent muscle-length / moment-arm discontinuity. We
reuse the inspection sweeps as the "motion": pose the model across each
coordinate's range, track the worst penetration per path-point/cylinder pair,
then project the point just outside the cylinder at that worst pose.

Radius-reduction and motion-rejection fallbacks (MATLAB Phase 3 priorities 2-3)
are not implemented here.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

from .geometry import euler_xyz_to_rotation_matrix, project_point_outside_cylinder
from .logutil import LOG, timed
from .wrap_fixer import PointProjection, find_wrap_object

try:
    import opensim
except Exception:  # pragma: no cover
    opensim = None


def _v(vec) -> np.ndarray:
    return np.array([vec.get(0), vec.get(1), vec.get(2)], float)


def _station_in_frame(state, src_frame, loc_vec3, dst_frame) -> np.ndarray:
    """Location of a station (Vec3 in src_frame) expressed in dst_frame."""
    out = src_frame.findStationLocationInAnotherFrame(state, loc_vec3, dst_frame)
    return _v(out)


def _build_combos(model, muscle_names):
    """Cross-body (path point body != cylinder body) pairs to monitor."""
    combos = []
    muscles = model.getMuscles()
    for mname in muscle_names:
        gp = muscles.get(mname).getGeometryPath()
        wrap_set, pp_set = gp.getWrapSet(), gp.getPathPointSet()
        for w in range(wrap_set.getSize()):
            won = wrap_set.get(w).getWrapObjectName()
            wo, wbody = find_wrap_object(model, won)
            if wo is None:
                continue
            cyl = opensim.WrapCylinder.safeDownCast(wo)
            if cyl is None:
                continue
            rxyz = cyl.get_xyz_body_rotation()
            combo = dict(
                muscle=mname, wrap=won, wbody_name=wbody.getName(), wframe=wbody,
                radius=cyl.get_radius(), length=cyl.get_length(),
                R=euler_xyz_to_rotation_matrix(rxyz.get(0), rxyz.get(1), rxyz.get(2)),
                t=_v(cyl.get_translation()),
                worst=0.0, pose=None,
            )
            for p in range(pp_set.getSize()):
                app = pp_set.get(p)
                if app.getBody().getName() == combo["wbody_name"]:
                    continue  # same-body handled by the static check
                pp = opensim.PathPoint.safeDownCast(app)
                if pp is None:
                    continue  # moving / conditional points are not edited
                c = dict(combo)
                c.update(pp=pp, ppname=pp.getName(), ppframe=app.getBody())
                combos.append(c)
    return combos


def scan_cross_body(
    mam, muscle_names: list, coordinate_names: list,
    n_pose: int = 30, max_displacement_mm: float = 5.0,
    margin_base_m: float = 0.002, margin_frac: float = 0.5,
    verbose: bool = True,
) -> list[PointProjection]:
    """Return cross-body projections (best, smallest-displacement per muscle)."""
    if opensim is None:
        return []
    model, state = mam.model, mam.state
    combos = _build_combos(model, muscle_names)
    if not combos:
        LOG.info("cross-body: no cross-body path-point/cylinder pairs to check")
        return []

    # Capability probe: ensure the frame transform API is available.
    try:
        _station_in_frame(state, combos[0]["ppframe"], combos[0]["pp"].get_location(),
                          combos[0]["wframe"])
    except Exception as exc:  # pragma: no cover
        LOG.warning("cross-body scan unavailable (frame API: %s) -- skipping", exc)
        return []

    # Build the pose list: single-DOF sweeps over each inspection coordinate.
    poses = []
    for c in coordinate_names:
        if c not in mam._defaults:
            continue
        coord = mam.coord_set.get(c)
        lo, hi = coord.getRangeMin(), coord.getRangeMax()
        for v in np.linspace(lo, hi, n_pose):
            poses.append((c, v))

    LOG.info("cross-body: scanning %d pairs across %d poses", len(combos), len(poses))
    for cname, val in poses:
        coord = mam.coord_set.get(cname)
        mam.reset_pose()
        mam._set_coord(coord, val, assemble=mam._assemble_needed(cname))
        for cb in combos:
            try:
                ptw = _station_in_frame(state, cb["ppframe"], cb["pp"].get_location(),
                                        cb["wframe"])
            except Exception:
                continue
            pt_cyl = cb["R"].T @ (ptw - cb["t"])
            if abs(pt_cyl[2]) > cb["length"] / 2:
                continue  # outside the cylinder's axial extent
            pen = cb["radius"] - float(np.hypot(pt_cyl[0], pt_cyl[1]))
            if pen > cb["worst"]:
                cb["worst"], cb["pose"] = pen, (cname, val)

    # Propose projections at each worst pose; keep best per muscle.
    best: dict[str, PointProjection] = {}
    for cb in combos:
        if cb["worst"] <= 0 or cb["pose"] is None:
            continue
        cname, val = cb["pose"]
        coord = mam.coord_set.get(cname)
        mam.reset_pose()
        mam._set_coord(coord, val, assemble=mam._assemble_needed(cname))
        loc = cb["pp"].get_location()
        ptw = _station_in_frame(state, cb["ppframe"], loc, cb["wframe"])
        margin = margin_base_m + margin_frac * cb["worst"]
        _, pt_new, _, r_point = project_point_outside_cylinder(
            ptw, cb["R"], cb["t"], cb["radius"], margin)
        new_pp = _station_in_frame(state, cb["wframe"],
                                   opensim.Vec3(*pt_new), cb["ppframe"])
        orig = _v(loc)
        disp_mm = float(np.linalg.norm(new_pp - orig) * 1000)
        if disp_mm >= max_displacement_mm:
            if verbose:
                LOG.info("cross-body: %s.%s projection too large (%.2f mm) -- skip",
                         cb["muscle"], cb["ppname"], disp_mm)
            continue
        proj = PointProjection(
            muscle_name=cb["muscle"], path_point_name=cb["ppname"],
            wrap_object_name=cb["wrap"], body_name=cb["ppframe"].getName(),
            original_location=tuple(orig), projected_location=tuple(new_pp),
            displacement_mm=disp_mm, radial_distance=r_point,
            cylinder_radius=cb["radius"], penetration_mm=cb["worst"] * 1000,
            method=(f"cross-body (worst {cb['worst']*1000:.2f} mm at "
                    f"{cname}={np.degrees(val):.1f} deg)"),
        )
        if cb["muscle"] not in best or disp_mm < best[cb["muscle"]].displacement_mm:
            best[cb["muscle"]] = proj
            if verbose:
                LOG.info("cross-body: %s.%s -> project %.2f mm (worst pen %.2f mm)",
                         cb["muscle"], cb["ppname"], disp_mm, cb["worst"] * 1000)
    return list(best.values())
