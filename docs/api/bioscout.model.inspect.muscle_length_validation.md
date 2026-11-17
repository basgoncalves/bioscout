# `bioscout.model.inspect.muscle_length_validation`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_length_validation.py)

Literature moment-arm AND muscle-architecture validation (reusable).

This is the muscle-length / fibre-architecture side of ``muscle_inspect`` (ported  
from the standalone MuscleLengthsChecker). It:

  * loads digitized literature bands (validation/literature_moment_arms.csv or the  
    consolidated literature_curves.csv), for moment arms, fascicle length and  
    pennation angle,  
  * computes the model's moment arms and produces a comparison figure (one ROW per  
    moment DOF) + RMSE csv  -> ``run_validation``,  
  * sweeps each joint coordinate and overlays the model's FASCICLE LENGTH and  
    PENNATION vs literature (quantity=fascicle_length|pennation) -> ``run_fibre_validation``.

Distinct from ``literature_jcf`` (joint contact forces) and from bioscout's own  
``validation`` module (moment-arm only, wired into run_moment_arm_inspection).  
Requires ``import opensim`` at run time.

## Contents

- [`study_color`](#study_color) — 
- [`load_literature`](#load_literature) — (muscle, moment_dof, x_dof) -> study -> sorted [(angle_deg, mean, sd)].
- [`load_muscle_map`](#load_muscle_map) — literature_muscle -> [model muscles] from a CSV (col1=name, col2=';'-separated).
- [`muscle_map_for`](#muscle_map_for) — Effective literature->model mapping: built-in MUSCLE_MAP overridden by the muscle-function matrix (validation/muscle_functions.csv) if present, else the legacy validation/muscle_map.csv. Both live next to ``csv_path``.
- [`grid_overlays`](#grid_overlays) — Bands to draw on a sweep grid for `coord_name`.
- [`run_validation`](#run_validation) — Comparison figure (one row per moment DOF) + RMSE csv. Returns figure path or None.
- [`run_validation_motion`](#run_validation_motion) — Moment-arm validation over the ACTUAL TRIAL MOTION (not a synthetic ROM sweep). For every literature (muscle, moment-DOF, x-DOF) entry the model's moment arm is evaluated at each recorded pose of ``motion_df`` (the trial IK), then plotted against the x-DOF angle the motion actually visited and overlaid on the literature band. This shows how well the model matches the literature over the range the task genuinely used. Saved as ``validation_moment_arms_motion.png`` (+ ``validation_motion_rmse.csv``).
- [`run_fibre_validation`](#run_fibre_validation) — Muscle-architecture validation: model fascicle length & pennation vs joint angle overlaid on literature (validation/literature_curves.csv rows with quantity=fascicle_length|pennation). Returns figure path or None if no such rows.

### `study_color`

```python
study_color(study)
```

| input | type | default |
|---|---|---|
| `study` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_length_validation.py#L67)</sub>

### `load_literature`

```python
load_literature(path, quantity='moment_arm')
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `quantity` | – | `'moment_arm'` |

(muscle, moment_dof, x_dof) -> study -> sorted [(angle_deg, mean, sd)].

Reads the consolidated ``literature_curves.csv``  
(quantity,muscle,moment_dof,x_dof,study,[task,]angle_deg,mean,sd), keeping only  
rows whose ``quantity`` matches. Header-driven: column order is resolved by name,  
so an optional ``task`` column (measurement condition: passive|MVC|walking|  
running|cadaver|...) can be present or absent without breaking parsing. Also  
accepts the legacy ``literature_moment_arms.csv`` layout  
(muscle,moment_dof,x_dof,study,angle_deg,mean,sd). For fascicle_length /  
pennation the moment_dof field is blank.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_length_validation.py#L73)</sub>

### `load_muscle_map`

```python
load_muscle_map(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

literature_muscle -> [model muscles] from a CSV (col1=name, col2=';'-separated).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_length_validation.py#L134)</sub>

### `muscle_map_for`

```python
muscle_map_for(csv_path)
```

| input | type | default |
|---|---|---|
| `csv_path` | – | required |

Effective literature->model mapping: built-in MUSCLE_MAP overridden by the  
muscle-function matrix (validation/muscle_functions.csv) if present, else the  
legacy validation/muscle_map.csv. Both live next to ``csv_path``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_length_validation.py#L150)</sub>

### `grid_overlays`

```python
grid_overlays(lit, coord_name, model_muscle_names, muscle_map=None)
```

| input | type | default |
|---|---|---|
| `lit` | – | required |
| `coord_name` | – | required |
| `model_muscle_names` | – | required |
| `muscle_map` | – | `None` |

Bands to draw on a sweep grid for `coord_name`.

Includes any literature panel whose moment axis == swept axis == this  
coordinate's base. The band is attached to every model compartment of the  
muscle present in the grid (for lumped muscles like gluteus maximus the same  
whole-muscle band is shown on each compartment -- approximate; the dedicated  
validation figure does the proper compartment-averaged comparison).  
Returns {model_muscle: [(label, color, ang_deg, mean_mm, sd_mm)]} (cm->mm).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_length_validation.py#L165)</sub>

### `run_validation`

```python
run_validation(model_path, csv_path, out_dir, side='_r', n=60)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `csv_path` | – | required |
| `out_dir` | – | required |
| `side` | – | `'_r'` |
| `n` | – | `60` |

Comparison figure (one row per moment DOF) + RMSE csv. Returns figure path or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_length_validation.py#L219)</sub>

### `run_validation_motion`

```python
run_validation_motion(model_path, motion_df, csv_path, out_dir, side='_r', max_frames=150)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `motion_df` | – | required |
| `csv_path` | – | required |
| `out_dir` | – | required |
| `side` | – | `'_r'` |
| `max_frames` | – | `150` |

Moment-arm validation over the ACTUAL TRIAL MOTION (not a synthetic ROM  
sweep). For every literature (muscle, moment-DOF, x-DOF) entry the model's  
moment arm is evaluated at each recorded pose of ``motion_df`` (the trial  
IK), then plotted against the x-DOF angle the motion actually visited and  
overlaid on the literature band. This shows how well the model matches the  
literature over the range the task genuinely used. Saved as  
``validation_moment_arms_motion.png`` (+ ``validation_motion_rmse.csv``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_length_validation.py#L313)</sub>

### `run_fibre_validation`

```python
run_fibre_validation(model_path, csv_path, out_dir, side='_r', n=40)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `csv_path` | – | required |
| `out_dir` | – | required |
| `side` | – | `'_r'` |
| `n` | – | `40` |

Muscle-architecture validation: model fascicle length & pennation vs joint  
angle overlaid on literature (validation/literature_curves.csv rows with  
quantity=fascicle_length|pennation). Returns figure path or None if no such rows.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_length_validation.py#L492)</sub>
