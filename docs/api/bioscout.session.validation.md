# `bioscout.session.validation`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py)

Trial-folder checks used by the GUI's calibration-session widget.

:class:`TrialValidator` (which inputs a trial folder has) and  
:class:`SessionManager` (trial discovery + readiness summary).

## Contents

- class [`TrialValidator`](#trialvalidator) — Validates trial folders for required input files.
  - [`TrialValidator.has_file`](#trialvalidatorhas_file) — Check if a file exists in trial directory or session root (supports glob patterns).
  - [`TrialValidator.validate_trial`](#trialvalidatorvalidate_trial) — Validate if trial has all required files.
  - [`TrialValidator.is_valid_trial`](#trialvalidatoris_valid_trial) — Check if folder is a valid trial (has C3D or TRC file).
  - [`TrialValidator.get_trial_status`](#trialvalidatorget_trial_status) — Get complete validation status for a trial.
- class [`SessionManager`](#sessionmanager) — Manages session-level operations and trial discovery.
  - [`SessionManager.discover_trials`](#sessionmanagerdiscover_trials) — Discover all trial folders in session (containing C3D or TRC files).
  - [`SessionManager.get_trial_list`](#sessionmanagerget_trial_list) — Get list of trials with their status information.
  - [`SessionManager.get_trial_by_name`](#sessionmanagerget_trial_by_name) — Get trial path by name.
  - [`SessionManager.validate_for_analysis`](#sessionmanagervalidate_for_analysis) — Validate if trial is ready for analysis.
  - [`SessionManager.validate_for_ceinms`](#sessionmanagervalidate_for_ceinms) — Validate if trial is ready for CEINMS calibration.
  - [`SessionManager.get_session_summary`](#sessionmanagerget_session_summary) — Get summary of session with trial statuses.

<a id="trialvalidator"></a>

## class `TrialValidator`

Validates trial folders for required input files.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L37)</sub>

<a id="trialvalidatorhas_file"></a>

### `TrialValidator.has_file`

```python
TrialValidator.has_file(trial_dir: Path, filename: str, session_dir: Path = None) -> bool
```

| input | type | default |
|---|---|---|
| `trial_dir` | Path | required |
| `filename` | str | required |
| `session_dir` | Path | `None` |

**returns** `bool`

Check if a file exists in trial directory or session root (supports glob patterns).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L60)</sub>

<a id="trialvalidatorvalidate_trial"></a>

### `TrialValidator.validate_trial`

```python
TrialValidator.validate_trial(
    trial_dir: Path,
    requirements: Dict[str, str],
    session_dir: Path = None
) -> Dict[str, bool]
```

| input | type | default |
|---|---|---|
| `trial_dir` | Path | required |
| `requirements` | Dict[str, str] | required |
| `session_dir` | Path | `None` |

**returns** `Dict[str, bool]`

Validate if trial has all required files.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L82)</sub>

<a id="trialvalidatoris_valid_trial"></a>

### `TrialValidator.is_valid_trial`

```python
TrialValidator.is_valid_trial(trial_dir: Path, session_dir: Path = None) -> bool
```

| input | type | default |
|---|---|---|
| `trial_dir` | Path | required |
| `session_dir` | Path | `None` |

**returns** `bool`

Check if folder is a valid trial (has C3D or TRC file).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L90)</sub>

<a id="trialvalidatorget_trial_status"></a>

### `TrialValidator.get_trial_status`

```python
TrialValidator.get_trial_status(
    trial_dir: Path,
    session_dir: Path = None
) -> Dict[str, any]
```

| input | type | default |
|---|---|---|
| `trial_dir` | Path | required |
| `session_dir` | Path | `None` |

**returns** `Dict[str, any]`

Get complete validation status for a trial.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L107)</sub>

<a id="sessionmanager"></a>

## class `SessionManager`

```python
SessionManager(session_path: Optional[str] = None)
```

| input | type | default |
|---|---|---|
| `session_path` | Optional[str] | `None` |

Manages session-level operations and trial discovery.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L132)</sub>

<a id="sessionmanagerdiscover_trials"></a>

### `SessionManager.discover_trials`

```python
SessionManager.discover_trials() -> List[Path]
```

**returns** `List[Path]`

Discover all trial folders in session (containing C3D or TRC files).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L143)</sub>

<a id="sessionmanagerget_trial_list"></a>

### `SessionManager.get_trial_list`

```python
SessionManager.get_trial_list() -> List[Dict]
```

**returns** `List[Dict]`

Get list of trials with their status information.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L156)</sub>

<a id="sessionmanagerget_trial_by_name"></a>

### `SessionManager.get_trial_by_name`

```python
SessionManager.get_trial_by_name(trial_name: str) -> Optional[Path]
```

| input | type | default |
|---|---|---|
| `trial_name` | str | required |

**returns** `Optional[Path]`

Get trial path by name.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L168)</sub>

<a id="sessionmanagervalidate_for_analysis"></a>

### `SessionManager.validate_for_analysis`

```python
SessionManager.validate_for_analysis(trial_name: str) -> Tuple[bool, str]
```

| input | type | default |
|---|---|---|
| `trial_name` | str | required |

**returns** `Tuple[bool, str]`

Validate if trial is ready for analysis.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L178)</sub>

<a id="sessionmanagervalidate_for_ceinms"></a>

### `SessionManager.validate_for_ceinms`

```python
SessionManager.validate_for_ceinms(trial_name: str) -> Tuple[bool, str]
```

| input | type | default |
|---|---|---|
| `trial_name` | str | required |

**returns** `Tuple[bool, str]`

Validate if trial is ready for CEINMS calibration.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L191)</sub>

<a id="sessionmanagerget_session_summary"></a>

### `SessionManager.get_session_summary`

```python
SessionManager.get_session_summary() -> Dict
```

**returns** `Dict`

Get summary of session with trial statuses.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/validation.py#L204)</sub>
