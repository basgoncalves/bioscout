# `bioscout.model.geometry`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py)

Where an ``.osim`` model's bone meshes actually resolve to — or don't.

  
**The failure this module exists to catch**

OpenSim resolves a mesh filename **relative to the folder holding the .osim**.  
Move a model, or move the geometry out from under it, and OpenSim opens the  
model with every muscle, marker and joint intact and **no bones at all** — no  
exception, no warning, nothing in the log. It looks like a rendering quirk. It  
is a model whose provenance you can no longer check by eye, and it is the single  
easiest way to publish a figure of the wrong skeleton.

Two more variants of the same silence:

* **Schema half-handling.** OpenSim 3.x writes ``<geometry_file>`` inside  
  ``DisplayGeometry``; 4.x writes ``<mesh_file>`` inside ``Mesh``. Code that  
  knows only one of them reports a clean bill of health for the other family.  
  Both are checked here, everywhere in the document — not only under ``<Body>``,  
  because ground meshes and contact geometry live outside it.  
* **Case.** ``pelvis.vtp`` vs ``Pelvis.vtp`` resolves on Windows and fails on  
  Linux. The model works for you and not for the collaborator you sent it to.

  
**The tiers**

A reference is resolved by walking the same places OpenSim does, in order, and  
recording *which* one hit. The tier is the point: "found it" is not the useful  
answer, "found it, but only in the bioscout install" is.

    local      the model's own folder, or its Geometry/ subfolder.  
               PORTABLE — the geometry travels with the .osim.  
    parent     ../Geometry beside the model's parent. Portable within a project  
               tree, not if the model alone is copied.  
    bundled    the Geometry/ shipped inside bioscout. Works wherever bioscout is  
               installed; silently different if that copy ever diverges.  
    search     an explicit --search dir, or $OPENSIM_HOME/Geometry. Machine-local.  
    absolute   the reference is an absolute path that exists. Machine-local, and  
               the worst of the resolving tiers: it will point somewhere wrong  
               on any other computer rather than fail loudly.  
    case       resolved only by ignoring filename case. Works on Windows, breaks  
               on Linux and macOS-with-case-sensitive-volumes.  
    empty      the file resolved but is zero bytes. A 0-byte mesh is never valid.  
    missing    nothing found. OpenSim will draw no bone here.

``local`` passes. Everything else that resolves is a warning — reported with its  
tier, so the reason is legible — and ``--strict`` turns warnings into failures.  
``empty`` and ``missing`` always fail.

Deliberately NOT searched: the current working directory. Some OpenSim versions  
fall back to it, but a check whose answer depends on where you were standing  
when you ran it is not a check.

Pure ``xml.etree`` + ``pathlib``: no OpenSim, no numpy, no bioscout imports at  
module level, so this runs in a bare environment and inside preflight.

## Contents

