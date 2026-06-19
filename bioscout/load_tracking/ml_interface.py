"""
Pluggable muscle-force / loading estimator interface.

This is the seam that lets the load-tracking module evolve from heuristic muscle
distribution (today) to the project's real ML / OpenSim / CEINMS muscle-force
pipeline (later) **without changing the report, GUI, or orchestrator code**.

An estimator takes a :class:`SessionData` plus its scalar internal load and
returns a ``{muscle_group: load}`` mapping. The default
:class:`HeuristicMuscleEstimator` uses ``muscle_map.distribute_load``. A future
``OpenSimMuscleEstimator`` (or an ML model trained on your prior data) can plug in
by subclassing :class:`MuscleForceEstimator` and overriding :meth:`estimate`.

    tracker = LoadTracker(athlete, estimator=MyOpenSimEstimator(model="…"))
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .importers import SessionData
from . import muscle_map


class MuscleForceEstimator(ABC):
    """Strategy interface: session + load → per-muscle-group load."""

    name: str = "abstract"

    @abstractmethod
    def estimate(self, session: SessionData, session_load: float) -> dict:
        """Return ``{muscle_group: load}``. Keys should be in
        :data:`muscle_map.MUSCLE_GROUPS` so the report/heatmap stay consistent."""
        raise NotImplementedError

    def supports(self, session: SessionData) -> bool:  # noqa: D401
        """Whether this estimator can handle the session (default: yes)."""
        return True


class HeuristicMuscleEstimator(MuscleForceEstimator):
    """Default: distribute internal load by activity type (see ``muscle_map``)."""

    name = "heuristic-activity-distribution"

    def estimate(self, session: SessionData, session_load: float) -> dict:
        return muscle_map.distribute_load(
            session_load, session.activity,
            raw_sport=session.raw_sport, notes=session.notes,
        )


# --------------------------------------------------------------------------- #
#  Stub for the future model-driven estimator. Intentionally not wired in yet —
#  it documents the integration contract for the OpenSim/CEINMS/ML pipeline.
# --------------------------------------------------------------------------- #
class OpenSimMuscleEstimator(MuscleForceEstimator):
    """Placeholder for model-driven per-muscle loads.

    Intended flow (future work, ties into BioScout's existing pipeline):
      1. If the session has paired kinematics (e.g. from the computer-vision pose
         model or a synced phone capture), run IK → ID → static optimisation /
         CEINMS to get muscle forces.
      2. Otherwise, use a pre-trained regression model (your prior-project data:
         wearable features → muscle-force impulses) to predict per-muscle loads.
      3. Fall back to the heuristic estimator when neither is available.
    """

    name = "opensim-ceinms (not yet implemented)"

    def __init__(self, model_path: str | None = None,
                 fallback: MuscleForceEstimator | None = None):
        self.model_path = model_path
        self.fallback = fallback or HeuristicMuscleEstimator()

    def supports(self, session: SessionData) -> bool:
        return False  # flip to True once the model path is implemented

    def estimate(self, session: SessionData, session_load: float) -> dict:
        # Until implemented, defer to the heuristic estimator so the app keeps working.
        return self.fallback.estimate(session, session_load)
