# `bioscout.model.inspect.radius_reduce`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/radius_reduce.py)

Radius-reduction fallback (MATLAB Phase 3, priority 2).

When projecting a path point can't remove a discontinuity (e.g. the wrap solver  
flips branches rather than a point sitting inside the cylinder), the next lever  
is to shrink the wrap cylinder's radius until the muscle's length/moment-arm  
curve becomes smooth. This module binary-searches the largest radius that  
removes the discontinuity, for muscles still flagged after the projection passes.

Requires ``import opensim``. Sweeps are done with the same MomentArmModel used  
elsewhere, so constraint handling / assemble-skipping are consistent.

## Contents

- [`reduce_radii`](#reduce_radii) — Binary-search a smaller radius per muscle until its discontinuity is gone.
- [`apply_radius_reductions`](#apply_radius_reductions) — 
- [`fix_with_radius_reduction`](#fix_with_radius_reduction) — Run the projection passes (wrap_fixer.fix_model_full), then -- for any suspect muscle still discontinuous -- shrink its wrap cylinder. Returns the FixResult, with a ``radius_reductions`` attribute attached.

### `reduce_radii`

```python
reduce_radii(
    model_path: str,
    muscles: list,
    coords: list,
    dk: dict,
    n: int = 40,
    min_radius_floor: float = 0.005,
    max_reduction: float = 0.01,
    tol: float = 0.0005,
    max_iter: int = 8,
    verbose: bool = True
) -> list
```

| input | type | default |
|---|---|---|
| `model_path` | str | required |
| `muscles` | list | required |
| `coords` | list | required |
| `dk` | dict | required |
| `n` | int | `40` |
| `min_radius_floor` | float | `0.005` |
| `max_reduction` | float | `0.01` |
| `tol` | float | `0.0005` |
| `max_iter` | int | `8` |
| `verbose` | bool | `True` |

**returns** `list`

Binary-search a smaller radius per muscle until its discontinuity is gone.

Returns a list of dicts: muscle, wrap, old_radius, new_radius, reduction_mm.  
Tests candidates on temporary models; does not modify ``model_path``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/radius_reduce.py#L59)</sub>

### `apply_radius_reductions`

```python
apply_radius_reductions(model, reductions: list, verbose: bool = True) -> int
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `reductions` | list | required |
| `verbose` | bool | `True` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/radius_reduce.py#L128)</sub>

### `fix_with_radius_reduction`

```python
fix_with_radius_reduction(
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
    radius_reduction: bool = True,
    detect_kwargs: Optional[dict] = None,
    rr_n: int = 40,
    verbose: bool = True
)
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
| `radius_reduction` | bool | `True` |
| `detect_kwargs` | Optional[dict] | `None` |
| `rr_n` | int | `40` |
| `verbose` | bool | `True` |

Run the projection passes (wrap_fixer.fix_model_full), then -- for any  
suspect muscle still discontinuous -- shrink its wrap cylinder. Returns the  
FixResult, with a ``radius_reductions`` attribute attached.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/radius_reduce.py#L142)</sub>
