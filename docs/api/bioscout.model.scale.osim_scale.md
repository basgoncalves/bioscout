# `bioscout.model.scale.osim_scale`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/osim_scale.py)

ScaleTool driving: build a scaled model, and place its markers.

Joins ``measurements.py`` (MeasurementSet construction) and ``model_scaler.py``  
(the GUI's wrapper) in ``bioscout.model.scale``. Despite its name,  
``place_markers_via_ik`` edits the model's marker placements -- it does not run  
a simulation, which is why it is here and not under ``simulate``.

Split out of the old ``bioscout/utils/openSim.py`` (docs/RESTRUCTURE_PLAN.md,  
stage 6) -- the code is unchanged, only its address.

## Contents

- [`scale_model_from_xml`](#scale_model_from_xml) — Scale an OpenSim model using a pre-existing ScaleTool setup XML (preserving its MeasurementSet, MarkerPlacer IK tasks, etc.) while overriding the key file paths and optionally the subject mass.
- [`scale_model`](#scale_model) — Scale an OpenSim model using the ScaleTool based on static marker data from a TRC file.
- [`run_scale_setup`](#run_scale_setup) — Run a ScaleTool setup XML exactly as written -- `bioscout model scale --setup`.
- [`name_model_after_file`](#name_model_after_file) — Rename ``<Model name="...">`` to ``name`` (default: the file's stem).
- [`copy_geometry_beside`](#copy_geometry_beside) — Copy the meshes ``osim_path`` references into ``<its folder>/Geometry/``.
- [`place_markers_via_ik`](#place_markers_via_ik) — Register a model's markers to the subject's STATIC pose WITHOUT ScaleTool's MarkerPlacer (which segfaults / throws bad_alloc on some complex models, e.g. the MRI/Lerner-knee model). Standard MarkerPlacer algorithm, done by hand:

### `scale_model_from_xml`

```python
scale_model_from_xml(
    setup_xml_path,
    generic_model_path,
    static_trc_path,
    scaled_model_path,
    mass=None
)
```

| input | type | default |
|---|---|---|
| `setup_xml_path` | – | required |
| `generic_model_path` | – | required |
| `static_trc_path` | – | required |
| `scaled_model_path` | – | required |
| `mass` | – | `None` |

Scale an OpenSim model using a pre-existing ScaleTool setup XML (preserving its  
MeasurementSet, MarkerPlacer IK tasks, etc.) while overriding the key file paths  
and optionally the subject mass.

  
**Args**

    setup_xml_path (str): Path to the ScaleTool setup XML file.  
    generic_model_path (str): Path to the unscaled generic .osim model.  
    static_trc_path (str): Path to the static trial TRC file.  
    scaled_model_path (str): Absolute path for the output scaled .osim model.  
    mass (float, optional): Subject mass in kg. Defaults to model total mass.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/osim_scale.py#L24)</sub>

### `scale_model`

```python
scale_model(
    generic_opensim_model_path,
    static_trc_path,
    scaled_model_path,
    scale_setup_output_dir=None,
    mass=None,
    time_range=None,
    marker_set_file=None,
    linear_scaling=True,
    marker_placer=False,
    ik_weights=None,
    setup_xml_path=None,
    run=True,
    marker_aliases=None,
    measurement_spec=None,
    scale_tool=None
)
```

| input | type | default |
|---|---|---|
| `generic_opensim_model_path` | – | required |
| `static_trc_path` | – | required |
| `scaled_model_path` | – | required |
| `scale_setup_output_dir` | – | `None` |
| `mass` | – | `None` |
| `time_range` | – | `None` |
| `marker_set_file` | – | `None` |
| `linear_scaling` | – | `True` |
| `marker_placer` | – | `False` |
| `ik_weights` | – | `None` |
| `setup_xml_path` | – | `None` |
| `run` | – | `True` |
| `marker_aliases` | – | `None` |
| `measurement_spec` | – | `None` |
| `scale_tool` | – | `None` |

Scale an OpenSim model using the ScaleTool based on static marker data from a TRC file.

The ScaleTool has two independent stages, exposed here as booleans that map  
1:1 onto OpenSim's own ``ModelScaler`` and ``MarkerPlacer``:

  * ``linear_scaling`` (ModelScaler) — dimensional scaling from marker  
    distances. Turn OFF for an already-personalised model (e.g. MRI/TPS  
    geometry) so its segment sizes are NOT changed.  
  * ``marker_placer`` (MarkerPlacer) — move the model's markers onto the  
    subject's static-trial markers (with an IK pass). Useful even when  
    ``linear_scaling`` is off, so markers line up for IK. Off by default  
    because it is memory-heavy with 100+ marker sets.

Combinations: both True = classic scale+placement; linear only = size but  
keep template markers; placer only = keep geometry, re-place markers  
(MRI case); both False = copy the model through unchanged.

  
**Args**

    scale_setup_output_dir: Directory where to save scale_setup.xml (defaults to scaled_model directory)  
    ik_weights: ``{marker: weight}`` for the standalone marker-registration  
        IK. A weight of 0 drops the marker from the pass entirely. Only  
        used when ``marker_placer`` is on; ignored otherwise. Default None  
        = every marker weighted 1.0, which is what this always did.  
    marker_aliases: ``{expected_name: name_this_lab_records}``. The default  
        measurement spec and the joint-centre construction name the  
        Vicon-CGM/powerlifting markers; a lab spelling them differently  
        (FAIS records LSACR/RSACR for LPSI/RPSI, RLFC/RMFC for RKNEL/RKNEM)  
        gets NO joint centre and almost no measurements without this, which  
        scales the pelvis and leaves the femurs generic — silently.  
        ``bioscout scale`` works this map out by asking.  
    measurement_spec: ``[(name, [(a, b), ...], {body: axes}), ...]`` to use  
        instead of ``measurements.DEFAULT_SPEC`` (which is written for the  
        powerlifting/Vicon-CGM protocol). ``marker_aliases`` still apply to  
        it. session.yaml: ``scale_measurements`` (see  
        ``measurements.spec_from_config``).  
    scale_tool: a ScaleTool setup .xml used as the TEMPLATE: its  
        MeasurementSet, scaling order and preserve_mass_distribution are  
        used as written; its paths, mass and time range are ignored and  
        filled from the arguments here. ``measurement_spec`` is then  
        unused. session.yaml: ``iterations.<name>.scale_tool``.  
    setup_xml_path: Where to write the ScaleTool setup. Defaults to  
        ``<scale_setup_output_dir>/scale_setup.xml``. This file is the  
        record of what was actually applied — the MeasurementSet, the  
        joint-centre-augmented TRC, the time range — and is the first thing  
        to read when a scaled model looks wrong.  
    run: False writes the setup and returns its path WITHOUT scaling. The  
        setup references files under ``_temp_scaling/`` (the augmented TRC,  
        the sanitised model), so that folder is kept in this mode — the  
        setup is loadable in the OpenSim GUI as written.

  
**Returns**

    The setup XML path when ``run=False``; otherwise None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/osim_scale.py#L102)</sub>

### `run_scale_setup`

```python
run_scale_setup(setup_xml_path, mass=None)
```

| input | type | default |
|---|---|---|
| `setup_xml_path` | – | required |
| `mass` | – | `None` |

Run a ScaleTool setup XML exactly as written -- `bioscout model scale --setup`.

No paths are overridden and nothing is re-enabled: what the file says is  
what runs. That is the point -- it makes a scaling run reproducible from  
the record `scale_model` leaves behind, and it opens a setup built in the  
OpenSim GUI.

Two things worth knowing about a setup that `scale_model` wrote:

* its MarkerPlacer is OFF. `scale_model` registers markers with a standalone  
  IK pass instead, because ScaleTool's own MarkerPlacer throws bad_alloc on  
  some complex models. Re-running the setup therefore reproduces the  
  DIMENSIONAL scaling, not the marker placement -- run `place_markers_via_ik`  
  after it if you need that too.  
* its paths are relative to the setup file, so the working directory has to  
  be that folder. This chdirs there and restores the old one afterwards.

Returns the ScaleTool exit status as a process return code (0 = scaled).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/osim_scale.py#L499)</sub>

### `name_model_after_file`

```python
name_model_after_file(osim_path, name=None)
```

| input | type | default |
|---|---|---|
| `osim_path` | – | required |
| `name` | – | `None` |

Rename ``<Model name="...">`` to ``name`` (default: the file's stem).

OpenSim's ScaleTool names its output after the TOOL, so every scaled model  
in every project lands as ``<Model name="ModelScaling">`` and the GUI's  
Navigator shows the same word for all of them. Nothing reads this name --  
it is the Navigator label and a couple of log lines -- so a failure here  
must never sink a scaling run.

Rewrites BYTES, not text: these models are CRLF, and text mode would turn  
every CRLF into LF and rewrite ~15000 line endings for a 30-character  
rename. ``surrogateescape`` round-trips anything the decoder dislikes.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/osim_scale.py#L545)</sub>

### `copy_geometry_beside`

```python
copy_geometry_beside(osim_path, source_model_path)
```

| input | type | default |
|---|---|---|
| `osim_path` | – | required |
| `source_model_path` | – | required |

Copy the meshes ``osim_path`` references into ``<its folder>/Geometry/``.

OpenSim resolves a bare ``<mesh_file>`` against the model's own folder, a  
``Geometry/`` beside it, and its INSTALLED Geometry folder. A model scaled  
into a session folder therefore still finds the meshes OpenSim ships  
(r_tibia, pelvis, ribs...) and silently loses the ones that are specific to  
the generic it came from -- for GPK that is r_femur/l_femur/fem_cond/  
tib_plat, i.e. exactly the segments the joint moments are about. The model  
loads with every muscle, marker and joint intact and no femurs, and nothing  
downstream can tell.

Copying them beside the output makes the scaled model portable, which is  
what ``bioscout model check --strict`` asks for. ~6 MB for GPK.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/osim_scale.py#L575)</sub>

### `place_markers_via_ik`

```python
place_markers_via_ik(
    model_path,
    static_trc,
    out_model_path,
    marker_set_file=None,
    time_range=None,
    work_dir=None,
    ik_weights=None,
    max_ik_seconds=2.0,
    scale_set_file=None
)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `static_trc` | – | required |
| `out_model_path` | – | required |
| `marker_set_file` | – | `None` |
| `time_range` | – | `None` |
| `work_dir` | – | `None` |
| `ik_weights` | – | `None` |
| `max_ik_seconds` | – | `2.0` |
| `scale_set_file` | – | `None` |

Register a model's markers to the subject's STATIC pose WITHOUT ScaleTool's  
MarkerPlacer (which segfaults / throws bad_alloc on some complex models, e.g.  
the MRI/Lerner-knee model). Standard MarkerPlacer algorithm, done by hand:

  1. run a normal IK on the static trial (this path works where MarkerPlacer  
     fails),  
  2. move the model to the MEAN static pose,  
  3. relocate each model marker to the averaged experimental marker position,  
     expressed in that marker's parent frame.

Writes the registered model to ``out_model_path``. Best-effort; on failure the  
base model is left as-is (markers un-registered).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/osim_scale.py#L654)</sub>
