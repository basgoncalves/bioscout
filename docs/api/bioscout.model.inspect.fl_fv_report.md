# `bioscout.model.inspect.fl_fv_report`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py)

Build the fibre force-length-velocity figure from a session.

`fl_fv_surface` draws; this module collects. Give it a `FlFvSpec` -- which  
tasks, which muscle groups, which models, which pictograms -- and a source that  
knows where a project keeps its files, and it produces the figure.

    from bioscout.model.inspect.fl_fv_report import FlFvSpec, build_fl_fv

    spec = FlFvSpec(  
        session_dir="/data/Athlete_03/25_03_31",  
        tasks={"Walking": ["Walking_03", "Walking_05"],  
               "Squat":   ["Squat_01", "Squat_02"]},  
        groups={"Vasti": ["vasint_r", "vaslat_r", "vasmed_r"],  
                "Triceps Surae": ["soleus_r", "gaslat_r", "gasmed_r"]},  
        models=["cateli", "gpk"],  
        model_colors={"cateli": "green", "gpk": "firebrick"},  
        task_icons={"Walking": "icons/walking.png"},  
        group_icons={"Vasti": "icons/vasti.png"})  
    build_fl_fv(spec, out_dir="figures")

NOTHING here is specific to one study: the tasks, their pictograms, the muscle  
groups and their pictograms, the models and their colours all come out of the  
spec. A project that needs different tasks or different muscles changes the  
spec, not this file.

WHERE THE NUMBERS COME FROM  
    `FlFvSource` is the seam. The default `BioscoutSource` reads a standard  
    bioscout session (`3_iterations/<model>/<trial>/...`). A project whose  
    layout or conventions differ subclasses it and overrides the handful of  
    hooks it needs -- which is also where project POLICY belongs (which .osim a  
    given algorithm ran on, how a joint's reaction columns are named, what to  
    do when the fibre output is degenerate). Keeping that out here means no  
    release of bioscout inherits one dataset's quirks.

## Contents

