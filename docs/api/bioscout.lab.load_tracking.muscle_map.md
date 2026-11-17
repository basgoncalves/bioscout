# `bioscout.lab.load_tracking.muscle_map`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/muscle_map.py)

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

## Contents

- [`distribution_for`](#distribution_for) — Return a normalised {muscle_group: fraction} mapping for a session.
- [`distribute_load`](#distribute_load) — Split a scalar session load across muscle groups.

### `distribution_for`

```python
distribution_for(activity: str, raw_sport: str = '', notes: str = '') -> dict
```

| input | type | default |
|---|---|---|
| `activity` | str | required |
| `raw_sport` | str | `''` |
| `notes` | str | `''` |

**returns** `dict`

Return a normalised {muscle_group: fraction} mapping for a session.

For strength sessions, free-text tags in ``notes``/``raw_sport`` (e.g. "leg  
day", "push", "deadlift") refine the default whole-body split.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/muscle_map.py#L116)</sub>

### `distribute_load`

```python
distribute_load(load: float, activity: str, raw_sport: str = '', notes: str = '') -> dict
```

| input | type | default |
|---|---|---|
| `load` | float | required |
| `activity` | str | required |
| `raw_sport` | str | `''` |
| `notes` | str | `''` |

**returns** `dict`

Split a scalar session load across muscle groups.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/muscle_map.py#L132)</sub>
