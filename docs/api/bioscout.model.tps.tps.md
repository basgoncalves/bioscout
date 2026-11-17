# `bioscout.model.tps.tps`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/tps.py)

Thin-plate-spline transform for a single body.

Refactor of the original ``OneBodyTPS`` class. Key changes:  
  * the ``tps`` dependency is imported lazily, so the package imports cleanly in  
    a plain numpy/pandas environment (and tests can monkeypatch it),  
  * no work in ``__init__`` beyond storing inputs; fitting is explicit via  
    :meth:`fit`, transforms via the ``transform_*`` methods (no hidden side  
    effects on construction),  
  * accepts plain numpy arrays *or* DataFrames with ``['r','a','s']`` columns,  
  * type hints + docstrings.

The spline is fit on **bone landmarks** (source = generic/scaled model space,  
target = subject MRI space) and then applied to every other point set attached  
to that body (muscle path points, skin markers, wrapping-surface points,  
full bone meshes).

## Contents

- class [`OneBodyTPS`](#onebodytps) — Fit a TPS on one body's bone landmarks and apply it to other point sets.
  - [`OneBodyTPS.fit`](#onebodytpsfit) — Fit the spline mapping ``source_bone`` landmarks onto ``target_bone``.
  - [`OneBodyTPS.is_fitted`](#onebodytpsis_fitted) — 
  - [`OneBodyTPS.transform_points`](#onebodytpstransform_points) — Apply the fitted spline to an (N,3) array or r/a/s DataFrame.
  - [`OneBodyTPS.transform_surface`](#onebodytpstransform_surface) — Apply the spline to a ``pyvista.PolyData`` mesh, returning a new mesh.
  - [`OneBodyTPS.transform_wraps`](#onebodytpstransform_wraps) — Transform wrapping-surface defining points.

<a id="onebodytps"></a>

## class `OneBodyTPS`

```python
OneBodyTPS(body_name: str, alpha: float = 0.002)
```

| input | type | default |
|---|---|---|
| `body_name` | str | required |
| `alpha` | float | `0.002` |

Fit a TPS on one body's bone landmarks and apply it to other point sets.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/tps.py#L51)</sub>

<a id="onebodytpsfit"></a>

### `OneBodyTPS.fit`

```python
OneBodyTPS.fit(
    source_bone,
    target_bone,
    exclude: Optional[Sequence[str]] = None
) -> 'OneBodyTPS'
```

| input | type | default |
|---|---|---|
| `source_bone` | – | required |
| `target_bone` | – | required |
| `exclude` | Optional[Sequence[str]] | `None` |

**returns** `'OneBodyTPS'`

Fit the spline mapping ``source_bone`` landmarks onto ``target_bone``.

If DataFrames are passed, ``exclude`` may name index labels (markers) to  
leave out of the fit (e.g. unreliable landmarks); the index order of the  
two frames must correspond.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/tps.py#L60)</sub>

<a id="onebodytpsis_fitted"></a>

### `OneBodyTPS.is_fitted`

```python
OneBodyTPS.is_fitted() -> bool
```

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/tps.py#L97)</sub>

<a id="onebodytpstransform_points"></a>

### `OneBodyTPS.transform_points`

```python
OneBodyTPS.transform_points(points) -> Array
```

| input | type | default |
|---|---|---|
| `points` | – | required |

**returns** `Array`

Apply the fitted spline to an (N,3) array or r/a/s DataFrame.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/tps.py#L105)</sub>

<a id="onebodytpstransform_surface"></a>

### `OneBodyTPS.transform_surface`

```python
OneBodyTPS.transform_surface(polydata)
```

| input | type | default |
|---|---|---|
| `polydata` | – | required |

Apply the spline to a ``pyvista.PolyData`` mesh, returning a new mesh.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/tps.py#L110)</sub>

<a id="onebodytpstransform_wraps"></a>

### `OneBodyTPS.transform_wraps`

```python
OneBodyTPS.transform_wraps(wrap_df: pd.DataFrame)
```

| input | type | default |
|---|---|---|
| `wrap_df` | pd.DataFrame | required |

Transform wrapping-surface defining points.

``wrap_df`` must have ``radius_point``, ``axis_point`` and  
``translation`` columns (each an array-like of 3 floats). Returns  
``[radius_points, axis_points, translations]`` after transformation.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/tps.py#L117)</sub>
