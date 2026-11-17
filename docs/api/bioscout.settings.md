# `bioscout.settings`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py)

Project settings — BUNDLED TEMPLATE (powerlifting squat study).

This is the default settings module shipped inside bioscout.  
``Project(..., scaffold_settings=True)`` copies it into a project and ``bioscout.Project()``  
falls back to it when a project has no settings.py of its own. A real  
project edits its OWN copy — KEEP THIS FILE.

``__version__`` here is the settings-SCHEMA version, an INDEPENDENT series  
from the bioscout package version: it is what a project pins to say which  
SHAPE of settings.py it was written against, and  
``check_settings_version`` compares its MAJOR.MINOR against a project's  
own value. Bump it only when that shape actually changes.

Running a project copy of this file directly:

    conda activate msk311  
    python settings.py                 # run the pipeline over ITERATIONS  
    python settings.py --check-scaling  
    python settings.py --rescale-all  
    python settings.py --sessions 25_03_31 --skip cateli --reuse-models

Every switch lives in the CONTROL PANEL below. Everything after it is  
configuration bioscout reads at run time, then the runner.

The reasoning that used to fill this file -- why a flag is set the way it is,  
what breaks if it is not -- is in bioscout/docs/SETTINGS.md, and the file it  
was extracted from is kept beside this one as settings.py.pre_streamline.

## Contents

