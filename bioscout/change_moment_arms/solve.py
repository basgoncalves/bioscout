"""Solve for the wrap radius that produces a requested moment-arm change.

Moment arm is ``dL/dq`` and, once a path wraps, a nonlinear function of the
geometry — so there is no closed form for "the radius that adds 5 mm". This
brackets and bisects on a caller-supplied ``measure(radius) -> curve`` instead,
which keeps every OpenSim call on the caller's side of the seam and makes the
search itself unit-testable against an analytic stub.

The objective is the **mean** change across the sweep rather than the change at
one pose, because the request is "shift the whole curve up", and a single-pose
match can be achieved by a radius that distorts the rest of the range.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence

import numpy as np

__all__ = ["SolveResult", "solve_radius_for_offset", "solve_scalar_for_target"]


@dataclass
class SolveResult:
    ok: bool
    radius: float
    achieved_mm: float
    requested_mm: float
    iterations: int
    history: List[tuple] = field(default_factory=list)
    reason: Optional[str] = None

    @property
    def error_mm(self) -> float:
        return self.achieved_mm - self.requested_mm


def _mean_offset_mm(curve: Sequence[float], baseline: Sequence[float]) -> float:
    a = np.asarray(curve, float)
    b = np.asarray(baseline, float)
    n = min(a.size, b.size)
    if n == 0:
        return float("nan")
    return float(np.nanmean(a[:n] - b[:n]) * 1000.0)     # m -> mm


def _bisect_ready(it):
    """No-op marker: the probe already bracketed the target."""
    return it


def solve_scalar_for_target(
    measure: Callable[[float], Sequence[float]],
    x0: float,
    baseline: Sequence[float],
    *,
    scale: Optional[float] = None,
    offset_mm: Optional[float] = None,
    step: float = 1.0,
    additive: bool = True,
    tol_mm: float = 0.2,
    max_iter: int = 20,
    max_span: float = 50.0,
) -> SolveResult:
    """Generic 1-D search for the parameter that hits a moment-arm target.

    ``measure(x)`` returns the moment-arm curve (metres) for parameter ``x``.
    The parameter can be anything monotonic-ish in moment arm: a wrap radius, or
    the magnitude of a path-point translation.

    Two target kinds, and the distinction matters for a whole-model change:

    * ``scale=k``   -> mean moment arm becomes ``k * baseline mean``. Sign is
      preserved, so abductors (negative here) and adductors (positive) both grow
      in magnitude. This is the right target for "the muscles are bigger".
    * ``offset_mm`` -> mean moment arm becomes ``baseline mean + offset``. Signed,
      so for a muscle whose moment arm is negative a positive offset *shrinks*
      its magnitude. Use ``scale`` unless you mean exactly this.

    ``additive`` brackets by ``x +/- step`` (a translation starting from 0);
    otherwise it brackets multiplicatively (a radius, which cannot cross zero).
    """
    base = np.asarray(list(baseline), float)
    m0 = float(np.nanmean(base))
    if scale is not None:
        target_mm = (m0 * scale - m0) * 1000.0
    elif offset_mm is not None:
        target_mm = float(offset_mm)
    else:
        raise ValueError("pass either scale= or offset_mm=")

    if abs(target_mm) < 1e-9:
        return SolveResult(True, x0, 0.0, target_mm, 0, [(x0, 0.0)])
    if abs(m0) < 1e-5 and scale is not None:
        return SolveResult(False, x0, 0.0, target_mm, 0, [],
                           "baseline moment arm is ~0 — this muscle barely spans "
                           "the coordinate, so a scale factor is meaningless")

    def val_at(x):
        return _mean_offset_mm(measure(x), base)

    history = [(x0, 0.0)]
    lo_x, lo_v = x0, 0.0
    it = 0

    # Which way does this parameter move the moment arm? MEASURE it, do not
    # assume. A muscle whose moment arm is negative about this coordinate (an
    # abductor, here) gets more negative as its wrap grows, so "make it bigger"
    # and "increase the parameter" point the same way — while the sign of the
    # target says the opposite. Assuming cost the whole first run: every
    # negative-moment-arm muscle bracketed away from its target and gave up at
    # the 3x limit.
    it += 1
    probe_x = (x0 + step) if additive else x0 * 1.25
    probe_v = val_at(probe_x)
    history.append((probe_x, probe_v))
    if not np.isfinite(probe_v):
        return SolveResult(False, x0, 0.0, target_mm, it, history,
                           "moment arm became non-finite on the first probe")
    if abs(probe_v) < 1e-12:
        return SolveResult(False, x0, 0.0, target_mm, it, history,
                           "this parameter does not move the moment arm at all")
    # step towards the target: same direction if the probe moved that way
    forward = (probe_v > 0) == (target_mm > 0)
    if forward:
        hi_x, hi_v = probe_x, probe_v
        if (target_mm > 0 and hi_v >= target_mm) or (target_mm < 0 and hi_v <= target_mm):
            lo_x, lo_v = x0, 0.0
            it = _bisect_ready(it)
        else:
            lo_x, lo_v = probe_x, probe_v
    else:
        step = -step
        hi_x, hi_v = x0, 0.0

    grow = target_mm > 0
    reached = forward and ((grow and hi_v >= target_mm) or
                           (not grow and hi_v <= target_mm))
    while not reached and it < max_iter:
        it += 1
        hi_x = (hi_x + step) if additive else hi_x * (1.25 if step > 0 else 0.8)
        if additive and abs(hi_x - x0) > abs(step) * max_span:
            return SolveResult(False, lo_x, lo_v, target_mm, it, history,
                               f"needed a displacement beyond {abs(step)*max_span:.3f} "
                               "— the request is larger than this edit can deliver")
        if not additive and (hi_x > x0 * 3.0 or hi_x < x0 / 3.0):
            return SolveResult(False, lo_x, lo_v, target_mm, it, history,
                               "needed a radius beyond 3x the original — the request "
                               "is larger than this wrap can deliver")
        v = val_at(hi_x)
        history.append((hi_x, v))
        if not np.isfinite(v):
            return SolveResult(False, lo_x, lo_v, target_mm, it, history,
                               "moment arm became non-finite")
        if (grow and v >= target_mm) or (not grow and v <= target_mm):
            hi_v = v
            reached = True
            break
        lo_x, lo_v = hi_x, v
    if not reached:
        return SolveResult(False, lo_x, lo_v, target_mm, it, history,
                           "could not bracket the target — the parameter ran to "
                           "its limit before reaching it, so this change is "
                           "larger than this muscle's geometry can deliver")

    if abs(hi_v - target_mm) <= tol_mm:
        return SolveResult(True, hi_x, hi_v, target_mm, it, history)

    best_x, best_v = hi_x, hi_v
    while it < max_iter:
        it += 1
        mid = 0.5 * (lo_x + hi_x)
        v = val_at(mid)
        history.append((mid, v))
        if abs(v - target_mm) < abs(best_v - target_mm):
            best_x, best_v = mid, v
        if abs(v - target_mm) <= tol_mm:
            return SolveResult(True, mid, v, target_mm, it, history)
        if (grow and v < target_mm) or (not grow and v > target_mm):
            lo_x = mid
        else:
            hi_x = mid
    return SolveResult(False, best_x, best_v, target_mm, it, history,
                       f"did not converge in {max_iter} iterations "
                       f"(closest {best_v:+.2f} vs {target_mm:+.2f} mm)")


def solve_radius_for_offset(
    measure: Callable[[float], Sequence[float]],
    r0: float,
    offset_mm: float,
    *,
    tol_mm: float = 0.2,
    max_iter: int = 20,
    max_factor: float = 3.0,
) -> SolveResult:
    """Find the radius whose mean moment arm sits ``offset_mm`` above baseline.

    ``measure(radius)`` returns the moment-arm curve (in metres) for that
    radius; ``measure(r0)`` defines the baseline.

    Growing a wrap cylinder normally increases the moment arm monotonically, so
    this expands the bracket geometrically and then bisects. A non-monotonic or
    unreachable request stops with ``ok=False`` and the closest radius found —
    the caller reports it rather than silently shipping a model that missed the
    target.
    """
    if r0 <= 0:
        raise ValueError(f"baseline radius must be > 0, got {r0}")
    baseline = list(measure(r0))
    history = [(r0, 0.0)]

    if abs(offset_mm) < 1e-9:
        return SolveResult(True, r0, 0.0, offset_mm, 0, history)

    lo_r, hi_r = r0, r0
    lo_v, hi_v = 0.0, 0.0
    it = 0
    grow = offset_mm > 0

    # -- bracket: expand until the achieved offset passes the request --------
    while it < max_iter:
        it += 1
        hi_r = hi_r * 1.25 if grow else hi_r * 0.8
        if hi_r > r0 * max_factor or hi_r < r0 / max_factor:
            return SolveResult(
                False, lo_r, lo_v, offset_mm, it, history,
                f"needed a radius beyond {max_factor:g}x the original "
                f"({hi_r:.4f} m) — the request is larger than this wrap can "
                "deliver; use the path-translation route or a smaller offset")
        val = _mean_offset_mm(measure(hi_r), baseline)
        history.append((hi_r, val))
        if not np.isfinite(val):
            return SolveResult(False, lo_r, lo_v, offset_mm, it, history,
                               "moment arm became non-finite — the path probably "
                               "lost contact with the wrap surface")
        if (grow and val >= offset_mm) or (not grow and val <= offset_mm):
            hi_v = val
            break
        lo_r, lo_v = hi_r, val
    else:
        return SolveResult(False, lo_r, lo_v, offset_mm, it, history,
                           "could not bracket the requested offset")

    if abs(hi_v - offset_mm) <= tol_mm:
        return SolveResult(True, hi_r, hi_v, offset_mm, it, history)

    # -- bisect --------------------------------------------------------------
    best_r, best_v = (hi_r, hi_v)
    while it < max_iter:
        it += 1
        mid = 0.5 * (lo_r + hi_r)
        val = _mean_offset_mm(measure(mid), baseline)
        history.append((mid, val))
        if abs(val - offset_mm) < abs(best_v - offset_mm):
            best_r, best_v = mid, val
        if abs(val - offset_mm) <= tol_mm:
            return SolveResult(True, mid, val, offset_mm, it, history)
        if (grow and val < offset_mm) or (not grow and val > offset_mm):
            lo_r = mid
        else:
            hi_r = mid
    return SolveResult(False, best_r, best_v, offset_mm, it, history,
                       f"did not converge within {max_iter} iterations "
                       f"(closest: {best_v:+.2f} mm vs {offset_mm:+.2f} mm requested)")
