# `bioscout.model.mri2msk.staple.trimesh_core`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py)

Triangulation core: a minimal stand-in for MATLAB's ``triangulation`` object  
plus the GIBOC-core ``Tri*`` mesh functions used by STAPLE.

Faces and vertex ids are 0-based here (MATLAB is 1-based). Missing neighbours  
are -1 (MATLAB uses NaN).

## Contents

- class [`Tri`](#tri) — Lightweight triangulation (points (N,3), faces (M,3) int, 0-based).
  - [`Tri.face_normals`](#triface_normals) — 
  - [`Tri.face_areas`](#triface_areas) — 
  - [`Tri.incenter`](#triincenter) — Inscribed-circle centres (MATLAB ``incenter``).
  - [`Tri.neighbors`](#trineighbors) — (M,3) face ids across each edge (opposite vertex j), -1 if none.
  - [`Tri.free_boundary`](#trifree_boundary) — Directed boundary edges (K,2) in face orientation.
  - [`Tri.vertex_attachments`](#trivertex_attachments) — Unique face ids attached to vertex ids.
  - [`Tri.face_neighbors_of`](#triface_neighbors_of) — 
  - [`Tri.vertex_normals`](#trivertex_normals) — Area-weighted vertex normals (MATLAB ``vertexNormal``).
  - [`Tri.kdtree`](#trikdtree) — 
  - [`Tri.nearest_neighbor`](#trinearest_neighbor) — 
- class [`Curve`](#curve) — 
- [`normalize`](#normalize) — 
- [`load_tri`](#load_tri) — Load an STL like MATLAB ``stlread`` (merge identical vertices) + TriFixNormals.
- [`tri_fix_normals`](#tri_fix_normals) — 
- [`tri_reduce_mesh`](#tri_reduce_mesh) — TriReduceMesh: keep faces (or faces attached to nodes / nearest nodes of points).
- [`tri_unite`](#tri_unite) — 
- [`tri_dilate_mesh`](#tri_dilate_mesh) — 
- [`tri_erode_mesh`](#tri_erode_mesh) — 
- [`tri_open_mesh`](#tri_open_mesh) — 
- [`tri_close_mesh`](#tri_close_mesh) — 
- [`tri_connected_patch`](#tri_connected_patch) — 
- [`boundary_loops`](#boundary_loops) — Closed boundary loops as lists of directed edges (each (k,2)).
- [`tri_fill_planar_holes`](#tri_fill_planar_holes) — 
- [`tri_keep_largest_patch`](#tri_keep_largest_patch) — 
- [`tri_inertia_ppties`](#tri_inertia_ppties) — TriInertiaPpties: (eigVecs, CenterVol(3,), InertiaMatrix, D(eigvals), mass).
- [`tri_change_cs`](#tri_change_cs) — 
- [`coeff_morpho`](#coeff_morpho) — 
- [`pca_coeff`](#pca_coeff) — MATLAB ``pca`` coefficients (columns), sign: largest |component| positive.
- [`polygon_area`](#polygon_area) — 
- [`in_polygon`](#in_polygon) — Vectorised point-in-polygon (boundary counted as inside, like inpolygon).
- [`tri_plan_intersect`](#tri_plan_intersect) — TriPlanIntersect: plane n.x + d = 0. Returns (curves, total_area).
- [`tri_slice_obj_along_axis`](#tri_slice_obj_along_axis) — 
- [`plan_polygon_area`](#plan_polygon_area) — Area returned by PlanPolygonCentroid3D (abs signed area in the curve plane).
- [`cut_long_bone_mesh`](#cut_long_bone_mesh) — 
- [`largest_edge_conv_hull`](#largest_edge_conv_hull) — LargestEdgeConvHull (3-D): all hull-triangle edges sorted by length desc.

<a id="tri"></a>

## class `Tri`

```python
Tri(points, faces)
```

| input | type | default |
|---|---|---|
| `points` | – | required |
| `faces` | – | required |

Lightweight triangulation (points (N,3), faces (M,3) int, 0-based).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L23)</sub>

<a id="triface_normals"></a>

### `Tri.face_normals`

```python
Tri.face_normals()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L41)</sub>

<a id="triface_areas"></a>

### `Tri.face_areas`

```python
Tri.face_areas()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L45)</sub>

<a id="triincenter"></a>

### `Tri.incenter`

```python
Tri.incenter()
```

Inscribed-circle centres (MATLAB ``incenter``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L49)</sub>

<a id="trineighbors"></a>

### `Tri.neighbors`

```python
Tri.neighbors()
```

(M,3) face ids across each edge (opposite vertex j), -1 if none.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L71)</sub>

<a id="trifree_boundary"></a>

### `Tri.free_boundary`

```python
Tri.free_boundary()
```

Directed boundary edges (K,2) in face orientation.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L86)</sub>

<a id="trivertex_attachments"></a>

### `Tri.vertex_attachments`

```python
Tri.vertex_attachments(vids) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `vids` | – | required |

**returns** `np.ndarray`

Unique face ids attached to vertex ids.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L100)</sub>

<a id="triface_neighbors_of"></a>

### `Tri.face_neighbors_of`

```python
Tri.face_neighbors_of(fids) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `fids` | – | required |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L109)</sub>

<a id="trivertex_normals"></a>

### `Tri.vertex_normals`

```python
Tri.vertex_normals()
```

Area-weighted vertex normals (MATLAB ``vertexNormal``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L114)</sub>

<a id="trikdtree"></a>

### `Tri.kdtree`

```python
Tri.kdtree()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L124)</sub>

<a id="trinearest_neighbor"></a>

### `Tri.nearest_neighbor`

```python
Tri.nearest_neighbor(pts) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `pts` | – | required |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L127)</sub>

<a id="curve"></a>

## class `Curve`

```python
Curve(pts, area)
```

| input | type | default |
|---|---|---|
| `pts` | – | required |
| `area` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L363)</sub>

### `normalize`

```python
normalize(v)
```

| input | type | default |
|---|---|---|
| `v` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L15)</sub>

### `load_tri`

```python
load_tri(path) -> Tri
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `Tri`

Load an STL like MATLAB ``stlread`` (merge identical vertices) + TriFixNormals.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L132)</sub>

### `tri_fix_normals`

```python
tri_fix_normals(tri: Tri) -> Tri
```

| input | type | default |
|---|---|---|
| `tri` | Tri | required |

**returns** `Tri`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L146)</sub>

### `tri_reduce_mesh`

```python
tri_reduce_mesh(tri: Tri, elmts_kept=None, nodes_kept=None) -> Tri
```

| input | type | default |
|---|---|---|
| `tri` | Tri | required |
| `elmts_kept` | – | `None` |
| `nodes_kept` | – | `None` |

**returns** `Tri`

TriReduceMesh: keep faces (or faces attached to nodes / nearest nodes of points).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L160)</sub>

### `tri_unite`

```python
tri_unite(a: Tri, b: Tri) -> Tri
```

| input | type | default |
|---|---|---|
| `a` | Tri | required |
| `b` | Tri | required |

**returns** `Tri`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L177)</sub>

### `tri_dilate_mesh`

```python
tri_dilate_mesh(sup: Tri, tin: Tri, nb) -> Tri
```

| input | type | default |
|---|---|---|
| `sup` | Tri | required |
| `tin` | Tri | required |
| `nb` | – | required |

**returns** `Tri`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L188)</sub>

### `tri_erode_mesh`

```python
tri_erode_mesh(tin: Tri, nb) -> Tri
```

| input | type | default |
|---|---|---|
| `tin` | Tri | required |
| `nb` | – | required |

**returns** `Tri`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L199)</sub>

### `tri_open_mesh`

```python
tri_open_mesh(sup: Tri, tin: Tri, nb) -> Tri
```

| input | type | default |
|---|---|---|
| `sup` | Tri | required |
| `tin` | Tri | required |
| `nb` | – | required |

**returns** `Tri`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L212)</sub>

### `tri_close_mesh`

```python
tri_close_mesh(sup: Tri, tin: Tri, nb) -> Tri
```

| input | type | default |
|---|---|---|
| `sup` | Tri | required |
| `tin` | Tri | required |
| `nb` | – | required |

**returns** `Tri`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L216)</sub>

### `tri_connected_patch`

```python
tri_connected_patch(tri: Tri, pts) -> Tri
```

| input | type | default |
|---|---|---|
| `tri` | Tri | required |
| `pts` | – | required |

**returns** `Tri`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L220)</sub>

### `boundary_loops`

```python
boundary_loops(tri: Tri) -> list[np.ndarray]
```

| input | type | default |
|---|---|---|
| `tri` | Tri | required |

**returns** `list[np.ndarray]`

Closed boundary loops as lists of directed edges (each (k,2)).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L233)</sub>

### `tri_fill_planar_holes`

```python
tri_fill_planar_holes(tin: Tri) -> Tri
```

| input | type | default |
|---|---|---|
| `tin` | Tri | required |

**returns** `Tri`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L257)</sub>

### `tri_keep_largest_patch`

```python
tri_keep_largest_patch(tin: Tri) -> Tri
```

| input | type | default |
|---|---|---|
| `tin` | Tri | required |

**returns** `Tri`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L280)</sub>

### `tri_inertia_ppties`

```python
tri_inertia_ppties(tri: Tri)
```

| input | type | default |
|---|---|---|
| `tri` | Tri | required |

TriInertiaPpties: (eigVecs, CenterVol(3,), InertiaMatrix, D(eigvals), mass).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L295)</sub>

### `tri_change_cs`

```python
tri_change_cs(tri: Tri, V, T) -> Tri
```

| input | type | default |
|---|---|---|
| `tri` | Tri | required |
| `V` | – | required |
| `T` | – | required |

**returns** `Tri`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L342)</sub>

### `coeff_morpho`

```python
coeff_morpho(tri: Tri) -> float
```

| input | type | default |
|---|---|---|
| `tri` | Tri | required |

**returns** `float`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L346)</sub>

### `pca_coeff`

```python
pca_coeff(X)
```

| input | type | default |
|---|---|---|
| `X` | – | required |

MATLAB ``pca`` coefficients (columns), sign: largest |component| positive.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L351)</sub>

### `polygon_area`

```python
polygon_area(xy)
```

| input | type | default |
|---|---|---|
| `xy` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L377)</sub>

### `in_polygon`

```python
in_polygon(px, py, vx, vy)
```

| input | type | default |
|---|---|---|
| `px` | – | required |
| `py` | – | required |
| `vx` | – | required |
| `vy` | – | required |

Vectorised point-in-polygon (boundary counted as inside, like inpolygon).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L382)</sub>

### `tri_plan_intersect`

```python
tri_plan_intersect(tri: Tri, n, d)
```

| input | type | default |
|---|---|---|
| `tri` | Tri | required |
| `n` | – | required |
| `d` | – | required |

TriPlanIntersect: plane n.x + d = 0. Returns (curves, total_area).

``d`` may also be a point on the plane (3,).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L400)</sub>

### `tri_slice_obj_along_axis`

```python
tri_slice_obj_along_axis(tri: Tri, axis, step, cut_offset=0.5)
```

| input | type | default |
|---|---|---|
| `tri` | Tri | required |
| `axis` | – | required |
| `step` | – | required |
| `cut_offset` | – | `0.5` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L475)</sub>

### `plan_polygon_area`

```python
plan_polygon_area(pts)
```

| input | type | default |
|---|---|---|
| `pts` | – | required |

Area returned by PlanPolygonCentroid3D (abs signed area in the curve plane).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L483)</sub>

### `cut_long_bone_mesh`

```python
cut_long_bone_mesh(tri: Tri, U0=None, L_ratio=0.33)
```

| input | type | default |
|---|---|---|
| `tri` | Tri | required |
| `U0` | – | `None` |
| `L_ratio` | – | `0.33` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L493)</sub>

### `largest_edge_conv_hull`

```python
largest_edge_conv_hull(pts)
```

| input | type | default |
|---|---|---|
| `pts` | – | required |

LargestEdgeConvHull (3-D): all hull-triangle edges sorted by length desc.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/staple/trimesh_core.py#L507)</sub>
