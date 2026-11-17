# `bioscout.model.tps.landmarks`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks.py)

Loaders for landmark / marker data.

Consolidates the original ``MRIBoneMarkers`` (3D Slicer JSON) and  
``OsimBoneMarkers`` (OpenSim marker XML) classes into plain functions that  
return tidy ``pandas`` DataFrames indexed by marker name with ``r/a/s`` columns  
(and ``body`` where applicable).

Changes vs original:  
  * functions, not classes-with-side-effects,  
  * no plotting (visualisation belongs elsewhere),  
  * the mm<->m and Slicer-orientation conventions are explicit parameters  
    instead of commented-out ``#*1000`` lines.

## Contents

- [`load_mri_landmarks`](#load_mri_landmarks) — Load bone landmarks from a 3D Slicer ``.mrk.json`` file.
- [`load_osim_bone_markers`](#load_osim_bone_markers) — Parse OpenSim bone-marker XML into a DataFrame.
- [`match_by_name`](#match_by_name) — Return ``(matched, only_in_mri, only_in_osim)`` marker-name lists.
- [`split_by_body`](#split_by_body) — Group a marker DataFrame (with a ``body`` column) into ``{body: df}``.

### `load_mri_landmarks`

```python
load_mri_landmarks(path: str | Path, apply_orientation: bool = True) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `path` | str \| Path | required |
| `apply_orientation` | bool | `True` |

**returns** `pd.DataFrame`

Load bone landmarks from a 3D Slicer ``.mrk.json`` file.

Slicer stores position and orientation separately; the displayed coordinate  
is ``orientation @ position``. ``apply_orientation`` controls whether that  
multiplication is applied (the original default was True).

Returns a DataFrame indexed by label with ``r/a/s`` columns.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks.py#L26)</sub>

### `load_osim_bone_markers`

```python
load_osim_bone_markers(path: str | Path) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `path` | str \| Path | required |

**returns** `pd.DataFrame`

Parse OpenSim bone-marker XML into a DataFrame.

Returns columns ``body``, ``r``, ``a``, ``s`` indexed by marker name.  
Equivalent to the original ``OsimBoneMarkers.data_frame``.

Works on OpenSim 3.x models (``<body>``) as well as 4.x  
(``<socket_parent_frame>``), and on a standalone ``MarkerSet`` XML.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks.py#L51)</sub>

### `match_by_name`

```python
match_by_name(
    osim_df: pd.DataFrame,
    mri_df: pd.DataFrame
) -> tuple[list[str], list[str], list[str]]
```

| input | type | default |
|---|---|---|
| `osim_df` | pd.DataFrame | required |
| `mri_df` | pd.DataFrame | required |

**returns** `tuple[list[str], list[str], list[str]]`

Return ``(matched, only_in_mri, only_in_osim)`` marker-name lists.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks.py#L86)</sub>

### `split_by_body`

```python
split_by_body(df: pd.DataFrame, names: list[str] | None = None) -> dict[str, pd.DataFrame]
```

| input | type | default |
|---|---|---|
| `df` | pd.DataFrame | required |
| `names` | list[str] \| None | `None` |

**returns** `dict[str, pd.DataFrame]`

Group a marker DataFrame (with a ``body`` column) into ``{body: df}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/landmarks.py#L97)</sub>
