# `bioscout.model.report`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/report.py)

Compare the DIMENSIONS and SEGMENT MASSES of several ``.osim`` models.

  
**Why this module exists**

Two people scaling the same subject with the same generic model can produce  
models that differ by tens of millimetres per segment and tens of percent per  
segment mass, and nothing in the resulting ``.osim`` says so. Before comparing  
kinematics, moments or joint contact forces ACROSS scaling methods, you need to  
know how far apart the models themselves are — otherwise a "method effect" is  
really a scaling artefact.

It reads the XML directly (``xml.etree`` only, via  
:mod:`bioscout.model.tps.osim_format` for the 3.x/4.x differences), so it  
needs **no OpenSim install** and never modifies the models.

  
**What "dimension" means here**

For every joint, the norm of its PARENT-frame offset translation: the distance  
from the parent body's origin to the joint centre, expressed in the parent  
frame. On a serial chain that is the parent segment's length — ``femur_r ->  
walker_knee_r`` IS the femur length. This is the quantity ScaleTool's scale  
factors actually act on, so it is what differs between scaling methods.

  
**Usage**

    from bioscout.model.report import compare_models  
    rep = compare_models(r"C:\path\to\models_folder")      # every *.osim in it  
    print(rep["segment_mass"])

    # explicit list + labels, and write the tables out  
    compare_models({"Addbio": "Addbio_Scaled_Model.osim",  
                    "Feri":   "Feri_Scaled_Model.osim"},  
                   out="model_comparison.xlsx",  
                   setups={"Feri": "Feri_Scaled_Setup.xml"})

Or from the command line::

    python -m bioscout.model.report <folder-or-models...> -o report.xlsx

## Contents

- [`read_model_geometry`](#read_model_geometry) — Bodies (mass / COM / inertia / mesh scale) and joints (offsets) of one model.
- [`read_scale_setup`](#read_scale_setup) — The intent behind a ScaleTool setup: subject mass/height, whether mass distribution was preserved, the scaling order, and any MANUAL ScaleSet override. A manual override in ``scaling_order`` is the usual reason two setups that look alike produce different segment lengths.
- [`dimension_sources`](#dimension_sources) — Which joint each body's dimension is measured to.
- [`segment_dimensions`](#segment_dimensions) — Each body's offset to its distal joint, named for the SEGMENT it describes.
- [`compare_models`](#compare_models) — Tabulate dimensions and segment masses across models.
- [`make_figures`](#make_figures) — Render the comparison figures. Returns the list of files written.

### `read_model_geometry`

```python
read_model_geometry(path) -> dict
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `dict`

Bodies (mass / COM / inertia / mesh scale) and joints (offsets) of one model.

Returns ``{"path", "version", "name", "bodies", "joints"}``. Works on  
OpenSim 3.x and 4.x; ``opensim`` is NOT imported.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/report.py#L299)</sub>

### `read_scale_setup`

```python
read_scale_setup(path) -> dict
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `dict`

The intent behind a ScaleTool setup: subject mass/height, whether mass  
distribution was preserved, the scaling order, and any MANUAL ScaleSet  
override. A manual override in ``scaling_order`` is the usual reason two  
setups that look alike produce different segment lengths.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/report.py#L356)</sub>

### `dimension_sources`

```python
dimension_sources(geom: Mapping) -> Dict[str, dict]
```

| input | type | default |
|---|---|---|
| `geom` | Mapping | required |

**returns** `Dict[str, dict]`

Which joint each body's dimension is measured to.

A body can parent several joints — ``pelvis`` parents hip_r, hip_l and back;  
``femur_r`` parents walker_knee_r and patellofemoral_r; ``torso`` parents  
acromial_r and acromial_l. The one with the LONGEST offset is the segment's  
long axis, so that is what gets reported as ``<body>_x/y/z/length``; the  
others are recorded here rather than silently dropped.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/report.py#L408)</sub>

### `segment_dimensions`

```python
segment_dimensions(geom: Mapping, per_axis: bool = True) -> Dict[str, float]
```

| input | type | default |
|---|---|---|
| `geom` | Mapping | required |
| `per_axis` | bool | `True` |

**returns** `Dict[str, float]`

Each body's offset to its distal joint, named for the SEGMENT it describes.

``{"femur_r_x": .., "femur_r_y": .., "femur_r_z": .., "femur_r_length": ..}``  
in metres, in the model's own body order. Components are SIGNED and expressed  
in the parent body's frame (a femur's y is negative — it points distally), so  
a sign difference between two models is a real difference, not a formatting  
artefact. ``_length`` is the vector norm: the number you would quote as  
"femur length", and what the TPS validation invariants check.

``per_axis=False`` returns only the ``_length`` entries.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/report.py#L427)</sub>

### `compare_models`

```python
compare_models(
    models,
    out: Optional[str] = None,
    setups: Optional[Mapping[str, str]] = None,
    figures: Union[bool, str, None] = None,
    geometry=None,
    verbose: bool = True
) -> dict
```

| input | type | default |
|---|---|---|
| `models` | – | required |
| `out` | Optional[str] | `None` |
| `setups` | Optional[Mapping[str, str]] | `None` |
| `figures` | Union[bool, str, None] | `None` |
| `geometry` | – | `None` |
| `verbose` | bool | `True` |

**returns** `dict`

Tabulate dimensions and segment masses across models.

  
**Parameters**

models : folder, list of ``.osim`` paths, or ``{label: path}``  
    A folder compares every ``.osim`` inside it. Labels are derived from the  
    filename (``Feri_Scaled_Model.osim`` -> ``Feri``) unless you pass a dict.  
out : str, optional  
    Write the tables to ``.xlsx`` (one sheet each) or ``.csv`` (one file per  
    table, suffixed).  
geometry : path or list of paths, optional  
    Where to find the generic ``.vtp``/``.stl`` meshes the models reference.  
    Searched before ``Geometry/`` beside the models and the copy bundled with  
    bioscout. Without them the mesh-derived sizes are unavailable (the joint  
    and mass tables are not affected).  
figures : bool or str, optional  
    ``True`` renders the figures beside ``out`` (or into the models' folder);  
    pass a path to choose the output folder. Four figures: segment  
    dimensions, segment mass + mass distribution, a mesh-scale heatmap and  
    left-right asymmetry, as .png and .pdf.  
setups : ``{label: ScaleTool setup .xml}``, optional  
    Adds a table of scaling INTENT — preserve_mass_distribution, scaling  
    order, manual overrides — which is usually what explains the differences.

  
**Returns**

dict of DataFrames: ``totals``, ``segment_mass``, ``segment_mass_fraction``,  
``segment_dimension``, ``mesh_scale``, ``asymmetry``, and ``scale_setup``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/report.py#L491)</sub>

### `make_figures`

```python
make_figures(
    rep,
    out_dir='.',
    prefix='model_comparison',
    dpi=200,
    formats=('png',),
    verbose=True
)
```

| input | type | default |
|---|---|---|
| `rep` | – | required |
| `out_dir` | – | `'.'` |
| `prefix` | – | `'model_comparison'` |
| `dpi` | – | `200` |
| `formats` | – | `('png',)` |
| `verbose` | – | `True` |

Render the comparison figures. Returns the list of files written.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/report.py#L1184)</sub>
