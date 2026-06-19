"""
BioScout — Load Tracking module
================================

Import training sessions from a fitness tracker (Amazfit / Zepp, Garmin, Strava,
etc.), estimate musculoskeletal loading and fatigue with validated sports-science
metrics, and produce a PDF report.

Design (hybrid, per the project goals):
    * Heuristic, interpretable load metrics ship today — TRIMP, session-RPE load,
      acute:chronic workload ratio (ACWR), monotony / strain, and a Banister
      fitness-fatigue impulse-response model.
    * A per-muscle-group distribution maps each session's load onto muscle groups
      by activity type, giving per-muscle accumulated load and fatigue.
    * A pluggable ``MuscleForceEstimator`` interface (``ml_interface.py``) lets the
      heuristic muscle layer be swapped later for the real ML / OpenSim / CEINMS
      muscle-force pipeline without changing the report or GUI code.

Public API
----------
    from bioscout.load_tracking import LoadTracker, load_sessions, SessionData

    tracker = LoadTracker(athlete=AthleteProfile(age=30, hr_max=190, hr_rest=55))
    tracker.add_files("path/to/sessions/")      # folder or list of files
    tracker.compute()
    tracker.report("load_report.pdf")
"""

from .importers import (
    SessionData,
    AthleteProfile,
    load_session_file,
    load_sessions,
    SUPPORTED_EXTENSIONS,
)
from .tracker import LoadTracker
from .ml_interface import MuscleForceEstimator, HeuristicMuscleEstimator
from .connect import load_credentials, pull_into_tracker

__all__ = [
    "SessionData",
    "AthleteProfile",
    "LoadTracker",
    "MuscleForceEstimator",
    "HeuristicMuscleEstimator",
    "load_session_file",
    "load_sessions",
    "load_credentials",
    "pull_into_tracker",
    "SUPPORTED_EXTENSIONS",
]
