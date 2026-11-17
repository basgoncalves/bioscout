# `bioscout.simulate.so_actuators`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_actuators.py)

SO reserve/residual actuators: which source is used, and helpers.

Rule (per iteration, session.yaml ``so_actuators``):  
  * set   -> that file's actuators REPLACE the model's non-muscle actuators  
             (SO runs on ``<model>_noact.osim`` + the file as force_set_files)  
  * unset -> the model's own actuators are used, nothing appended  
  * neither has any -> warning (SO would silently push muscles instead)  
Pure XML, no opensim import, so scripts can use it too.

## Contents

- [`actuator_names`](#actuator_names) — Names of the non-muscle actuators in an .osim or a force-set .xml.
- [`extract_actuators`](#extract_actuators) — Write the model's non-muscle actuators as a force-set file.
- [`stripped_model`](#stripped_model) — ``<model>_noact.osim`` next to the model (same Geometry), muscles only. Rebuilt when missing or older than the source.
- [`strip_in_place`](#strip_in_place) — Remove every non-muscle actuator from ``osim_path`` itself. Returns how many were removed. For a model whose SO actuators come from an ``so_actuators`` file: the model stays muscles-only and there is ONE place (the file) that says which reserves/residuals SO gets.
- [`plan`](#plan) — -> (model_to_run, force_set_file_or_None, note). Warns if no actuators.
- [`percent_spec`](#percent_spec) — ``so_actuators: percent_40`` -> 40.0; anything else -> None.
- [`percent_reserves`](#percent_reserves) — Write ``out_xml`` = ``template_xml`` with each RESERVE at ``percent`` % of the trial's peak |ID moment| of its coordinate.
- [`peak_id_residuals`](#peak_id_residuals) — {actuator: peak |ID residual|} over [t0, t1] of an inverse_dynamics.sto.
- [`scale_residuals`](#scale_residuals) — Raise each pelvis residual's optimal_force to >= margin x its peak ID residual, so control <= 1 can carry the whole residual. Never lowers a value. Every <optimal_force> of the actuator is set (some files carry the tag twice). Returns {actuator: (old, new)} for the ones changed.
- [`bound_controls`](#bound_controls) — Every non-muscle actuator to control -1..1 (2026-11-03).

### `actuator_names`

```python
actuator_names(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

Names of the non-muscle actuators in an .osim or a force-set .xml.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_actuators.py#L24)</sub>

### `extract_actuators`

```python
extract_actuators(osim_path, out_xml)
```

| input | type | default |
|---|---|---|
| `osim_path` | – | required |
| `out_xml` | – | required |

Write the model's non-muscle actuators as a force-set file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_actuators.py#L34)</sub>

### `stripped_model`

```python
stripped_model(osim_path)
```

| input | type | default |
|---|---|---|
| `osim_path` | – | required |

``<model>_noact.osim`` next to the model (same Geometry), muscles only.  
Rebuilt when missing or older than the source.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_actuators.py#L48)</sub>

### `strip_in_place`

```python
strip_in_place(osim_path)
```

| input | type | default |
|---|---|---|
| `osim_path` | – | required |

Remove every non-muscle actuator from ``osim_path`` itself.  
Returns how many were removed. For a model whose SO actuators come from an  
``so_actuators`` file: the model stays muscles-only and there is ONE place  
(the file) that says which reserves/residuals SO gets.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_actuators.py#L62)</sub>

### `plan`

```python
plan(model_path, actuators_path=None)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `actuators_path` | – | `None` |

-> (model_to_run, force_set_file_or_None, note). Warns if no actuators.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_actuators.py#L77)</sub>

### `percent_spec`

```python
percent_spec(value)
```

| input | type | default |
|---|---|---|
| `value` | – | required |

``so_actuators: percent_40`` -> 40.0; anything else -> None.

``percent_XX`` is not a file. It asks for a reserve set built PER TRIAL:  
every reserve's optimal_force is XX % of the peak |ID moment| of its own  
coordinate in THAT trial. A file written once per session cannot do this --  
two trials of one session do not have the same joint moments.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_actuators.py#L110)</sub>

### `percent_reserves`

```python
percent_reserves(template_xml, id_sto, percent, out_xml, t0=None, t1=None, floor=1.0)
```

| input | type | default |
|---|---|---|
| `template_xml` | – | required |
| `id_sto` | – | required |
| `percent` | – | required |
| `out_xml` | – | required |
| `t0` | – | `None` |
| `t1` | – | `None` |
| `floor` | – | `1.0` |

Write ``out_xml`` = ``template_xml`` with each RESERVE at ``percent`` % of  
the trial's peak |ID moment| of its coordinate.

A reserve is a CoordinateActuator whose name ends in ``_reserve``; its  
coordinate is its ``<coordinate>`` (else the name without the suffix) and  
the moment is the ``<coordinate>_moment`` column of the inverse dynamics  
over [t0, t1]. Reserves named in a ``<!-- percent_fixed: a b -->`` comment  
of the template keep the template's value. Everything else in the template -- pelvis residuals, lumbar  
actuators, control bounds -- is left exactly as written. ``floor`` (N*m)  
keeps an actuator from vanishing on a coordinate that carries no moment.  
Returns ``{actuator: (peak_ID_moment, optimal_force)}``; a reserve whose  
coordinate has no ID column is left at the template's value and reported  
with a peak of None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_actuators.py#L123)</sub>

### `peak_id_residuals`

```python
peak_id_residuals(id_sto, t0=None, t1=None)
```

| input | type | default |
|---|---|---|
| `id_sto` | – | required |
| `t0` | – | `None` |
| `t1` | – | `None` |

{actuator: peak |ID residual|} over [t0, t1] of an inverse_dynamics.sto.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_actuators.py#L188)</sub>

### `scale_residuals`

```python
scale_residuals(actuators_xml, id_sto, t0=None, t1=None, margin=1.0, out_xml=None)
```

| input | type | default |
|---|---|---|
| `actuators_xml` | – | required |
| `id_sto` | – | required |
| `t0` | – | `None` |
| `t1` | – | `None` |
| `margin` | – | `1.0` |
| `out_xml` | – | `None` |

Raise each pelvis residual's optimal_force to >= margin x its peak ID  
residual, so control <= 1 can carry the whole residual. Never lowers a  
value. Every <optimal_force> of the actuator is set (some files carry the  
tag twice). Returns {actuator: (old, new)} for the ones changed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_actuators.py#L202)</sub>

### `bound_controls`

```python
bound_controls(actuators_xml, id_sto, t0=None, t1=None, margin=1.1, out_xml=None)
```

| input | type | default |
|---|---|---|
| `actuators_xml` | – | required |
| `id_sto` | – | required |
| `t0` | – | `None` |
| `t1` | – | `None` |
| `margin` | – | `1.1` |
| `out_xml` | – | `None` |

Every non-muscle actuator to control -1..1 (2026-11-03).

OpenSim SO with -Inf..Inf controls can diverge at a frame where the optimiser  
does not converge (K2L Gehen_01, 6.43 s: MX 712 kN*m, control 891). With every  
control in -1..1 an actuator can never exceed its optimal_force. An actuator that  
was unbounded (pelvis residuals, lumbar, ...) has its optimal_force raised to  
margin x the peak |ID| of what it actuates if smaller, so it can still carry the  
whole load; actuators that already had finite limits (reserves) keep their  
optimal_force. Returns {name: (old_limits, old_force, new_force)} for the changed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_actuators.py#L229)</sub>
