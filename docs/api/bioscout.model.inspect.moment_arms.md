# `bioscout.model.inspect.moment_arms`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arms.py)

Moment-arm and muscle-length sweeps over coordinate range of motion.

For a given coordinate, set it across its range (holding the rest of the model  
at its default pose) and record each spanning muscle's moment arm and length.  
Requires ``import opensim``.

  
**Performance notes**

The expensive call is ``model.assemble`` (the constraint solver). Two things keep  
this fast:  
  * spanning-muscle detection poses the model once per sample and loops muscles  
    inside (not once per muscle), and  
  * ``assemble`` is skipped for coordinates that do not drive any constrained  
    (dependent) coordinate -- detected once per coordinate. Only joints like the  
    knee (patella coupler) actually need the solver.

## Contents

- class [`CoordinateSweep`](#coordinatesweep) — 
- class [`MomentArmModel`](#momentarmmodel) — Wraps an OpenSim model for repeated coordinate sweeps.
  - [`MomentArmModel.reset_pose`](#momentarmmodelreset_pose) — 
  - [`MomentArmModel.all_muscle_names`](#momentarmmodelall_muscle_names) — 
  - [`MomentArmModel.find_spanning_muscles`](#momentarmmodelfind_spanning_muscles) — Return muscles whose moment arm about ``coord_name`` is non-trivial.
  - [`MomentArmModel.sweep`](#momentarmmodelsweep) — 
  - [`MomentArmModel.moment_arm_over_motion`](#momentarmmodelmoment_arm_over_motion) — Moment arm of each muscle about ``mdof_coord`` at every frame of a recorded motion (as opposed to a synthetic single-DOF sweep).
- [`canonical_flip`](#canonical_flip) — Return +1.0 or -1.0 to express a model coordinate in the CANONICAL (literature) convention. [knee flexion-sign reconciliation]
- [`compute_sweeps`](#compute_sweeps) — Compute moment-arm/length sweeps for several coordinates.
- [`discontinuous_muscles`](#discontinuous_muscles) — Names of muscles whose moment-arm or length curve has a discontinuity.

<a id="coordinatesweep"></a>

## class `CoordinateSweep`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arms.py#L42)</sub>

<a id="momentarmmodel"></a>

## class `MomentArmModel`

```python
MomentArmModel(osim_path: str)
```

| input | type | default |
|---|---|---|
| `osim_path` | str | required |

Wraps an OpenSim model for repeated coordinate sweeps.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arms.py#L59)</sub>

<a id="momentarmmodelreset_pose"></a>

### `MomentArmModel.reset_pose`

```python
MomentArmModel.reset_pose()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arms.py#L86)</sub>

<a id="momentarmmodelall_muscle_names"></a>

### `MomentArmModel.all_muscle_names`

```python
MomentArmModel.all_muscle_names(muscle_filter: Optional[list] = None) -> list
```

| input | type | default |
|---|---|---|
| `muscle_filter` | Optional[list] | `None` |

**returns** `list`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arms.py#L127)</sub>

<a id="momentarmmodelfind_spanning_muscles"></a>

### `MomentArmModel.find_spanning_muscles`

```python
MomentArmModel.find_spanning_muscles(
    coord_name: str,
    candidate_names: list,
    n_sample: int = 3,
    threshold: float = 0.0001
) -> list
```

| input | type | default |
|---|---|---|
| `coord_name` | str | required |
| `candidate_names` | list | required |
| `n_sample` | int | `3` |
| `threshold` | float | `0.0001` |

**returns** `list`

Return muscles whose moment arm about ``coord_name`` is non-trivial.

Poses the model once per sample and evaluates all muscles at that pose.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arms.py#L135)</sub>

<a id="momentarmmodelsweep"></a>

### `MomentArmModel.sweep`

```python
MomentArmModel.sweep(coord_name: str, muscle_names: list, n: int = 80) -> CoordinateSweep
```

| input | type | default |
|---|---|---|
| `coord_name` | str | required |
| `muscle_names` | list | required |
| `n` | int | `80` |

**returns** `CoordinateSweep`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arms.py#L164)</sub>

<a id="momentarmmodelmoment_arm_over_motion"></a>

### `MomentArmModel.moment_arm_over_motion`

```python
MomentArmModel.moment_arm_over_motion(
    motion_df,
    mdof_coord,
    muscle_names,
    in_degrees=True
)
```

| input | type | default |
|---|---|---|
| `motion_df` | – | required |
| `mdof_coord` | – | required |
| `muscle_names` | – | required |
| `in_degrees` | – | `True` |

Moment arm of each muscle about ``mdof_coord`` at every frame of a  
recorded motion (as opposed to a synthetic single-DOF sweep).

``motion_df`` is an IK-style DataFrame with a ``time`` column plus one  
column per coordinate name (rotational coords in DEGREES when  
``in_degrees``). The FULL pose is set each frame (every coordinate the  
model shares with the motion), so cross-DOF coupling is respected.  
Returns ``(time, {muscle: np.array})`` with moment arms in metres.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arms.py#L204)</sub>

### `canonical_flip`

```python
canonical_flip(coord)
```

| input | type | default |
|---|---|---|
| `coord` | – | required |

Return +1.0 or -1.0 to express a model coordinate in the CANONICAL  
(literature) convention. [knee flexion-sign reconciliation]

Only the knee differs across our models: Rajagopal/Catelli define knee  
flexion POSITIVE (range ~0..+150 deg) whereas GPK/Lernagopal -- and the  
literature database -- define knee flexion NEGATIVE (~-140..+10 deg). To  
compare any model against the same literature we flip flexion-positive knees  
so every model is shown/scored in the flexion-negative frame. Flipping the  
knee coordinate negates both the joint-angle axis and the moment-arm sign.  
Detected from the coordinate's range (no model editing required).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arms.py#L250)</sub>

### `compute_sweeps`

```python
compute_sweeps(
    osim_path: str,
    coordinate_names: Optional[list] = None,
    muscle_filter: Optional[list] = None,
    n: int = 80,
    auto_select: bool = True
) -> dict
```

| input | type | default |
|---|---|---|
| `osim_path` | str | required |
| `coordinate_names` | Optional[list] | `None` |
| `muscle_filter` | Optional[list] | `None` |
| `n` | int | `80` |
| `auto_select` | bool | `True` |

**returns** `dict`

Compute moment-arm/length sweeps for several coordinates.

Returns ``{coordinate_name: CoordinateSweep}``. Coordinates that don't exist  
in the model are skipped with a warning.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arms.py#L275)</sub>

### `discontinuous_muscles`

```python
discontinuous_muscles(sweeps: dict, **detect_kwargs) -> set
```

| input | type | default |
|---|---|---|
| `sweeps` | dict | required |
| `**detect_kwargs` | – | – |

**returns** `set`

Names of muscles whose moment-arm or length curve has a discontinuity.

Extra keyword args (e.g. ``min_jump_m``, ``k_global``) are forwarded to  
``detect_discontinuities`` to tune sensitivity.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/moment_arms.py#L315)</sub>
