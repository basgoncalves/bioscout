# `bioscout.core.status`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/status.py)

What is on disk, per session -- the read-only page you check a run against.

    from bioscout.core import status  
    status.table(project_dir)                     # DataFrame, one row per session  
    status.table(project_dir, verbose=True)       # + one row per trial x stage

    bioscout project status [PATH] [--subjects 009,010] [--sessions pre,post]

Runs nothing and writes nothing. Every column is a file test:

    mass      session.yaml body_mass            windowed  trials with a time_range  
    trials    trials to solve                   jc_trc    static trial has joint centres  
    emg_only  captures with no markers          model     the iteration's scaled model  
    staged    trials with a c3d in 1_c3dfiles/   solved    trials with a JRA on disk  
    exported  trials with 2_experimental/<trial>/

`solved` is the joint reaction after static optimisation  
(``joint_contact_forces/output_so.sto``) -- the contact  
force a project reports -- not merely "SO wrote something".

The roster comes from ``project.yaml``'s ``project:`` section when it has one  
(``subjects:``, ``skip_subjects:``, ``session_states:``); otherwise from the  
folders under ``simulations/``.

## Contents

- [`subjects`](#subjects) — Subject folders under ``simulations/``, honouring project.yaml's ``subjects:`` / ``skip_subjects:``.
- [`sessions_for`](#sessions_for) — Session folders that carry a session.yaml, in ``session_states`` order.
- [`trial_stages`](#trial_stages) — ``{stage: bool}`` -- which stage outputs exist for one trial.
- [`table`](#table) — One row per session (plus one per trial when ``verbose``). Returns a pandas DataFrame, or a list of dicts when pandas is not installed.

### `subjects`

```python
subjects(project_dir, only=None)
```

| input | type | default |
|---|---|---|
| `project_dir` | – | required |
| `only` | – | `None` |

Subject folders under ``simulations/``, honouring project.yaml's  
``subjects:`` / ``skip_subjects:``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/status.py#L63)</sub>

### `sessions_for`

```python
sessions_for(project_dir, subject, only=None)
```

| input | type | default |
|---|---|---|
| `project_dir` | – | required |
| `subject` | – | required |
| `only` | – | `None` |

Session folders that carry a session.yaml, in ``session_states`` order.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/status.py#L81)</sub>

### `trial_stages`

```python
trial_stages(session_dir, trial, iteration)
```

| input | type | default |
|---|---|---|
| `session_dir` | – | required |
| `trial` | – | required |
| `iteration` | – | required |

``{stage: bool}`` -- which stage outputs exist for one trial.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/status.py#L98)</sub>

### `table`

```python
table(
    project_dir='.',
    subjects_=None,
    sessions=None,
    iteration=None,
    verbose=False,
    log=print
)
```

| input | type | default |
|---|---|---|
| `project_dir` | – | `'.'` |
| `subjects_` | – | `None` |
| `sessions` | – | `None` |
| `iteration` | – | `None` |
| `verbose` | – | `False` |
| `log` | – | `print` |

One row per session (plus one per trial when ``verbose``). Returns a  
pandas DataFrame, or a list of dicts when pandas is not installed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/status.py#L167)</sub>
