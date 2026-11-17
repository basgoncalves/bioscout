# `bioscout.model.mri2msk.geometry`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py)

Mesh I/O and pure-numpy transform helpers (no OpenSim dependency).

Port of the helper functions at the bottom of MRI2MSK.m.

Conventions kept from MATLAB:  
* Vertex arrays are (N, 3) row vectors. MATLAB's ``V * R`` (rows times R) is  
  therefore ``V @ R`` here.  
* Single points/vectors passed to :func:`apply_transform` are 1-D (3,) arrays and  
  are rotated as column vectors, i.e. ``R @ v`` (MATLAB ``R*v``).

## Contents

- [`load_stl`](#load_stl) — Return (vertices (N,3), faces (M,3)) of an STL. Replaces GIBBON import_STL.
- [`save_stl`](#save_stl) — Write a binary STL. Replaces MATLAB stlwrite(triangulation(...)).
- [`max_extent`](#max_extent) — Largest pairwise distance between vertices (MATLAB ``max(pdist(V))``).
- [`max_extent_subsampled`](#max_extent_subsampled) — Mirror of MATLAB ``pdist(V(floor(1:size(V,1)/10000:end),:))``.
- [`downsample_mesh`](#downsample_mesh) — Quadric decimation to ~n_vertices (MATLAB ``reducepatch``).
- [`rotation_y`](#rotation_y) — Rotation about the Y (long) axis, radians.
- [`rotation_xyz_body`](#rotation_xyz_body) — Body-fixed XYZ rotation as used by OpenSim wrap objects (Rx @ Ry @ Rz).
- [`xyz_body_from_matrix`](#xyz_body_from_matrix) — Inverse of :func:`rotation_xyz_body` (same formulas as the MATLAB code).
- [`apply_transform`](#apply_transform) — ``R @ (v - pivot)`` (+ pivot if ``restore_translation``).
- [`calc_angle_2d`](#calc_angle_2d) — Signed angle (deg) from 2-D vector u to v.
- [`rotate_obj_file`](#rotate_obj_file) — Rotate vertices ('v') and normals ('vn') of a Wavefront OBJ; copy other lines.

### `load_stl`

```python
load_stl(path: str | Path) -> tuple[np.ndarray, np.ndarray]
```

| input | type | default |
|---|---|---|
| `path` | str \| Path | required |

**returns** `tuple[np.ndarray, np.ndarray]`

Return (vertices (N,3), faces (M,3)) of an STL. Replaces GIBBON import_STL.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py#L22)</sub>

### `save_stl`

```python
save_stl(path: str | Path, vertices: np.ndarray, faces: np.ndarray) -> None
```

| input | type | default |
|---|---|---|
| `path` | str \| Path | required |
| `vertices` | np.ndarray | required |
| `faces` | np.ndarray | required |

**returns** `None`

Write a binary STL. Replaces MATLAB stlwrite(triangulation(...)).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py#L28)</sub>

### `max_extent`

```python
max_extent(vertices: np.ndarray) -> float
```

| input | type | default |
|---|---|---|
| `vertices` | np.ndarray | required |

**returns** `float`

Largest pairwise distance between vertices (MATLAB ``max(pdist(V))``).

Computed on the convex hull, which gives the exact same maximum but avoids the  
O(N^2) memory of a full pdist on a dense MRI mesh.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py#L33)</sub>

### `max_extent_subsampled`

```python
max_extent_subsampled(vertices: np.ndarray, n: int = 10000) -> float
```

| input | type | default |
|---|---|---|
| `vertices` | np.ndarray | required |
| `n` | int | `10000` |

**returns** `float`

Mirror of MATLAB ``pdist(V(floor(1:size(V,1)/10000:end),:))``.

The MATLAB code subsamples to ~10k vertices before pdist. The exact hull method  
is used here because it is both faster and not approximate; the result may  
differ from the MATLAB value by a fraction of a percent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py#L46)</sub>

### `downsample_mesh`

```python
downsample_mesh(vertices: np.ndarray, faces: np.ndarray, n_vertices: int = 10000)
```

| input | type | default |
|---|---|---|
| `vertices` | np.ndarray | required |
| `faces` | np.ndarray | required |
| `n_vertices` | int | `10000` |

Quadric decimation to ~n_vertices (MATLAB ``reducepatch``).

Uses trimesh's ``simplify_quadric_decimation`` (needs ``fast-simplification``).  
The target is expressed in faces (~2x vertices for a closed mesh).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py#L56)</sub>

### `rotation_y`

```python
rotation_y(theta: float) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `theta` | float | required |

**returns** `np.ndarray`

Rotation about the Y (long) axis, radians.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py#L72)</sub>

### `rotation_xyz_body`

```python
rotation_xyz_body(rx: float, ry: float, rz: float) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `rx` | float | required |
| `ry` | float | required |
| `rz` | float | required |

**returns** `np.ndarray`

Body-fixed XYZ rotation as used by OpenSim wrap objects (Rx @ Ry @ Rz).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py#L78)</sub>

### `xyz_body_from_matrix`

```python
xyz_body_from_matrix(R: np.ndarray) -> tuple[float, float, float]
```

| input | type | default |
|---|---|---|
| `R` | np.ndarray | required |

**returns** `tuple[float, float, float]`

Inverse of :func:`rotation_xyz_body` (same formulas as the MATLAB code).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py#L89)</sub>

### `apply_transform`

```python
apply_transform(v, R: np.ndarray, pivot, restore_translation: bool) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `v` | – | required |
| `R` | np.ndarray | required |
| `pivot` | – | required |
| `restore_translation` | bool | required |

**returns** `np.ndarray`

``R @ (v - pivot)`` (+ pivot if ``restore_translation``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py#L97)</sub>

### `calc_angle_2d`

```python
calc_angle_2d(u, v) -> float
```

| input | type | default |
|---|---|---|
| `u` | – | required |
| `v` | – | required |

**returns** `float`

Signed angle (deg) from 2-D vector u to v.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py#L105)</sub>

### `rotate_obj_file`

```python
rotate_obj_file(input_file, output_file, R, pivot, restore_translation: bool) -> None
```

| input | type | default |
|---|---|---|
| `input_file` | – | required |
| `output_file` | – | required |
| `R` | – | required |
| `pivot` | – | required |
| `restore_translation` | bool | required |

**returns** `None`

Rotate vertices ('v') and normals ('vn') of a Wavefront OBJ; copy other lines.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/geometry.py#L114)</sub>
