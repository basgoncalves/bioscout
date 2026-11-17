# `bioscout.model.mri2msk.pipeline`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py)

MRI2MSK warping pipeline - Python port of the executeStepXX functions in MRI2MSK.m.

Steps (numbering follows the README / GUI):

    step1_rescale_and_align        executeStep01  
    step2_align_skin               executeStep02  
    step2b_add_skin_to_base_model  executeStep02b  
    (3: user creates landmarks in OpenSim Creator Mesh Warper)  
    step4_create_warp_setup        executeStep03  
    (5: user warps the model in OpenSim Creator Model Warper)  
    step6_replace_skin             executeStep04b  
    step7a_correct_torsion         executeStep05  
    step7b_correct_mass_centers    executeStep06  
    step8_mechanical_knee_axis     executeStep07

The GUI and the post-scaling steps (IK, muscle path check, muscle optimiser) are  
not ported yet.

## Contents

- class [`Config`](#config) — 
  - [`Config.stl_dir`](#configstl_dir) — 
  - [`Config.skin_dir`](#configskin_dir) — 
  - [`Config.landmark_dir`](#configlandmark_dir) — 
  - [`Config.warped_dir`](#configwarped_dir) — 
  - [`Config.has_skin`](#confighas_skin) — 
- class [`BoneAlignment`](#bonealignment) — 
  - [`BoneAlignment.to_dict`](#bonealignmentto_dict) — 
  - [`BoneAlignment.from_dict`](#bonealignmentfrom_dict) — 
- [`save_prealignment`](#save_prealignment) — 
- [`load_prealignment`](#load_prealignment) — Load the JSON written by step 1, or fall back to the MATLAB .mat file.
- [`scale_factor_to_participant`](#scale_factor_to_participant) — Factor from base-model size back to participant [m] (MATLAB 1/(resize*1000)).
- [`jcs_staple`](#jcs_staple) — Default JCS routine: the Python port of STAPLE in ``mri2msk.staple``.
- [`step1_rescale_and_align`](#step1_rescale_and_align) — Align each participant bone to the OpenSim CS and rescale it to the base bone size.
- [`step2_align_skin`](#step2_align_skin) — Transform skin STLs with the bone alignments; write unscaled and base-scaled copies.
- [`step2b_add_skin_to_base_model`](#step2b_add_skin_to_base_model) — Attach the base-scaled skin meshes to the base model for visual reference.
- [`prepare_mesh_warper_files`](#prepare_mesh_warper_files) — Copy base + participant meshes for each bone into ``landmarks/meshes``.
- [`resolve_warp_template`](#resolve_warp_template) — Pick the warp setup template (no skin / skin / sparse skin with *_2.stl files).
- [`step4_create_warp_setup`](#step4_create_warp_setup) — Fill the OpenSim Creator warp template with scale factors, landmark paths and markers.
- [`warp_source_model`](#warp_source_model) — Model to warp: skin model from step 2 (marker-adjusted version preferred), else base.
- [`step5_warp_model`](#step5_warp_model) — Apply warp_setup.xml to the model (Python Model Warper, replaces OSC step).
- [`step6_replace_skin`](#step6_replace_skin) — Point skin meshes of the warped model to the participant-scale skin STLs.
- [`step7a_correct_torsion`](#step7a_correct_torsion) — Undo the femoral/tibial torsion introduced by warping (relative to the base model).
- [`step7b_correct_mass_centers`](#step7b_correct_mass_centers) — Set body COMs from warped *MassCenter* markers and scale knee/patella splines.
- [`compute_mechanical_knee_axis`](#compute_mechanical_knee_axis) — Frontal-plane femur-tibia angle (deg) per side from the step-1 frames.
- [`mka_label`](#mka_label) — 
- [`participant_bone_meshes`](#participant_bone_meshes) — Participant bone STLs (MRI frame, mm) decimated for plotting.
- [`plot_mka`](#plot_mka) — 3-D debug plot of pelvis/femur/tibia frames (replaces the MATLAB uifigure).
- [`step8_mechanical_knee_axis`](#step8_mechanical_knee_axis) — Apply half the MKA angle to the femoral-condyle and tibial-plateau weld frames.
- [`detect_completed_steps`](#detect_completed_steps) — Rough equivalent of the GUI's detectCompletedSteps().

<a id="config"></a>

## class `Config`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L40)</sub>

<a id="configstl_dir"></a>

### `Config.stl_dir`

```python
Config.stl_dir() -> Path
```

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L56)</sub>

<a id="configskin_dir"></a>

### `Config.skin_dir`

```python
Config.skin_dir() -> Path
```

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L60)</sub>

<a id="configlandmark_dir"></a>

### `Config.landmark_dir`

```python
Config.landmark_dir() -> Path
```

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L64)</sub>

<a id="configwarped_dir"></a>

### `Config.warped_dir`

```python
Config.warped_dir() -> Path
```

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L68)</sub>

<a id="confighas_skin"></a>

### `Config.has_skin`

```python
Config.has_skin() -> bool
```

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L72)</sub>

<a id="bonealignment"></a>

## class `BoneAlignment`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L80)</sub>

<a id="bonealignmentto_dict"></a>

### `BoneAlignment.to_dict`

```python
BoneAlignment.to_dict()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L85)</sub>

<a id="bonealignmentfrom_dict"></a>

### `BoneAlignment.from_dict`

```python
BoneAlignment.from_dict(d)
```

| input | type | default |
|---|---|---|
| `d` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L91)</sub>

### `save_prealignment`

```python
save_prealignment(stl_dir: Path, pre: dict[str, BoneAlignment]) -> Path
```

| input | type | default |
|---|---|---|
| `stl_dir` | Path | required |
| `pre` | dict[str, BoneAlignment] | required |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L97)</sub>

### `load_prealignment`

```python
load_prealignment(stl_dir: Path) -> dict[str, BoneAlignment]
```

| input | type | default |
|---|---|---|
| `stl_dir` | Path | required |

**returns** `dict[str, BoneAlignment]`

Load the JSON written by step 1, or fall back to the MATLAB .mat file.

Keys are canonical: 'pelvis', 'femur_l', 'femur_r', 'tibia_l', 'tibia_r'.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L103)</sub>

### `scale_factor_to_participant`

```python
scale_factor_to_participant(al: BoneAlignment) -> float
```

| input | type | default |
|---|---|---|
| `al` | BoneAlignment | required |

**returns** `float`

Factor from base-model size back to participant [m] (MATLAB 1/(resize*1000)).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L144)</sub>

### `jcs_staple`

```python
jcs_staple(stl_path: Path, bone: str, side: str)
```

| input | type | default |
|---|---|---|
| `stl_path` | Path | required |
| `bone` | str | required |
| `side` | str | required |

Default JCS routine: the Python port of STAPLE in ``mri2msk.staple``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L179)</sub>

### `step1_rescale_and_align`

```python
step1_rescale_and_align(
    cfg: Config,
    jcs_func: JCSFunc = jcs_staple
) -> dict[str, BoneAlignment]
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |
| `jcs_func` | JCSFunc | `jcs_staple` |

**returns** `dict[str, BoneAlignment]`

Align each participant bone to the OpenSim CS and rescale it to the base bone size.

Writes ``*_resizedToOpenSim_inOpenSimCS.stl`` next to each input STL and  
``stls/preAligningToOpenSim.json``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L195)</sub>

### `step2_align_skin`

```python
step2_align_skin(cfg: Config, n_vertices: int = 10000) -> None
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |
| `n_vertices` | int | `10000` |

**returns** `None`

Transform skin STLs with the bone alignments; write unscaled and base-scaled copies.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L238)</sub>

### `step2b_add_skin_to_base_model`

```python
step2b_add_skin_to_base_model(cfg: Config) -> Path
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |

**returns** `Path`

Attach the base-scaled skin meshes to the base model for visual reference.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L267)</sub>

### `prepare_mesh_warper_files`

```python
prepare_mesh_warper_files(cfg: Config) -> dict[str, dict]
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |

**returns** `dict[str, dict]`

Copy base + participant meshes for each bone into ``landmarks/meshes``.

Returns per bone: source (base STL), destination (participant STL in  
OpenSim CS) and the landmark CSV paths the user should export to.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L309)</sub>

### `resolve_warp_template`

```python
resolve_warp_template(cfg: Config) -> Path
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |

**returns** `Path`

Pick the warp setup template (no skin / skin / sparse skin with *_2.stl files).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L339)</sub>

### `step4_create_warp_setup`

```python
step4_create_warp_setup(cfg: Config, template: Path | None = None) -> Path
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |
| `template` | Path \| None | `None` |

**returns** `Path`

Fill the OpenSim Creator warp template with scale factors, landmark paths and markers.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L361)</sub>

### `warp_source_model`

```python
warp_source_model(cfg: Config) -> Path
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |

**returns** `Path`

Model to warp: skin model from step 2 (marker-adjusted version preferred), else base.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L403)</sub>

### `step5_warp_model`

```python
step5_warp_model(cfg: Config, model_file: Path | None = None) -> Path
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |
| `model_file` | Path \| None | `None` |

**returns** `Path`

Apply warp_setup.xml to the model (Python Model Warper, replaces OSC step).

Writes warpedModel/warpedModel.osim and warpedModel/warpedGeometry/*.obj.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L415)</sub>

### `step6_replace_skin`

```python
step6_replace_skin(cfg: Config, suffix: str = '_scaledToBaseModel') -> Path
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |
| `suffix` | str | `'_scaledToBaseModel'` |

**returns** `Path`

Point skin meshes of the warped model to the participant-scale skin STLs.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L430)</sub>

### `step7a_correct_torsion`

```python
step7a_correct_torsion(cfg: Config) -> Path
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |

**returns** `Path`

Undo the femoral/tibial torsion introduced by warping (relative to the base model).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L451)</sub>

### `step7b_correct_mass_centers`

```python
step7b_correct_mass_centers(cfg: Config) -> Path
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |

**returns** `Path`

Set body COMs from warped *MassCenter* markers and scale knee/patella splines.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L536)</sub>

### `compute_mechanical_knee_axis`

```python
compute_mechanical_knee_axis(pre: dict[str, BoneAlignment]) -> dict[str, float]
```

| input | type | default |
|---|---|---|
| `pre` | dict[str, BoneAlignment] | required |

**returns** `dict[str, float]`

Frontal-plane femur-tibia angle (deg) per side from the step-1 frames.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L581)</sub>

### `mka_label`

```python
mka_label(side: str, angle: float) -> str
```

| input | type | default |
|---|---|---|
| `side` | str | required |
| `angle` | float | required |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L590)</sub>

### `participant_bone_meshes`

```python
participant_bone_meshes(
    cfg: Config,
    n_faces: int = 4000
) -> dict[str, tuple[np.ndarray, np.ndarray]]
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |
| `n_faces` | int | `4000` |

**returns** `dict[str, tuple[np.ndarray, np.ndarray]]`

Participant bone STLs (MRI frame, mm) decimated for plotting.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L596)</sub>

### `plot_mka`

```python
plot_mka(
    pre: dict[str, BoneAlignment],
    mka: dict[str, float],
    axis_len: float = 50.0,
    bones: dict | None = None
)
```

| input | type | default |
|---|---|---|
| `pre` | dict[str, BoneAlignment] | required |
| `mka` | dict[str, float] | required |
| `axis_len` | float | `50.0` |
| `bones` | dict \| None | `None` |

3-D debug plot of pelvis/femur/tibia frames (replaces the MATLAB uifigure).

``bones``: optional {name: (vertices, faces)} in the same (MRI, mm) frame,  
drawn as translucent surfaces under the coordinate systems.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L616)</sub>

### `step8_mechanical_knee_axis`

```python
step8_mechanical_knee_axis(
    cfg: Config,
    confirm: bool | Callable[[dict], bool] = True,
    show_plot: bool = True
) -> Path | None
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |
| `confirm` | bool \| Callable[[dict], bool] | `True` |
| `show_plot` | bool | `True` |

**returns** `Path \| None`

Apply half the MKA angle to the femoral-condyle and tibial-plateau weld frames.

``confirm``: True = apply without asking, False = only report, or a callable  
receiving ``{'l': deg, 'r': deg}`` (model correction values) returning bool.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L667)</sub>

### `detect_completed_steps`

```python
detect_completed_steps(cfg: Config) -> dict[str, bool]
```

| input | type | default |
|---|---|---|
| `cfg` | Config | required |

**returns** `dict[str, bool]`

Rough equivalent of the GUI's detectCompletedSteps().

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/pipeline.py#L717)</sub>
