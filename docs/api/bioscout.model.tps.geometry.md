# `bioscout.model.tps.geometry`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/geometry.py)

Pure geometric helpers (numpy only).

Ported from the original ``rotation_utils.py`` with no behavioural change, but:  
  * no plotting code (moved out of the math layer),  
  * no ``print`` side effects (callers get values / use logging),  
  * docstrings and type hints,  
  * an explicit, tested Kabsch implementation shared by the axis classes.

Every function here is dependency-light and covered by ``tests/test_geometry.py``.

## Contents

- [`rotation_matrix`](#rotation_matrix) — Rotation matrix for counter-clockwise rotation of ``theta`` radians about ``axis`` (Euler-Rodrigues). Identical to the original.
- [`kabsch`](#kabsch) — Best-fit rigid rotation+translation mapping ``source`` onto ``target``.
- [`axes_rotation`](#axes_rotation) — Backwards-compatible wrapper around the original ``axes_rotation``.
- [`rotate_about_centroid`](#rotate_about_centroid) — Centre ``data`` on its centroid then rotate by ``R``.
- [`plane_normal`](#plane_normal) — Unit normal of the plane through three points (p2 is the vertex).
- [`point_distance_to_vector`](#point_distance_to_vector) — Perpendicular distance from ``point`` to the line through the origin along ``vector`` (the vector origin must already be subtracted from point).
- [`project_point_to_vector`](#project_point_to_vector) — Orthogonal projection of ``point`` onto ``vector`` (origin-subtracted).
- [`project_point_to_plane`](#project_point_to_plane) — Project ``point`` onto the plane defined by a point and unit normal.
- [`rmse`](#rmse) — Root-mean-square error between two point sets of equal shape.

### `rotation_matrix`

```python
rotation_matrix(axis: Sequence[float], theta: float) -> Array
```

| input | type | default |
|---|---|---|
| `axis` | Sequence[float] | required |
| `theta` | float | required |

**returns** `Array`

Rotation matrix for counter-clockwise rotation of ``theta`` radians  
about ``axis`` (Euler-Rodrigues). Identical to the original.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/geometry.py#L21)</sub>

### `kabsch`

```python
kabsch(source: Array, target: Array) -> Tuple[Array, Array]
```

| input | type | default |
|---|---|---|
| `source` | Array | required |
| `target` | Array | required |

**returns** `Tuple[Array, Array]`

Best-fit rigid rotation+translation mapping ``source`` onto ``target``.

Returns ``(R, t)`` such that ``(R @ source_centred.T).T + t ~= target``.  
Reflection-safe (determinant correction). This is the shared core that the  
original duplicated inside ``axes_rotation`` and ``TransformBodyToOsim``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/geometry.py#L37)</sub>

### `axes_rotation`

```python
axes_rotation(first: Array, second: Array)
```

| input | type | default |
|---|---|---|
| `first` | Array | required |
| `second` | Array | required |

Backwards-compatible wrapper around the original ``axes_rotation``.

Returns ``(R, t, center_first, center_second)`` mapping ``second`` onto  
``first`` (same signature/semantics as the original function).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/geometry.py#L58)</sub>

### `rotate_about_centroid`

```python
rotate_about_centroid(data: Array, R: Array) -> Array
```

| input | type | default |
|---|---|---|
| `data` | Array | required |
| `R` | Array | required |

**returns** `Array`

Centre ``data`` on its centroid then rotate by ``R``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/geometry.py#L73)</sub>

### `plane_normal`

```python
plane_normal(p1: Array, p2: Array, p3: Array) -> Array
```

| input | type | default |
|---|---|---|
| `p1` | Array | required |
| `p2` | Array | required |
| `p3` | Array | required |

**returns** `Array`

Unit normal of the plane through three points (p2 is the vertex).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/geometry.py#L79)</sub>

### `point_distance_to_vector`

```python
point_distance_to_vector(point: Array, vector: Array) -> float
```

| input | type | default |
|---|---|---|
| `point` | Array | required |
| `vector` | Array | required |

**returns** `float`

Perpendicular distance from ``point`` to the line through the origin  
along ``vector`` (the vector origin must already be subtracted from point).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/geometry.py#L87)</sub>

### `project_point_to_vector`

```python
project_point_to_vector(point: Array, vector: Array) -> Array
```

| input | type | default |
|---|---|---|
| `point` | Array | required |
| `vector` | Array | required |

**returns** `Array`

Orthogonal projection of ``point`` onto ``vector`` (origin-subtracted).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/geometry.py#L93)</sub>

### `project_point_to_plane`

```python
project_point_to_plane(point: Array, point_on_plane: Array, normal: Array) -> Array
```

| input | type | default |
|---|---|---|
| `point` | Array | required |
| `point_on_plane` | Array | required |
| `normal` | Array | required |

**returns** `Array`

Project ``point`` onto the plane defined by a point and unit normal.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/geometry.py#L102)</sub>

### `rmse`

```python
rmse(a: Array, b: Array) -> float
```

| input | type | default |
|---|---|---|
| `a` | Array | required |
| `b` | Array | required |

**returns** `float`

Root-mean-square error between two point sets of equal shape.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/geometry.py#L108)</sub>
