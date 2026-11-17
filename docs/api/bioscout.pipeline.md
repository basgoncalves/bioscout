# `bioscout.pipeline`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/pipeline.py)

bioscout.pipeline — project-level orchestration driven by settings flags.

This folds the old per-project driver scripts (redo_pipeline.py, run_pipeline.py,  
redo_ceinms.py, summarize_results.py) into the package so a project is run with a  
single command::

    python -m bioscout -b settings.py

The settings module controls what runs via module-level flags::

    RUN_PIPELINE = True   # rebuild inputs from c3d + IK/ID/MA/SO/JRA + CEINMS  
    RUN_SUMMARY  = True   # build the results/manuscript summary  
    RUN_SCALING  = False  # (optional) re-scale models before the pipeline

``run_project`` reads those flags and calls the steps below. Everything operates  
on a ``bioscout.Project`` rooted at the settings file's folder.

## Contents

- [`reset_simulations`](#reset_simulations) — Back up and reset a project's simulations tree to inputs-only.
- [`run_pipeline`](#run_pipeline) — Full-resolution, non-destructive run of the whole pipeline.
- [`run_summary`](#run_summary) — Build the project's results/manuscript summary.
- [`run_project`](#run_project) — Dispatcher for ``python -m bioscout -b settings.py``.

### `reset_simulations`

```python
reset_simulations(
    project_dir=None,
    backup=True,
    dry_run=False,
    subjects=None,
    session=None,
    trials=None,
    trial_keep=None,
    session_keep=None,
    raw_inputs=False,
    extra_backup=('results', os.path.join('manuscript', 'figures')),
    verbose=True
)
```

| input | type | default |
|---|---|---|
| `project_dir` | – | `None` |
| `backup` | – | `True` |
| `dry_run` | – | `False` |
| `subjects` | – | `None` |
| `session` | – | `None` |
| `trials` | – | `None` |
| `trial_keep` | – | `None` |
| `session_keep` | – | `None` |
| `raw_inputs` | – | `False` |
| `extra_backup` | – | `('results', os.path.join('manuscript', 'figures'))` |
| `verbose` | – | `True` |

Back up and reset a project's simulations tree to inputs-only.

For each ``simulations/<subject>/<session>``:  
  * every trial folder is reduced to ``trial_keep`` (raw inputs + trial  
    settings); all generated outputs — IK/ID/MA/SO/JRA results, ``setup_*.xml``,  
    ``MuscleAnalysis/``, ``Execution*/``, plots, filtered EMG, ... — are deleted;  
  * session-level CEINMS *inputs* (``session_keep``) are kept; calibration  
    *outputs* (``subjectCalibrated*``, ``*_parameters.png``, ``*_vs_uncalibrated.png``)  
    and any non-trial sub-folder (``calibrationOutput*``, old run backups) are deleted.

Before deleting anything, ``simulations/`` and every existing path in  
``extra_backup`` (project-relative, e.g. ``results/`` and ``manuscript/figures/``)  
are copied to timestamped siblings ``<name>_backup_<YYYYmmdd_HHMMSS>`` that all  
share one timestamp. Use ``dry_run=True`` to preview without touching disk.

Pass ``subjects`` (name or list), ``session`` (name or list) and/or ``trials``  
(name or list) to scope the reset to just those; the backup is then limited to  
the selected subtree too. When ``trials`` is given, only matching trial folders  
are reset — non-trial dirs and session-level files in that session are left  
untouched. With no scope, every subject/session is reset and the whole tree is  
backed up.

Returns a dict: ``{"timestamp", "backups": [...], "trials_reset", "removed"}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/pipeline.py#L86)</sub>

### `run_pipeline`

```python
run_pipeline(
    project_dir=None,
    scale=False,
    ceinms=True,
    replace=True,
    calibration_trials=('Walking_02', 'Squat_BW_01'),
    backup=True,
    normalise_inputs=None
)
```

| input | type | default |
|---|---|---|
| `project_dir` | – | `None` |
| `scale` | – | `False` |
| `ceinms` | – | `True` |
| `replace` | – | `True` |
| `calibration_trials` | – | `('Walking_02', 'Squat_BW_01')` |
| `backup` | – | `True` |
| `normalise_inputs` | – | `None` |

Full-resolution, non-destructive run of the whole pipeline.

For every subject/session/trial: export_c3d (regenerates markers/grf/emg/  
trial_settings from the C3D at native sampling — no downsampling and no  
destructive strip), then run IK -> ID -> MA -> SO -> muscle moments -> JRA,  
and finally CEINMS per session (normalise EMG + calibrate + execute). Model  
scaling is intentionally NOT performed (existing scaled models are reused);  
pass ``scale=True`` only once that is wired up.

Trials with no c3d but an existing .trc (template/MRI subjects) are analysed  
from their existing markers/grf as-is. ``backup`` and ``normalise_inputs``  
are accepted for backwards compatibility but no longer used.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/pipeline.py#L383)</sub>

### `run_summary`

```python
run_summary(project_dir=None)
```

| input | type | default |
|---|---|---|
| `project_dir` | – | `None` |

Build the project's results/manuscript summary.

The summary is intentionally project-specific (manuscript figures, metric &  
curve CSVs), so it lives in the project as ``summarize_results.py`` and is  
executed here. Falls back to the package summary (``utils.summary``) if the  
project script is absent.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/pipeline.py#L552)</sub>

### `run_project`

```python
run_project(project_dir, settings_module)
```

| input | type | default |
|---|---|---|
| `project_dir` | – | required |
| `settings_module` | – | required |

Dispatcher for ``python -m bioscout -b settings.py``.

Reads RUN_PIPELINE / RUN_SUMMARY / RUN_SCALING from the settings module and  
runs the requested stages. Returns True if everything requested succeeded.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/pipeline.py#L575)</sub>
