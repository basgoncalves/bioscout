"""
LoadTracker — orchestrator for the load-tracking module.

Ties the pieces together:
    import sessions  →  per-session load (metrics)  →  per-muscle distribution
    (ml_interface)  →  aggregate metrics + per-muscle fatigue  →  PDF report.

Typical use
-----------
    from bioscout.load_tracking import LoadTracker, AthleteProfile

    tracker = LoadTracker(athlete=AthleteProfile(name="Bas", age=30,
                                                 hr_max=190, hr_rest=55))
    tracker.add_files("C:/data/zepp_exports/")      # folder, glob, or list
    tracker.compute()
    tracker.report("load_report.pdf")               # writes the PDF
    print(tracker.summary_text())                   # console summary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .importers import SessionData, AthleteProfile, load_sessions
from .ml_interface import MuscleForceEstimator, HeuristicMuscleEstimator
from . import metrics, fatigue


@dataclass
class LoadResults:
    sessions: list = field(default_factory=list)
    session_loads: list = field(default_factory=list)        # list[dict] from metrics.session_load
    loads: list = field(default_factory=list)                # list[float] unified load
    muscle_loads: list = field(default_factory=list)         # list[{muscle: load}]
    daily: list = field(default_factory=list)                # list[DailyLoad]
    acwr: dict = field(default_factory=dict)
    mono_strain: dict = field(default_factory=dict)
    ff: dict = field(default_factory=dict)                   # fitness-fatigue
    muscle_states: list = field(default_factory=list)        # list[MuscleState]
    recommendations: list = field(default_factory=list)


class LoadTracker:
    def __init__(self, athlete: Optional[AthleteProfile] = None,
                 estimator: Optional[MuscleForceEstimator] = None):
        self.athlete = athlete or AthleteProfile()
        self.estimator = estimator or HeuristicMuscleEstimator()
        self.sessions: list[SessionData] = []
        self.results: Optional[LoadResults] = None

    # ----- ingestion ------------------------------------------------------- #
    def add_files(self, paths) -> int:
        """Add sessions from a folder/glob/list. Returns number of sessions added."""
        new = load_sessions(paths)
        self.sessions.extend(new)
        self.sessions.sort(key=lambda s: s.start_time)
        return len(new)

    def add_session(self, session: SessionData) -> None:
        self.sessions.append(session)
        self.sessions.sort(key=lambda s: s.start_time)

    def add_zepp(self, token: str, region: str = "de2",
                 limit: Optional[int] = None, enrich: bool = True) -> int:
        """Pull sessions straight from your Zepp/Huami cloud account."""
        from .zepp_cloud import pull_zepp
        new = pull_zepp(token, region=region, limit=limit, enrich=enrich)
        self.sessions.extend(new)
        self.sessions.sort(key=lambda s: s.start_time)
        return len(new)

    def add_strava(self, client_id, client_secret, refresh_token,
                   after=None, limit: Optional[int] = None,
                   with_streams: bool = True) -> int:
        """Pull activities from Strava (Zepp → Strava auto-sync)."""
        from .strava_api import pull_strava
        new = pull_strava(client_id, client_secret, refresh_token,
                          after=after, limit=limit, with_streams=with_streams)
        self.sessions.extend(new)
        self.sessions.sort(key=lambda s: s.start_time)
        return len(new)

    # ----- computation ----------------------------------------------------- #
    def compute(self) -> LoadResults:
        if not self.sessions:
            raise ValueError("No sessions loaded. Call add_files()/add_session() first.")

        res = LoadResults(sessions=list(self.sessions))
        for s in self.sessions:
            sl = metrics.session_load(s, self.athlete)
            res.session_loads.append(sl)
            res.loads.append(sl["load"])
            res.muscle_loads.append(self.estimator.estimate(s, sl["load"]))

        res.daily = metrics.daily_series(self.sessions, res.loads)
        res.acwr = metrics.ewma_acwr(res.daily)
        res.mono_strain = metrics.weekly_monotony_strain(res.daily)
        res.ff = metrics.fitness_fatigue(res.daily)
        res.muscle_states = fatigue.compute_muscle_states(self.sessions, res.muscle_loads)
        res.recommendations = fatigue.recovery_recommendation(res.muscle_states)

        self.results = res
        return res

    # ----- outputs --------------------------------------------------------- #
    def report(self, output_path: str, title: Optional[str] = None) -> str:
        if self.results is None:
            self.compute()
        from .report import build_report   # local import (matplotlib heavy)
        return build_report(self.athlete, self.results, output_path, title=title)

    def summary_text(self) -> str:
        if self.results is None:
            self.compute()
        r = self.results
        lines = [
            f"Athlete: {self.athlete.name}",
            f"Sessions: {len(r.sessions)}  "
            f"({r.sessions[0].date} → {r.sessions[-1].date})",
            f"Estimator: {self.estimator.name}",
            "",
            f"Latest ACWR: "
            + (f"{r.acwr['latest_acwr']:.2f} "
               f"({metrics.acwr_status(r.acwr['latest_acwr'])[0]})"
               if r.acwr.get('latest_acwr') is not None else "n/a"),
            f"Weekly load: "
            + (f"{r.mono_strain['weekly_load']:.0f}"
               if r.mono_strain.get('weekly_load') is not None else "n/a"),
            f"Monotony: "
            + (f"{r.mono_strain['monotony']:.2f}"
               if r.mono_strain.get('monotony') is not None else "n/a"),
            f"Fatigue (Banister): "
            + (f"{r.ff['latest_fatigue']:.0f}"
               if r.ff.get('latest_fatigue') is not None else "n/a"),
            "",
            "Most-loaded muscle groups:",
        ]
        for st in r.muscle_states[:5]:
            if st.fatigue_index > 0:
                lines.append(f"  {st.label:<26} {st.fatigue_index:5.1f}/100  "
                             f"({st.status}"
                             + (f", ACWR {st.acwr:.2f}" if st.acwr else "") + ")")
        lines.append("")
        lines.extend(textwrap_indent(r.recommendations))
        return "\n".join(lines)


def textwrap_indent(notes) -> list[str]:
    import textwrap
    out = []
    for n in notes:
        wrapped = textwrap.fill(n, width=78,
                                initial_indent="• ", subsequent_indent="  ")
        out.append(wrapped)
    return out
