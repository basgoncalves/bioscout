# `bioscout.model.inspect.wrap_fixer`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/wrap_fixer.py)

Detect and fix muscle path points that lie inside wrap cylinders.

Ported from the MATLAB ``checkAllPathPointsInsideCylinders`` /  
``applyCorrectionSuggestions`` logic (Phase 1 of the original pipeline) plus an  
optional motion-free cross-body scan over the coordinate range of motion.

This is the correction that removes the geometry violations responsible for  
discontinuous, non-physiological moment arms. Requires ``import opensim``.

## Contents

- class [`PointProjection`](#pointprojection) — 
- class [`FixResult`](#fixresult) — 
- [`find_wrap_object`](#find_wrap_object) — Return (wrap_object, owning_body) for a wrap object by name, or (None, None).
- [`check_points_inside_cylinders`](#check_points_inside_cylinders) — Find path points inside *same-body* wrap cylinders and propose projections.
- [`apply_projections`](#apply_projections) — Apply (write into the model) all auto-fixable projections. Returns count applied.
- [`fix_model`](#fix_model) — Load a model, project path points out of same-body wrap cylinders, save it.
- [`fix_model_full`](#fix_model_full) — Static (same-body) fix + optional sweep-driven cross-body fix.

<a id="pointprojection"></a>

## class `PointProjection`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/wrap_fixer.py#L33)</sub>

<a id="fixresult"></a>

## class `FixResult`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/wrap_fixer.py#L48)</sub>

### `find_wrap_object`

```python
find_wrap_object(model, wrap_obj_name: str)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `wrap_obj_name` | str | required |

Return (wrap_object, owning_body) for a wrap object by name, or (None, None).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/wrap_fixer.py#L82)</sub>

### `check_points_inside_cylinders`

```python
check_points_inside_cylinders(
    model,
    state,
    muscle_names: list,
    max_penetration_mm: float = 5.0,
    margin: float = 0.0001,
    max_displacement_mm: float = 5.0,
    verbose: bool = True
) -> list[PointProjection]
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `state` | – | required |
| `muscle_names` | list | required |
| `max_penetration_mm` | float | `5.0` |
| `margin` | float | `0.0001` |
| `max_displacement_mm` | float | `5.0` |
| `verbose` | bool | `True` |

**returns** `list[PointProjection]`

Find path points inside *same-body* wrap cylinders and propose projections.

Deep violations (> ``max_penetration_mm``) are reported but not auto-fixed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/wrap_fixer.py#L98)</sub>

### `apply_projections`

```python
apply_projections(model, projections: list[PointProjection], verbose: bool = True) -> int
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `projections` | list[PointProjection] | required |
| `verbose` | bool | `True` |

**returns** `int`

Apply (write into the model) all auto-fixable projections. Returns count applied.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/wrap_fixer.py#L198)</sub>

### `fix_model`

```python
fix_model(
    input_osim: str,
    output_osim: str,
    muscle_filter: Optional[list] = None,
    max_penetration_mm: float = 5.0,
    verbose: bool = True
) -> FixResult
```

| input | type | default |
|---|---|---|
| `input_osim` | str | required |
| `output_osim` | str | required |
| `muscle_filter` | Optional[list] | `None` |
| `max_penetration_mm` | float | `5.0` |
| `verbose` | bool | `True` |

**returns** `FixResult`

Load a model, project path points out of same-body wrap cylinders, save it.

  
**Parameters**

input_osim, output_osim : str  
    Paths to the original and corrected ``.osim`` files.  
muscle_filter : list[str] | None  
    Substrings to restrict which muscles are checked. ``None`` = all muscles.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/wrap_fixer.py#L230)</sub>

### `fix_model_full`

```python
fix_model_full(
    input_osim: str,
    output_osim: str,
    muscle_filter: Optional[list] = None,
    max_penetration_mm: float = 5.0,
    cross_body: bool = True,
    coordinate_names: Optional[list] = None,
    suspect_muscles: Optional[set] = None,
    n_pose: int = 30,
    max_displacement_mm: float = 5.0,
    margin_base_m: float = 0.002,
    margin_frac: float = 0.5,
    verbose: bool = True
) -> FixResult
```

| input | type | default |
|---|---|---|
| `input_osim` | str | required |
| `output_osim` | str | required |
| `muscle_filter` | Optional[list] | `None` |
| `max_penetration_mm` | float | `5.0` |
| `cross_body` | bool | `True` |
| `coordinate_names` | Optional[list] | `None` |
| `suspect_muscles` | Optional[set] | `None` |
| `n_pose` | int | `30` |
| `max_displacement_mm` | float | `5.0` |
| `margin_base_m` | float | `0.002` |
| `margin_frac` | float | `0.5` |
| `verbose` | bool | `True` |

**returns** `FixResult`

Static (same-body) fix + optional sweep-driven cross-body fix.

``suspect_muscles`` restricts the (expensive) cross-body scan to muscles  
known to have a discontinuity. ``coordinate_names`` are the coordinates whose  
range-of-motion sweeps provide the poses for the cross-body scan.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/wrap_fixer.py#L274)</sub>