- class [`Subjects`](#subjects) — Roster AUTO-DISCOVERED from simulations/<subject>/<session>/ for the active SESSION, each stamped with its GROUPS template (see above). Scales to hundreds of subjects/sessions with zero per-row typing — onboard the backlog by dropping folders into simulations/ and mapping them in SUBJECT_GROUP (or set default_group).
  - [`Subjects.by_name`](#subjectsby_name) — 
  - [`Subjects.names`](#subjectsnames) — 
- class [`BatchSettings`](#batchsettings) — All project + batch-analysis configuration.
  - [`BatchSettings.trial_type`](#batchsettingstrial_type) — 'Squat_35kg_02' -> 'Squat_35kg' (groups reps of a task).
  - [`BatchSettings.model_for`](#batchsettingsmodel_for) — 
  - [`BatchSettings.JRA_COLUMNS`](#batchsettingsjra_columns) — Joint-reaction (contact-force) column names per model (knee differs) and per leg. ``side`` = 'r'/'l' (accepts 'right'/'left').
  - [`BatchSettings.results_dir`](#batchsettingsresults_dir) — 
- class [`CEINMSSettings`](#ceinmssettings) — 
- class [`SummarySettings`](#summarysettings) — Configuration for the results summary (bioscout.summarize_results()).
- class [`PlottingSettings`](#plottingsettings) — Central colours / line styles / sizes for RESULT figures (not the GUI — that's UISettings). Keyed by DATA SOURCE so different quantities never share a colour: EMG grey, muscle moment orange, ID black, CEINMS blue, SO red, literature green. Read by bioscout via ``utils.plot_style('<source>')``; anything omitted falls back to the package defaults (utils.DEFAULT_PLOT_STYLE).
- class [`UISettings`](#uisettings) — Desktop-app (GUI) look & feel.
- class [`RecordingSettings`](#recordingsettings) — Video capture / recording defaults (experimental).
- [`run_catelli_marker_placer_ik_id_ma_so_ceinms`](#run_catelli_marker_placer_ik_id_ma_so_ceinms) — 
- [`run_deadlifts_export_to_ceinms_jrf`](#run_deadlifts_export_to_ceinms_jrf) — From scratch: the two 35 kg deadlifts through the CEINMS pipeline for the cateli and GPK models —     ingest c3d -> export (markers/GRF/EMG) -> session EMG normalise     -> IK -> ID -> MA -> CEINMS execution -> CEINMS moments -> CEINMS JRA. NO CEINMS calibration: reuses each iteration's existing ceinms_calibration/subjectCalibrated.xml.

<a id="subjects"></a>

## class `Subjects`

Roster AUTO-DISCOVERED from simulations/<subject>/<session>/ for the active  
SESSION, each stamped with its GROUPS template (see above). Scales to hundreds  
of subjects/sessions with zero per-row typing — onboard the backlog by dropping  
folders into simulations/ and mapping them in SUBJECT_GROUP (or set default_group).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L250)</sub>

<a id="subjectsby_name"></a>

### `Subjects.by_name`

```python
Subjects.by_name(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L262)</sub>

<a id="subjectsnames"></a>

### `Subjects.names`

```python
Subjects.names()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L266)</sub>

<a id="batchsettings"></a>

## class `BatchSettings`

All project + batch-analysis configuration.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L269)</sub>

<a id="batchsettingstrial_type"></a>

### `BatchSettings.trial_type`

```python
BatchSettings.trial_type(trial_name)
```

| input | type | default |
|---|---|---|
| `trial_name` | – | required |

'Squat_35kg_02' -> 'Squat_35kg' (groups reps of a task).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L414)</sub>

<a id="batchsettingsmodel_for"></a>

### `BatchSettings.model_for`

```python
BatchSettings.model_for(subject, force_type='SO')
```

| input | type | default |
|---|---|---|
| `subject` | – | required |
| `force_type` | – | `'SO'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L419)</sub>

<a id="batchsettingsjra_columns"></a>

### `BatchSettings.JRA_COLUMNS`

```python
BatchSettings.JRA_COLUMNS(model_name, side='r')
```

| input | type | default |
|---|---|---|
| `model_name` | – | required |
| `side` | – | `'r'` |

Joint-reaction (contact-force) column names per model (knee differs)  
and per leg. ``side`` = 'r'/'l' (accepts 'right'/'left').

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L424)</sub>

<a id="batchsettingsresults_dir"></a>

### `BatchSettings.results_dir`

```python
BatchSettings.results_dir()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L439)</sub>

<a id="ceinmssettings"></a>

## class `CEINMSSettings`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L442)</sub>

<a id="summarysettings"></a>

## class `SummarySettings`

Configuration for the results summary (bioscout.summarize_results()).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L510)</sub>

<a id="plottingsettings"></a>

## class `PlottingSettings`

Central colours / line styles / sizes for RESULT figures (not the GUI —  
that's UISettings). Keyed by DATA SOURCE so different quantities never share  
a colour: EMG grey, muscle moment orange, ID black, CEINMS blue, SO red,  
literature green. Read by bioscout via ``utils.plot_style('<source>')``;  
anything omitted falls back to the package defaults (utils.DEFAULT_PLOT_STYLE).

Each source maps to {'color', 'ls' (line style), 'lw' (line width)}.

COLOURS ARE PLAIN (R, G, B) IN 0-255 — pick any colour and paste the RGB here.  
Colour picker:  https://share.google/Va9O7umqecaS1dthG  
(Hex '#2E86AB', a named colour 'tab:blue', or 0-1 tuples also work — bioscout  
auto-detects 0-255 vs 0-1.)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L557)</sub>

<a id="uisettings"></a>

## class `UISettings`

Desktop-app (GUI) look & feel.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L586)</sub>

<a id="recordingsettings"></a>

## class `RecordingSettings`

Video capture / recording defaults (experimental).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L610)</sub>

### `run_catelli_marker_placer_ik_id_ma_so_ceinms`

```python
run_catelli_marker_placer_ik_id_ma_so_ceinms()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L627)</sub>

### `run_deadlifts_export_to_ceinms_jrf`

```python
run_deadlifts_export_to_ceinms_jrf()
```

From scratch: the two 35 kg deadlifts through the CEINMS pipeline for the  
cateli and GPK models —  
    ingest c3d -> export (markers/GRF/EMG) -> session EMG normalise  
    -> IK -> ID -> MA -> CEINMS execution -> CEINMS moments -> CEINMS JRA.  
NO CEINMS calibration: reuses each iteration's existing  
ceinms_calibration/subjectCalibrated.xml.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/settings.py#L642)</sub>
