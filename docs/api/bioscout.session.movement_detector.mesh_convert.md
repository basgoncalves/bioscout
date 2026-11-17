# `bioscout.session.movement_detector.mesh_convert`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_convert.py)

mesh_convert — turn scanned / exported surface meshes into STL.

Photogrammetry and phone-scan apps hand you an ``.obj`` (plus an ``.mtl`` and a  
texture), but every mesh consumer downstream of BioScout — OpenSim body  
geometry, ``tps_personalise``'s bone warping, the model report — wants  
``.stl`` or ``.vtp``. This module is the small bridge.

The ``.obj`` reader is pure Python + stdlib, so it works in any environment  
BioScout runs in. Other input formats (``.ply``, ``.vtp``, ``.vtk``, ``.stl``)  
are delegated to ``pyvista`` if it happens to be installed.

Typical use::

    from bioscout.session.movement_detector import convert_to_stl  
    out = convert_to_stl("3DModel.obj")                    # -> 3DModel.stl  
    out = convert_to_stl("3DModel.obj", scale=0.001)       # mm -> m (OpenSim)

Command line::

    python -m bioscout.session.movement_detector.mesh_convert 3DModel.obj --scale 0.001

  
**Notes**

* STL carries geometry only — materials, textures and vertex colours in the  
  source (``.mtl`` / ``.jpg``) are dropped. That is a property of the format,  
  not of this converter.  
* OpenSim geometry is expressed in **metres**. Scan exports are usually  
  millimetres or arbitrary units, so pass ``scale`` (or use ``--scale``) rather  
  than discovering a 1000x-too-large femur inside the model.  
* Faces with more than three vertices are fan-triangulated, which is correct  
  for convex polygons (what mesh exporters emit) and adequate otherwise.

## Contents

- [`read_obj`](#read_obj) — Read a Wavefront ``.obj`` into ``(vertices, triangles)``.
- [`write_stl`](#write_stl) — Write ``vertices``/``triangles`` to an STL file.
- [`obj_to_stl`](#obj_to_stl) — Convert a Wavefront ``.obj`` to STL.
- [`convert_to_stl`](#convert_to_stl) — Convert any supported surface mesh to STL, dispatching on the suffix.
- [`convert_dir`](#convert_dir) — Convert every mesh matching ``pattern`` in ``folder`` to STL.

### `read_obj`

```python
read_obj(path: str | Path) -> Tuple[List[Vec3], List[Tri]]
```

| input | type | default |
|---|---|---|
| `path` | str \| Path | required |

**returns** `Tuple[List[Vec3], List[Tri]]`

Read a Wavefront ``.obj`` into ``(vertices, triangles)``.

Only ``v`` and ``f`` records matter for a surface mesh; normals (``vn``),  
texture coordinates (``vt``), groups, smoothing and material directives are  
ignored. Face indices may be 1-based (normal) or negative (relative to the  
vertices seen so far) — both are handled, as are ``v/vt/vn`` triplets.

  
**Parameters**

path : str or Path  
    Source ``.obj`` file.

  
**Returns**

(vertices, triangles)  
    ``vertices`` is a list of ``(x, y, z)``; ``triangles`` a list of  
    0-based index triples.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_convert.py#L54)</sub>

### `write_stl`

```python
write_stl(
    vertices: Sequence[Vec3],
    triangles: Iterable[Tri],
    out_path: str | Path,
    ascii_stl: bool = False,
    name: str = 'bioscout'
) -> Path
```

| input | type | default |
|---|---|---|
| `vertices` | Sequence[Vec3] | required |
| `triangles` | Iterable[Tri] | required |
| `out_path` | str \| Path | required |
| `ascii_stl` | bool | `False` |
| `name` | str | `'bioscout'` |

**returns** `Path`

Write ``vertices``/``triangles`` to an STL file.

Binary by default (roughly 5x smaller and faster to load in OpenSim);  
``ascii_stl=True`` produces the text form, which is useful only for  
diffing or debugging.

Facet normals are recomputed from the vertex winding, so a source whose  
normals disagreed with its winding comes out self-consistent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_convert.py#L119)</sub>

### `obj_to_stl`

```python
obj_to_stl(
    obj_path: str | Path,
    out_path: str | Path | None = None,
    scale: float = 1.0,
    ascii_stl: bool = False
) -> Path
```

| input | type | default |
|---|---|---|
| `obj_path` | str \| Path | required |
| `out_path` | str \| Path \| None | `None` |
| `scale` | float | `1.0` |
| `ascii_stl` | bool | `False` |

**returns** `Path`

Convert a Wavefront ``.obj`` to STL.

  
**Parameters**

obj_path : str or Path  
    Source mesh.  
out_path : str or Path, optional  
    Destination. Defaults to ``obj_path`` with an ``.stl`` suffix, written  
    beside the source.  
scale : float  
    Multiply every coordinate by this. Use ``0.001`` for a millimetre scan  
    destined for OpenSim (metres).  
ascii_stl : bool  
    Write text STL instead of binary.

  
**Returns**

Path  
    The file written.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_convert.py#L160)</sub>

### `convert_to_stl`

```python
convert_to_stl(
    src: str | Path,
    out_path: str | Path | None = None,
    scale: float = 1.0,
    ascii_stl: bool = False
) -> Path
```

| input | type | default |
|---|---|---|
| `src` | str \| Path | required |
| `out_path` | str \| Path \| None | `None` |
| `scale` | float | `1.0` |
| `ascii_stl` | bool | `False` |

**returns** `Path`

Convert any supported surface mesh to STL, dispatching on the suffix.

``.obj`` uses the stdlib reader above. ``.ply`` / ``.vtp`` / ``.vtk`` /  
``.stl`` are read with ``pyvista``, which BioScout already depends on for  
the ``tps_personalise`` bone warping; if it is not installed those formats  
raise :class:`ImportError` with the pip hint.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_convert.py#L193)</sub>

### `convert_dir`

```python
convert_dir(
    folder: str | Path,
    pattern: str = '*.obj',
    out_dir: str | Path | None = None,
    scale: float = 1.0,
    ascii_stl: bool = False
) -> List[Path]
```

| input | type | default |
|---|---|---|
| `folder` | str \| Path | required |
| `pattern` | str | `'*.obj'` |
| `out_dir` | str \| Path \| None | `None` |
| `scale` | float | `1.0` |
| `ascii_stl` | bool | `False` |

**returns** `List[Path]`

Convert every mesh matching ``pattern`` in ``folder`` to STL.

Failures are logged and skipped rather than aborting the batch; the return  
value lists only the files actually written.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/mesh_convert.py#L233)</sub>
