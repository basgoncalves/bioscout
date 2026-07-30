"""Wire the solver to real OpenSim moment-arm sweeps.

This is the only module here that needs ``opensim``; everything else is pure
file/maths so it can be tested without one. Imports are lazy and the failure is
reported rather than raised, so an environment without OpenSim still gets the
listing and the volume measurements.
"""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

from .solve import SolveResult, solve_radius_for_offset
from .wraps import read_wraps, set_wrap_radii

__all__ = ["Target", "list_targets", "sweep_moment_arm", "apply_offset",
           "apply_to_muscle", "apply_batch", "check_model",
           "list_coordinates", "expand_coordinates"]


@dataclass
class Target:
    """One adjustable (muscle, coordinate) pair and how it can be adjusted."""

    muscle: str
    coordinate: str
    wraps: List[str] = field(default_factory=list)
    peak_ma_mm: Optional[float] = None

    @property
    def route(self) -> str:
        return "wrap radius" if self.wraps else "path translation"


def list_coordinates(model: str | Path) -> List[str]:
    """Every coordinate name in the model — pure XML, so no OpenSim needed.

    Used to validate what the user typed before paying for a sweep: an unknown
    name previously surfaced as "no muscle has a moment arm > 1 mm", which
    points at the wrong problem entirely.
    """
    import xml.etree.ElementTree as ET
    root = ET.parse(Path(model)).getroot()
    out, seen = [], set()
    for c in root.iter("Coordinate"):
        n = c.get("name")
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def expand_coordinates(text: str, model: str | Path) -> tuple:
    """Parse a user coordinate string into validated names.

    Accepts a comma- or space-separated list, and expands a side-less name to
    both sides (``hip_adduction`` -> ``hip_adduction_r``, ``hip_adduction_l``)
    since a bilateral change is the normal case for a gait/lifting study.

    Returns ``(valid, unknown)``.
    """
    known = list_coordinates(model)
    kset = set(known)
    valid, unknown = [], []
    for raw in str(text).replace(",", " ").split():
        raw = raw.strip()
        if not raw:
            continue
        if raw in kset:
            if raw not in valid:
                valid.append(raw)
            continue
        sided = [f"{raw}_{s}" for s in ("r", "l") if f"{raw}_{s}" in kset]
        if sided:
            for c in sided:
                if c not in valid:
                    valid.append(c)
        else:
            unknown.append(raw)
    return valid, unknown


def _sweeps(model, coord, muscles=None, n=40):
    from bioscout.muscle_inspect import moment_arms
    return moment_arms.compute_sweeps(str(model), coordinate_names=[coord],
                                      muscle_filter=muscles, n=n)


def list_targets(model: str | Path, coordinate: str, *, n: int = 12,
                 min_ma_mm: float = 1.0) -> List[Target]:
    """Muscles that genuinely span ``coordinate``, and how each can be changed.

    ``min_ma_mm`` defaults to 1 mm rather than the 0.1 mm used elsewhere: below
    that a "moment arm" is numerical residue from a muscle that does not cross
    the joint at all (gastrocnemius shows ~0.2 mm about the hip), and offering
    it as something to tune is worse than useless.
    """
    wraps_by_muscle: Dict[str, List[str]] = {}
    for name, info in read_wraps(model).items():
        for m in info.muscles:
            if info.scalable:
                wraps_by_muscle.setdefault(m, []).append(name)

    out: List[Target] = []
    sw = _sweeps(model, coordinate, n=n).get(coordinate)
    if sw is None:
        return out
    for muscle, ma in sw.moment_arms.items():
        peak = float(np.nanmax(np.abs(np.asarray(ma, float)))) * 1000.0
        if peak < min_ma_mm:
            continue
        out.append(Target(muscle=muscle, coordinate=coordinate,
                          wraps=sorted(wraps_by_muscle.get(muscle, [])),
                          peak_ma_mm=peak))
    return sorted(out, key=lambda t: -(t.peak_ma_mm or 0))


def sweep_moment_arm(model: str | Path, muscle: str, coordinate: str,
                     n: int = 40) -> np.ndarray:
    """Moment-arm curve (metres) for one muscle about one coordinate."""
    sw = _sweeps(model, coordinate, muscles=[muscle], n=n).get(coordinate)
    if sw is None or muscle not in sw.moment_arms:
        raise KeyError(f"no moment-arm sweep for {muscle} about {coordinate}")
    return np.asarray(sw.moment_arms[muscle], float)


