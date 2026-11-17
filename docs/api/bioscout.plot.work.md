# `bioscout.plot.work`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/work.py)

bioscout.plot.work — muscle work, from .sto files to a tidy table.

    W_i = ∫ F_i(t) · v_i(t) dt

``F`` is whatever force the algorithm produced (static optimisation's  
``*_force.sto``, CEINMS' ``MuscleForces.sto``); ``v`` is muscle–tendon  
shortening velocity, the negated derivative of ``_MuscleAnalysis_Length.sto``.  
That length comes from the kinematics alone, so it is IDENTICAL for every  
algorithm run on the same trial — the algorithms differ only in the force,  
which is exactly the comparison worth making.

FOUR PHASES, AND SAYING WHICH ONE YOU DREW  
    ``total``       ∫|F·v| dt   concentric + eccentric. A muscle doing equal  
                                positive and negative work scores high here.  
    ``concentric``  ∫ F·v dt over v > 0 only.  
    ``eccentric``   ∫ F·|v| dt over v < 0 only.  
    ``net``         ∫ F·v dt    — signed; the other three are its parts.

    These rank muscles differently and the difference is not small, so the  
    phase is written into the table (``Variable = "muscle_work_total"``) rather  
    than left to the caller's memory. Quote a figure, quote the phase.

Nothing here needs OpenSim, scipy or a bioscout session: the .sto reader is  
plain text on purpose, so this runs on a collaborator's laptop and in CI.

## Contents

- [`group_of`](#group_of) — Which functional group a muscle column belongs to, side suffix ignored. Returns ``None`` for a column no group claims (``time``, a coordinate, a muscle the map does not list).
- [`read_sto`](#read_sto) — ``(column_names, ndarray)`` from an OpenSim/CEINMS .sto or .mot.
- [`muscle_work`](#muscle_work) — ``{group: work in J}`` for one trial and one limb.
- [`work_table`](#work_table) — Many trials -> a tidy table (see :mod:`bioscout.plot.tidy`).
- [`find_trials`](#find_trials) — 
- [`trial_inputs`](#trial_inputs) — ``(force_path, length_path)`` for one trial, or ``(None, None)``.
- [`session_records`](#session_records) — Trial records for :func:`work_table`, walked off a bioscout session.

### `group_of`

```python
group_of(name, groups=None)
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `groups` | – | `None` |

Which functional group a muscle column belongs to, side suffix ignored.  
Returns ``None`` for a column no group claims (``time``, a coordinate, a  
muscle the map does not list).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/work.py#L73)</sub>

### `read_sto`

```python
read_sto(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

``(column_names, ndarray)`` from an OpenSim/CEINMS .sto or .mot.

Deliberately plain text: this must work in an environment with no OpenSim  
and no scipy. Ragged or non-numeric lines are skipped rather than raising —  
a half-written file from an interrupted run should cost you one trial, not  
the figure.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/work.py#L86)</sub>

### `muscle_work`

```python
muscle_work(force, length, side='_r', phase='total', groups=None, per_muscle=False)
```

| input | type | default |
|---|---|---|
| `force` | – | required |
| `length` | – | required |
| `side` | – | `'_r'` |
| `phase` | – | `'total'` |
| `groups` | – | `None` |
| `per_muscle` | – | `False` |

``{group: work in J}`` for one trial and one limb.

``force`` and ``length`` are paths to the two .sto files (or already-read  
``(head, array)`` tuples). The force is resampled onto the length's time  
base with linear interpolation — static optimisation usually writes a  
coarser grid than the muscle analysis, and integrating on the coarser of  
the two throws away velocity detail for no reason.

Returns ``{}`` rather than raising when either file is missing or unusable,  
so a batch over a part-solved session skips the gaps.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/work.py#L123)</sub>

### `work_table`

```python
work_table(
    records,
    phase='total',
    groups=None,
    sides=('_r',),
    per_muscle=False,
    quiet=True
)
```

| input | type | default |
|---|---|---|
| `records` | – | required |
| `phase` | – | `'total'` |
| `groups` | – | `None` |
| `sides` | – | `('_r',)` |
| `per_muscle` | – | `False` |
| `quiet` | – | `True` |

Many trials -> a tidy table (see :mod:`bioscout.plot.tidy`).

``records`` is any iterable of dicts. Two keys are used here — ``force``  
and ``length``, the two .sto paths — and EVERY other key is copied onto the  
rows as a column, so you label your data with whatever your study is  
actually split by::

    rows = bs.plot.work_table([  
        {"Task": "run",  "Condition": "pre",  "Trial": "run_01",  
         "force": ".../StaticOptimization_force.sto",  
         "length": ".../_MuscleAnalysis_Length.sto"},  
        ...  
    ])

``sides`` may hold ``"_r"``, ``"_l"`` or both; the limb lands in a ``Side``  
column so a figure can pool it (the default) or split on it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/work.py#L179)</sub>

### `find_trials`

```python
find_trials(session, iteration)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `iteration` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/work.py#L231)</sub>

### `trial_inputs`

```python
trial_inputs(session, iteration, trial, algo='SO', ceinms_dir=None)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `iteration` | – | required |
| `trial` | – | required |
| `algo` | – | `'SO'` |
| `ceinms_dir` | – | `None` |

``(force_path, length_path)`` for one trial, or ``(None, None)``.

``algo`` is ``"SO"`` or ``"CEINMS"``. For CEINMS the newest  
``Execution_*`` folder wins unless ``ceinms_dir`` names one — pin it when a  
figure has to be reproducible across a re-run that added executions.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/work.py#L241)</sub>

### `session_records`

```python
session_records(session, iteration, algos=('SO',), trials=None, label=None, **keys)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `iteration` | – | required |
| `algos` | – | `('SO',)` |
| `trials` | – | `None` |
| `label` | – | `None` |
| `**keys` | – | – |

Trial records for :func:`work_table`, walked off a bioscout session.

``label`` is an optional ``callable(trial_name) -> dict`` that turns a  
trial name into the study's own keys — the task it belongs to, the  
condition, the repetition. That callable is the ONLY project-specific thing  
in this whole path, and it stays in the project::

    recs = bs.plot.session_records(  
        sess, "iteration_1", algos=("SO", "CEINMS"),  
        label=lambda t: {"Task": task_of(t), "Condition": cond_of(t)},  
        Subject="021")

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/work.py#L260)</sub>
