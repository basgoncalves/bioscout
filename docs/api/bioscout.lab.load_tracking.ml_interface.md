# `bioscout.lab.load_tracking.ml_interface`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/ml_interface.py)

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

## Contents

- class [`MuscleForceEstimator`](#muscleforceestimator) — Strategy interface: session + load → per-muscle-group load.
  - [`MuscleForceEstimator.estimate`](#muscleforceestimatorestimate) — Return ``{muscle_group: load}``. Keys should be in :data:`muscle_map.MUSCLE_GROUPS` so the report/heatmap stay consistent.
  - [`MuscleForceEstimator.supports`](#muscleforceestimatorsupports) — Whether this estimator can handle the session (default: yes).
- class [`HeuristicMuscleEstimator`](#heuristicmuscleestimator) — Default: distribute internal load by activity type (see ``muscle_map``).
  - [`HeuristicMuscleEstimator.estimate`](#heuristicmuscleestimatorestimate) — 
- class [`OpenSimMuscleEstimator`](#opensimmuscleestimator) — Placeholder for model-driven per-muscle loads.
  - [`OpenSimMuscleEstimator.supports`](#opensimmuscleestimatorsupports) — 
  - [`OpenSimMuscleEstimator.estimate`](#opensimmuscleestimatorestimate) — 

<a id="muscleforceestimator"></a>

## class `MuscleForceEstimator`(ABC)

Strategy interface: session + load → per-muscle-group load.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/ml_interface.py#L25)</sub>

<a id="muscleforceestimatorestimate"></a>

### `MuscleForceEstimator.estimate`

```python
MuscleForceEstimator.estimate(session: SessionData, session_load: float) -> dict
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |
| `session_load` | float | required |

**returns** `dict`

Return ``{muscle_group: load}``. Keys should be in  
:data:`muscle_map.MUSCLE_GROUPS` so the report/heatmap stay consistent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/ml_interface.py#L31)</sub>

<a id="muscleforceestimatorsupports"></a>

### `MuscleForceEstimator.supports`

```python
MuscleForceEstimator.supports(session: SessionData) -> bool
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |

**returns** `bool`

Whether this estimator can handle the session (default: yes).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/ml_interface.py#L36)</sub>

<a id="heuristicmuscleestimator"></a>

## class `HeuristicMuscleEstimator`(MuscleForceEstimator)

Default: distribute internal load by activity type (see ``muscle_map``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/ml_interface.py#L41)</sub>

<a id="heuristicmuscleestimatorestimate"></a>

### `HeuristicMuscleEstimator.estimate`

```python
HeuristicMuscleEstimator.estimate(session: SessionData, session_load: float) -> dict
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |
| `session_load` | float | required |

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/ml_interface.py#L46)</sub>

<a id="opensimmuscleestimator"></a>

## class `OpenSimMuscleEstimator`(MuscleForceEstimator)

```python
OpenSimMuscleEstimator(
    model_path: str | None = None,
    fallback: MuscleForceEstimator | None = None
)
```

| input | type | default |
|---|---|---|
| `model_path` | str \| None | `None` |
| `fallback` | MuscleForceEstimator \| None | `None` |

Placeholder for model-driven per-muscle loads.

Intended flow (future work, ties into BioScout's existing pipeline):  
  1. If the session has paired kinematics (e.g. from the computer-vision pose  
     model or a synced phone capture), run IK → ID → static optimisation /  
     CEINMS to get muscle forces.  
  2. Otherwise, use a pre-trained regression model (your prior-project data:  
     wearable features → muscle-force impulses) to predict per-muscle loads.  
  3. Fall back to the heuristic estimator when neither is available.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/ml_interface.py#L57)</sub>

<a id="opensimmuscleestimatorsupports"></a>

### `OpenSimMuscleEstimator.supports`

```python
OpenSimMuscleEstimator.supports(session: SessionData) -> bool
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/ml_interface.py#L76)</sub>

<a id="opensimmuscleestimatorestimate"></a>

### `OpenSimMuscleEstimator.estimate`

```python
OpenSimMuscleEstimator.estimate(session: SessionData, session_load: float) -> dict
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |
| `session_load` | float | required |

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/ml_interface.py#L79)</sub>
