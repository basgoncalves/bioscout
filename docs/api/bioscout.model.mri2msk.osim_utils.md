# `bioscout.model.mri2msk.osim_utils`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py)

OpenSim-API helpers (port of the torsion-correction helpers in MRI2MSK.m).

Requires the ``opensim`` Python bindings (4.4+ recommended, e.g.  
``conda install -c opensim-org opensim``).

## Contents

- [`vec3_to_np`](#vec3_to_np) — 
- [`np_to_vec3`](#np_to_vec3) — 
- [`get_offset_frame`](#get_offset_frame) — Return the joint's PhysicalOffsetFrame called ``frame_name``.
- [`iter_meshes`](#iter_meshes) — Yield every Mesh attached directly to ``body``.
- [`set_body_mesh_file`](#set_body_mesh_file) — 
- [`set_condyle_mesh_file`](#set_condyle_mesh_file) — 
- [`set_tibial_plateau_mesh_file`](#set_tibial_plateau_mesh_file) — 
- [`transform_markers`](#transform_markers) — 
- [`transform_path_points`](#transform_path_points) — Rotate fixed PathPoints of all muscles attached to ``frame_name``.
- [`transform_wrap_objects`](#transform_wrap_objects) — 
- [`fix_femoral_condyles`](#fix_femoral_condyles) — Re-locate femur weld + medial/lateral condyle frames after femur rotation.
- [`get_model_angles_and_offsets`](#get_model_angles_and_offsets) — Condylar, tibial-plateau and tibial-torsion angles (deg) in the transverse plane.
- [`wrap_coordinate_functions_with_scale`](#wrap_coordinate_functions_with_scale) — Wrap the translational TransformAxis functions of a CustomJoint in a MultiplierFunction(scale) - used to scale patellofemoral / Lerner knee splines.

### `vec3_to_np`

```python
vec3_to_np(v) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `v` | – | required |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L15)</sub>

### `np_to_vec3`

```python
np_to_vec3(a) -> 'osim.Vec3'
```

| input | type | default |
|---|---|---|
| `a` | – | required |

**returns** `'osim.Vec3'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L19)</sub>

### `get_offset_frame`

```python
get_offset_frame(joint, frame_name: str)
```

| input | type | default |
|---|---|---|
| `joint` | – | required |
| `frame_name` | str | required |

Return the joint's PhysicalOffsetFrame called ``frame_name``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L25)</sub>

### `iter_meshes`

```python
iter_meshes(body)
```

| input | type | default |
|---|---|---|
| `body` | – | required |

Yield every Mesh attached directly to ``body``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L34)</sub>

### `set_body_mesh_file`

```python
set_body_mesh_file(model, body_name: str, geom_filter: str, mesh_file: str) -> None
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `body_name` | str | required |
| `geom_filter` | str | required |
| `mesh_file` | str | required |

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L49)</sub>

### `set_condyle_mesh_file`

```python
set_condyle_mesh_file(model, side: str, mesh_file: str) -> None
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `side` | str | required |
| `mesh_file` | str | required |

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L56)</sub>

### `set_tibial_plateau_mesh_file`

```python
set_tibial_plateau_mesh_file(model, side: str, mesh_file: str) -> None
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `side` | str | required |
| `mesh_file` | str | required |

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L63)</sub>

### `transform_markers`

```python
transform_markers(model, frame_name, R, pivot, restore_translation) -> None
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `frame_name` | – | required |
| `R` | – | required |
| `pivot` | – | required |
| `restore_translation` | – | required |

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L71)</sub>

### `transform_path_points`

```python
transform_path_points(model, state, frame_name, R, pivot, restore_translation) -> None
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `state` | – | required |
| `frame_name` | – | required |
| `R` | – | required |
| `pivot` | – | required |
| `restore_translation` | – | required |

**returns** `None`

Rotate fixed PathPoints of all muscles attached to ``frame_name``.

Points that don't down-cast to PathPoint (e.g. MovingPathPoint) are skipped,  
as in the MATLAB version.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L80)</sub>

### `transform_wrap_objects`

```python
transform_wrap_objects(body, R, pivot) -> None
```

| input | type | default |
|---|---|---|
| `body` | – | required |
| `R` | – | required |
| `pivot` | – | required |

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L100)</sub>

### `fix_femoral_condyles`

```python
fix_femoral_condyles(model, side: str, R, femur_translation) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `side` | str | required |
| `R` | – | required |
| `femur_translation` | – | required |

**returns** `np.ndarray`

Re-locate femur weld + medial/lateral condyle frames after femur rotation.

Returns the new femur weld location (used as pivot for the condyle mesh).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L111)</sub>

### `get_model_angles_and_offsets`

```python
get_model_angles_and_offsets(model, state, side: str, knee_axis_ref)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `state` | – | required |
| `side` | str | required |
| `knee_axis_ref` | – | required |

Condylar, tibial-plateau and tibial-torsion angles (deg) in the transverse plane.

Returns ``(angles, translations)`` dicts:  
``angles = {'cond', 'tibialPlat', 'torsion'}``, ``translations = {'femur', 'tibia'}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L142)</sub>

### `wrap_coordinate_functions_with_scale`

```python
wrap_coordinate_functions_with_scale(joint, scale: float, axes=(3, 4, 5)) -> None
```

| input | type | default |
|---|---|---|
| `joint` | – | required |
| `scale` | float | required |
| `axes` | – | `(3, 4, 5)` |

**returns** `None`

Wrap the translational TransformAxis functions of a CustomJoint in a  
MultiplierFunction(scale) - used to scale patellofemoral / Lerner knee splines.

OpenSim takes ownership of the functions passed to setFunction(); the Python  
proxies must give up ownership (``thisown = False``) or Python frees them a  
second time (segfault).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/osim_utils.py#L178)</sub>
