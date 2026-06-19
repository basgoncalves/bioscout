"""
Sports-science load metrics for the load-tracking module.

All metrics are well-established in the training-load literature:

    * **TRIMP** (Training Impulse) — internal load from heart rate.
        - Banister TRIMP (HR-reserve weighted, exponential) when a continuous HR
          trace + resting/max HR are available.
        - Edwards summated-zone TRIMP (time in 5 HR zones × zone number) otherwise.
    * **session-RPE load** = RPE(0-10) × duration(min)  [Foster, 2001].
    * **ACWR** (acute:chronic workload ratio) — 7-day acute vs 28-day chronic load.
      The "sweet spot" is ~0.8-1.3; >1.5 is associated with elevated injury risk
      (Gabbett, 2016). Computed here with the EWMA variant (Williams et al., 2017).
    * **Monotony** = mean daily load / SD daily load; **Strain** = weekly load ×
      monotony  [Foster, 2001].
    * **Banister fitness-fatigue** impulse-response model: fitness and fatigue as
      exponentially-decaying sums of past load (τ_fitness≈42 d, τ_fatigue≈7 d).

These are heuristics, not measured muscle forces — see ``ml_interface.py`` for the
hook that lets the real ML/OpenSim muscle-force model replace the muscle layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np

from .importers import SessionData, AthleteProfile


# --------------------------------------------------------------------------- #
#  Per-session internal load (TRIMP / sRPE)
# --------------------------------------------------------------------------- #
def hr_reserve_fraction(hr: float, hr_rest: float, hr_max: float) -> float:
    denom = max(hr_max - hr_rest, 1.0)
    return float(np.clip((hr - hr_rest) / denom, 0.0, 1.0))


def banister_trimp(session: SessionData, athlete: AthleteProfile) -> Optional[float]:
    """Banister TRIMP from a continuous HR trace.

    TRIMP = Σ_i Δt_min,i · HRr_i · 0.64·e^(b·HRr_i),  b=1.92 (M) / 1.67 (F).
    Returns None when there is no usable HR trace.
    """
    hr_rest = athlete.resolved_hr_rest()
    hr_max = athlete.resolved_hr_max()
    b = 1.92 if athlete.sex.upper().startswith("M") else 1.67

    if session.hr.size >= 2 and session.time_s.size == session.hr.size:
        t = session.time_s
        hr = session.hr
        total = 0.0
        for i in range(1, len(t)):
            if not (np.isfinite(hr[i]) and hr[i] > 0):
                continue
            dt_min = (t[i] - t[i - 1]) / 60.0
            if dt_min <= 0 or dt_min > 5:   # guard against gaps
                continue
            hrr = hr_reserve_fraction(hr[i], hr_rest, hr_max)
            total += dt_min * hrr * 0.64 * np.exp(b * hrr)
        return float(total) if total > 0 else None

    # fall back to average-HR formula over the whole session
    if session.avg_hr and session.duration_min > 0:
        hrr = hr_reserve_fraction(session.avg_hr, hr_rest, hr_max)
        return float(session.duration_min * hrr * 0.64 * np.exp(b * hrr))
    return None


def edwards_trimp(session: SessionData, athlete: AthleteProfile) -> Optional[float]:
    """Edwards summated heart-rate-zone TRIMP (zones at 50-60-70-80-90 %HRmax)."""
    hr_max = athlete.resolved_hr_max()
    zones = [0.5, 0.6, 0.7, 0.8, 0.9, 1.01]  # zone i = [zones[i-1], zones[i])

    if session.hr.size >= 2 and session.time_s.size == session.hr.size:
        t, hr = session.time_s, session.hr
        zsum = 0.0
        for i in range(1, len(t)):
            if not (np.isfinite(hr[i]) and hr[i] > 0):
                continue
            dt_min = (t[i] - t[i - 1]) / 60.0
            if dt_min <= 0 or dt_min > 5:
                continue
            frac = hr[i] / hr_max
            z = 0
            for k in range(1, 6):
                if frac >= zones[k - 1]:
                    z = k
            if z:
                zsum += dt_min * z
        return float(zsum) if zsum > 0 else None

    if session.avg_hr and session.duration_min > 0:
        frac = session.avg_hr / hr_max
        z = sum(1 for k in range(1, 6) if frac >= zones[k - 1])
        return float(session.duration_min * z) if z else None
    return None


def srpe_load(session: SessionData) -> Optional[float]:
    """session-RPE load = RPE × duration(min). Needs a manual RPE (0-10)."""
    if session.rpe is not None and session.duration_min > 0:
        return float(session.rpe * session.duration_min)
    return None


def estimate_rpe_from_hr(session: SessionData, athlete: AthleteProfile) -> Optional[float]:
    """Estimate session RPE (0-10) from %HR-reserve when RPE wasn't recorded."""
    if not session.avg_hr:
        return None
    hrr = hr_reserve_fraction(session.avg_hr,
                              athlete.resolved_hr_rest(),
                              athlete.resolved_hr_max())
    return round(float(np.clip(hrr * 10.0, 0.5, 10.0)), 1)


