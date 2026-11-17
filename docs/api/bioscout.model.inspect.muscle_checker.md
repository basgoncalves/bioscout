# `bioscout.model.inspect.muscle_checker`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py)

Motion-driven muscle-path checker -- Python port of the MATLAB `muscleChecker`.

Inputs: an OpenSim model (.osim) and one or more kinematics files (.mot).  
Mirrors the MATLAB pipeline `checkAndFixMusclePaths` / `calcMuscleLengthsForMotion`:

  Phase 1  static same-body geometry check  (project points out of cylinders)  
  Phase 1b temp model with the Phase-1 fixes  
  Phase 2  compute muscle LENGTHS across the motion frames, detect discontinuities  
  Phase 3  cross-body projection (worst penetration over motion frames)  ->  
           radius reduction (binary search over the full motion)  ->  motion rejection  
  Phase 4  summary  
  outer    iteration loop; writes <model>_modWO.osim and <model>_modWO_log.txt

Defaults, thresholds and behaviour match the MATLAB version. Requires `opensim`.

## Contents

- class [`MotionModel`](#motionmodel) — 
  - [`MotionModel.n_frames`](#motionmodeln_frames) — 
  - [`MotionModel.pose`](#motionmodelpose) — 
  - [`MotionModel.lengths`](#motionmodellengths) — 
- class [`Corrections`](#corrections) — 
- [`read_mot`](#read_mot) — Return (time, {column: array}, in_degrees, column_names).
- [`get_muscle_subset`](#get_muscle_subset) — 
- [`derive_side`](#derive_side) — 
- [`filter_by_side`](#filter_by_side) — 
- [`propose_cross_body`](#propose_cross_body) — Scan the given motion frames, track worst penetration, propose projections.
- [`estimate_min_radius`](#estimate_min_radius) — 
- [`apply_radius_reductions`](#apply_radius_reductions) — 
- [`apply_corrections`](#apply_corrections) — 
- [`calc_muscle_lengths_for_motion`](#calc_muscle_lengths_for_motion) — 
- [`check_and_fix_muscle_paths`](#check_and_fix_muscle_paths) — Returns (success, corrected_model_path, log_path).
- [`compute_lengths`](#compute_lengths) — (time, muscle_names, N x M lengths) for the filtered muscles over the motion.
- [`plot_length_waveforms`](#plot_length_waveforms) — 

<a id="motionmodel"></a>

## class `MotionModel`

```python
MotionModel(
    model_path: str,
    mot_path: str,
    coordinate_names: Optional[list] = None,
    filter_freq: float = 0.0
)
```

| input | type | default |
|---|---|---|
| `model_path` | str | required |
| `mot_path` | str | required |
| `coordinate_names` | Optional[list] | `None` |
| `filter_freq` | float | `0.0` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L98)</sub>

<a id="motionmodeln_frames"></a>

### `MotionModel.n_frames`

```python
MotionModel.n_frames()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L147)</sub>

<a id="motionmodelpose"></a>

### `MotionModel.pose`

```python
MotionModel.pose(frame: int)
```

| input | type | default |
|---|---|---|
| `frame` | int | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L150)</sub>

<a id="motionmodellengths"></a>

### `MotionModel.lengths`

```python
MotionModel.lengths(muscle_names: list, frames=None) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `muscle_names` | list | required |
| `frames` | – | `None` |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L162)</sub>

<a id="corrections"></a>

## class `Corrections`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L344)</sub>

### `read_mot`

```python
read_mot(path: str)
```

| input | type | default |
|---|---|---|
| `path` | str | required |

Return (time, {column: array}, in_degrees, column_names).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L73)</sub>

### `get_muscle_subset`

```python
get_muscle_subset(model, muscle_filter) -> list
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `muscle_filter` | – | required |

**returns** `list`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L180)</sub>

### `derive_side`

```python
derive_side(motion_path: str) -> str
```

| input | type | default |
|---|---|---|
| `motion_path` | str | required |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L190)</sub>

### `filter_by_side`

```python
filter_by_side(names: list, side: str) -> list
```

| input | type | default |
|---|---|---|
| `names` | list | required |
| `side` | str | required |

**returns** `list`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L198)</sub>

### `propose_cross_body`

```python
propose_cross_body(mm, combos, scan_frames, verbose=True)
```

| input | type | default |
|---|---|---|
| `mm` | – | required |
| `combos` | – | required |
| `scan_frames` | – | required |
| `verbose` | – | `True` |

Scan the given motion frames, track worst penetration, propose projections.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L244)</sub>

### `estimate_min_radius`

```python
estimate_min_radius(
    model_path,
    mot_path,
    muscle,
    wrap_name,
    r0,
    coordinate_names,
    filter_freq,
    dk,
    verbose=True
)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `mot_path` | – | required |
| `muscle` | – | required |
| `wrap_name` | – | required |
| `r0` | – | required |
| `coordinate_names` | – | required |
| `filter_freq` | – | required |
| `dk` | – | required |
| `verbose` | – | `True` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L294)</sub>

### `apply_radius_reductions`

```python
apply_radius_reductions(model, reductions, verbose=True)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `reductions` | – | required |
| `verbose` | – | `True` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L329)</sub>

### `apply_corrections`

```python
apply_corrections(model_path, output_path, corr: Corrections, verbose=True)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `output_path` | – | required |
| `corr` | Corrections | required |
| `verbose` | – | `True` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L351)</sub>

### `calc_muscle_lengths_for_motion`

```python
calc_muscle_lengths_for_motion(
    model_path,
    motion_files,
    coordinate_names=None,
    muscle_filter=None,
    filter_freq=0.0,
    dk=None,
    verbose=True
)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `motion_files` | – | required |
| `coordinate_names` | – | `None` |
| `muscle_filter` | – | `None` |
| `filter_freq` | – | `0.0` |
| `dk` | – | `None` |
| `verbose` | – | `True` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L364)</sub>

### `check_and_fix_muscle_paths`

```python
check_and_fix_muscle_paths(
    model_file,
    motion_files,
    coordinate_names=None,
    muscle_filter=None,
    filter_freq=0.0,
    max_iterations=3,
    min_jump_mm=1.0,
    out_dir=None,
    verbose=True
)
```

| input | type | default |
|---|---|---|
| `model_file` | – | required |
| `motion_files` | – | required |
| `coordinate_names` | – | `None` |
| `muscle_filter` | – | `None` |
| `filter_freq` | – | `0.0` |
| `max_iterations` | – | `3` |
| `min_jump_mm` | – | `1.0` |
| `out_dir` | – | `None` |
| `verbose` | – | `True` |

Returns (success, corrected_model_path, log_path).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L497)</sub>

### `compute_lengths`

```python
compute_lengths(
    model_path,
    mot_path,
    coordinate_names=None,
    muscle_filter=None,
    filter_freq=0.0
)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `mot_path` | – | required |
| `coordinate_names` | – | `None` |
| `muscle_filter` | – | `None` |
| `filter_freq` | – | `0.0` |

(time, muscle_names, N x M lengths) for the filtered muscles over the motion.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L573)</sub>

### `plot_length_waveforms`

```python
plot_length_waveforms(time, names, before_L, after_L, outdir, tag, dk=None)
```

| input | type | default |
|---|---|---|
| `time` | – | required |
| `names` | – | required |
| `before_L` | – | required |
| `after_L` | – | required |
| `outdir` | – | required |
| `tag` | – | required |
| `dk` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/muscle_checker.py#L584)</sub>
