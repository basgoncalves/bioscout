# `bioscout.model.scale.pyosim_scale`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/pyosim_scale.py)

Model scaling with bioscout.pyosim, for iterations with ``engine: pyosim``.

Same inputs and outputs as :func:`bioscout.model.scale.osim_scale.scale_model`, and  
the same preparation, done here as plain XML/text without OpenSim (2026-11-03: a  
pyosim iteration never touches OpenSim):

  * trailing NUL padding stripped from the generic (some warping tools add it);  
  * markers in BatchSettings.markers_to_skip and markers on ground dropped from a  
    scale-ready copy of the generic and of the marker-set file;  
  * joint centres (Harrington hips, knee/ankle midpoints) added to a scaling-only  
    copy of the static TRC;  
  * a ScaleTool setup written: the iteration's ``scale_tool`` template with the marker  
    aliases applied (every marker it names must be in the static TRC), or a  
    MeasurementSet from ``measurement_spec`` (pairs in both the model marker set and  
    the TRC, bodies the model has);

then pyosim measures, scales (bodies, markers, muscle lengths) and registers the  
markers on the static pose, leaving the derived joint-centre markers out of that  
registration, as the OpenSim route does. The setup is a normal ScaleTool file, so the  
OpenSim GUI can open it, but nothing here runs OpenSim.

## Contents

- [`scale_model`](#scale_model) — 
- [`increase_isometric_force`](#increase_isometric_force) — max_isometric_force x factor -> <model>_increased_<f>.osim, as osim_ops' version, in plain XML.

### `scale_model`

```python
scale_model(
    generic_opensim_model_path,
    static_trc_path,
    scaled_model_path,
    scale_setup_output_dir=None,
    mass=None,
    marker_set_file=None,
    linear_scaling=True,
    marker_placer=False,
    marker_aliases=None,
    measurement_spec=None,
    scale_tool=None,
    time_range=None,
    **_ignored
)
```

| input | type | default |
|---|---|---|
| `generic_opensim_model_path` | – | required |
| `static_trc_path` | – | required |
| `scaled_model_path` | – | required |
| `scale_setup_output_dir` | – | `None` |
| `mass` | – | `None` |
| `marker_set_file` | – | `None` |
| `linear_scaling` | – | `True` |
| `marker_placer` | – | `False` |
| `marker_aliases` | – | `None` |
| `measurement_spec` | – | `None` |
| `scale_tool` | – | `None` |
| `time_range` | – | `None` |
| `**_ignored` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/pyosim_scale.py#L180)</sub>

### `increase_isometric_force`

```python
increase_isometric_force(osim_modelPath, muscleList='all', factor=1.0)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | required |
| `muscleList` | – | `'all'` |
| `factor` | – | `1.0` |

max_isometric_force x factor -> <model>_increased_<f>.osim, as osim_ops' version, in plain XML.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale/pyosim_scale.py#L231)</sub>
