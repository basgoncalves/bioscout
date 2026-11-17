# `bioscout.lab.load_tracking.fatigue`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/fatigue.py)

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

## Contents

- class [`MuscleState`](#musclestate) — 
- [`per_muscle_daily`](#per_muscle_daily) — Build a continuous per-day load series per muscle group.
- [`compute_muscle_states`](#compute_muscle_states) — Compute the full fatigue state for every muscle group.
- [`recovery_recommendation`](#recovery_recommendation) — Plain-language recovery notes derived from the muscle states.

<a id="musclestate"></a>

## class `MuscleState`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/fatigue.py#L30)</sub>

### `per_muscle_daily`

```python
per_muscle_daily(sessions, muscle_loads_per_session) -> dict
```

| input | type | default |
|---|---|---|
| `sessions` | – | required |
| `muscle_loads_per_session` | – | required |

**returns** `dict`

Build a continuous per-day load series per muscle group.

``muscle_loads_per_session`` is a list (aligned with ``sessions``) of  
``{muscle: load}`` dicts. Returns ``{muscle: (days, loads_array)}`` over the  
full date span with zero-filled rest days.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/fatigue.py#L73)</sub>

### `compute_muscle_states`

```python
compute_muscle_states(
    sessions,
    muscle_loads_per_session,
    tau_fatigue: float = 7.0,
    tau_fitness: float = 42.0
) -> list[MuscleState]
```

| input | type | default |
|---|---|---|
| `sessions` | – | required |
| `muscle_loads_per_session` | – | required |
| `tau_fatigue` | float | `7.0` |
| `tau_fitness` | float | `42.0` |

**returns** `list[MuscleState]`

Compute the full fatigue state for every muscle group.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/fatigue.py#L98)</sub>

### `recovery_recommendation`

```python
recovery_recommendation(states: list[MuscleState]) -> list[str]
```

| input | type | default |
|---|---|---|
| `states` | list[MuscleState] | required |

**returns** `list[str]`

Plain-language recovery notes derived from the muscle states.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/fatigue.py#L148)</sub>
