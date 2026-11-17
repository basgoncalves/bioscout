# `bioscout.model.io`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/io.py)

File input/output shared across ``bioscout.model``: meshes, models, landmarks.

One place to load things, so ``measure``, ``geometry``, ``tps`` & co. don't each  
grow their own reader. Heavy dependencies (trimesh, vtk, opensim) are imported  
inside the functions: importing this module costs nothing.

Note: never run a file from inside ``bioscout/model`` as a plain script  
(``python measure.py``) — this ``io.py`` (and the ``inspect`` package) would  
shadow the standard-library modules of the same name. Use ``python -m`` or the  
``bioscout`` command.

## Contents

- [`read_vtp_python`](#read_vtp_python) — ``.vtp`` -> ``(vertices (N,3), triangles (M,3))`` with numpy only.
- [`read_vtp`](#read_vtp) — OpenSim ``.vtp`` -> ``(vertices (N,3), triangles (M,3))``.
- [`load_mesh`](#load_mesh) — Any bone mesh -> single ``trimesh.Trimesh``.
- [`load_mesh_arrays`](#load_mesh_arrays) — Mesh as plain ``(vertices, faces)`` numpy arrays (no trimesh object).
- [`read_landmarks`](#read_landmarks) — CSV with columns ``name,x,y,z`` -> ``{name: array([x, y, z])}``.
- [`write_landmarks`](#write_landmarks) — ``{name: xyz}`` -> CSV with columns ``name,x,y,z``.
- [`load_model`](#load_model) — ``opensim.Model`` with bioscout's relaxed assembly accuracy.

### `read_vtp_python`

```python
read_vtp_python(path: PathLike) -> Tuple['object', 'object']
```

| input | type | default |
|---|---|---|
| `path` | PathLike | required |

**returns** `Tuple['object', 'object']`

``.vtp`` -> ``(vertices (N,3), triangles (M,3))`` with numpy only.

The fallback for environments without vtk. Polygons are fan-triangulated,  
so quads and n-gons work; point data (normals, scalars) is ignored.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/io.py#L91)</sub>

### `read_vtp`

```python
read_vtp(path: PathLike) -> Tuple['object', 'object']
```

| input | type | default |
|---|---|---|
| `path` | PathLike | required |

**returns** `Tuple['object', 'object']`

OpenSim ``.vtp`` -> ``(vertices (N,3), triangles (M,3))``.

Uses vtk when it is installed, otherwise :func:`read_vtp_python` (numpy  
only) -- a model's bone geometry should not need a vtk install to measure.  
Polygons are triangulated, so quads/n-gons in older OpenSim geometry work.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/io.py#L140)</sub>

### `load_mesh`

```python
load_mesh(path: PathLike)
```

| input | type | default |
|---|---|---|
| `path` | PathLike | required |

Any bone mesh -> single ``trimesh.Trimesh``.

STL/OBJ/PLY/... via trimesh, ``.vtp`` (OpenSim geometry) via vtk.  
Raises ``FileNotFoundError`` for a missing file (trimesh on its own gives  
an unhelpful ``ValueError``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/io.py#L168)</sub>

### `load_mesh_arrays`

```python
load_mesh_arrays(path: PathLike)
```

| input | type | default |
|---|---|---|
| `path` | PathLike | required |

Mesh as plain ``(vertices, faces)`` numpy arrays (no trimesh object).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/io.py#L189)</sub>

### `read_landmarks`

```python
read_landmarks(path: PathLike) -> Dict[str, 'object']
```

| input | type | default |
|---|---|---|
| `path` | PathLike | required |

**returns** `Dict[str, 'object']`

CSV with columns ``name,x,y,z`` -> ``{name: array([x, y, z])}``.

Blank coordinates are skipped (so a half-filled template still loads).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/io.py#L199)</sub>

### `write_landmarks`

```python
write_landmarks(path: PathLike, landmarks: Dict[str, 'object']) -> Path
```

| input | type | default |
|---|---|---|
| `path` | PathLike | required |
| `landmarks` | Dict[str, 'object'] | required |

**returns** `Path`

``{name: xyz}`` -> CSV with columns ``name,x,y,z``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/io.py#L216)</sub>

### `load_model`

```python
load_model(path: PathLike, accuracy=None)
```

| input | type | default |
|---|---|---|
| `path` | PathLike | required |
| `accuracy` | – | `None` |

``opensim.Model`` with bioscout's relaxed assembly accuracy.

Thin re-export of :func:`bioscout.model.opensim_base.load_model` (the one  
implementation), imported lazily so this module does not need OpenSim.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/io.py#L231)</sub>
