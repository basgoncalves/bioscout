"""Detect and fix muscle path points that lie inside wrap cylinders.

Ported from the MATLAB ``checkAllPathPointsInsideCylinders`` /
``applyCorrectionSuggestions`` logic (Phase 1 of the original pipeline) plus an
optional motion-free cross-body scan over the coordinate range of motion.

This is the correction that removes the geometry violations responsible for
discontinuous, non-physiological moment arms. Requires ``import opensim``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .geometry import (
    euler_xyz_to_rotation_matrix,
    project_point_outside_cylinder,
)
from .logutil import LOG, timed

try:
    import opensim
except Exception:  # pragma: no cover - opensim only needed at run time
    opensim = None


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class PointProjection:
    muscle_name: str
    path_point_name: str
    wrap_object_name: str
    body_name: str
    original_location: tuple
    projected_location: tuple
    displacement_mm: float
    radial_distance: float
    cylinder_radius: float
    penetration_mm: float
    method: str = "geometry check (point inside cylinder)"


@dataclass
class FixResult:
    projections: list = field(default_factory=list)
    skipped_deep: list = field(default_factory=list)
    output_model: Optional[str] = None
    summary: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _require_opensim():
    if opensim is None:
        raise ImportError(
            "The 'opensim' Python package is required to run wrap_fixer. "
            "Install it (e.g. `conda install -c opensim-org opensim`) and run "
            "this on your local machine."
        )


def _vec3_to_np(v) -> np.ndarray:
    return np.array([v.get(0), v.get(1), v.get(2)], float)


def _muscle_names(model, muscle_filter: Optional[list]) -> list:
    """All muscle names, optionally filtered to those containing any substring."""
    names = []
    muscles = model.getMuscles()
    for i in range(muscles.getSize()):
        name = muscles.get(i).getName()
        if muscle_filter is None or any(f in name for f in muscle_filter):
            names.append(name)
    return names


def find_wrap_object(model, wrap_obj_name: str):
    """Return (wrap_object, owning_body) for a wrap object by name, or (None, None)."""
    body_set = model.getBodySet()
    for i in range(body_set.getSize()):
        body = body_set.get(i)
        wos = body.getWrapObjectSet()
        for j in range(wos.getSize()):
            wo = wos.get(j)
            if wo.getName() == wrap_obj_name:
                return wo, body
    return None, None


# ---------------------------------------------------------------------------
# Phase 1: static same-body geometry check
# ---------------------------------------------------------------------------
def check_points_inside_cylinders(
    model,
    state,
    muscle_names: list,
    max_penetration_mm: float = 5.0,
    margin: float = 0.0001,
    max_displacement_mm: float = 5.0,
    verbose: bool = True,
) -> list[PointProjection]:
    """Find path points inside *same-body* wrap cylinders and propose projections.

    Deep violations (> ``max_penetration_mm``) are reported but not auto-fixed.
    """
    _require_opensim()
    projections: list[PointProjection] = []
    muscles = model.getMuscles()

    for mname in muscle_names:
        muscle = muscles.get(mname)
        geo_path = muscle.getGeometryPath()
        wrap_set = geo_path.getWrapSet()
        pp_set = geo_path.getPathPointSet()

        for w in range(wrap_set.getSize()):
            wrap_obj_name = wrap_set.get(w).getWrapObjectName()
            wrap_obj, wrap_body = find_wrap_object(model, wrap_obj_name)
            if wrap_obj is None:
                continue
            cyl = opensim.WrapCylinder.safeDownCast(wrap_obj)
            if cyl is None:
                continue  # only cylinders are handled

            radius = cyl.get_radius()
            length = cyl.get_length()
            t_cyl = _vec3_to_np(cyl.get_translation())
            r_xyz = cyl.get_xyz_body_rotation()
            R_cyl = euler_xyz_to_rotation_matrix(r_xyz.get(0), r_xyz.get(1), r_xyz.get(2))
            wrap_body_name = wrap_body.getName()

            for p in range(pp_set.getSize()):
                abs_pp = pp_set.get(p)
                if abs_pp.getBody().getName() != wrap_body_name:
                    continue  # static check only for same-body points
                pp = opensim.PathPoint.safeDownCast(abs_pp)
                if pp is None:
                    continue  # moving/conditional points are not edited here

                pt_body = _vec3_to_np(pp.get_location())
                pt_cyl = R_cyl.T @ (pt_body - t_cyl)
                r_point = float(np.hypot(pt_cyl[0], pt_cyl[1]))
                axial = abs(pt_cyl[2])

                inside_radially = r_point < radius
                inside_axially = axial < length / 2.0
                if not (inside_radially and inside_axially):
                    continue

                penetration_mm = (radius - r_point) * 1000.0
                _, pt_new, disp_mm, _ = project_point_outside_cylinder(
                    pt_body, R_cyl, t_cyl, radius, margin
                )

                proj = PointProjection(
                    muscle_name=mname,
                    path_point_name=pp.getName(),
                    wrap_object_name=wrap_obj_name,
                    body_name=wrap_body_name,
                    original_location=tuple(pt_body),
                    projected_location=tuple(pt_new),
                    displacement_mm=disp_mm,
                    radial_distance=r_point,
                    cylinder_radius=radius,
                    penetration_mm=penetration_mm,
                )

                if penetration_mm > max_penetration_mm or disp_mm > max_displacement_mm:
                    if verbose:
                        LOG.info(
                            "SKIP (deep/large): %s.%s inside %s "
                            "(penetration=%.2f mm, disp=%.2f mm)",
                            mname, proj.path_point_name, wrap_obj_name,
                            penetration_mm, disp_mm,
                        )
                    proj.method = "skipped (needs manual review)"
                    # keep it out of the auto-applied list but record it
                    projections.append(proj)
                    continue

                if verbose:
                    LOG.info(
                        "VIOLATION: %s.%s inside %s (r=%.4f < R=%.4f, "
                        "penetration=%.2f mm -> project %.2f mm)",
                        mname, proj.path_point_name, wrap_obj_name,
                        r_point, radius, penetration_mm, disp_mm,
                    )
                projections.append(proj)

    return projections


def apply_projections(model, projections: list[PointProjection], verbose: bool = True) -> int:
    """Apply (write into the model) all auto-fixable projections. Returns count applied."""
    _require_opensim()
    muscles = model.getMuscles()
    applied = 0
    for proj in projections:
        if proj.method.startswith("skipped"):
            continue
        try:
            muscle = muscles.get(proj.muscle_name)
            pp_set = muscle.getGeometryPath().getPathPointSet()
            for p in range(pp_set.getSize()):
                abs_pp = pp_set.get(p)
                if abs_pp.getName() != proj.path_point_name:
                    continue
                pp = opensim.PathPoint.safeDownCast(abs_pp)
                if pp is None:
                    break
                pp.set_location(opensim.Vec3(*proj.projected_location))
                applied += 1
                if verbose:
                    LOG.info("Applied: %s.%s (%.2f mm)",
                             proj.muscle_name, proj.path_point_name, proj.displacement_mm)
                break
        except Exception as exc:  # pragma: no cover
            LOG.error("applying %s.%s: %s", proj.muscle_name, proj.path_point_name, exc)
    return applied


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------
def fix_model(
    input_osim: str,
    output_osim: str,
    muscle_filter: Optional[list] = None,
    max_penetration_mm: float = 5.0,
    verbose: bool = True,
) -> FixResult:
    """Load a model, project path points out of same-body wrap cylinders, save it.

    Parameters
    ----------
    input_osim, output_osim : str
        Paths to the original and corrected ``.osim`` files.
    muscle_filter : list[str] | None
        Substrings to restrict which muscles are checked. ``None`` = all muscles.
    """
    _require_opensim()
    with timed(f"load model {input_osim}"):
        model = opensim.Model(input_osim)
        state = model.initSystem()

    names = _muscle_names(model, muscle_filter)
    LOG.info("Checking %d muscles for path points inside wrap cylinders", len(names))

    with timed("geometry check (path points vs wrap cylinders)"):
        projections = check_points_inside_cylinders(
            model, state, names, max_penetration_mm=max_penetration_mm, verbose=verbose
        )

    fixable = [p for p in projections if not p.method.startswith("skipped")]
    skipped = [p for p in projections if p.method.startswith("skipped")]

    with timed(f"apply {len(fixable)} projections + save corrected model"):
        applied = apply_projections(model, fixable, verbose=verbose)
        model.finalizeConnections()
        model.printToXML(output_osim)

    summary = (
        f"{applied} path points projected outside wrap cylinders; "
        f"{len(skipped)} deep/large violations skipped (manual review). "
        f"Corrected model saved to {output_osim}."
    )
    LOG.i

def fix_model_full(
    input_osim: str,
    output_osim: str,
    muscle_filter: Optional[list] = None,
    max_penetration_mm: float = 5.0,
    cross_body: bool = True,
    coordinate_names: Optional[list] = None,
    suspect_muscles: Optional[set] = None,
    n_pose: int = 30,
    max_displacement_mm: float = 5.0,
    margin_base_m: float = 0.002,
    margin_frac: float = 0.5,
    verbose: bool = True,
) -> FixResult:
    """Static (same-body) fix + optional sweep-driven cross-body fix.

    ``suspect_muscles`` restricts the (expensive) cross-body scan to muscles
    known to have a discontinuity. ``coordinate_names`` are the coordinates whose
    range-of-motion sweeps provide the poses for the cross-body scan.
    """
    _require_opensim()
    from .moment_arms import MomentArmModel, DEFAULT_COORDINATES
    from . import cross_body as _cb

    # --- Phase 1: static, same-body ---
    with timed(f"load model {input_osim}"):
        mam = MomentArmModel(input_osim)
    names = _muscle_names(mam.model, muscle_filter)
    LOG.info("Static check: %d muscles", len(names))
    with timed("static geometry check (same-body)"):
        static = check_points_inside_cylinders(
            mam.model, mam.state, names, max_penetration_mm=max_penetration_mm,
            max_displacement_mm=max_displacement_mm, verbose=verbose)
    fixable = [p for p in static if not p.method.startswith("skipped")]
    skipped = [p for p in static if p.method.startswith("skipped")]
    with timed(f"apply {len(fixable)} static projections + save"):
        apply_projections(mam.model, fixable, verbose=verbose)
        mam.model.finalizeConnections()
        mam.model.printToXML(output_osim)
    all_proj = list(fixable)

    # --- Phase 3: cross-body, sweep-driven ---
    if cross_body:
        coords = coordinate_names or DEFAULT_COORDINATES
        with timed(f"reload static-fixed model {output_osim}"):
            mam2 = MomentArmModel(output_osim)
        names2 = _muscle_names(mam2.model, muscle_filter)
        if suspect_muscles is not None:
            names2 = [n for n in names2 if n in suspect_muscles]
        if not names2:
            LOG.info("cross-body: no suspect muscles to check (skipping)")
        else:
            with timed(f"cross-body scan ({len(names2)} suspect muscles, n_pose={n_pose})"):
                cb_projs = _cb.scan_cross_body(
                    mam2, names2, coords, n_pose=n_pose,
                    max_displacement_mm=max_displacement_mm,
                    margin_base_m=margin_base_m, margin_frac=margin_frac,
                    verbose=verbose)
            if cb_projs:
                with timed(f"apply {len(cb_projs)} cross-body projections + save"):
                    apply_projections(mam2.model, cb_projs, verbose=verbose)
                    mam2.model.finalizeConnections()
                    mam2.model.printToXML(output_osim)
                all_proj += cb_projs

    summary = (
        f"{len(all_proj)} path points projected "
        f"({len(fixable)} static, {len(all_proj) - len(fixable)} cross-body); "
        f"{len(skipped)} deep/large violations skipped. Saved to {output_osim}."
    )
    LOG.info(summary)
    return FixResult(projections=all_proj, skipped_deep=skipped,
                     output_model=output_osim, summary=summary)
