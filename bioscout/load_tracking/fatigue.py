"""
Per-muscle fatigue model.

Takes the per-muscle daily load (built from each session's distributed load) and
computes, for every muscle group:

    * a Banister fatigue signal (7-day decay) and fitness signal (42-day decay),
    * an EWMA acute:chronic workload ratio (ACWR),
    * a 0-100 **fatigue index** combining recent accumulated load with the ACWR
      spike penalty,
    * a recovery/readiness label.

The fatigue index is intentionally a transparent composite, not a measured
quantity. It is normalised *within the athlete's own history* so it reads as
"how loaded is this muscle right now relative to your typical load".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import numpy as np

from .muscle_map import MUSCLE_GROUPS, MUSCLE_LABELS


@dataclass
class MuscleState:
    muscle: str
    label: str
    daily_load: list = field(default_factory=list)     # per-day distributed load
    days: list = field(default_factory=list)
    fitness: float = 0.0
    fatigue: float = 0.0
    acute: float = 0.0
    chronic: float = 0.0
    acwr: Optional[float] = None
    fatigue_index: float = 0.0      # 0-100
    status: str = "fresh"
    color: str = "#2f9e44"


def _ewma_last(loads: np.ndarray, tc: int) -> float:
    lam = 2.0 / (tc + 1.0)
    v = 0.0
    for x in loads:
        v = x * lam + v * (1 - lam)
    return float(v)


def _banister_last(loads: np.ndarray, tau: float) -> float:
    d = np.exp(-1.0 / tau)
    v = 0.0
    for x in loads:
        v = v * d + x
    return float(v)


def _status_from_index(idx: float) -> tuple[str, str]:
    if idx < 25:
        return "fresh", "#2f9e44"
    if idx < 50:
        return "moderate", "#94d82d"
    if idx < 70:
        return "loaded", "#f59f00"
    if idx < 85:
        return "high", "#fd7e14"
    return "very high", "#e03131"


def per_muscle_daily(sessions, muscle_loads_per_session) -> dict:
    """Build a continuous per-day load series per muscle group.

    ``muscle_loads_per_session`` is a list (aligned with ``sessions``) of
    ``{muscle: load}`` dicts. Returns ``{muscle: (days, loads_array)}`` over the
    full date span with zero-filled rest days.
    """
    if not sessions:
        return {m: ([], np.array([])) for m in MUSCLE_GROUPS}

    start = min(s.date for s in sessions)
    end = max(s.date for s in sessions)
    span = (end - start).days + 1
    days = [start + timedelta(days=i) for i in range(span)]
    idx = {d: i for i, d in enumerate(days)}

    series = {m: np.zeros(span) for m in MUSCLE_GROUPS}
    for s, mload in zip(sessions, muscle_loads_per_session):
        i = idx[s.date]
        for m, ld in mload.items():
            if m in series:
                series[m][i] += ld
    return {m: (days, series[m]) for m in MUSCLE_GROUPS}


def compute_muscle_states(sessions, muscle_loads_per_session,
                          tau_fatigue: float = 7.0,
                          tau_fitness: float = 42.0) -> list[MuscleState]:
    """Compute the full fatigue state for every muscle group."""
    daily = per_muscle_daily(sessions, muscle_loads_per_session)

    # First pass: raw Banister fatigue per muscle, to normalise the index across
    # muscles by the busiest muscle's fatigue (keeps the 0-100 scale comparable).
    raw_fatigue = {}
    states: list[MuscleState] = []
    for m in MUSCLE_GROUPS:
        days, loads = daily[m]
        if loads.size == 0 or loads.sum() == 0:
            raw_fatigue[m] = 0.0
            continue
        raw_fatigue[m] = _banister_last(loads, tau_fatigue)

    max_fatigue = max(raw_fatigue.values()) if raw_fatigue else 0.0

    for m in MUSCLE_GROUPS:
        days, loads = daily[m]
        st = MuscleState(muscle=m, label=MUSCLE_LABELS.get(m, m),
                         daily_load=loads.tolist() if loads.size else [],
                         days=days)
        if loads.size == 0 or loads.sum() == 0:
            st.status, st.color = "no load", "#adb5bd"
            states.append(st)
            continue

        st.fatigue = raw_fatigue[m]
        st.fitness = _banister_last(loads, tau_fitness)
        st.acute = _ewma_last(loads, 7)
        st.chronic = _ewma_last(loads, 28)
        st.acwr = (st.acute / st.chronic) if st.chronic > 1e-9 else None

        # Composite index: 80 % normalised recent fatigue + up to 20 % ACWR-spike penalty.
        base = (st.fatigue / max_fatigue) if max_fatigue > 0 else 0.0
        spike = 0.0
        if st.acwr is not None and st.acwr > 1.3:
            spike = min((st.acwr - 1.3) / 0.7, 1.0)   # 1.3→0, 2.0→1
        idx = float(np.clip(80.0 * base + 20.0 * spike, 0.0, 100.0))
        st.fatigue_index = round(idx, 1)
        st.status, st.color = _status_from_index(idx)
        states.append(st)

    # Sort most-fatigued first for the report
    states.sort(key=lambda s: s.fatigue_index, reverse=True)
    return states


def recovery_recommendation(states: list[MuscleState]) -> list[str]:
    """Plain-language recovery notes derived from the muscle states."""
    notes = []
    loaded = [s for s in states if s.fatigue_index >= 70]
    spiking = [s for s in states if s.acwr is not None and s.acwr > 1.5]
    if loaded:
        names = ", ".join(s.label for s in loaded[:4])
        notes.append(f"High accumulated load in: {names}. Prioritise recovery "
                     f"(sleep, protein, mobility) and avoid stacking high-intensity "
                     f"sessions targeting these groups.")
    if spiking:
        names = ", ".join(f"{s.label} (ACWR {s.acwr:.2f})" for s in spiking[:4])
        notes.append(f"Workload spiking faster than your chronic baseline in: "
                     f"{names}. Elevated injury risk — ramp volume more gradually.")
    if not loaded and not spiking:
        notes.append("No muscle group is in the high-fatigue or high-risk band. "
                     "Load is well distributed and within your typical range.")
    return notes
