# `bioscout.model.inspect.validation`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/validation.py)

Literature moment-arm validation (reusable).

Loads digitized literature bands (validation/literature_moment_arms.csv), computes  
the model's moment arms, and (a) produces a dedicated comparison figure laid out  
with one ROW per moment DOF (flexion, adduction, rotation, ...) + RMSE csv, and  
(b) provides band overlays for the sweep grids where the panel's moment axis ==  
swept axis and the muscle maps 1:1 to a model muscle.

## Contents

- [`load_literature`](#load_literature) — (muscle, moment_dof, x_dof) -> study -> sorted [(angle_deg, mean_cm, sd_cm)].
- [`grid_overlays`](#grid_overlays) — Bands to draw on a sweep grid for `coord_name`.
- [`run_validation`](#run_validation) — Comparison figure (one row per moment DOF) + RMSE csv. Returns figure path or None.

### `load_literature`

```python
load_literature(path, quantity='moment_arm')
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `quantity` | – | `'moment_arm'` |

(muscle, moment_dof, x_dof) -> study -> sorted [(angle_deg, mean_cm, sd_cm)].

Header-driven: accepts the consolidated ``literature_curves`` schema  
(quantity,muscle,moment_dof,x_dof,study,[task,]angle_deg,mean,sd) -- keeping  
only rows whose ``quantity`` matches -- as well as the legacy layout  
(muscle,moment_dof,x_dof,study,angle_deg,mean_cm,sd_cm). An optional ``task``  
column is folded into the study label so different measurement tasks stay as  
distinct series.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/validation.py#L39)</sub>

### `grid_overlays`

```python
grid_overlays(lit, coord_name, model_muscle_names)
```

| input | type | default |
|---|---|---|
| `lit` | – | required |
| `coord_name` | – | required |
| `model_muscle_names` | – | required |

Bands to draw on a sweep grid for `coord_name`.

Includes any literature panel whose moment axis == swept axis == this  
coordinate's base. The band is attached to every model compartment of the  
muscle present in the grid (for lumped muscles like gluteus maximus the same  
whole-muscle band is shown on each compartment -- approximate; the dedicated  
validation figure does the proper compartment-averaged comparison).  
Returns {model_muscle: [(label, color, ang_deg, mean_mm, sd_mm)]} (cm->mm).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/validation.py#L97)</sub>

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

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/validation.py#L147)</sub>
