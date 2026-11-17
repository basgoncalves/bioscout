# `bioscout.lab.load_tracking`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/__init__.py)

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

  
**Public API**

    from bioscout.lab.load_tracking import LoadTracker, load_sessions, SessionData

    tracker = LoadTracker(athlete=AthleteProfile(age=30, hr_max=190, hr_rest=55))  
    tracker.add_files("path/to/sessions/")      # folder or list of files  
    tracker.compute()  
    tracker.report("load_report.pdf")

## Available as `bioscout.lab.load_tracking.<name>`

- [`bioscout.lab.load_tracking.SessionData`](bioscout.lab.load_tracking.importers.md#sessiondata) — from `bioscout.lab.load_tracking.importers`
- [`bioscout.lab.load_tracking.AthleteProfile`](bioscout.lab.load_tracking.importers.md#athleteprofile) — from `bioscout.lab.load_tracking.importers`
- [`bioscout.lab.load_tracking.load_session_file`](bioscout.lab.load_tracking.importers.md#load_session_file) — from `bioscout.lab.load_tracking.importers`
- [`bioscout.lab.load_tracking.load_sessions`](bioscout.lab.load_tracking.importers.md#load_sessions) — from `bioscout.lab.load_tracking.importers`
- [`bioscout.lab.load_tracking.SUPPORTED_EXTENSIONS`](bioscout.lab.load_tracking.importers.md#supported_extensions) — from `bioscout.lab.load_tracking.importers`
- [`bioscout.lab.load_tracking.LoadTracker`](bioscout.lab.load_tracking.tracker.md#loadtracker) — from `bioscout.lab.load_tracking.tracker`
- [`bioscout.lab.load_tracking.MuscleForceEstimator`](bioscout.lab.load_tracking.ml_interface.md#muscleforceestimator) — from `bioscout.lab.load_tracking.ml_interface`
- [`bioscout.lab.load_tracking.HeuristicMuscleEstimator`](bioscout.lab.load_tracking.ml_interface.md#heuristicmuscleestimator) — from `bioscout.lab.load_tracking.ml_interface`
- [`bioscout.lab.load_tracking.load_credentials`](bioscout.lab.load_tracking.connect.md#load_credentials) — from `bioscout.lab.load_tracking.connect`
- [`bioscout.lab.load_tracking.pull_into_tracker`](bioscout.lab.load_tracking.connect.md#pull_into_tracker) — from `bioscout.lab.load_tracking.connect`