- class [`FlFvSpec`](#flfvspec) — Everything study-specific, in one place.
  - [`FlFvSpec.colour_of`](#flfvspeccolour_of) — 
  - [`FlFvSpec.label_of`](#flfvspeclabel_of) — 
  - [`FlFvSpec.group_colour`](#flfvspecgroup_colour) — 
  - [`FlFvSpec.colors`](#flfvspeccolors) — 
- class [`FlFvSource`](#flfvsource) — The seam between the figure and a project's folder layout.
  - [`FlFvSource.force`](#flfvsourceforce) — 
  - [`FlFvSource.activation`](#flfvsourceactivation) — 
  - [`FlFvSource.mt_length`](#flfvsourcemt_length) — 
  - [`FlFvSource.fibre_states`](#flfvsourcefibre_states) — 
  - [`FlFvSource.model_file`](#flfvsourcemodel_file) — 
  - [`FlFvSource.jra`](#flfvsourcejra) — 
  - [`FlFvSource.bodyweight_N`](#flfvsourcebodyweight_n) — 
  - [`FlFvSource.time_range`](#flfvsourcetime_range) — 
  - [`FlFvSource.sides`](#flfvsourcesides) — 
  - [`FlFvSource.jra_columns`](#flfvsourcejra_columns) — The three force columns of one joint reaction, project convention.
- class [`BioscoutSource`](#bioscoutsource) — A standard bioscout session: `3_iterations/<model>/<trial>/...`.
  - [`BioscoutSource.root`](#bioscoutsourceroot) — 
  - [`BioscoutSource.trial_dir`](#bioscoutsourcetrial_dir) — 
  - [`BioscoutSource.force`](#bioscoutsourceforce) — 
  - [`BioscoutSource.activation`](#bioscoutsourceactivation) — 
  - [`BioscoutSource.mt_length`](#bioscoutsourcemt_length) — 
  - [`BioscoutSource.fibre_states`](#bioscoutsourcefibre_states) — CEINMS solves its own fibre dynamics; SO has none of its own.
  - [`BioscoutSource.model_file`](#bioscoutsourcemodel_file) — 
  - [`BioscoutSource.jra`](#bioscoutsourcejra) — 
  - [`BioscoutSource.bodyweight_N`](#bioscoutsourcebodyweight_n) — 
- [`trial_traces`](#trial_traces) — {group: raw arrays} for one trial, over NCYC samples of the cycle.
- [`task_traces`](#task_traces) — {group: trace} averaged over the repetitions of one task, one limb.
- [`joint_range_bw`](#joint_range_bw) — (min, max) |R| of one joint contact force over the task, in BW.
- [`collect`](#collect) — {(task, model, algo): {group: trace}}, {(task, model, algo, joint): (lo, hi)}.
- [`build_fl_fv`](#build_fl_fv) — Collect and draw. Returns the paths written.

<a id="flfvspec"></a>

## class `FlFvSpec`

Everything study-specific, in one place.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L79)</sub>

<a id="flfvspeccolour_of"></a>

### `FlFvSpec.colour_of`

```python
FlFvSpec.colour_of(model)
```

| input | type | default |
|---|---|---|
| `model` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L98)</sub>

<a id="flfvspeclabel_of"></a>

### `FlFvSpec.label_of`

```python
FlFvSpec.label_of(model)
```

| input | type | default |
|---|---|---|
| `model` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L102)</sub>

<a id="flfvspecgroup_colour"></a>

### `FlFvSpec.group_colour`

```python
FlFvSpec.group_colour(group)
```

| input | type | default |
|---|---|---|
| `group` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L105)</sub>

<a id="flfvspeccolors"></a>

### `FlFvSpec.colors`

```python
FlFvSpec.colors()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L109)</sub>

<a id="flfvsource"></a>

## class `FlFvSource`

The seam between the figure and a project's folder layout.

Every method may return None; a missing file drops that series quietly  
rather than failing the whole figure.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L117)</sub>

<a id="flfvsourceforce"></a>

### `FlFvSource.force`

```python
FlFvSource.force(model, trial, algo)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trial` | – | required |
| `algo` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L124)</sub>

<a id="flfvsourceactivation"></a>

### `FlFvSource.activation`

```python
FlFvSource.activation(model, trial, algo)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trial` | – | required |
| `algo` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L125)</sub>

<a id="flfvsourcemt_length"></a>

### `FlFvSource.mt_length`

```python
FlFvSource.mt_length(model, trial)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trial` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L126)</sub>

<a id="flfvsourcefibre_states"></a>

### `FlFvSource.fibre_states`

```python
FlFvSource.fibre_states(model, trial, algo)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trial` | – | required |
| `algo` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L127)</sub>

<a id="flfvsourcemodel_file"></a>

### `FlFvSource.model_file`

```python
FlFvSource.model_file(model, algo)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `algo` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L128)</sub>

<a id="flfvsourcejra"></a>

### `FlFvSource.jra`

```python
FlFvSource.jra(model, trial, algo)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trial` | – | required |
| `algo` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L129)</sub>

<a id="flfvsourcebodyweight_n"></a>

### `FlFvSource.bodyweight_N`

```python
FlFvSource.bodyweight_N(model)
```

| input | type | default |
|---|---|---|
| `model` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L130)</sub>

<a id="flfvsourcetime_range"></a>

### `FlFvSource.time_range`

```python
FlFvSource.time_range(trial)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L131)</sub>

<a id="flfvsourcesides"></a>

### `FlFvSource.sides`

```python
FlFvSource.sides(trial)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L132)</sub>

<a id="flfvsourcejra_columns"></a>

### `FlFvSource.jra_columns`

```python
FlFvSource.jra_columns(model, joint, side)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `joint` | – | required |
| `side` | – | required |

The three force columns of one joint reaction, project convention.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L134)</sub>

<a id="bioscoutsource"></a>

## class `BioscoutSource`(FlFvSource)

```python
BioscoutSource(session_dir, spec=None)
```

| input | type | default |
|---|---|---|
| `session_dir` | – | required |
| `spec` | – | `None` |

A standard bioscout session: `3_iterations/<model>/<trial>/...`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L143)</sub>

<a id="bioscoutsourceroot"></a>

### `BioscoutSource.root`

```python
BioscoutSource.root()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L151)</sub>

<a id="bioscoutsourcetrial_dir"></a>

### `BioscoutSource.trial_dir`

```python
BioscoutSource.trial_dir(model, trial)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trial` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L155)</sub>

<a id="bioscoutsourceforce"></a>

### `BioscoutSource.force`

```python
BioscoutSource.force(model, trial, algo)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trial` | – | required |
| `algo` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L165)</sub>

<a id="bioscoutsourceactivation"></a>

### `BioscoutSource.activation`

```python
BioscoutSource.activation(model, trial, algo)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trial` | – | required |
| `algo` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L173)</sub>

<a id="bioscoutsourcemt_length"></a>

### `BioscoutSource.mt_length`

```python
BioscoutSource.mt_length(model, trial)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trial` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L181)</sub>

<a id="bioscoutsourcefibre_states"></a>

### `BioscoutSource.fibre_states`

```python
BioscoutSource.fibre_states(model, trial, algo)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trial` | – | required |
| `algo` | – | required |

CEINMS solves its own fibre dynamics; SO has none of its own.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L186)</sub>

<a id="bioscoutsourcemodel_file"></a>

### `BioscoutSource.model_file`

```python
BioscoutSource.model_file(model, algo)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `algo` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L197)</sub>

<a id="bioscoutsourcejra"></a>

### `BioscoutSource.jra`

```python
BioscoutSource.jra(model, trial, algo)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `trial` | – | required |
| `algo` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L201)</sub>

<a id="bioscoutsourcebodyweight_n"></a>

### `BioscoutSource.bodyweight_N`

```python
BioscoutSource.bodyweight_N(model)
```

| input | type | default |
|---|---|---|
| `model` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L209)</sub>

### `trial_traces`

```python
trial_traces(spec, src, model, trial, algo, bw, par)
```

| input | type | default |
|---|---|---|
| `spec` | – | required |
| `src` | – | required |
| `model` | – | required |
| `trial` | – | required |
| `algo` | – | required |
| `bw` | – | required |
| `par` | – | required |

{group: raw arrays} for one trial, over NCYC samples of the cycle.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L268)</sub>

### `task_traces`

```python
task_traces(spec, src, model, trials, algo, where='')
```

| input | type | default |
|---|---|---|
| `spec` | – | required |
| `src` | – | required |
| `model` | – | required |
| `trials` | – | required |
| `algo` | – | required |
| `where` | – | `''` |

{group: trace} averaged over the repetitions of one task, one limb.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L325)</sub>

### `joint_range_bw`

```python
joint_range_bw(spec, src, model, trials, algo, joint)
```

| input | type | default |
|---|---|---|
| `spec` | – | required |
| `src` | – | required |
| `model` | – | required |
| `trials` | – | required |
| `algo` | – | required |
| `joint` | – | required |

(min, max) |R| of one joint contact force over the task, in BW.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L353)</sub>

### `collect`

```python
collect(spec, src, cache_path=None, refresh=False, verbose=True)
```

| input | type | default |
|---|---|---|
| `spec` | – | required |
| `src` | – | required |
| `cache_path` | – | `None` |
| `refresh` | – | `False` |
| `verbose` | – | `True` |

{(task, model, algo): {group: trace}}, {(task, model, algo, joint): (lo, hi)}.

Reading the .sto files dominates the runtime; drawing is seconds. The cache  
is INCREMENTAL and saved after every task, so an interrupted run leaves  
progress behind and the next one picks up where it stopped.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L375)</sub>

### `build_fl_fv`

```python
build_fl_fv(
    spec,
    src=None,
    out_dir='.',
    split='muscle',
    groups=None,
    cache_path=None,
    refresh=False,
    elev=26.0,
    azim=-122.0,
    prefix='fig_fl_fv_surface',
    **kw
)
```

| input | type | default |
|---|---|---|
| `spec` | – | required |
| `src` | – | `None` |
| `out_dir` | – | `'.'` |
| `split` | – | `'muscle'` |
| `groups` | – | `None` |
| `cache_path` | – | `None` |
| `refresh` | – | `False` |
| `elev` | – | `26.0` |
| `azim` | – | `-122.0` |
| `prefix` | – | `'fig_fl_fv_surface'` |
| `**kw` | – | – |

Collect and draw. Returns the paths written.

split "muscle"  one figure per muscle group, its pictogram and name in the  
                top-left corner  
split "all"     every group on one figure, a ROW per group with its  
                pictogram and name in the left gutter

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_report.py#L504)</sub>
