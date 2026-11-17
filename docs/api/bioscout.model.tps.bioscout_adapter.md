# `bioscout.model.tps.bioscout_adapter`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/bioscout_adapter.py)

BioScout integration — the only BioScout-aware file in this package.

Everything else here is standalone, so this module is import-safe even when  
BioScout is absent: it only touches BioScout at call time.

The main entry point is :func:`personalise_iteration`, which works against the  
session-centric layout BioScout uses now::

    simulations/<subject>/<session>/session.yaml     # iterations live here  
    generic models/<family>/<generic>.osim           # shared model library

Given a session and an iteration name it resolves that iteration's generic  
model, warps it onto the subject's MRI landmarks, and writes  
``<generic stem>_tps_<subject>.osim`` next to the generic — the naming the  
``*_mri`` iterations in ``session.yaml`` expect.

Typical use::

    from bioscout.model.tps import personalise_iteration

    personalise_iteration(  
        "simulations/Athlete_03/25_03_31", "rajagopal",  
        mri_landmarks="models/Athlete_03_MRI_Katya/25_03_31/landmarks.mrk.json",  
    )

## Contents

- [`default_template`](#default_template) — Path to the bundled bone-landmark template.
- [`personalise_iteration`](#personalise_iteration) — TPS-personalise one iteration's model from a BioScout session.
- [`inspect_model`](#inspect_model) — Run the moment-arm sweep on a model and report what it found.
- [`run_for_player`](#run_for_player) — Older players.json-based entry point, kept for existing callers.
- [`run_step_for_trial`](#run_step_for_trial) — Adapter matching BioScout's ``_run_<step>(self, config)`` pattern.

### `default_template`

```python
default_template() -> Path
```

**returns** `Path`

Path to the bundled bone-landmark template.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/bioscout_adapter.py#L50)</sub>

### `personalise_iteration`

```python
personalise_iteration(
    session_dir: str | Path,
    iteration: str,
    mri_landmarks: str | Path,
    source_model: str | Path | None = None,
    bone_marker_template: str | Path | None = None,
    template_source_model: str | Path | None = None,
    output_dir: str | Path | None = None,
    output_name: str | None = None,
    geometry_dir: str | Path | None = None,
    check_template_frames: bool = True,
    inspect: bool = True,
    **overrides
) -> PersonalisationResult
```

| input | type | default |
|---|---|---|
| `session_dir` | str \| Path | required |
| `iteration` | str | required |
| `mri_landmarks` | str \| Path | required |
| `source_model` | str \| Path \| None | `None` |
| `bone_marker_template` | str \| Path \| None | `None` |
| `template_source_model` | str \| Path \| None | `None` |
| `output_dir` | str \| Path \| None | `None` |
| `output_name` | str \| None | `None` |
| `geometry_dir` | str \| Path \| None | `None` |
| `check_template_frames` | bool | `True` |
| `inspect` | bool | `True` |
| `**overrides` | – | – |

**returns** `PersonalisationResult`

TPS-personalise one iteration's model from a BioScout session.

  
**Parameters**

session_dir, iteration  
    Locate ``session.yaml`` and the iteration whose ``generic`` model is  
    being personalised.  
mri_landmarks  
    3D Slicer ``.mrk.json`` of the subject's segmented bone landmarks.  
source_model  
    The ``.osim`` actually warped. Defaults to the iteration's generic  
    model. Pass the subject-scaled model instead if you want the warp  
    applied on top of dimensional scaling.  
bone_marker_template, template_source_model  
    Default to the bundled template and the model its frames came from, so  
    the frame-compatibility check runs by default. Passing  
    ``check_template_frames=False`` downgrades a mismatch to a warning.  
output_dir, output_name  
    Default to writing ``<generic stem>_tps_<subject>.osim`` beside the  
    generic model, which is what a ``*_mri`` iteration in ``session.yaml``  
    points at.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/bioscout_adapter.py#L60)</sub>

### `inspect_model`

```python
inspect_model(
    model_path,
    coords=None,
    muscle_filter=None,
    n=None,
    validate=True,
    make_plots=True
)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `coords` | – | `None` |
| `muscle_filter` | – | `None` |
| `n` | – | `None` |
| `validate` | – | `True` |
| `make_plots` | – | `True` |

Run the moment-arm sweep on a model and report what it found.

A TPS warp moves every muscle path point and every wrap-surface  
translation, so it is exactly the operation that can introduce a  
discontinuous moment arm in a model whose paths were clean beforehand.  
Checking is therefore part of producing the model, not a separate chore.

Delegates to ``muscle_inspect.run_moment_arm_inspection``, which besides  
sweeping and plotting also writes a wrap-corrected ``<model>_modWO.osim``  
**next to** the model. That corrected file is an extra artefact to compare  
against — nothing is repointed at it and the model given here is untouched.

Needs ``opensim``. Returns a dict describing what was produced, with  
``ok=False`` and a ``reason`` when it could not run: a failed inspection  
must never invalidate a good warp, so the caller carries on regardless.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/bioscout_adapter.py#L215)</sub>

### `run_for_player`

```python
run_for_player(
    project_root: str | Path,
    player_id: str,
    trial: Optional[str] = None,
    **overrides
) -> PersonalisationResult
```

| input | type | default |
|---|---|---|
| `project_root` | str \| Path | required |
| `player_id` | str | required |
| `trial` | Optional[str] | `None` |
| `**overrides` | – | – |

**returns** `PersonalisationResult`

Older players.json-based entry point, kept for existing callers.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/bioscout_adapter.py#L279)</sub>

### `run_step_for_trial`

```python
run_step_for_trial(analysis_obj) -> PersonalisationResult
```

| input | type | default |
|---|---|---|
| `analysis_obj` | – | required |

**returns** `PersonalisationResult`

Adapter matching BioScout's ``_run_<step>(self, config)`` pattern.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/bioscout_adapter.py#L292)</sub>
