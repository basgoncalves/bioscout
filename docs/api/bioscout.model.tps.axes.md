# `bioscout.model.tps.axes`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/axes.py)

Anatomical axis construction and rigid alignment of each body to OpenSim.

Refactor of the original ``TransformBodyToOsim`` / ``GetPelvisAxes`` /  
``GetFemurAxes`` / ``GetTibiaAxes`` classes. The anatomical-axis *definitions*  
(which landmarks build each axis, and the left/right handedness handling) are  
preserved exactly; the shared rigid-alignment maths is delegated to  
:func:`tps_personalise.geometry.kabsch` instead of being copy-pasted three  
times, and ``print`` calls are replaced with logging.

Convention (unchanged from original): OpenSim body axes are taken as  
``[[0,0,1],[1,0,0],[0,1,0]] * 50`` and each body's MRI anatomical axes are  
rigidly rotated onto them.

## Contents

- class [`PelvisAxes`](#pelvisaxes) — Pelvis anatomical frame from ASIS_r/ASIS_l/pub_super_c.
  - [`PelvisAxes.apply_to_non_bone`](#pelvisaxesapply_to_non_bone) — 
- class [`FemurAxes`](#femuraxes) — Femur anatomical frame; handles right/left automatically.
  - [`FemurAxes.apply_to_non_bone`](#femuraxesapply_to_non_bone) — 
  - [`FemurAxes.transform_patella`](#femuraxestransform_patella) — Rotate a patella into its child frame using this femur's IS axis.
  - [`FemurAxes.apply_patella_non_bone`](#femuraxesapply_patella_non_bone) — Rotate arbitrary patella points into the frame set by the last :meth:`transform_patella` call (used for patella meshes).
- class [`TibiaAxes`](#tibiaaxes) — Tibia anatomical frame; handles right/left automatically.
  - [`TibiaAxes.apply_to_non_bone`](#tibiaaxesapply_to_non_bone) — 

<a id="pelvisaxes"></a>

## class `PelvisAxes`

```python
PelvisAxes(bone_numpy: Array, bone_markers: Sequence[str])
```

| input | type | default |
|---|---|---|
| `bone_numpy` | Array | required |
| `bone_markers` | Sequence[str] | required |

Pelvis anatomical frame from ASIS_r/ASIS_l/pub_super_c.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/axes.py#L40)</sub>

<a id="pelvisaxesapply_to_non_bone"></a>

### `PelvisAxes.apply_to_non_bone`

```python
PelvisAxes.apply_to_non_bone(data: Array) -> Array
```

| input | type | default |
|---|---|---|
| `data` | Array | required |

**returns** `Array`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/axes.py#L66)</sub>

<a id="femuraxes"></a>

## class `FemurAxes`

```python
FemurAxes(bone_numpy: Array, bone_markers: Sequence[str])
```

| input | type | default |
|---|---|---|
| `bone_numpy` | Array | required |
| `bone_markers` | Sequence[str] | required |

Femur anatomical frame; handles right/left automatically.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/axes.py#L71)</sub>

<a id="femuraxesapply_to_non_bone"></a>

### `FemurAxes.apply_to_non_bone`

```python
FemurAxes.apply_to_non_bone(data: Array) -> Array
```

| input | type | default |
|---|---|---|
| `data` | Array | required |

**returns** `Array`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/axes.py#L110)</sub>

<a id="femuraxestransform_patella"></a>

### `FemurAxes.transform_patella`

```python
FemurAxes.transform_patella(
    patella_bone: Array,
    patella_markers: Sequence[str],
    patella_muscles: Optional[Array] = None
)
```

| input | type | default |
|---|---|---|
| `patella_bone` | Array | required |
| `patella_markers` | Sequence[str] | required |
| `patella_muscles` | Optional[Array] | `None` |

Rotate a patella into its child frame using this femur's IS axis.

Port of the original ``GetFemurAxes.transform_patella``: builds the  
patella mediolateral axis from ``patella_lat_*``/``patella_med_*``, the  
PA axis from the femur IS axis, then recentres on the ``patella_*``  
marker. Returns ``(bone_in_child, muscles_in_child_or_None)``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/axes.py#L114)</sub>

<a id="femuraxesapply_patella_non_bone"></a>

### `FemurAxes.apply_patella_non_bone`

```python
FemurAxes.apply_patella_non_bone(data: Array) -> Array
```

| input | type | default |
|---|---|---|
| `data` | Array | required |

**returns** `Array`

Rotate arbitrary patella points into the frame set by the last  
:meth:`transform_patella` call (used for patella meshes).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/axes.py#L154)</sub>

<a id="tibiaaxes"></a>

## class `TibiaAxes`

```python
TibiaAxes(bone_numpy: Array, bone_markers: Sequence[str])
```

| input | type | default |
|---|---|---|
| `bone_numpy` | Array | required |
| `bone_markers` | Sequence[str] | required |

Tibia anatomical frame; handles right/left automatically.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/axes.py#L160)</sub>

<a id="tibiaaxesapply_to_non_bone"></a>

### `TibiaAxes.apply_to_non_bone`

```python
TibiaAxes.apply_to_non_bone(data: Array) -> Array
```

| input | type | default |
|---|---|---|
| `data` | Array | required |

**returns** `Array`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/axes.py#L199)</sub>
