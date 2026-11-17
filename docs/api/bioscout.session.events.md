# `bioscout.session.events`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/events.py)

Gait/task events from editable definitions, not from code.

Which instants a figure shows (hip drive, impact peak, bottom of a squat ...)  
is a METHODS decision, so it lives in data: ``bioscout/session/events.yaml``  
ships the defaults per task, ``project.yaml`` overrides them for a project  
under ``events:`` and ``session.yaml`` for one session. The keys and their  
meaning are documented at the top of ``events.yaml``.

The task, its cycle and its phases come from the movement detector  
(``2_experimental/<trial>/movement_detection.yaml``); the signals from the  
trial's IK ``.mot`` and ``grf.mot``. Nothing here re-detects foot contacts.

    >>> defs = load_definitions(project_dir, session_dir)  
    >>> ev = resolve_events(defs["running"], "r", phases, signals)  
    >>> [(e.name, e.time, e.letter) for e in ev]

``bioscout session events TRIAL`` prints what a trial resolves to.

## Contents

- class [`Event`](#event) — 
- [`load_definitions`](#load_definitions) — {task: {event name: spec}} after the three tiers are merged.
- [`trial_signals`](#trial_signals) — name -> (t, values). IK columns in DEGREES (pelvis translations in m); ``grf_vertical_{l,r}`` and ``grf_anterior_{l,r}`` in N when GRF is given as ``(t, {side: vy}, {side: vx})`` (what ``jcf_coverage.grf_for`` returns).
- [`trial_phases`](#trial_phases) — (task, {phase: (start, end)}) from a movement_detection.yaml dict, for the analysed leg, restricted to [t0, t1]: the cycle's ``stance`` gives swing/stance; a squat's ``tasks[].phases`` give descent/hold/ concentric. ``cycle`` is always the window itself.
- [`resolve_events`](#resolve_events) — Every event in ``defs`` that the data supports, sorted by time. Missing signal/phase: skipped when ``optional``, else raises in strict mode and is skipped (with a stderr note) otherwise.
- [`events_for_trial`](#events_for_trial) — (task, phases, [Event]) for ``.../3_iterations/<it>/<trial>`` or ``.../2_experimental/<trial>``. Uses jcf_coverage's discovery so the same IK/GRF files feed both the figure and this listing.

<a id="event"></a>

## class `Event`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/events.py#L40)</sub>

### `load_definitions`

```python
load_definitions(project_dir=None, session_dir=None, defaults=None) -> dict
```

| input | type | default |
|---|---|---|
| `project_dir` | – | `None` |
| `session_dir` | – | `None` |
| `defaults` | – | `None` |

**returns** `dict`

{task: {event name: spec}} after the three tiers are merged.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/events.py#L82)</sub>

### `trial_signals`

```python
trial_signals(ik_names, ik_data, degrees, grf=None) -> dict
```

| input | type | default |
|---|---|---|
| `ik_names` | – | required |
| `ik_data` | – | required |
| `degrees` | – | required |
| `grf` | – | `None` |

**returns** `dict`

name -> (t, values). IK columns in DEGREES (pelvis translations in m);  
``grf_vertical_{l,r}`` and ``grf_anterior_{l,r}`` in N when GRF is given  
as ``(t, {side: vy}, {side: vx})`` (what ``jcf_coverage.grf_for`` returns).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/events.py#L116)</sub>

### `trial_phases`

```python
trial_phases(det: dict, side: str, t0: float, t1: float) -> tuple
```

| input | type | default |
|---|---|---|
| `det` | dict | required |
| `side` | str | required |
| `t0` | float | required |
| `t1` | float | required |

**returns** `tuple`

(task, {phase: (start, end)}) from a movement_detection.yaml dict,  
for the analysed leg, restricted to [t0, t1]: the cycle's ``stance``  
gives swing/stance; a squat's ``tasks[].phases`` give descent/hold/  
concentric. ``cycle`` is always the window itself.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/events.py#L145)</sub>

### `resolve_events`

```python
resolve_events(defs: dict, side: str, phases: dict, signals: dict, strict=False) -> list
```

| input | type | default |
|---|---|---|
| `defs` | dict | required |
| `side` | str | required |
| `phases` | dict | required |
| `signals` | dict | required |
| `strict` | – | `False` |

**returns** `list`

Every event in ``defs`` that the data supports, sorted by time.  
Missing signal/phase: skipped when ``optional``, else raises in strict  
mode and is skipped (with a stderr note) otherwise.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/events.py#L231)</sub>

### `events_for_trial`

```python
events_for_trial(trial, side=None, t0=None, t1=None, strict=False)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |
| `side` | – | `None` |
| `t0` | – | `None` |
| `t1` | – | `None` |
| `strict` | – | `False` |

(task, phases, [Event]) for ``.../3_iterations/<it>/<trial>`` or  
``.../2_experimental/<trial>``. Uses jcf_coverage's discovery so the  
same IK/GRF files feed both the figure and this listing.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/events.py#L317)</sub>
