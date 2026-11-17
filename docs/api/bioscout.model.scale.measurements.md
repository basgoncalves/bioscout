# `bioscout.model.scale.measurements`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py)

Build a real ScaleTool MeasurementSet for the powerlifting marker protocol.

  
**WHY THIS MODULE EXISTS**

``openSim.scale_model`` used to construct ``osim.ScaleTool()`` from scratch and  
call ``ModelScaler.setApply(True)`` without ever populating a MeasurementSet.  
OpenSim accepts that silently: with no measurements there is nothing to compute  
a scale factor from, so EVERY body keeps a scale factor of 1.0 and the only  
thing that actually changes is the total mass (``setSubjectMass``). The result  
looks like a scaled model, is named ``scaled.osim``, and is generic geometry  
carrying the subject's mass. That is the bug this module fixes.

The measurement basis is the ``*WK`` virtual joint-centre markers that already  
exist in ``markers_powerlifter.xml``:

    RHJCWK  femur_r  (0, 0, 0)          -> hip joint centre  
    RKJCWK  tibia_r  (0, 0.0074, 0)     -> knee joint centre  
    RAJCWK  talus_r  (0, 0, 0)          -> ankle joint centre

They sit on body origins, so they are the joint centres in EVERY model  
regardless of that model's segment lengths -- unlike the skin markers in  
``markers_powerlifter.xml``, whose hard-coded local positions were authored for  
one specific generic and are wrong on the others. That makes the femur/tibia  
scale factors model-independent, which is exactly what we want when the same  
static trial scales Catelli, Lernagopal and GPK.

The catch: those markers exist in the MODEL but in no TRC, because the motion  
capture cannot see a joint centre. ``augment_static_trc`` computes them from the  
skin markers -- knee/ankle as the midpoint of the epicondyle/malleoli pairs, hip  
via the Harrington (2007) pelvis regression -- and writes them into a copy of  
the static TRC so ScaleTool can pair them up.

Joint-centre markers must NOT take part in marker registration (they are derived,  
not measured), so ``marker_placement_markerset`` strips them again for the  
standalone IK pass.

## Contents