def apply_offset(model: str | Path, out_path: str | Path, muscle: str,
                 coordinate: str, offset_mm: float, *, wraps: Optional[List[str]] = None,
                 n: int = 40, tol_mm: float = 0.2, max_iter: int = 20) -> dict:
    """Grow the muscle's wrap surface(s) until its moment arm rises by ``offset_mm``.

    Every trial radius is written to a scratch copy and swept, so the input
    model is never touched until the search succeeds.
    """
    model, out_path = Path(model), Path(out_path)
    info = read_wraps(model)
    names = wraps or [w for w, i in info.items()
                      if muscle in i.muscles and i.scalable]
    if not names:
        return {"ok": False, "reason":
                f"{muscle} has no scalable wrap surface — use the path-translation "
                "route (paths.translate_path_points) for this muscle",
                "route": "path translation"}
    base = {w: info[w].radius for w in names}
    r0 = float(np.mean(list(base.values())))

    tmpdir = Path(tempfile.mkdtemp(prefix="cma_"))
    trial = tmpdir / model.name
    try:
        def measure(radius: float):
            factor = radius / r0
            set_wrap_radii(model, trial, {w: base[w] * factor for w in names})
            return sweep_moment_arm(trial, muscle, coordinate, n=n)

        res: SolveResult = solve_radius_for_offset(
            measure, r0, offset_mm, tol_mm=tol_mm, max_iter=max_iter)
        factor = res.radius / r0
        final = {w: base[w] * factor for w in names}
        set_wrap_radii(model, trial, final)
        shutil.copy2(trial, out_path)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return {"ok": res.ok, "route": "wrap radius", "model": str(out_path),
            "wraps": {w: (base[w], final[w]) for w in names},
            "radius_factor": factor, "requested_mm": offset_mm,
            "achieved_mm": res.achieved_mm, "error_mm": res.error_mm,
            "iterations": res.iterations, "reason": res.reason}


def check_model(model: str | Path, coordinates: Optional[List[str]] = None,
                n: int = 40) -> dict:
    """Re-run the discontinuity check — inflating a wrap is exactly the edit
    that shoves a path through a bone, so never skip this."""
    from bioscout.muscle_inspect import moment_arms
    sw = moment_arms.compute_sweeps(str(model), coordinate_names=coordinates, n=n)
    bad = moment_arms.discontinuous_muscles(sw)
    return {"discontinuous": sorted(bad), "coordinates": sorted(sw)}


# ---------------------------------------------------------------- batch route
#: Axes probed when choosing which way to move a wrap-less muscle's path.
_PROBE_AXES = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def _muscle_bodies(model, muscle):
    from .paths import read_path_points
    seen, out = set(), []
    for _n, body, _xyz in read_path_points(model, muscle):
        if body and body not in seen:
            seen.add(body)
            out.append(body)
    return out


def _best_translation_direction(model, muscle, coordinate, baseline=None, *,
                                probe_mm=2.0, n=7):
    """Pick (body, axis) whose displacement moves the moment arm most.

    Probes one small displacement per body axis with a deliberately coarse
    sweep — this only has to rank directions, and a fine sweep here would
    multiply the cost of a whole-model run for no extra accuracy. The chosen
    direction is then solved properly at full resolution.

    The probe baseline is re-measured **at the probe resolution**. Comparing a
    7-sample probe curve against the caller's 25-sample baseline is not merely
    a shape mismatch that numpy rejects (it did: "operands could not be
    broadcast together with shapes (7,) (25,)", which skipped every
    translation-route muscle in the first whole-model run) — the two are
    sampled at different joint angles, so even truncating to a common length
    would compare the wrong poses. ``baseline`` is still accepted, and
    ignored, so existing call sites keep working.
    """
    import tempfile
    from .paths import translate_path_points
    from .solve import _mean_offset_mm

    tmp = Path(tempfile.mkdtemp(prefix="cma_dir_")) / Path(model).name
    try:
        try:
            base = sweep_moment_arm(model, muscle, coordinate, n=n)
        except Exception:
            return None
        best = None
        for body in _muscle_bodies(model, muscle):
            for ax in _PROBE_AXES:
                d = np.asarray(ax, float) * (probe_mm / 1000.0)
                try:
                    translate_path_points(model, tmp, muscle, d, bodies=[body])
                    curve = sweep_moment_arm(tmp, muscle, coordinate, n=n)
                except Exception:
                    continue
                dv = _mean_offset_mm(curve, base)
                if not np.isfinite(dv):
                    continue
                if best is None or abs(dv) > abs(best[2]):
                    best = (body, np.asarray(ax, float), dv)
        return best
    finally:
        shutil.rmtree(tmp.parent, ignore_errors=True)


def _target_mm(baseline, scale, offset_mm) -> float:
    """The requested change, in mm, however it was expressed.

    Resolving ``scale`` to millimetres here (rather than passing it down) is
    what lets a run be split across two routes: stage two is asked for the
    *remaining* deficit, which only exists as an absolute number.
    """
    if scale is not None:
        m0 = float(np.nanmean(np.asarray(baseline, float)))
        return (m0 * scale - m0) * 1000.0
    if offset_mm is None:
        raise ValueError("pass either scale= or offset_mm=")
    return float(offset_mm)


