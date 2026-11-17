# `bioscout.model.tps.osim_model`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_model.py)

Parse an OpenSim ``.osim`` file into tidy DataFrames.

Consolidates the parsing logic that the original spread across  
``OsimMusclePathsAndWrapping`` (in ``tps_scripts.py``) and ``FixWraps`` (in  
``wrap_scripts.py``). Pure XML parsing — no ``opensim`` import needed, so this is  
fast and unit-testable against a small fixture model.

  
**Returned frames**

``muscle_path_points`` : label, muscle, body, r, a, s  
``wrap_surfaces``       : name(index), body, muscle, rotation, translation,  
                          radius, length, range  
``joints``              : name, body, translation, rotation

## Contents

- class [`OsimModelXML`](#osimmodelxml) — Lightweight, parse-once view of an OpenSim model XML.
  - [`OsimModelXML.muscle_path_points`](#osimmodelxmlmuscle_path_points) — 
  - [`OsimModelXML.wrap_surfaces`](#osimmodelxmlwrap_surfaces) — 
  - [`OsimModelXML.joints`](#osimmodelxmljoints) — 
- [`detect_joint_centre_preset`](#detect_joint_centre_preset) — Pick the joint-centre preset that matches a model's joint names.
- [`joint_centre_maps`](#joint_centre_maps) — ``(custom_joint_centres, pin_joint_centres)`` for a model.
- [`body_meshes`](#body_meshes) — Yield ``(body, mesh_name, mesh_file)`` for every ``Mesh`` under a Body.
- [`write_personalised_model`](#write_personalised_model) — Assemble a personalised ``.osim`` from transformed geometry.
- [`wraps_to_points`](#wraps_to_points) — Add ``radius_point`` and ``axis_point`` columns for TPS transformation.

<a id="osimmodelxml"></a>

## class `OsimModelXML`

```python
OsimModelXML(path: str | Path)
```

| input | type | default |
|---|---|---|
| `path` | str \| Path | required |

Lightweight, parse-once view of an OpenSim model XML.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_model.py#L308)</sub>

<a id="osimmodelxmlmuscle_path_points"></a>

### `OsimModelXML.muscle_path_points`

```python
OsimModelXML.muscle_path_points() -> pd.DataFrame
```

**returns** `pd.DataFrame`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_model.py#L316)</sub>

<a id="osimmodelxmlwrap_surfaces"></a>

### `OsimModelXML.wrap_surfaces`

```python
OsimModelXML.wrap_surfaces() -> pd.DataFrame
```

**returns** `pd.DataFrame`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_model.py#L335)</sub>

<a id="osimmodelxmljoints"></a>

### `OsimModelXML.joints`

```python
OsimModelXML.joints() -> pd.DataFrame
```

**returns** `pd.DataFrame`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_model.py#L388)</sub>

### `detect_joint_centre_preset`

```python
detect_joint_centre_preset(model: str | Path) -> str
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |

**returns** `str`

Pick the joint-centre preset that matches a model's joint names.

Returns a key of :data:`MODEL_PRESETS`. Raises when no preset fits, which is  
the honest outcome — guessing would leave joint centres un-personalised  
while the run still reports success.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_model.py#L101)</sub>

### `joint_centre_maps`

```python
joint_centre_maps(model: str | Path)
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |

``(custom_joint_centres, pin_joint_centres)`` for a model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_model.py#L128)</sub>

### `body_meshes`

```python
body_meshes(scaled_model: str | Path)
```

| input | type | default |
|---|---|---|
| `scaled_model` | str \| Path | required |

Yield ``(body, mesh_name, mesh_file)`` for every ``Mesh`` under a Body.

Used to transform and repoint bone geometry per body. Generic — no  
hard-coded mesh-name map (unlike the original notebook).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_model.py#L144)</sub>

### `write_personalised_model`

```python
write_personalised_model(
    scaled_model: str | Path,
    markers: Mapping[str, Sequence[float]],
    muscles: Mapping[str, Sequence[float]],
    out_path: str | Path,
    model_name: str = 'tps_transformed',
    custom_joint_centres: Mapping[str, tuple[str, str]] = CUSTOM_JOINT_CENTRES,
    pin_joint_centres: Mapping[str, tuple[str, str]] = PIN_JOINT_CENTRES,
    wraps: Mapping[str, Sequence[float]] | None = None,
    mesh_files: Mapping[str, str] | None = None,
    validate: bool = True
) -> Dict[str, int]
```

| input | type | default |
|---|---|---|
| `scaled_model` | str \| Path | required |
| `markers` | Mapping[str, Sequence[float]] | required |
| `muscles` | Mapping[str, Sequence[float]] | required |
| `out_path` | str \| Path | required |
| `model_name` | str | `'tps_transformed'` |
| `custom_joint_centres` | Mapping[str, tuple[str, str]] | `CUSTOM_JOINT_CENTRES` |
| `pin_joint_centres` | Mapping[str, tuple[str, str]] | `PIN_JOINT_CENTRES` |
| `wraps` | Mapping[str, Sequence[float]] \| None | `None` |
| `mesh_files` | Mapping[str, str] \| None | `None` |
| `validate` | bool | `True` |

**returns** `Dict[str, int]`

Assemble a personalised ``.osim`` from transformed geometry.

Port of notebook 4: parse the scaled model XML and, by name-match, overwrite  
(a) muscle ``PathPoint`` locations, (b) ``Marker`` locations (bone, joint and  
skin markers), (c) joint offset-frame translations (joint centres),  
(d) ``WrapCylinder`` translations, and (e) ``Mesh`` files (repoint to the  
transformed bone surfaces, scale reset to ``1 1 1``). Pure ``xml.etree`` — no  
opensim needed to write; if ``validate`` and opensim is importable the result  
is loaded back to catch structural errors.

  
**Parameters**

markers, muscles, wraps : mapping of name -> (x, y, z) in model metres.  
mesh_files : mapping of ``Mesh`` name -> new ``mesh_file`` path (relative to  
    the model), e.g. ``{"pelvis_geom_1": "bones/pelvis.stl"}``.

Returns counts: ``{"muscle_points", "markers", "joint_centres", "wraps",  
"meshes"}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_model.py#L158)</sub>

### `wraps_to_points`

```python
wraps_to_points(wrap_df: pd.DataFrame) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `wrap_df` | pd.DataFrame | required |

**returns** `pd.DataFrame`

Add ``radius_point`` and ``axis_point`` columns for TPS transformation.

Mirrors the original ``OsimWrapsByBodies.wraps_to_points_by_bodies`` point  
construction (radius point in -X, axis point along +Z), but returns a single  
frame rather than a dict-by-body (grouping is the caller's choice).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/osim_model.py#L403)</sub>
