# `bioscout.model.mri2msk.postwarp`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py)

Post-Warp pipeline on a BioScout session.

    <participant>/<session>/             e.g. TD13/session1  
        session.yaml                     subject, session, body_mass, static_trial,  
                                         trials, iterations: {mri_lernagopal: ...}  
        1_c3dfiles/<trial>.c3d           raw captures (BioScout convention)  
        2_experimental/<trial>/          exported TRC / GRF / EMG      (step 0)  
        3_iterations/mri_lernagopal/  
            <subject>_mri_scaled.osim    our scaled model               (step 1)  
            <trial>/external_biomechanics/joint_angles.mot, inverse_dynamics.sto  
                    static_optimisation/*StaticOptimization_force.sto  
                    joint_contact_forces/output_so.sto, contributions_so.sto/.png

Steps 0 and 2-6 are BioScout's own (``Session.export`` and the per-trial  
``run_ik / run_id / run_so / run_jra / run_jra_contributions``), so results are  
identical to a BioScout run. Step 1 (scaling) is MRI2MSK-specific: the warped  
(MRI) segments keep scale 1, only feet/torso/arms are scaled from markers  
(template ``templates/scale_setup_unwarped_segments.xml``). The iteration  
declares the result as ``model_scaled`` without ``model_generic``, so BioScout  
uses it as given and never rescales it.

The iteration name contains "lernagopal" on purpose: BioScout picks the knee  
contact-force columns from the iteration folder name.

## Contents

- class [`PostWarpSession`](#postwarpsession) — 
  - [`PostWarpSession.yaml`](#postwarpsessionyaml) — 
  - [`PostWarpSession.iter_dir`](#postwarpsessioniter_dir) — 
  - [`PostWarpSession.scaled_model`](#postwarpsessionscaled_model) — 
  - [`PostWarpSession.exists`](#postwarpsessionexists) — 
  - [`PostWarpSession.read_yaml`](#postwarpsessionread_yaml) — 
  - [`PostWarpSession.write_yaml`](#postwarpsessionwrite_yaml) — 
  - [`PostWarpSession.c3d_files`](#postwarpsessionc3d_files) — 
  - [`PostWarpSession.static_trial`](#postwarpsessionstatic_trial) — 
  - [`PostWarpSession.trials`](#postwarpsessiontrials) — Dynamic trials (session.yaml order, else the c3d files), static excluded.
  - [`PostWarpSession.static_trc`](#postwarpsessionstatic_trc) — 
  - [`PostWarpSession.create`](#postwarpsessioncreate) — Make the session folder + session.yaml (BioScout scaffold) + MRI iteration.
  - [`PostWarpSession.update_yaml`](#postwarpsessionupdate_yaml) — Ensure project_dir, body_mass and the MRI iteration (model_scaled, no rescaling).
  - [`PostWarpSession.session`](#postwarpsessionsession) — 
  - [`PostWarpSession.iteration`](#postwarpsessioniteration) — 
  - [`PostWarpSession.run_export`](#postwarpsessionrun_export) — 
  - [`PostWarpSession.run_scale`](#postwarpsessionrun_scale) — ScaleTool: measurement scaling for unwarped segments, scale 1 for warped ones.
  - [`PostWarpSession.run_trial`](#postwarpsessionrun_trial) — 
  - [`PostWarpSession.trial_dir`](#postwarpsessiontrial_dir) — 
  - [`PostWarpSession.exported`](#postwarpsessionexported) — 
  - [`PostWarpSession.trial_status`](#postwarpsessiontrial_status) — 
- [`latest_warped_model`](#latest_warped_model) — 
- [`find_sessions`](#find_sessions) — Sub-folders that look like BioScout sessions (session.yaml or 1_c3dfiles).
- [`c3d_dir`](#c3d_dir) — 
- [`trc_time_range`](#trc_time_range) — 
- [`c3d_body_mass`](#c3d_body_mass) — PROCESSING:BODYMASS (Vicon/Nexus) from a C3D file, if present.
- [`spreadsheet_body_mass`](#spreadsheet_body_mass) — ('Weight (kg)', file) for the participant ID from an .xlsx/.csv in the participant folder or up to two parents (e.g. 'Anthroprometrische Daten.xlsx').
- [`detect_body_mass`](#detect_body_mass) — Static C3D PROCESSING:BODYMASS first, then a participant spreadsheet.
- [`bioscout_available`](#bioscout_available) — 
- [`summary_peaks`](#summary_peaks) — Peak total JCF per joint (N and BW) from a contributions DataFrame or csv.

<a id="postwarpsession"></a>

## class `PostWarpSession`

```python
PostWarpSession(
    session_dir,
    participant_folder,
    warped_model=None,
    mass=None,
    marker_placer=True,
    log=print
)
```

| input | type | default |
|---|---|---|
| `session_dir` | – | required |
| `participant_folder` | – | required |
| `warped_model` | – | `None` |
| `mass` | – | `None` |
| `marker_placer` | – | `True` |
| `log` | – | `print` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L156)</sub>

<a id="postwarpsessionyaml"></a>

### `PostWarpSession.yaml`

```python
PostWarpSession.yaml() -> Path
```

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L169)</sub>

<a id="postwarpsessioniter_dir"></a>

### `PostWarpSession.iter_dir`

```python
PostWarpSession.iter_dir() -> Path
```

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L173)</sub>

<a id="postwarpsessionscaled_model"></a>

### `PostWarpSession.scaled_model`

```python
PostWarpSession.scaled_model() -> Path
```

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L177)</sub>

<a id="postwarpsessionexists"></a>

### `PostWarpSession.exists`

```python
PostWarpSession.exists() -> bool
```

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L180)</sub>

<a id="postwarpsessionread_yaml"></a>

### `PostWarpSession.read_yaml`

```python
PostWarpSession.read_yaml() -> dict
```

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L183)</sub>

<a id="postwarpsessionwrite_yaml"></a>

### `PostWarpSession.write_yaml`

```python
PostWarpSession.write_yaml(d: dict)
```

| input | type | default |
|---|---|---|
| `d` | dict | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L189)</sub>

<a id="postwarpsessionc3d_files"></a>

### `PostWarpSession.c3d_files`

```python
PostWarpSession.c3d_files() -> list[Path]
```

**returns** `list[Path]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L193)</sub>

<a id="postwarpsessionstatic_trial"></a>

### `PostWarpSession.static_trial`

```python
PostWarpSession.static_trial() -> str | None
```

**returns** `str \| None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L197)</sub>

<a id="postwarpsessiontrials"></a>

### `PostWarpSession.trials`

```python
PostWarpSession.trials() -> list[str]
```

**returns** `list[str]`

Dynamic trials (session.yaml order, else the c3d files), static excluded.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L203)</sub>

<a id="postwarpsessionstatic_trc"></a>

### `PostWarpSession.static_trc`

```python
PostWarpSession.static_trc() -> Path | None
```

**returns** `Path \| None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L211)</sub>

<a id="postwarpsessioncreate"></a>

### `PostWarpSession.create`

```python
PostWarpSession.create(c3d_sources: list[Path] | None = None) -> Path
```

| input | type | default |
|---|---|---|
| `c3d_sources` | list[Path] \| None | `None` |

**returns** `Path`

Make the session folder + session.yaml (BioScout scaffold) + MRI iteration.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L217)</sub>

<a id="postwarpsessionupdate_yaml"></a>

### `PostWarpSession.update_yaml`

```python
PostWarpSession.update_yaml()
```

Ensure project_dir, body_mass and the MRI iteration (model_scaled, no rescaling).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L234)</sub>

<a id="postwarpsessionsession"></a>

### `PostWarpSession.session`

```python
PostWarpSession.session()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L262)</sub>

<a id="postwarpsessioniteration"></a>

### `PostWarpSession.iteration`

```python
PostWarpSession.iteration()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L275)</sub>

<a id="postwarpsessionrun_export"></a>

### `PostWarpSession.run_export`

```python
PostWarpSession.run_export(replace=False)
```

| input | type | default |
|---|---|---|
| `replace` | – | `False` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L279)</sub>

<a id="postwarpsessionrun_scale"></a>

### `PostWarpSession.run_scale`

```python
PostWarpSession.run_scale() -> Path
```

**returns** `Path`

ScaleTool: measurement scaling for unwarped segments, scale 1 for warped ones.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L314)</sub>

<a id="postwarpsessionrun_trial"></a>

### `PostWarpSession.run_trial`

```python
PostWarpSession.run_trial(step: str, trial: str, replace=True)
```

| input | type | default |
|---|---|---|
| `step` | str | required |
| `trial` | str | required |
| `replace` | – | `True` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L366)</sub>

<a id="postwarpsessiontrial_dir"></a>

### `PostWarpSession.trial_dir`

```python
PostWarpSession.trial_dir(trial: str) -> Path
```

| input | type | default |
|---|---|---|
| `trial` | str | required |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L389)</sub>

<a id="postwarpsessionexported"></a>

### `PostWarpSession.exported`

```python
PostWarpSession.exported(trial: str) -> bool
```

| input | type | default |
|---|---|---|
| `trial` | str | required |

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L392)</sub>

<a id="postwarpsessiontrial_status"></a>

### `PostWarpSession.trial_status`

```python
PostWarpSession.trial_status(trial: str) -> dict[str, bool]
```

| input | type | default |
|---|---|---|
| `trial` | str | required |

**returns** `dict[str, bool]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L395)</sub>

### `latest_warped_model`

```python
latest_warped_model(participant_folder: Path) -> Path | None
```

| input | type | default |
|---|---|---|
| `participant_folder` | Path | required |

**returns** `Path \| None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L45)</sub>

### `find_sessions`

```python
find_sessions(participant_folder: Path) -> list[Path]
```

| input | type | default |
|---|---|---|
| `participant_folder` | Path | required |

**returns** `list[Path]`

Sub-folders that look like BioScout sessions (session.yaml or 1_c3dfiles).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L54)</sub>

### `c3d_dir`

```python
c3d_dir(session_dir: Path) -> Path
```

| input | type | default |
|---|---|---|
| `session_dir` | Path | required |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L63)</sub>

### `trc_time_range`

```python
trc_time_range(trc: Path) -> tuple[float, float]
```

| input | type | default |
|---|---|---|
| `trc` | Path | required |

**returns** `tuple[float, float]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L70)</sub>

### `c3d_body_mass`

```python
c3d_body_mass(c3d_file: Path) -> float | None
```

| input | type | default |
|---|---|---|
| `c3d_file` | Path | required |

**returns** `float \| None`

PROCESSING:BODYMASS (Vicon/Nexus) from a C3D file, if present.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L83)</sub>

### `spreadsheet_body_mass`

```python
spreadsheet_body_mass(participant_folder: Path, participant_id: str | None = None)
```

| input | type | default |
|---|---|---|
| `participant_folder` | Path | required |
| `participant_id` | str \| None | `None` |

('Weight (kg)', file) for the participant ID from an .xlsx/.csv in the  
participant folder or up to two parents (e.g. 'Anthroprometrische Daten.xlsx').

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L104)</sub>

### `detect_body_mass`

```python
detect_body_mass(
    participant_folder: Path,
    session_dir: Path | None = None,
    log=print
) -> float | None
```

| input | type | default |
|---|---|---|
| `participant_folder` | Path | required |
| `session_dir` | Path \| None | `None` |
| `log` | – | `print` |

**returns** `float \| None`

Static C3D PROCESSING:BODYMASS first, then a participant spreadsheet.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L131)</sub>

### `bioscout_available`

```python
bioscout_available() -> bool
```

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L406)</sub>

### `summary_peaks`

```python
summary_peaks(df, mass=None) -> str
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `mass` | – | `None` |

**returns** `str`

Peak total JCF per joint (N and BW) from a contributions DataFrame or csv.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/mri2msk/postwarp.py#L411)</sub>