def apply_to_muscle(model, out_path, muscle, coordinate, *, scale=None,
                    offset_mm=None, n=25, tol_mm=0.2, max_iter=18,
                    probe_n=7, fallback=True, partial=True,
                    min_fraction=0.25, max_shift_mm=25.0) -> dict:
    """Change one muscle's moment arm, choosing the route automatically.

    Wrap radius when the muscle has a scalable wrap (the mechanism: the surface
    stands in for muscle bulk); otherwise a rigid translation of its path points
    (weaker — it models the attachment moving, not the bulk). The route is
    always reported so a mixed batch stays interpretable.

    Two behaviours keep a whole-model run from collapsing to a handful of
    changed muscles:

    ``fallback``
        A wrap that runs out of room at 3x its radius is not the end of the
        line — the remaining deficit is then chased by translating the path,
        starting from the already-inflated model. The result records
        ``route="wrap radius + path translation"`` so the mixed provenance
        stays visible in the report.

    ``partial``
        When even that cannot reach the target, keep the largest change that
        *was* achievable instead of leaving the muscle untouched. A wrap
        surface has a hard geometric ceiling, so refusing anything short of the
        full request turns a +50% run into a +0% run for most of the model.
        The result carries ``ok=False, applied=True, partial=True`` and the
        achieved fraction, so a shortfall is reported rather than hidden.
        ``min_fraction`` is the floor below which a change is too small to be
        worth keeping.

    ``max_shift_mm`` caps the translation route: past ~25 mm the edit stops
    being "the attachment sits slightly differently" and becomes a different
    muscle.
    """
    from .solve import solve_scalar_for_target
    from .paths import translate_path_points

    model, out_path = Path(model), Path(out_path)
    res = {"muscle": muscle, "coordinate": coordinate, "ok": False,
           "applied": False, "partial": False, "route": None, "reason": None}
    try:
        baseline = sweep_moment_arm(model, muscle, coordinate, n=n)
    except Exception as exc:
        res["reason"] = f"baseline sweep failed: {type(exc).__name__}: {exc}"
        return res
    res["baseline_mm"] = float(np.nanmean(baseline) * 1000.0)
    try:
        want_mm = _target_mm(baseline, scale, offset_mm)
    except ValueError as exc:
        res["reason"] = str(exc)
        return res
    res["requested_mm"] = want_mm
    if abs(want_mm) < 1e-9:
        res.update(ok=True, applied=False, achieved_mm=0.0, error_mm=0.0,
                   iterations=0, reason="no change requested")
        return res

    info = read_wraps(model)
    names = [w for w, i in info.items() if muscle in i.muscles and i.scalable]
    tmpdir = Path(tempfile.mkdtemp(prefix="cma_"))
    trial = tmpdir / model.name
    stage1 = tmpdir / ("s1_" + model.name)
    achieved = 0.0
    iters = 0
    src = model                       # model the next stage edits
    reasons = []
    try:
        if names:                                    # ---- wrap-radius route
            res["route"] = "wrap radius"
            base_r = {w: info[w].radius for w in names}
            r0 = float(np.mean(list(base_r.values())))

            def measure(r):
                set_wrap_radii(model, trial, {w: base_r[w] * (r / r0) for w in names})
                return sweep_moment_arm(trial, muscle, coordinate, n=n)

            sol = solve_scalar_for_target(measure, r0, baseline,
                                          offset_mm=want_mm, additive=False,
                                          tol_mm=tol_mm, max_iter=max_iter)
            factor = sol.radius / r0
            final = {w: base_r[w] * factor for w in names}
            set_wrap_radii(model, stage1, final)
            res.update(wraps={w: (base_r[w], final[w]) for w in names},
                       radius_factor=factor)
            achieved, iters = sol.achieved_mm, sol.iterations
            if sol.reason:
                reasons.append(f"wrap: {sol.reason}")
            if sol.ok:
                shutil.copy2(stage1, out_path)
                res.update(ok=True, applied=True, achieved_mm=achieved,
                           error_mm=achieved - want_mm, iterations=iters)
                return res
            src = stage1              # keep what the wrap did, chase the rest
            if not fallback:
                keep = (partial and abs(achieved) >= abs(want_mm) * min_fraction
                        and achieved * want_mm > 0)
                if keep:
                    shutil.copy2(stage1, out_path)
                res.update(applied=keep, partial=keep, achieved_mm=achieved,
                           error_mm=achieved - want_mm, iterations=iters,
                           fraction=abs(achieved / want_mm),
                           reason="; ".join(reasons))
                return res

        # ---- translation route: primary, or fallback for the wrap deficit --
        remaining = want_mm - achieved
        if abs(remaining) > tol_mm:
            base2 = (baseline if src is model
                     else sweep_moment_arm(src, muscle, coordinate, n=n))
            pick = _best_translation_direction(src, muscle, coordinate, n=probe_n)
            if pick is None:
                reasons.append("no path-point displacement moves this muscle's "
                               "moment arm")
            else:
                body, axis, _dv = pick
                res["body"] = body
                res["axis"] = axis.tolist()

                def measure2(mm):
                    translate_path_points(src, trial, muscle,
                                          axis * (mm / 1000.0), bodies=[body])
                    return sweep_moment_arm(trial, muscle, coordinate, n=n)

                sol2 = solve_scalar_for_target(
                    measure2, 0.0, base2, offset_mm=remaining, step=2.0,
                    additive=True, tol_mm=tol_mm, max_iter=max_iter,
                    max_span=max(1.0, max_shift_mm / 2.0))
                translate_path_points(src, out_path, muscle,
                                      axis * (sol2.radius / 1000.0), bodies=[body])
                res["displacement_mm"] = sol2.radius
                res["route"] = ("wrap radius + path translation" if names
                                else "path translation")
                achieved += sol2.achieved_mm
                iters += sol2.iterations
                if sol2.reason:
                    reasons.append(f"translation: {sol2.reason}")
                if sol2.ok:
                    res.update(ok=True, applied=True, achieved_mm=achieved,
                               error_mm=achieved - want_mm, iterations=iters)
                    return res

        # ---- target unreached: keep the best partial, or leave it alone ----
        frac = abs(achieved / want_mm)
        res.update(achieved_mm=achieved, error_mm=achieved - want_mm,
                   iterations=iters, fraction=frac,
                   reason="; ".join(reasons) or "target not reached")
        keep = partial and frac >= min_fraction and achieved * want_mm > 0
        if keep and src is not model and not out_path.exists():
            shutil.copy2(src, out_path)          # wrap-only partial
        res["applied"] = bool(keep and out_path.exists())
        res["partial"] = res["applied"]
        if not res["applied"]:
            res["reason"] = (f"{res['reason']} — best {achieved:+.2f} of "
                             f"{want_mm:+.2f} mm, below the {min_fraction:.0%} "
                             "floor, left unchanged")
    except Exception as exc:
        res["reason"] = f"{type(exc).__name__}: {exc}"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return res