- [`apply_aliases`](#apply_aliases) — ``names`` with ``aliases`` applied. Unknown names pass through.
- [`resolve_spec`](#resolve_spec) — A measurement spec with ``aliases`` applied to every marker name.
- [`suggest_alias`](#suggest_alias) — Plausible stand-ins for ``missing`` among ``candidates``, best first.
- [`read_trc`](#read_trc) — Return ``(header_lines, marker_names, frames, data)``.
- [`write_trc`](#write_trc) — Write a TRC, rewriting the NumMarkers field in the header to match.
- [`harrington_hjc`](#harrington_hjc) — Hip joint centres from the pelvis markers (Harrington et al., 2007).
- [`compute_joint_centres`](#compute_joint_centres) — Per-frame joint centres from a parsed TRC. Returns ``{name: (n,3)}``.
- [`augment_static_trc`](#augment_static_trc) — Write a copy of the static TRC with the ``*WK`` joint centres appended.
- [`marker_placement_markerset`](#marker_placement_markerset) — Strip the ``*WK`` joint-centre markers from a copy of the marker set.
- [`spec_from_config`](#spec_from_config) — A measurement spec from session.yaml's ``scale_measurements`` list.
- [`model_marker_names`](#model_marker_names) — 
- [`model_body_names`](#model_body_names) — 
- [`markerset_file_names`](#markerset_file_names) — Marker names declared in an OpenSim marker-set XML.
- [`build_measurement_set`](#build_measurement_set) — Return ``(MeasurementSet, report_lines)`` for this model + static TRC.
- [`verify_scaled`](#verify_scaled) — Compare a scaled model against its generic and shout if nothing changed.
- [`mass_from_static_grf`](#mass_from_static_grf) — Measured body mass = mean total vertical GRF / g over the static trial.
- [`set_total_mass`](#set_total_mass) — Scale every body's mass and inertia so the model totals ``target_mass``.

### `apply_aliases`

```python
apply_aliases(aliases, *names)
```

| input | type | default |
|---|---|---|
| `aliases` | – | required |
| `*names` | – | – |

``names`` with ``aliases`` applied. Unknown names pass through.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L69)</sub>

### `resolve_spec`

```python
resolve_spec(spec, aliases)
```

| input | type | default |
|---|---|---|
| `spec` | – | required |
| `aliases` | – | required |

A measurement spec with ``aliases`` applied to every marker name.

Returns the spec unchanged when there is nothing to apply, so callers can  
pass the result straight to :func:`build_measurement_set`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L76)</sub>

### `suggest_alias`

```python
suggest_alias(missing, candidates, limit=6)
```

| input | type | default |
|---|---|---|
| `missing` | – | required |
| `candidates` | – | required |
| `limit` | – | `6` |

Plausible stand-ins for ``missing`` among ``candidates``, best first.

Cheap and deliberately transparent: same side prefix (L/R) first, then  
shared substrings. It is a shortlist for a human to choose from, never an  
automatic substitution -- picking the wrong ankle marker is not an error  
anything downstream can detect.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L92)</sub>

### `read_trc`

```python
read_trc(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

Return ``(header_lines, marker_names, frames, data)``.

``data`` is ``(n_frames, 3 * n_markers)``; ``frames`` is the Frame#/Time  
columns as ``(n_frames, 2)``. Missing values come back as NaN.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L127)</sub>

### `write_trc`

```python
write_trc(path, header_lines, names, frames, data)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `header_lines` | – | required |
| `names` | – | required |
| `frames` | – | required |
| `data` | – | required |

Write a TRC, rewriting the NumMarkers field in the header to match.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L159)</sub>

### `harrington_hjc`

```python
harrington_hjc(lasi, rasi, lpsi, rpsi)
```

| input | type | default |
|---|---|---|
| `lasi` | – | required |
| `rasi` | – | required |
| `lpsi` | – | required |
| `rpsi` | – | required |

Hip joint centres from the pelvis markers (Harrington et al., 2007).

Inputs and outputs are in the TRC's own units (mm) and global frame. The  
regression is defined in a pelvis-local frame -- x anterior, y superior,  
z to the subject's right -- built from the ASIS/PSIS midpoints, so it is  
independent of how the subject was oriented in the lab.

Returns ``(lhjc, rhjc, pelvis_width, pelvis_depth)``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L188)</sub>

### `compute_joint_centres`

```python
compute_joint_centres(names, data, aliases=None)
```

| input | type | default |
|---|---|---|
| `names` | – | required |
| `data` | – | required |
| `aliases` | – | `None` |

Per-frame joint centres from a parsed TRC. Returns ``{name: (n,3)}``.

``aliases`` maps the expected skin-marker names to what this lab records  
(see :data:`EXPECTED_MARKERS`); without it a lab using different spellings  
gets no joint centres at all. It is applied to the OUTPUT names too, so a  
model whose marker set calls the hip centre ``RHJC`` rather than  
``RHJCWK`` (alias ``RHJCWK: RHJC``) gets a TRC the measurement spec --  
resolved through the same aliases -- can actually pair up.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L220)</sub>

### `augment_static_trc`

```python
augment_static_trc(trc_in, trc_out=None, verbose=True, aliases=None)
```

| input | type | default |
|---|---|---|
| `trc_in` | – | required |
| `trc_out` | – | `None` |
| `verbose` | – | `True` |
| `aliases` | – | `None` |

Write a copy of the static TRC with the ``*WK`` joint centres appended.

Returns the path to the augmented TRC (or ``trc_in`` unchanged if no joint  
centre could be built -- e.g. the pelvis or knee markers are absent).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L261)</sub>

### `marker_placement_markerset`

```python
marker_placement_markerset(markerset_path, out_dir)
```

| input | type | default |
|---|---|---|
| `markerset_path` | – | required |
| `out_dir` | – | required |

Strip the ``*WK`` joint-centre markers from a copy of the marker set.

The joint centres are derived, not measured, so they must drive SCALING but  
never marker REGISTRATION -- otherwise the IK pass would drag the model's  
real markers around to satisfy a regression estimate.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L296)</sub>

### `spec_from_config`

```python
spec_from_config(items)
```

| input | type | default |
|---|---|---|
| `items` | – | required |

A measurement spec from session.yaml's ``scale_measurements`` list.

A mapping ``{name: {pairs: [[a, b], ...], bodies: {body: axes}}}`` (one  
line per measurement -- folds in an editor) or the older list of  
``{name, pairs, bodies}``. ``axes`` any of ``"X"``, ``"XY"``, ``"XYZ"`` ...  
Returns the tuple form :func:`build_measurement_set` takes. Marker aliases  
still apply on top.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L378)</sub>

### `model_marker_names`

```python
model_marker_names(model)
```

| input | type | default |
|---|---|---|
| `model` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L401)</sub>

### `model_body_names`

```python
model_body_names(model)
```

| input | type | default |
|---|---|---|
| `model` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L406)</sub>

### `markerset_file_names`

```python
markerset_file_names(markerset_path)
```

| input | type | default |
|---|---|---|
| `markerset_path` | – | required |

Marker names declared in an OpenSim marker-set XML.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L411)</sub>

### `build_measurement_set`

```python
build_measurement_set(model, trc_path, spec=None, verbose=True, model_markers=None)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trc_path` | – | required |
| `spec` | – | `None` |
| `verbose` | – | `True` |
| `model_markers` | – | `None` |

Return ``(MeasurementSet, report_lines)`` for this model + static TRC.

Only marker pairs present in BOTH the model marker set and the TRC are  
emitted, and only for bodies this model actually has. Anything dropped is  
reported rather than silently skipped -- a silently empty MeasurementSet is  
the bug this whole module exists to prevent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L420)</sub>

### `verify_scaled`

```python
verify_scaled(generic_path, scaled_path, tol=0.0001, verbose=True)
```

| input | type | default |
|---|---|---|
| `generic_path` | – | required |
| `scaled_path` | – | required |
| `tol` | – | `0.0001` |
| `verbose` | – | `True` |

Compare a scaled model against its generic and shout if nothing changed.

Returns ``(changed: bool, lines: list[str])``. The whole point: a model that  
came out of ScaleTool with every body at 1.0 is INDISTINGUISHABLE from the  
generic apart from mass, and that is precisely the failure mode that  
produced months of 'scaled' results built on generic geometry.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L508)</sub>

### `mass_from_static_grf`

```python
mass_from_static_grf(grf_mot, g=9.80665, verbose=True)
```

| input | type | default |
|---|---|---|
| `grf_mot` | – | required |
| `g` | – | `9.80665` |
| `verbose` | – | `True` |

Measured body mass = mean total vertical GRF / g over the static trial.

Returns ``None`` if the file is missing or the plates read as unloaded.  
Preferred over a typed-in ``body_mass``: the force plates measured this  
subject on this day, wearing what they wore in the trial.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L560)</sub>

### `set_total_mass`

```python
set_total_mass(model_path, target_mass, out_path=None, verbose=True)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `target_mass` | – | required |
| `out_path` | – | `None` |
| `verbose` | – | `True` |

Scale every body's mass and inertia so the model totals ``target_mass``.

For an MRI/TPS-personalised model the geometry must NOT be touched, so  
ScaleTool's ModelScaler is off -- which also means nothing ever applies the  
subject's mass, and the model keeps the generic's. This applies mass alone:  
one uniform factor on every body's mass and inertia, leaving every segment  
length, marker and muscle path exactly as the personalisation left them.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/measurements.py#L602)</sub>
