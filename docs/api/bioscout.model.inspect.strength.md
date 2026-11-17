# `bioscout.model.inspect.strength`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/strength.py)

Isometric joint-strength validation.

Compares the model's MAXIMUM ISOMETRIC joint moment (all agonists fully active)  
against the pooled literature MVC band (validation/strength_isometric.csv).

Model max isometric moment about a coordinate =  
    | sum over the joint's agonist muscles of  force(activation=1) * moment_arm |  
computed with the muscles equilibrated at each joint angle (velocity = 0).

This validates moment arms + max isometric forces + force-length together (joint  
strength), which is different from the pure moment-arm geometry check. Requires  
``import opensim``.

## Contents

- [`load_strength_lit`](#load_strength_lit) — joint_action -> (coordinate, [(x_value, mean_nm, sd_nm)]).
- [`load_muscle_groups`](#load_muscle_groups) — joint_action -> (coordinate_or_None, [model muscle names without side]).
- [`run_strength`](#run_strength) — Isometric strength figure (model vs literature MVC band) + RMSE csv.
- [`isokinetic_peaks`](#isokinetic_peaks) — Model peak concentric moment (Nm) at each angular velocity.
- [`run_isokinetic`](#run_isokinetic) — Isokinetic (concentric) peak moment vs velocity: model vs literature band.

### `load_strength_lit`

```python
load_strength_lit(path, test=None)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `test` | – | `None` |

joint_action -> (coordinate, [(x_value, mean_nm, sd_nm)]).

Reads the consolidated ``literature_strength.csv``  
(test,joint_action,coordinate,x_value,x_unit,mean_nm,sd_nm,n_datasets), keeping  
only rows whose ``test`` matches (isometric | isokinetic). Also accepts the  
legacy per-test files (joint_action,coordinate,x,mean_nm,sd_nm,...). x_value is  
a joint angle (deg) for isometric and an angular velocity (deg/s) for isokinetic.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/strength.py#L29)</sub>

### `load_muscle_groups`

```python
load_muscle_groups(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

joint_action -> (coordinate_or_None, [model muscle names without side]).

Reads the muscle-function matrix (muscle_functions.csv: action columns are 0/1)  
if given one; otherwise the legacy joint_action,coordinate,model_muscles layout.  
The action's coordinate is taken from literature_strength.csv at run time, so the  
coordinate slot is None when loading from the matrix.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/strength.py#L63)</sub>

### `run_strength`

```python
run_strength(model_path, lit_csv, groups_csv, out_dir, side='_r', n=40)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `lit_csv` | – | required |
| `groups_csv` | – | required |
| `out_dir` | – | required |
| `side` | – | `'_r'` |
| `n` | – | `40` |

Isometric strength figure (model vs literature MVC band) + RMSE csv.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/strength.py#L121)</sub>

### `isokinetic_peaks`

```python
isokinetic_peaks(mam, coord_name, muscle_names, angles_deg, velocities_degps)
```

| input | type | default |
|---|---|---|
| `mam` | – | required |
| `coord_name` | – | required |
| `muscle_names` | – | required |
| `angles_deg` | – | required |
| `velocities_degps` | – | required |

Model peak concentric moment (Nm) at each angular velocity.

At each joint angle the agonists are equilibrated at activation=1 (isometric  
force F_iso, moment arm a, optimal fibre length L0, v_max). For a joint speed  
omega, each muscle's fibre velocity ~ a*omega (rigid tendon); its force is  
scaled by the Hill concentric multiplier fv(a*omega / (v_max*L0)). Peak moment  
= max over angle of |sum F_iso*fv*a|.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/strength.py#L204)</sub>

### `run_isokinetic`

```python
run_isokinetic(
    model_path,
    iso_lit_csv,
    groups_csv,
    angle_lit_csv,
    out_dir,
    side='_r',
    n_angle=25
)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `iso_lit_csv` | – | required |
| `groups_csv` | – | required |
| `angle_lit_csv` | – | required |
| `out_dir` | – | required |
| `side` | – | `'_r'` |
| `n_angle` | – | `25` |

Isokinetic (concentric) peak moment vs velocity: model vs literature band.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/strength.py#L264)</sub>
