# `bioscout.lab.load_tracking.contraction`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/contraction.py)

Contraction-type work breakdown (heuristic).

Splits each muscle group's mechanical work into **concentric** (positive /  
shortening), **eccentric** (negative / lengthening) and **isometric** (static)  
fractions, by activity type.

Why heuristic: true concentric/eccentric/isometric work needs muscle force ×  
fibre velocity from a musculoskeletal model (OpenSim/CEINMS) — it cannot be  
measured by a wrist tracker. The fractions below are evidence-informed  
approximations of the dominant contraction mode per modality:

    * Cycling is almost purely concentric (no braking phase).  
    * Running/walking use the stretch-shorten cycle — large eccentric component  
      in the calf/quad/hamstring at foot strike; downhill (hiking) skews eccentric.  
    * Resistance training is roughly balanced concentric/eccentric.  
    * Postural/core demand skews isometric.

Per-muscle eccentric bias further nudges "braking" muscles (quads, hamstrings,  
calves, lower back) toward eccentric in gait-type activities.

This sits behind the same estimator seam (``ml_interface``): when the OpenSim /  
CEINMS pipeline is wired in, replace ``work_breakdown_for_session`` with model-  
derived per-muscle positive/negative/isometric work and the report/GUI stay the same.

## Contents

- [`split_for`](#split_for) — Return (concentric, isometric, eccentric) fractions for an activity/muscle.
- [`work_breakdown_for_session`](#work_breakdown_for_session) — Split one session's per-muscle load into contraction-type work.
- [`aggregate_work`](#aggregate_work) — Accumulate contraction-type work per muscle across sessions.

### `split_for`

```python
split_for(activity: str, muscle: str = '') -> tuple[float, float, float]
```

| input | type | default |
|---|---|---|
| `activity` | str | required |
| `muscle` | str | `''` |

**returns** `tuple[float, float, float]`

Return (concentric, isometric, eccentric) fractions for an activity/muscle.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/contraction.py#L52)</sub>

### `work_breakdown_for_session`

```python
work_breakdown_for_session(activity: str, muscle_loads: dict) -> dict
```

| input | type | default |
|---|---|---|
| `activity` | str | required |
| `muscle_loads` | dict | required |

**returns** `dict`

Split one session's per-muscle load into contraction-type work.

``muscle_loads`` is ``{muscle: load}``. Returns  
``{muscle: {"concentric":x, "isometric":y, "eccentric":z, "total":t}}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/contraction.py#L62)</sub>

### `aggregate_work`

```python
aggregate_work(sessions, muscle_loads_per_session) -> dict
```

| input | type | default |
|---|---|---|
| `sessions` | – | required |
| `muscle_loads_per_session` | – | required |

**returns** `dict`

Accumulate contraction-type work per muscle across sessions.

Returns::

    {  
      "per_muscle": {muscle: {concentric, isometric, eccentric, total}},  
      "totals": {concentric, isometric, eccentric, total},  
      "percent": {concentric, isometric, eccentric},   # of total work  
    }

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/contraction.py#L80)</sub>
