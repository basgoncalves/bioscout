# `bioscout.model.mri2msk.model_warper`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py)

Python re-implementation of the OpenSim Creator Model Warper (step 5).

Reads the ``warp_setup.xml`` written by step 4 (an OSC ``ModelWarperV3Document``)  
and applies its scaling steps, in document order, to the base model:

==========================================  ====================================  
OSC scaling step                            what is warped  
==========================================  ====================================  
ThinPlateSplineMeshesScalingStep            mesh vertices -> new .obj files  
ThinPlateSplineOffsetFrameTranslation...    PhysicalOffsetFrame translations  
ThinPlateSplinePathPointsScalingStep        PathPoint locations  
ThinPlateSplineStationsScalingStep          Station / Marker locations  
ThinPlateSplineWrapCylinderScalingStep      WrapCylinder centre, axis, radius  
ManuallyScaleBodySegmentsScalingStep        OpenSim body scaling (scale factors)  
==========================================  ====================================

TPS details (reverse-engineered from OSC output; matches OSC to < 0.001 mm on  
the MRI2MSK example participant):

* 3-D thin-plate spline with kernel U(r) = r, landmarks multiplied by the  
  source/destination prescale, fitted source -> destination.  
* Affine part ``f(p) = a0 + [a1 a2 a3] p``. ``apply_affine_translation`` (default  
  false) toggles a0. With ``apply_affine_rotation`` false (default) the linear  
  part is replaced by ``diag(|a1|, |a2|, |a3|)`` (column norms) when  
  ``apply_affine_scale`` is true (default), else by identity.  
  ``apply_non_affine_warp`` (default true) toggles the radial-basis part.  
* ``compensate_for_frame_changes``: a point given in frame F is moved into the  
  landmarks frame L with the *original* model's default pose, warped, and  
  moved back into F with the pose of the model *as warped so far*.  
* Wrap cylinders: centre c -> f(c); axis z' = f(c + 1 mm * z) - f(c);  
  radius' = |f(c + r x) - f(c)|; x' = that vector made orthogonal to z'.

## Contents

- class [`TPS`](#tps) — 
  - [`TPS.fit`](#tpsfit) — 
- class [`Step`](#step) — 
  - [`Step.enabled`](#stepenabled) — 
  - [`Step.flag`](#stepflag) — 
  - [`Step.targets`](#steptargets) — 
- class [`ModelWarper`](#modelwarper) — 
  - [`ModelWarper.run`](#modelwarperrun) — 
- [`read_mesh`](#read_mesh) — Read vertices (N,3) and triangle faces (M,3, 0-based) from .vtp/.obj/.stl.
- [`write_obj`](#write_obj) — 
- [`read_warp_setup`](#read_warp_setup) — 
- [`warp_model`](#warp_model) — 

<a id="tps"></a>

## class `TPS`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L50)</sub>

<a id="tpsfit"></a>

### `TPS.fit`

```python
TPS.fit(src, dst)
```

| input | type | default |
|---|---|---|
| `src` | – | required |
| `dst` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L56)</sub>

<a id="step"></a>

## class `Step`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L152)</sub>

<a id="stepenabled"></a>

### `Step.enabled`

```python
Step.enabled() -> bool
```

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L158)</sub>

<a id="stepflag"></a>

### `Step.flag`

```python
Step.flag(key, default) -> bool
```

| input | type | default |
|---|---|---|
| `key` | – | required |
| `default` | – | required |

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L161)</sub>

<a id="steptargets"></a>

### `Step.targets`

```python
Step.targets(key) -> list[str]
```

| input | type | default |
|---|---|---|
| `key` | – | required |

**returns** `list[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L165)</sub>

<a id="modelwarper"></a>

## class `ModelWarper`

```python
ModelWarper(model_file, setup_file, out_model_file, geometry_dir, log=print)
```

| input | type | default |
|---|---|---|
| `model_file` | – | required |
| `setup_file` | – | required |
| `out_model_file` | – | required |
| `geometry_dir` | – | required |
| `log` | – | `print` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L180)</sub>

<a id="modelwarperrun"></a>

### `ModelWarper.run`

```python
ModelWarper.run() -> Path
```

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L352)</sub>

### `read_mesh`

```python
read_mesh(path) -> tuple[np.ndarray, np.ndarray]
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `tuple[np.ndarray, np.ndarray]`

Read vertices (N,3) and triangle faces (M,3, 0-based) from .vtp/.obj/.stl.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L97)</sub>

### `write_obj`

```python
write_obj(path, V, F) -> None
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `V` | – | required |
| `F` | – | required |

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L139)</sub>

### `read_warp_setup`

```python
read_warp_setup(path) -> list[Step]
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `list[Step]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L169)</sub>

### `warp_model`

```python
warp_model(model_file, setup_file, out_model_file, geometry_dir, log=print) -> Path
```

| input | type | default |
|---|---|---|
| `model_file` | – | required |
| `setup_file` | – | required |
| `out_model_file` | – | required |
| `geometry_dir` | – | required |
| `log` | – | `print` |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/model_warper.py#L383)</sub>
