"""
Contraction-type work breakdown (heuristic).

Splits each muscle group's mechanical work into **concentric** (positive /
shortening), **eccentric** (negative / lengthening) and **isometric** (static)
fractions, by activity type.

Why heuristic: true concentric/eccentric/isometric work needs muscle force ×
fibre velocity from a musculoskeletal model (OpenSim/CEINMS) — it cannot be
measured by a wrist tracker. The fractions below are evidence-informed
approximations of the dominant contraction mode per modality:

    * Cycling is almost purely concentric (no braking phase).
    * Running/walking use the stretch-shorten cycle — large eccentric component
      in the calf/quad/hamstring at foot strike; downhill (hiking) skews eccentric.
    * Resistance training is roughly balanced concentric/eccentric.
    * Postural/core demand skews isometric.

Per-muscle eccentric bias further nudges "braking" muscles (quads, hamstrings,
calves, lower back) toward eccentric in gait-type activities.

This sits behind the same estimator seam (``ml_interface``): when the OpenSim /
CEINMS pipeline is wired in, replace ``work_breakdown_for_session`` with model-
derived per-muscle positive/negative/isometric work and the report/GUI stay the same.
"""

from __future__ import annotations

from .muscle_map import MUSCLE_GROUPS

# (concentric, isometric, eccentric) — must sum to 1.0 per activity.
CONTRACTION_SPLIT = {
    "running":    (0.45, 0.15, 0.40),
    "walking":    (0.45, 0.20, 0.35),
    "hiking":     (0.40, 0.18, 0.42),   # descents add eccentric load
    "cycling":    (0.80, 0.15, 0.05),   # concentric-dominant, minimal braking
    "rowing":     (0.62, 0.18, 0.20),
    "swimming":   (0.70, 0.18, 0.12),
    "elliptical": (0.60, 0.18, 0.22),
    "strength":   (0.45, 0.10, 0.45),   # balanced lifting/lowering
    "generic":    (0.50, 0.20, 0.30),
}

# Muscles that act as "brakes" pick up extra eccentric share in gait activities
# (running/walking/hiking). Value = fraction of that muscle's concentric work
# reassigned to eccentric.
_ECC_BIAS_MUSCLES = {"quadriceps", "hamstrings", "calves", "lower_back"}
_GAIT_ACTIVITIES = {"running", "walking", "hiking"}
_ECC_BIAS = 0.15


def split_for(activity: str, muscle: str = "") -> tuple[float, float, float]:
    """Return (concentric, isometric, eccentric) fractions for an activity/muscle."""
    conc, iso, ecc = CONTRACTION_SPLIT.get(activity, CONTRACTION_SPLIT["generic"])
    if activity in _GAIT_ACTIVITIES and muscle in _ECC_BIAS_MUSCLES:
        shift = conc * _ECC_BIAS
        conc -= shift
        ecc += shift
    return conc, iso, ecc


def work_breakdown_for_session(activity: str, muscle_loads: dict) -> dict:
    """Split one session's per-muscle load into contraction-type work.

    ``muscle_loads`` is ``{muscle: load}``. Returns
    ``{muscle: {"concentric":x, "isometric":y, "eccentric":z, "total":t}}``.
    """
    out = {}
    for muscle, load in muscle_loads.items():
        conc, iso, ecc = split_for(activity, muscle)
        out[muscle] = {
            "concentric": load * conc,
            "isometric": load * iso,
            "eccentric": load * ecc,
            "total": load,
        }
    return out


def aggregate_work(sessions, muscle_loads_per_session) -> dict:
    """Accumulate contraction-type work per muscle across sessions.

    Returns::

        {
          "per_muscle": {muscle: {concentric, isometric, eccentric, total}},
          "totals": {concentric, isometric, eccentric, total},
          "percent": {concentric, isometric, eccentric},   # of total work
        }
    """
    per_muscle = {m: {"concentric": 0.0, "isometric": 0.0,
                      "eccentric": 0.0, "total": 0.0} for m in MUSCLE_GROUPS}
    for sess, mload in zip(sessions, muscle_loads_per_session):
        wb = work_breakdown_for_session(sess.activity, mload)
        for m, parts in wb.items():
            if m not in per_muscle:
                per_muscle[m] = {"concentric": 0.0, "isometric": 0.0,
                                 "eccentric": 0.0, "total": 0.0}
            for k in ("concentric", "isometric", "eccentric", "total"):
                per_muscle[m][k] += parts[k]

    totals = {"concentric": 0.0, "isometric": 0.0, "eccentric": 0.0, "total": 0.0}
    for parts in per_muscle.values():
        for k in totals:
            totals[k] += parts[k]

    t = totals["total"] or 1.0
    percent = {
        "concentric": 100.0 * totals["concentric"] / t,
        "isometric": 100.0 * totals["isometric"] / t,
        "eccentric": 100.0 * totals["eccentric"] / t,
    }
    # drop muscles with no work for tidy reporting
    per_muscle = {m: v for m, v in per_muscle.items() if v["total"] > 0}
    return {"per_muscle": per_muscle, "totals": totals, "percent": percent}
