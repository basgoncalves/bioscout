"""Radius-reduction fallback (MATLAB Phase 3, priority 2).

When projecting a path point can't remove a discontinuity (e.g. the wrap solver
flips branches rather than a point sitting inside the cylinder), the next lever
is to shrink the wrap cylinder's radius until the muscle's length/moment-arm
curve becomes smooth. This module binary-searches the largest radius that
removes the discontinuity, for muscles still flagged after the projection passes.

Requires ``import opensim``. Sweeps are done with the same MomentArmModel used
elsewhere, so constraint handling / assemble-skipping are consistent.
"""
from __future__ import annotations

import os
import tempfile
from typing import Optional

from .logutil import LOG, timed
from .discontinuity import detect_discontinuities
from .wrap_fixer import find_wrap_object
from . import wrap_fixer

try:
    import opensim
except Exception:  # pragma: no cover
    opensim = None


def _require_opensim():
    if opensim is None:
        raise ImportError("radius_reduce requires the 'opensim' Python package.")


def _muscle_discontinuous(mam, muscle: str, coords: list, n: int, dk: dict) -> bool:
    """True if the muscle's length or moment-arm curve jumps over any coord sweep."""
    for c in coords:
        if c not in mam._defaults:
            continue
        sw = mam.sweep(c, [muscle], n=n)
        if detect_discontinuities(sw.lengths[muscle], **dk):
            return True
        if detect_discontinuities(sw.moment_arms[muscle], **dk):
            return True
    return False


def _wrap_cylinders_of(model, muscle: str) -> list:
    gp = model.getMuscles().get(muscle).getGeometryPath()
    ws = gp.getWrapSet()
    names = []
    for w in range(ws.getSize()):
        won = ws.get(w).getWrapObjectName()
        wo, _ = find_wrap_object(model, won)
        if wo is not None and opensim.WrapCylinder.safeDownCast(wo) is not None:
            names.append(won)
    return names


def reduce_radii(
    model_path: str, muscles: list, coords: list, dk: dict,
    n: int = 40, min_radius_floor: float = 0.005, max_reduction: float = 0.010,
    tol: float = 0.0005, max_iter: int = 8, verbose: bool = True,
) -> list:
    """Binary-search a smaller radius per muscle until its discontinuity is gone.

    Returns a list of dicts: muscle, wrap, old_radius, new_radius, reduction_mm.
    Tests candidates on temporary models; does not modify ``model_path``.
    """
    _require_opensim()
    from .moment_arms import MomentArmModel

    reductions = []
    for muscle in muscles:
        base = MomentArmModel(model_path)
        wrap_names = _wrap_cylinders_of(base.model, muscle)
        del base
        fixed = False
        for won in wrap_names:
            if fixed:
                break
            probe = MomentArmModel(model_path)
            wo, _ = find_wrap_object(probe.model, won)
            r0 = opensim.WrapCylinder.safeDownCast(wo).get_radius()
            del probe

            lo = max(min_radius_floor, r0 - max_reduction)
            hi = r0
            best = None
            for _ in range(max_iter):
                mid = 0.5 * (lo + hi)
                fd, tmpf = tempfile.mkstemp(suffix=".osim")
                os.close(fd)
                try:
                    m = opensim.Model(model_path)
                    m.initSystem()
                    wo2, _ = find_wrap_object(m, won)
                    opensim.WrapCylinder.safeDownCast(wo2).set_radius(mid)
                    m.finalizeConnections()
                    m.printToXML(tmpf)
                    mam = MomentArmModel(tmpf)
                    disc = _muscle_discontinuous(mam, muscle, coords, n, dk)
                    del mam
                finally:
                    try:
                        os.remove(tmpf)
                    except OSError:
                        pass
                if disc:
                    hi = mid          # still bad -> need smaller
                else:
                    best = mid
                    lo = mid          # works -> try larger (keep as much radius as possible)
                if hi - lo < tol:
                    break
            if best is not None and best < r0:
                reductions.append(dict(muscle=muscle, wrap=won, old_radius=r0,
                                       new_radius=best, reduction_mm=(r0 - best) * 1000))
                fixed = True
                if verbose:
                    LOG.info("radius: %s / %s  %.4f -> %.4f m (-%.2f mm)",
                             muscle, won, r0, best, (r0 - best) * 1000)
        if not fixed and verbose:
            LOG.info("radius: %s not resolved by radius reduction (try quadrant / "
                     "manual review, or it may be a ROM-limit artifact)", muscle)
    return reductions


def apply_radius_reductions(model, reductions: list, verbose: bool = True) -> int:
    _require_opensim()
    applied = 0
    for r in reductions:
        wo, _ = find_wrap_object(model, r["wrap"])
        wc = opensim.WrapCylinder.safeDownCast(wo) if wo is not None else None
        if wc is not None:
            wc.set_radius(r["new_radius"])
            applied += 1
            if verbose:
                LOG.info("applied radius: %s -> %.4f m", r["wrap"], r["new_radius"])
    return applied


def fix_with_radius_reduction(
    input_osim: str, output_osim: str, *,
    muscle_filter: Optional[list] = None, max_penetration_mm: float = 5.0,
    cross_body: bool = True, coordinate_names: Optional[list] = None,
    suspect_muscles: Optional[set] = None, n_pose: int = 30,
    max_displacement_mm: float = 5.0, margin_base_m: float = 0.002,
    margin_frac: float = 0.5, radius_reduction: bool = True,
    detect_kwargs: Optional[dict] = None, rr_n: int = 40, verbose: bool = True,
):
    """Run the projection passes (wrap_fixer.fix_model_full), then -- for any
    suspect muscle still discontinuous -- shrink its wrap cylinder. Returns the
    FixResult, with a ``radius_reductions`` attribute attached.
    """
    res = wrap_fixer.fix_model_full(
        input_osim, output_osim, muscle_filter=muscle_filter,
        max_penetration_mm=max_penetration_mm, cross_body=cross_body,
        coordinate_names=coordinate_names, suspect_muscles=suspect_muscles,
        n_pose=n_pose, max_displacement_mm=max_displacement_mm,
        margin_base_m=margin_base_m, margin_frac=margin_frac, verbose=verbose)
    res.radius_reductions = []
    if not radius_reduction or not suspect_muscles:
        return res

    _require_opensim()
    from .moment_arms import MomentArmModel, DEFAULT_COORDINATES
    coords = coordinate_names or DEFAULT_COORDINATES
    dk = detect_kwargs or {}

    mam = MomentArmModel(output_osim)
    present = set(mam.all_muscle_names(muscle_filter))
    targets = [m for m in suspect_muscles if m in present]
    still = [m for m in targets if _muscle_discontinuous(mam, m, coords, rr_n, dk)]
    del mam
    if not still:
        LOG.info("radius reduction: nothing discontinuous left after projection")
        return res

    with timed(f"radius reduction ({len(still)} muscles)"):
        reductions = reduce_radii(output_osim, still, coords, dk, n=rr_n, verbose=verbose)
    if reductions:
        m = opensim.Model(output_osim)
        m.initSystem()
        apply_radius_reductions(m, reductions, verbose=verbose)
        m.finalizeConnections()
        m.printToXML(output_osim)
        res.radius_reductions = reductions
        res.summary += f"  +{len(reductions)} radius reductions applied."
    else:
        LOG.info("radius reduction: no radius change resolved the remaining muscles")
    return res
