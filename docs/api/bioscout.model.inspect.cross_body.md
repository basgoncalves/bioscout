# `bioscout.model.inspect.cross_body`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/cross_body.py)

Cross-body wrap penetration fix, driven by coordinate sweeps (no .mot needed).

Ports the MATLAB pipeline's Phase 3 *cross-body point projection*: a path point  
on one body can dip inside a wrap cylinder on a different body only at certain  
poses, producing a pose-dependent muscle-length / moment-arm discontinuity. We  
reuse the inspection sweeps as the "motion": pose the model across each  
coordinate's range, track the worst penetration per path-point/cylinder pair,  
then project the point just outside the cylinder at that worst pose.

Radius-reduction and motion-rejection fallbacks (MATLAB Phase 3 priorities 2-3)  
are not implemented here.

## Contents

- [`scan_cross_body`](#scan_cross_body) — Return cross-body projections (best, smallest-displacement per muscle).

### `scan_cross_body`

```python
scan_cross_body(
    mam,
    muscle_names: list,
    coordinate_names: list,
    n_pose: int = 30,
    max_displacement_mm: float = 5.0,
    margin_base_m: float = 0.002,
    margin_frac: float = 0.5,
    verbose: bool = True
) -> list[PointProjection]
```

| input | type | default |
|---|---|---|
| `mam` | – | required |
| `muscle_names` | list | required |
| `coordinate_names` | list | required |
| `n_pose` | int | `30` |
| `max_displacement_mm` | float | `5.0` |
| `margin_base_m` | float | `0.002` |
| `margin_frac` | float | `0.5` |
| `verbose` | bool | `True` |

**returns** `list[PointProjection]`

Return cross-body projections (best, smallest-displacement per muscle).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/cross_body.py#L75)</sub>
