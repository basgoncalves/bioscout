# `bioscout.plot.summary`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/summary.py)

BioScout — Summary module  
==========================

Kinematics / kinetics / muscle summaries for processed trials.

Columns = joint DOFs (left + right share a column; left = red, right = blue).  
Rows (configurable via ``settings.SummarySettings.rows``):

    1. Joint angle    (IK; per-joint per-side mean marker error box)  
    2. EMG            (filtered-normalised; channels mapped to the joint muscles)  
    3. Joint moment   (ID) + summed muscle moment (SO / CEINMS)  
    4. Moment arms    (mean of +MA and -MA muscles acting on the coordinate)  
    5. Muscle forces  (mean of the same +MA / -MA muscle groups)  
    6. Activations    (mean of the same groups; EMG envelope shaded behind)  
    7. Energetics     (mean metabolic rate of the same groups, if available)

Every panel carries a small legend; missing data leaves a "no data" panel.

CLI (wired in __main__.py):  
    python -m bioscout --summary                       # ./settings.py if present  
    python -m bioscout --summary "<proj>/settings.py"  # that project's settings  
    python -m bioscout --summary "<...>/SomeTrial"      # ONE trial only (fast)  
    python -m bioscout --summary -t "<...>/SomeTrial"   # ONE trial only (explicit)  
    python -m bioscout --summary -overall               # overall only  
    python -m bioscout --summary -s 012                 # one subject

## Contents

- [`discover`](#discover) — 
- [`plot_trial`](#plot_trial) — 
- [`plot_overall`](#plot_overall) — 
- [`run_summary`](#run_summary) — Build summaries. ``trial_path`` (or a trial directory passed as ``settings_path``) restricts to a single trial for fast iteration.

### `discover`

```python
discover(project_root, subject=None)
```

| input | type | default |
|---|---|---|
| `project_root` | – | required |
| `subject` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/summary.py#L474)</sub>

### `plot_trial`

```python
plot_trial(info, save_dir=None)
```

| input | type | default |
|---|---|---|
| `info` | – | required |
| `save_dir` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/summary.py#L517)</sub>

### `plot_overall`

```python
plot_overall(targets, project_root, out_dir=None)
```

| input | type | default |
|---|---|---|
| `targets` | – | required |
| `project_root` | – | required |
| `out_dir` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/summary.py#L712)</sub>

### `run_summary`

```python
run_summary(
    settings_path=None,
    subject=None,
    overall_only=False,
    project_root=None,
    trial_path=None
)
```

| input | type | default |
|---|---|---|
| `settings_path` | – | `None` |
| `subject` | – | `None` |
| `overall_only` | – | `False` |
| `project_root` | – | `None` |
| `trial_path` | – | `None` |

Build summaries. ``trial_path`` (or a trial directory passed as  
``settings_path``) restricts to a single trial for fast iteration.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/summary.py#L846)</sub>