def apply_batch(model, out_path, muscles, coordinate, *, scale=None,
                offset_mm=None, n=25, probe_n=7, partial=True,
                fallback=True, min_fraction=0.25, log=print) -> dict:
    """Apply the same target to many muscles, accumulating into ONE model.

    Each muscle is solved against the model produced so far, so the edits
    compose. A muscle that fails is reported and skipped rather than aborting
    the run — on a 100-muscle model a single awkward path should not cost you
    the other 99.

    A muscle that only got *part* of the way is kept and reported as PARTIAL:
    the alternative is a run where the request quietly applies to four muscles
    out of seventy, which reads as success and is not.
    """
    model, out_path = Path(model), Path(out_path)
    work = Path(tempfile.mkdtemp(prefix="cma_batch_"))
    cur = work / "cur.osim"
    shutil.copy2(model, cur)
    results = []
    try:
        for i, m in enumerate(muscles, 1):
            nxt = work / "nxt.osim"
            if nxt.exists():
                nxt.unlink()
            r = apply_to_muscle(cur, nxt, m, coordinate, scale=scale,
                                offset_mm=offset_mm, n=n, probe_n=probe_n,
                                partial=partial, fallback=fallback,
                                min_fraction=min_fraction)
            results.append(r)
            if r.get("applied") and nxt.exists():
                shutil.copy2(nxt, cur)
                tag = "" if r.get("ok") else f"  PARTIAL {r.get('fraction', 0):.0%}"
                log(f"[ma] {i:3d}/{len(muscles)} {m:16s} {r['route']:30s} "
                    f"{r['baseline_mm']:+7.1f} -> "
                    f"{r['baseline_mm'] + r['achieved_mm']:+7.1f} mm "
                    f"(err {r['error_mm']:+.2f}){tag}")
            else:
                log(f"[ma] {i:3d}/{len(muscles)} {m:16s} SKIPPED — {r.get('reason')}")
        shutil.copy2(cur, out_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    ok = [r for r in results if r.get("ok")]
    part = [r for r in results if r.get("applied") and not r.get("ok")]
    applied = ok + part
    return {"model": str(out_path), "results": results,
            "n_ok": len(ok), "n_partial": len(part),
            "n_applied": len(applied),
            "n_failed": len(results) - len(applied),
            "routes": {rt: sum(1 for r in applied if r.get("route") == rt)
                       for rt in {r["route"] for r in applied if r.get("route")}}}
