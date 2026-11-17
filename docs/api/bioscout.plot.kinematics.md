# `bioscout.plot.kinematics`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py)

Joint angles and IK marker errors, compared across a session's iterations.

    bioscout plot kinematics <session path>  
    bioscout plot kinematics <session path> --skip thesis_manual ast  
    bioscout plot kinematics . --trial Bare1_Right,Bare2_Right --reference kainz_pwph

`bioscout plot collings` answers "which muscles does each model rank  
differently"; this answers the question that comes before it: do the model  
iterations even agree on the KINEMATICS, and how well does each one track the  
markers. Same grammar — one session, every iteration under ``3_iterations/``,  
output in ``<session>/4_outputs/`` — and, like collings, plain text readers  
only, so it runs without OpenSim on the path.

WHAT IT READS  (per iteration, per trial; written by `bioscout simulate exbiomec`)

    3_iterations/<iteration>/<trial>/external_biomechanics/  
        joint_angles.mot             IK result            (``ik.mot`` also accepted)  
        _ik_marker_errors.sto        per frame: RMS and max marker error  
        _ik_marker_errors_all.sto    per frame, per marker

WHAT IT WRITES  (``<session>/4_outputs/kinematics/``)

    joint_angles_<trial>.png     one panel per coordinate, one line per iteration  
    marker_errors_<trial>.png    RMS and max error over time + marker x iteration map  
    marker_errors_overview.png   every iteration, every trial, on one page  
    joint_angles.csv             min / max / range per coordinate, and the  
                                 difference from the reference iteration  
    marker_errors.csv            mean / peak RMS and max error, worst marker

COLOUR IS THE ITERATION'S OWN  
    Lines and bars take ``color:`` and ``label:`` from session.yaml, so an  
    iteration looks the same here as in every other bioscout figure. Only  
    iterations without a colour fall back to a fixed palette. The marker map  
    is the exception: it shows a magnitude, so it is one hue, light to dark.

THE DASHED LINES ARE GUIDANCE, NOT A VERDICT  
    20 mm RMS and 40 mm max are OpenSim's rule-of-thumb limits for IK. They  
    are drawn so a figure can be read without the documentation open, and  
    they move with ``--rms-limit`` / ``--max-limit``.

ANGLES ARE UNWRAPPED BEFORE THEY ARE COMPARED  
    A pelvis rotation that crosses +/-180 deg is one smooth curve drawn as a  
    full-height jump, and the "range" of such a curve is 360. Rotations are  
    unwrapped and re-centred into (-180, 180] first, otherwise a participant  
    who walks the lab in the other direction dominates every statistic.

## Contents

