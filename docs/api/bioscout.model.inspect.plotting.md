# `bioscout.model.inspect.plotting`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/plotting.py)

Plot moment-arm / muscle-length sweeps, before vs after correction.

No OpenSim dependency -- operates on the CoordinateSweep objects from  
moment_arms.compute_sweeps. Optionally overlays literature moment-arm bands  
(cm->mm) on the moment-arm grids.

## Contents

- [`plot_coordinate`](#plot_coordinate) — Plot one figure (grid of muscles) for a single coordinate. Returns file path.
- [`plot_comparison`](#plot_comparison) — Plot every coordinate present in either sweep dict. Returns saved file paths.

### `plot_coordinate`

```python
plot_coordinate(
    coord_name,
    before,
    after,
    quantity='moment_arm',
    outdir='.',
    mark_discontinuities=True,
    literature=None
)
```

| input | type | default |
|---|---|---|
| `coord_name` | – | required |
| `before` | – | required |
| `after` | – | required |
| `quantity` | – | `'moment_arm'` |
| `outdir` | – | `'.'` |
| `mark_discontinuities` | – | `True` |
| `literature` | – | `None` |

Plot one figure (grid of muscles) for a single coordinate. Returns file path.

`literature` (moment_arm only): {muscle: [(label, color, ang_deg, mean_mm, sd_mm)]}.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/plotting.py#L32)</sub>

### `plot_comparison`

```python
plot_comparison(
    before_sweeps,
    after_sweeps,
    outdir='.',
    quantities=('moment_arm', 'length'),
    mark_discontinuities=True,
    literature=None
)
```

| input | type | default |
|---|---|---|
| `before_sweeps` | – | required |
| `after_sweeps` | – | required |
| `outdir` | – | `'.'` |
| `quantities` | – | `('moment_arm', 'length')` |
| `mark_discontinuities` | – | `True` |
| `literature` | – | `None` |

Plot every coordinate present in either sweep dict. Returns saved file paths.

`literature`: {coordinate_name: {muscle: [(label, color, ang, mean_mm, sd_mm)]}}.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/plotting.py#L107)</sub>
