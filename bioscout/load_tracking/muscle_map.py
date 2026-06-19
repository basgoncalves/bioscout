"""
Activity → muscle-group load distribution.

A session's internal load (TRIMP / sRPE, from ``metrics.py``) is distributed onto
muscle groups according to its activity type. The weights below are an
evidence-informed first approximation of *relative muscular involvement* by
modality (e.g. running loads the calf/quad/hamstring/glute chain; cycling is
quad/glute dominant; rowing recruits the posterior chain plus upper body). They
sum to ~1.0 per activity so that "load" is conserved when distributed.

This is deliberately a thin, transparent layer. The real per-muscle forces will
come from the OpenSim / CEINMS / ML pipeline via ``ml_interface.py``; this map is
the heuristic default and the fallback when no kinematic data is available.

Muscle groups (kept coarse on purpose — they map cleanly onto OpenSim muscle sets
later, e.g. quadriceps → {rect_fem, vas_med, vas_int, vas_lat}):
    quadriceps, hamstrings, gluteals, calves, hip_flexors, adductors,
    lower_back, core, upper_back, shoulders, chest, arms
"""

from __future__ import annotations

MUSCLE_GROUPS = (
    "quadriceps", "hamstrings", "gluteals", "calves", "hip_flexors",
    "adductors", "lower_back", "core", "upper_back", "shoulders", "chest", "arms",
)

# Human-friendly labels for the report
MUSCLE_LABELS = {
    "quadriceps": "Quadriceps",
    "hamstrings": "Hamstrings",
    "gluteals": "Gluteals",
    "calves": "Calves (gastroc/soleus)",
    "hip_flexors": "Hip flexors",
    "adductors": "Adductors",
    "lower_back": "Lower back (erectors)",
    "core": "Core / abdominals",
    "upper_back": "Upper back (lats/traps)",
    "shoulders": "Shoulders (deltoids)",
    "chest": "Chest (pectorals)",
    "arms": "Arms (biceps/triceps)",
}

# Relative involvement per canonical activity type. Rows need not be exactly 1.0;
# they are normalised at use time.
_DISTRIBUTION = {
    "running": {
        "quadriceps": 0.22, "hamstrings": 0.20, "gluteals": 0.18, "calves": 0.22,
        "hip_flexors": 0.08, "core": 0.06, "lower_back": 0.04,
    },
    "walking": {
        "quadriceps": 0.20, "hamstrings": 0.16, "gluteals": 0.20, "calves": 0.22,
        "hip_flexors": 0.10, "core": 0.06, "lower_back": 0.06,
    },
    "hiking": {
        "quadriceps": 0.24, "hamstrings": 0.16, "gluteals": 0.20, "calves": 0.20,
        "hip_flexors": 0.08, "core": 0.06, "lower_back": 0.06,
    },
    "cycling": {
        "quadriceps": 0.34, "gluteals": 0.22, "hamstrings": 0.16, "calves": 0.14,
        "hip_flexors": 0.08, "core": 0.04, "lower_back": 0.02,
    },
    "rowing": {
        "quadriceps": 0.18, "gluteals": 0.14, "hamstrings": 0.10, "lower_back": 0.12,
        "upper_back": 0.16, "core": 0.10, "arms": 0.12, "shoulders": 0.08,
    },
    "swimming": {
        "upper_back": 0.20, "shoulders": 0.22, "chest": 0.16, "arms": 0.14,
        "core": 0.12, "gluteals": 0.08, "hamstrings": 0.04, "quadriceps": 0.04,
    },
    "elliptical": {
        "quadriceps": 0.22, "hamstrings": 0.16, "gluteals": 0.18, "calves": 0.14,
        "hip_flexors": 0.08, "core": 0.06, "upper_back": 0.06, "arms": 0.06,
        "chest": 0.04,
    },
    "strength": {
        # Whole-body default for mixed gym sessions; override per-session with
        # session.notes tags (see tagged_strength_distribution) when known.
        "quadriceps": 0.14, "hamstrings": 0.10, "gluteals": 0.12, "lower_back": 0.10,
        "core": 0.10, "upper_back": 0.12, "shoulders": 0.10, "chest": 0.10,
        "arms": 0.08, "calves": 0.04,
    },
    "generic": {
        # Even-ish whole-body spread when the modality is unknown.
        "quadriceps": 0.14, "hamstrings": 0.12, "gluteals": 0.12, "calves": 0.10,
        "core": 0.10, "lower_back": 0.08, "upper_back": 0.10, "shoulders": 0.08,
        "chest": 0.08, "arms": 0.08,
    },
}

# Recognised free-text tags for targeted strength sessions (matched in notes/raw_sport).
_STRENGTH_TAGS = {
    "leg": {"quadriceps": 0.30, "hamstrings": 0.22, "gluteals": 0.24,
            "calves": 0.12, "adductors": 0.08, "core": 0.04},
    "lower": {"quadriceps": 0.28, "hamstrings": 0.22, "gluteals": 0.24,
              "calves": 0.12, "lower_back": 0.08, "core": 0.06},
    "squat": {"quadriceps": 0.34, "gluteals": 0.26, "hamstrings": 0.16,
              "lower_back": 0.10, "core": 0.08, "calves": 0.06},
    "deadlift": {"hamstrings": 0.26, "gluteals": 0.24, "lower_back": 0.22,
                 "upper_back": 0.12, "core": 0.10, "quadriceps": 0.06},
    "push": {"chest": 0.32, "shoulders": 0.30, "arms": 0.26, "core": 0.12},
    "pull": {"upper_back": 0.38, "arms": 0.30, "shoulders": 0.16, "core": 0.16},
    "upper": {"chest": 0.22, "upper_back": 0.22, "shoulders": 0.22, "arms": 0.22,
              "core": 0.12},
    "core": {"core": 0.55, "lower_back": 0.25, "hip_flexors": 0.20},
}


def _normalise(weights: dict) -> dict:
    total = sum(weights.values())
    if total <= 0:
        return {}
    return {m: w / total for m, w in weights.items()}


def distribution_for(activity: str, raw_sport: str = "", notes: str = "") -> dict:
    """Return a normalised {muscle_group: fraction} mapping for a session.

    For strength sessions, free-text tags in ``notes``/``raw_sport`` (e.g. "leg
    day", "push", "deadlift") refine the default whole-body split.
    """
    activity = (activity or "generic").lower()
    if activity == "strength":
        text = f"{raw_sport} {notes}".lower()
        for tag, w in _STRENGTH_TAGS.items():
            if tag in text:
                return _normalise(dict(w))
    base = _DISTRIBUTION.get(activity, _DISTRIBUTION["generic"])
    return _normalise(dict(base))


def distribute_load(load: float, activity: str,
                    raw_sport: str = "", notes: str = "") -> dict:
    """Split a scalar session load across muscle groups."""
    dist = distribution_for(activity, raw_sport, notes)
    return {m: load * f for m, f in dist.items()}