- [`read_table`](#read_table) — (names, array, in_degrees) of an OpenSim .mot/.sto. Whitespace split: OpenSim writes tabs, MATLAB-written files add trailing ones, and neither puts a space inside a column name.
- [`ik_file`](#ik_file) — First of ``names`` that exists for this iteration/trial, or None.
- [`unwrap_deg`](#unwrap_deg) — A rotation in degrees without the +/-180 jumps, centred in (-180, 180].
- [`load_angles`](#load_angles) — {coordinate: degrees (metres for translations)} plus ``time``.
- [`load_errors`](#load_errors) — dict(time, rms, max [mm], markers {name: mean mm}) or None.
- [`session_order`](#session_order) — ``iterations`` in the order session.yaml lists them (the order their author chose, which keeps a sweep together); the rest follow, sorted.
- [`iteration_styles`](#iteration_styles) — {iteration: (label, colour, dash)} — session.yaml first, palette after.
- [`expand_dofs`](#expand_dofs) — [(row, title, [coordinate, ...])]: pelvis row, then one row per side.
- [`joint_angle_figure`](#joint_angle_figure) — ``data``: {iteration: load_angles(...)}, in drawing order.
- [`marker_error_figure`](#marker_error_figure) — ``errs``: {iteration: load_errors(...)}, in drawing order.
- [`overview_figure`](#overview_figure) — Every iteration on one page: bar = mean over trials, dots = each trial.
- [`angle_rows`](#angle_rows) — One row per iteration and coordinate; differences are against ``reference`` (interpolated onto its time base).
- [`error_row`](#error_row) — 
- [`kinematics_session`](#kinematics_session) — Compare joint angles and marker errors across iterations, one pair of figures per trial plus an overview and two tables. Returns the files written (empty when no iteration has IK results).
- [`find_session`](#find_session) — ``path`` if it holds session.yaml, else the single session below it.
- [`main`](#main) — 

### `read_table`

```python
read_table(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

(names, array, in_degrees) of an OpenSim .mot/.sto. Whitespace split:  
OpenSim writes tabs, MATLAB-written files add trailing ones, and neither  
puts a space inside a column name.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L80)</sub>

### `ik_file`

```python
ik_file(session, iteration, trial, names)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `iteration` | – | required |
| `trial` | – | required |
| `names` | – | required |

First of ``names`` that exists for this iteration/trial, or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L106)</sub>

### `unwrap_deg`

```python
unwrap_deg(y)
```

| input | type | default |
|---|---|---|
| `y` | – | required |

A rotation in degrees without the +/-180 jumps, centred in (-180, 180].

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L117)</sub>

### `load_angles`

```python
load_angles(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

{coordinate: degrees (metres for translations)} plus ``time``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L126)</sub>

### `load_errors`

```python
load_errors(session, iteration, trial)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `iteration` | – | required |
| `trial` | – | required |

dict(time, rms, max [mm], markers {name: mean mm}) or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L142)</sub>

### `session_order`

```python
session_order(session, iterations)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `iterations` | – | required |

``iterations`` in the order session.yaml lists them (the order their  
author chose, which keeps a sweep together); the rest follow, sorted.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L174)</sub>

### `iteration_styles`

```python
iteration_styles(session, iterations)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `iterations` | – | required |

{iteration: (label, colour, dash)} — session.yaml first, palette after.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L182)</sub>

### `expand_dofs`

```python
expand_dofs(dofs)
```

| input | type | default |
|---|---|---|
| `dofs` | – | required |

[(row, title, [coordinate, ...])]: pelvis row, then one row per side.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L198)</sub>

### `joint_angle_figure`

```python
joint_angle_figure(data, styles, path, title, dofs=DEFAULT_DOFS)
```

| input | type | default |
|---|---|---|
| `data` | – | required |
| `styles` | – | required |
| `path` | – | required |
| `title` | – | required |
| `dofs` | – | `DEFAULT_DOFS` |

``data``: {iteration: load_angles(...)}, in drawing order.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L242)</sub>

### `marker_error_figure`

```python
marker_error_figure(
    errs,
    styles,
    path,
    title,
    rms_limit=RMS_LIMIT_MM,
    max_limit=MAX_LIMIT_MM
)
```

| input | type | default |
|---|---|---|
| `errs` | – | required |
| `styles` | – | required |
| `path` | – | required |
| `title` | – | required |
| `rms_limit` | – | `RMS_LIMIT_MM` |
| `max_limit` | – | `MAX_LIMIT_MM` |

``errs``: {iteration: load_errors(...)}, in drawing order.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L293)</sub>

### `overview_figure`

```python
overview_figure(
    rows,
    styles,
    its,
    path,
    title,
    rms_limit=RMS_LIMIT_MM,
    max_limit=MAX_LIMIT_MM
)
```

| input | type | default |
|---|---|---|
| `rows` | – | required |
| `styles` | – | required |
| `its` | – | required |
| `path` | – | required |
| `title` | – | required |
| `rms_limit` | – | `RMS_LIMIT_MM` |
| `max_limit` | – | `MAX_LIMIT_MM` |

Every iteration on one page: bar = mean over trials, dots = each trial.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L357)</sub>

### `angle_rows`

```python
angle_rows(trial, data, coords, reference=None)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |
| `data` | – | required |
| `coords` | – | required |
| `reference` | – | `None` |

One row per iteration and coordinate; differences are against  
``reference`` (interpolated onto its time base).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L395)</sub>

### `error_row`

```python
error_row(trial, it, e)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |
| `it` | – | required |
| `e` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L422)</sub>

### `kinematics_session`

```python
kinematics_session(
    session,
    skip=(),
    trials=None,
    iterations=None,
    dofs=DEFAULT_DOFS,
    reference=None,
    out_dir=None,
    rms_limit=RMS_LIMIT_MM,
    max_limit=MAX_LIMIT_MM,
    log=print
)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `skip` | – | `()` |
| `trials` | – | `None` |
| `iterations` | – | `None` |
| `dofs` | – | `DEFAULT_DOFS` |
| `reference` | – | `None` |
| `out_dir` | – | `None` |
| `rms_limit` | – | `RMS_LIMIT_MM` |
| `max_limit` | – | `MAX_LIMIT_MM` |
| `log` | – | `print` |

Compare joint angles and marker errors across iterations, one pair of  
figures per trial plus an overview and two tables. Returns the files  
written (empty when no iteration has IK results).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L442)</sub>

### `find_session`

```python
find_session(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

``path`` if it holds session.yaml, else the single session below it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L520)</sub>

### `main`

```python
main(argv=None)
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/kinematics.py#L540)</sub>
