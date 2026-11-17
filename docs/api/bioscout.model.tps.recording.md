# `bioscout.model.tps.recording`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/recording.py)

Write transformed geometry back to disk.

Refactor of ``ScaleAndRecordData``. Each record_* call writes one CSV (markers  
in metres) or STL (surfaces). Changes:  
  * no work in ``__init__`` — call :meth:`write_all` (or the individual methods)  
    explicitly,  
  * units conversion factor is a parameter, not a magic ``/1000``,  
  * uses a context-local numpy print option instead of mutating global state.

## Contents

- class [`GeometryWriter`](#geometrywriter) — Persist transformed markers / muscle paths / wraps / surfaces for a body.
  - [`GeometryWriter.write_bone_markers`](#geometrywriterwrite_bone_markers) — 
  - [`GeometryWriter.write_skin_markers`](#geometrywriterwrite_skin_markers) — 
  - [`GeometryWriter.write_muscle_paths`](#geometrywriterwrite_muscle_paths) — 
  - [`GeometryWriter.write_wrap_translations`](#geometrywriterwrite_wrap_translations) — 
  - [`GeometryWriter.write_surfaces`](#geometrywriterwrite_surfaces) — Save each pyvista surface as STL (converted back to metres).

<a id="geometrywriter"></a>

## class `GeometryWriter`

```python
GeometryWriter(body: str, output_dir: str | Path, to_metres: float = 0.001)
```

| input | type | default |
|---|---|---|
| `body` | str | required |
| `output_dir` | str \| Path | required |
| `to_metres` | float | `0.001` |

Persist transformed markers / muscle paths / wraps / surfaces for a body.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/recording.py#L30)</sub>

<a id="geometrywriterwrite_bone_markers"></a>

### `GeometryWriter.write_bone_markers`

```python
GeometryWriter.write_bone_markers(points, names) -> Optional[Path]
```

| input | type | default |
|---|---|---|
| `points` | – | required |
| `names` | – | required |

**returns** `Optional[Path]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/recording.py#L52)</sub>

<a id="geometrywriterwrite_skin_markers"></a>

### `GeometryWriter.write_skin_markers`

```python
GeometryWriter.write_skin_markers(points, names) -> Optional[Path]
```

| input | type | default |
|---|---|---|
| `points` | – | required |
| `names` | – | required |

**returns** `Optional[Path]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/recording.py#L55)</sub>

<a id="geometrywriterwrite_muscle_paths"></a>

### `GeometryWriter.write_muscle_paths`

```python
GeometryWriter.write_muscle_paths(points, names) -> Optional[Path]
```

| input | type | default |
|---|---|---|
| `points` | – | required |
| `names` | – | required |

**returns** `Optional[Path]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/recording.py#L58)</sub>

<a id="geometrywriterwrite_wrap_translations"></a>

### `GeometryWriter.write_wrap_translations`

```python
GeometryWriter.write_wrap_translations(points, names) -> Optional[Path]
```

| input | type | default |
|---|---|---|
| `points` | – | required |
| `names` | – | required |

**returns** `Optional[Path]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/recording.py#L61)</sub>

<a id="geometrywriterwrite_surfaces"></a>

### `GeometryWriter.write_surfaces`

```python
GeometryWriter.write_surfaces(surfaces, names: Sequence[str]) -> list[Path]
```

| input | type | default |
|---|---|---|
| `surfaces` | – | required |
| `names` | Sequence[str] | required |

**returns** `list[Path]`

Save each pyvista surface as STL (converted back to metres).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/recording.py#L64)</sub>