- class [`GeometryRef`](#geometryref) — One ``<geometry_file>``/``<mesh_file>`` value and what became of it.
  - [`GeometryRef.ok`](#geometryrefok) — Resolvable at all — i.e. OpenSim will draw *something*.
  - [`GeometryRef.portable`](#geometryrefportable) — Resolvable from the model's own folder, so it survives being moved.
  - [`GeometryRef.name`](#geometryrefname) — 
- class [`Measure`](#measure) — Model-dependent front end to :mod:`bioscout.model.measure`.
  - [`Measure.add_model`](#measureadd_model) — Register a model. ``meshes`` keys: ``acetabulum_{r,l}``, ``femoral_head_{r,l}`` (or ``femur_{r,l}`` for whole bones).
  - [`Measure.add_folder`](#measureadd_folder) — Register a Meshlab/segmentation folder (meshes discovered per side).
  - [`Measure.acetabular_coverage`](#measureacetabular_coverage) — Coverage for one model/side; extra kwargs go to :func:`bioscout.model.measure.acetabular_coverage`.
  - [`Measure.acetabular_coverage_all`](#measureacetabular_coverage_all) — 
  - [`Measure.summary`](#measuresummary) — 
- [`geometry_refs`](#geometry_refs) — Every geometry reference in a model, deduplicated by raw value.
- [`bundled_geometry_dir`](#bundled_geometry_dir) — The ``Geometry/`` folder shipped inside bioscout, if it can be located.
- [`search_roots_for`](#search_roots_for) — ``[(tier, directory), ...]`` to try, in order, for one model.
- [`clear_cache`](#clear_cache) — Forget indexed directories. Call between runs if the tree changed.
- [`resolve_ref`](#resolve_ref) — Fill in ``ref.tier`` and ``ref.resolved``. Mutates and returns ``ref``.

<a id="geometryref"></a>

## class `GeometryRef`

One ``<geometry_file>``/``<mesh_file>`` value and what became of it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L90)</sub>

<a id="geometryrefok"></a>

### `GeometryRef.ok`

```python
GeometryRef.ok() -> bool
```

**returns** `bool`

Resolvable at all — i.e. OpenSim will draw *something*.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L101)</sub>

<a id="geometryrefportable"></a>

### `GeometryRef.portable`

```python
GeometryRef.portable() -> bool
```

**returns** `bool`

Resolvable from the model's own folder, so it survives being moved.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L106)</sub>

<a id="geometryrefname"></a>

### `GeometryRef.name`

```python
GeometryRef.name() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L111)</sub>

<a id="measure"></a>

## class `Measure`

```python
Measure()
```

Model-dependent front end to :mod:`bioscout.model.measure`.

One entry per model: the ``.osim`` path (optional) plus the bone meshes  
to measure on. Meshes can be given explicitly or picked up from a  
Meshlab/segmentation folder::

    m = Measure()  
    i = m.add_model("models/022.osim",  
                    meshes={"acetabulum_l": "acetabulum_l.stl",  
                            "femoral_head_l": "femoral_head_l.stl"})  
    j = m.add_folder(r"...\022\Meshlab_BG")  
    m.acetabular_coverage(i, side="l")  
    m.summary()                     # list of result dicts

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L115)</sub>

<a id="measureadd_model"></a>

### `Measure.add_model`

```python
Measure.add_model(
    osim=None,
    meshes: Optional[Dict[str, object]] = None,
    landmarks=None,
    name: Optional[str] = None
) -> int
```

| input | type | default |
|---|---|---|
| `osim` | – | `None` |
| `meshes` | Optional[Dict[str, object]] | `None` |
| `landmarks` | – | `None` |
| `name` | Optional[str] | `None` |

**returns** `int`

Register a model. ``meshes`` keys: ``acetabulum_{r,l}``,  
``femoral_head_{r,l}`` (or ``femur_{r,l}`` for whole bones).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L136)</sub>

<a id="measureadd_folder"></a>

### `Measure.add_folder`

```python
Measure.add_folder(folder, name: Optional[str] = None, landmarks=None) -> int
```

| input | type | default |
|---|---|---|
| `folder` | – | required |
| `name` | Optional[str] | `None` |
| `landmarks` | – | `None` |

**returns** `int`

Register a Meshlab/segmentation folder (meshes discovered per side).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L152)</sub>

<a id="measureacetabular_coverage"></a>

### `Measure.acetabular_coverage`

```python
Measure.acetabular_coverage(i_model: int, side: str = 'r', **kw) -> Optional[dict]
```

| input | type | default |
|---|---|---|
| `i_model` | int | required |
| `side` | str | `'r'` |
| `**kw` | – | – |

**returns** `Optional[dict]`

Coverage for one model/side; extra kwargs go to  
:func:`bioscout.model.measure.acetabular_coverage`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L174)</sub>

<a id="measureacetabular_coverage_all"></a>

### `Measure.acetabular_coverage_all`

```python
Measure.acetabular_coverage_all(sides=('r', 'l'), **kw) -> List[dict]
```

| input | type | default |
|---|---|---|
| `sides` | – | `('r', 'l')` |
| `**kw` | – | – |

**returns** `List[dict]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L199)</sub>

<a id="measuresummary"></a>

### `Measure.summary`

```python
Measure.summary() -> List[dict]
```

**returns** `List[dict]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L203)</sub>

### `geometry_refs`

```python
geometry_refs(model_path) -> List[GeometryRef]
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |

**returns** `List[GeometryRef]`

Every geometry reference in a model, deduplicated by raw value.

Scans the WHOLE document rather than only ``<Body>`` subtrees: v4 puts  
ground and contact meshes outside the body set, and a check that misses them  
reports a clean model that renders half a skeleton.

Raises ``ET.ParseError`` / ``OSError`` — callers decide whether an unreadable  
model is fatal.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L234)</sub>

### `bundled_geometry_dir`

```python
bundled_geometry_dir() -> Optional[Path]
```

**returns** `Optional[Path]`

The ``Geometry/`` folder shipped inside bioscout, if it can be located.

Derived from this file's own position first — that works in a source  
checkout with nothing installed — and only then from an import.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L267)</sub>

### `search_roots_for`

```python
search_roots_for(model_path, extra: Optional[Sequence] = None) -> List[tuple]
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `extra` | Optional[Sequence] | `None` |

**returns** `List[tuple]`

``[(tier, directory), ...]`` to try, in order, for one model.

Every entry is a directory that exists. ``extra`` comes from ``--search``  
and is tried before ``$OPENSIM_HOME/Geometry``, both under tier ``search``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L286)</sub>

### `clear_cache`

```python
clear_cache() -> None
```

**returns** `None`

Forget indexed directories. Call between runs if the tree changed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L352)</sub>

### `resolve_ref`

```python
resolve_ref(ref: GeometryRef, model_path, extra: Optional[Sequence] = None) -> GeometryRef
```

| input | type | default |
|---|---|---|
| `ref` | GeometryRef | required |
| `model_path` | – | required |
| `extra` | Optional[Sequence] | `None` |

**returns** `GeometryRef`

Fill in ``ref.tier`` and ``ref.resolved``. Mutates and returns ``ref``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/geometry.py#L357)</sub>
