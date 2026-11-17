# `bioscout.model.edit.osim_ops`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py)

Model-editing operations backed by the OpenSim API.

Masses, isometric force, coordinate ranges/locks, wrapping surfaces, muscle  
copying and the moment-arm sanity checks -- everything that CHANGES an .osim.  
``bioscout.model.edit.ops`` declares these in its ``delegates_to=`` map.

Split out of the old ``bioscout/utils/openSim.py`` (docs/RESTRUCTURE_PLAN.md,  
stage 6) -- the code is unchanged, only its address.

## Contents

- [`scale_body_masses`](#scale_body_masses) — Scale the body masses of model_target to match the percentages of model_reference.
- [`add_mass_to_body`](#add_mass_to_body) — Add a specific mass to a body in the OpenSim model.
- [`print_body_mass_per_segment`](#print_body_mass_per_segment) — Print the mass of each body segment in the OpenSim model.
- [`increase_isometric_force`](#increase_isometric_force) — Increase the isometric force of a specified muscle by a given factor.
- [`lock_model_coordinates`](#lock_model_coordinates) — Lock specified coordinates in the OpenSim model.
- [`coord_moment_arms`](#coord_moment_arms) — Check which coordinates the muscles in the list have moment arms about (non-zero across the range of the model)
- [`add_wrapping_surfaces`](#add_wrapping_surfaces) — Add wrapping surfaces from reference OpenSim model to target model.
- [`edit_model_range_coordinates`](#edit_model_range_coordinates) — Edit the range of motion for a specific coordinate in the OpenSim model.
- [`add_wrapping_surface_to_model`](#add_wrapping_surface_to_model) — Add a wrapping surface to an OpenSim model.
- [`add_muscles_to_model`](#add_muscles_to_model) — Add muscles from a source OpenSim model to a target OpenSim model.
- [`copy_model_coordinate`](#copy_model_coordinate) — Copy one or more coordinates from a source model to a target model via XML manipulation.
- [`checkMuscleMomentArms`](#checkmusclemomentarms) — Adapted from Willi Koller: https://github.com/WilliKoller/OpenSimMatlabBasic/blob/main/checkMuscleMomentArms.m Models Verified for:     - Rajagopal 2015     - Cateli
- [`muscles_per_coordinate`](#muscles_per_coordinate) — 
- [`sampleMuscleQuantities`](#samplemusclequantities) — Sample muscle-tendon quantities across the range of motion of the coordinates spanned by the muscle (Modenese 2015 muscle optimiser helper).
- [`edit_pelvis_com_actuators`](#edit_pelvis_com_actuators) — Edit the pelvis center of mass actuator in the OpenSim model.
- [`normalise_muscle`](#normalise_muscle) — 

### `scale_body_masses`

```python
scale_body_masses(osim_modelPath)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | required |

Scale the body masses of model_target to match the percentages of model_reference.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L52)</sub>

### `add_mass_to_body`

```python
add_mass_to_body(osim_modelPath, body_name, mass_to_add)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | required |
| `body_name` | – | required |
| `mass_to_add` | – | required |

Add a specific mass to a body in the OpenSim model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L101)</sub>

### `print_body_mass_per_segment`

```python
print_body_mass_per_segment(osim_modelPath=None)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |

Print the mass of each body segment in the OpenSim model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L121)</sub>

### `increase_isometric_force`

```python
increase_isometric_force(osim_modelPath=None, muscleList='all', factor: float = None)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `muscleList` | – | `'all'` |
| `factor` | float | `None` |

Increase the isometric force of a specified muscle by a given factor.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L135)</sub>

### `lock_model_coordinates`

```python
lock_model_coordinates(
    osim_modelPath=None,
    coordinates_to_lock: list = None,
    save_path=None,
    unlock=False
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `coordinates_to_lock` | list | `None` |
| `save_path` | – | `None` |
| `unlock` | – | `False` |

Lock specified coordinates in the OpenSim model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L165)</sub>

### `coord_moment_arms`

```python
coord_moment_arms(osim_model, muscle_list)
```

| input | type | default |
|---|---|---|
| `osim_model` | – | required |
| `muscle_list` | – | required |

Check which coordinates the muscles in the list have moment arms about (non-zero across the range of the model)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L195)</sub>

### `add_wrapping_surfaces`

```python
add_wrapping_surfaces(
    reference_model_path=None,
    target_model_path=None,
    output_model_path=None
)
```

| input | type | default |
|---|---|---|
| `reference_model_path` | – | `None` |
| `target_model_path` | – | `None` |
| `output_model_path` | – | `None` |

Add wrapping surfaces from reference OpenSim model to target model.

  
**Args**

    reference_model_path (str): Path to reference .osim file  
    target_model_path (str): Path to target .osim file  
    output_model_path (str): Path for output .osim file with wrapping surfaces

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L224)</sub>

### `edit_model_range_coordinates`

```python
edit_model_range_coordinates(osim_modelPath, coordinate_name, new_range: list, save_path)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | required |
| `coordinate_name` | – | required |
| `new_range` | list | required |
| `save_path` | – | required |

Edit the range of motion for a specific coordinate in the OpenSim model.

  
**Args**

    osim_modelPath (str): Path to the .osim model file  
    coordinate_name (str): Name of the coordinate to edit  
    new_range (list): New range of motion as [min, max] in radians  
    save_path (str): Path to save the modified model

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L291)</sub>

### `add_wrapping_surface_to_model`

```python
add_wrapping_surface_to_model(model_path, surface_name, wrap_name, save_path=None)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `surface_name` | – | required |
| `wrap_name` | – | required |
| `save_path` | – | `None` |

Add a wrapping surface to an OpenSim model.

  
**Args**

    model_path (str): Path to the .osim model file  
    surface_name (str): Name of the wrapping surface to add  
    wrap_name (str): Name of the wrap object to create  
    save_path (str, optional): Path to save the modified model. If None, saves to model_path with '_wrap_added' suffix

  
**Returns**

    str: Path to the saved model file

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L316)</sub>

### `add_muscles_to_model`

```python
add_muscles_to_model(source_model_path, target_model_path, muscle_names, save_path=None)
```

| input | type | default |
|---|---|---|
| `source_model_path` | – | required |
| `target_model_path` | – | required |
| `muscle_names` | – | required |
| `save_path` | – | `None` |

Add muscles from a source OpenSim model to a target OpenSim model.

  
**Args**

    source_model_path (str): Path to the source .osim model file  
    target_model_path (str): Path to the target .osim model file  
    muscle_names (list): List of muscle names to copy from source to target  
    save_path (str, optional): Path to save the modified model. If None, saves to target_model_path with '_muscles_added' suffix

  
**Returns**

    str: Path to the saved model file

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L366)</sub>

### `copy_model_coordinate`

```python
copy_model_coordinate(
    src_model=None,
    target_model=None,
    coordinate_name=None,
    target_joint_name=None
)
```

| input | type | default |
|---|---|---|
| `src_model` | – | `None` |
| `target_model` | – | `None` |
| `coordinate_name` | – | `None` |
| `target_joint_name` | – | `None` |

Copy one or more coordinates from a source model to a target model via XML manipulation.

coordinate_name: str or list of str  
target_joint_name: str, list of str (matched by index to coordinate_name), or None  
    If None, the source joint name is used for each coordinate.

Adds each coordinate to the target joint's <coordinates> list and mirrors  
any SpatialTransform/TransformAxis references from the source joint.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L479)</sub>

### `checkMuscleMomentArms`

```python
checkMuscleMomentArms(model_file_path=None, ik_file_path=None, leg='l', threshold=0.005)
```

| input | type | default |
|---|---|---|
| `model_file_path` | – | `None` |
| `ik_file_path` | – | `None` |
| `leg` | – | `'l'` |
| `threshold` | – | `0.005` |

Adapted from Willi Koller: https://github.com/WilliKoller/OpenSimMatlabBasic/blob/main/checkMuscleMomentArms.m  
Models Verified for:  
    - Rajagopal 2015  
    - Cateli 

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L614)</sub>

### `muscles_per_coordinate`

```python
muscles_per_coordinate(osimModel=None)
```

| input | type | default |
|---|---|---|
| `osimModel` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L886)</sub>

### `sampleMuscleQuantities`

```python
sampleMuscleQuantities(osimModel, osimMuscle, muscleQuant, N_eval)
```

| input | type | default |
|---|---|---|
| `osimModel` | – | required |
| `osimMuscle` | – | required |
| `muscleQuant` | – | required |
| `N_eval` | – | required |

Sample muscle-tendon quantities across the range of motion of the  
coordinates spanned by the muscle (Modenese 2015 muscle optimiser helper).

For each combination of N_eval values per spanned coordinate the model is  
posed, muscles are equilibrated (elastic tendon, activation = 1) and the  
following are recorded per evaluation point:

    [muscleTendonLength, normalizedFiberLength, tendonLength,  
     normalizedFiberLength*cos(pennation), pennationAngle]

muscleQuant='MTL' returns only muscleTendonLength per point; 'all' returns  
the full row above (the indices used by optimMuscleParams are 0,1,2,4).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L921)</sub>

### `edit_pelvis_com_actuators`

```python
edit_pelvis_com_actuators(osim_modelPath, actuatorsFilePath)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | required |
| `actuatorsFilePath` | – | required |

Edit the pelvis center of mass actuator in the OpenSim model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L1059)</sub>

### `normalise_muscle`

```python
normalise_muscle(muscle_forces_path, osim_modelPath)
```

| input | type | default |
|---|---|---|
| `muscle_forces_path` | – | required |
| `osim_modelPath` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/osim_ops.py#L1084)</sub>