def session_load(session: SessionData, athlete: AthleteProfile) -> dict:
    """Compute every per-session load metric. Returns a dict of named values.

    ``load`` is the unified internal-load figure used downstream (Banister TRIMP
    preferred; Edwards or sRPE as fallback) so that mixed HR/non-HR sessions are
    comparable on one axis.
    """
    bt = banister_trimp(session, athlete)
    et = edwards_trimp(session, athlete)
    srpe = srpe_load(session)
    est_rpe = estimate_rpe_from_hr(session, athlete)

    if bt is not None:
        load, basis = bt, "banister_trimp"
    elif et is not None:
        load, basis = et, "edwards_trimp"
    elif srpe is not None:
        load, basis = srpe, "srpe"
    elif est_rpe is not None and session.duration_min > 0:
        load, basis = est_rpe * session.duration_min, "estimated_srpe"
    else:
        load, basis = 0.0, "none"

    return {
        "banister_trimp": bt,
        "edwards_trimp": et,
        "srpe": srpe,
        "estimated_rpe": est_rpe,
        "load": float(load),
        "basis": basis,
    }


# --------------------------------------------------------------------------- #
#  Time-series / aggregate metrics over a series of sessions
# --------------------------------------------------------------------------- #
@dataclass
class DailyLoad:
    day: date
    load: float = 0.0
    by_activity: dict = field(default_factory=dict)


def daily_series(sessions: list[SessionData], loads: list[float]) -> list[DailyLoad]:
    """Collapse sessions to one load value per calendar day (gaps filled with 0)."""
    if not sessions:
        return []
    agg: dict[date, DailyLoad] = {}
    for s, ld in zip(sessions, loads):
        d = s.date
        if d not in agg:
            agg[d] = DailyLoad(day=d)
        agg[d].load += ld
        agg[d].by_activity[s.activity] = agg[d].by_activity.get(s.activity, 0.0) + ld

    start, end = min(agg), max(agg)
    out: list[DailyLoad] = []
    cur = start
    while cur <= end:
        out.append(agg.get(cur, DailyLoad(day=cur)))
        cur += timedelta(days=1)
    return out


def ewma_acwr(daily: list[DailyLoad],
              acute_tc: int = 7, chronic_tc: int = 28) -> dict:
    """EWMA acute:chronic workload ratio (Williams et al., 2017).

    Returns per-day acute load, chronic load, ACWR, plus the latest values.
    """
    if not daily:
        return {"days": [], "acute": [], "chronic": [], "acwr": [],
                "latest_acwr": None, "latest_acute": None, "latest_chronic": None}

    loads = np.array([d.load for d in daily], float)
    days = [d.day for d in daily]
    la = 2.0 / (acute_tc + 1.0)
    lc = 2.0 / (chronic_tc + 1.0)

    acute = np.zeros_like(loads)
    chronic = np.zeros_like(loads)
    a = c = 0.0
    for i, x in enumerate(loads):
        a = x * la + a * (1 - la)
        c = x * lc + c * (1 - lc)
        acute[i] = a
        chronic[i] = c
    acwr = np.divide(acute, chronic, out=np.zeros_like(acute), where=chronic > 1e-9)

    return {
        "days": days,
        "acute": acute.tolist(),
        "chronic": chronic.tolist(),
        "acwr": acwr.tolist(),
        "latest_acwr": float(acwr[-1]) if chronic[-1] > 1e-9 else None,
        "latest_acute": float(acute[-1]),
        "latest_chronic": float(chronic[-1]),
    }


def weekly_monotony_strain(daily: list[DailyLoad]) -> dict:
    """Monotony & strain for the most recent rolling 7-day window."""
    if len(daily) < 1:
        return {"weekly_load": None, "monotony": None, "strain": None}
    window = [d.load for d in daily[-7:]]
    arr = np.array(window, float)
    weekly = float(arr.sum())
    sd = float(arr.std(ddof=0))
    mean = float(arr.mean())
    monotony = mean / sd if sd > 1e-6 else None
    strain = weekly * monotony if monotony is not None else None
    return {"weekly_load": weekly, "monotony": monotony, "strain": strain}


def fitness_fatigue(daily: list[DailyLoad],
                    tau_fitness: float = 42.0,
                    tau_fatigue: float = 7.0,
                    k_fit: float = 1.0, k_fat: float = 2.0) -> dict:
    """Banister fitness-fatigue impulse-response model.

    fitness(t) = Σ load(τ)·e^-(t-τ)/tau_fitness
    fatigue(t) = Σ load(τ)·e^-(t-τ)/tau_fatigue
    form(t)    = k_fit·fitness - k_fat·fatigue   (a.k.a. "performance potential")

    Returns per-day series plus latest scalars. Fatigue decays ~7 d; fitness ~42 d.
    """
    if not daily:
        return {"days": [], "fitness": [], "fatigue": [], "form": [],
                "latest_fitness": None, "latest_fatigue": None, "latest_form": None}

    loads = np.array([d.load for d in daily], float)
    days = [d.day for d in daily]
    df = np.exp(-1.0 / tau_fitness)
    dg = np.exp(-1.0 / tau_fatigue)

    fitness = np.zeros_like(loads)
    fatigue = np.zeros_like(loads)
    g = h = 0.0
    for i, x in enumerate(loads):
        g = g * df + x
        h = h * dg + x
        fitness[i] = g
        fatigue[i] = h
    form = k_fit * fitness - k_fat * fatigue
    return {
        "days": days,
        "fitness": fitness.tolist(),
        "fatigue": fatigue.tolist(),
        "form": form.tolist(),
        "latest_fitness": float(fitness[-1]),
        "latest_fatigue": float(fatigue[-1]),
        "latest_form": float(form[-1]),
    }


def acwr_status(acwr: Optional[float]) -> tuple[str, str]:
    """Map an ACWR value to (label, matplotlib colour)."""
    if acwr is None:
        return "no data", "#888888"
    if acwr < 0.8:
        return "undertraining", "#3b8ed0"
    if acwr <= 1.3:
        return "optimal", "#2f9e44"
    if acwr <= 1.5:
        return "caution", "#f59f00"
    return "high risk", "#e03131"
