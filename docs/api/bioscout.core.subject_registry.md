# `bioscout.core.subject_registry`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py)

  
**subject_registry.py**

Manages the per-project subjects.json file.

Each project has one subjects.json at its root (next to settings.py).  
The registry enforces unique subject IDs and stores all anthropometric /  
demographic / clinical data so settings.py stays thin.

  
**Schema for each subject entry**

{  
    "name": "",  
    "group": "fais",          # experimental group label  
    "sex": "M",               # M / F / Other  
    "age": null,              # years (int)  
    "height_m": null,         # metres (float)  
    "mass_kg": null,          # kilograms (float)  
    "dominant_leg": "right",  # right / left / bilateral  
    "affected_side": "",      # right / left / bilateral / "" (none)  
    "injury_type": "",        # free text, e.g. "FAIS cam"  
    "surgery_date": null,     # ISO-8601 string or null  
    "static_trial": "static1",  
    "notes": "",  
    "extra": {},              # any future / project-specific fields  
    "added": "YYYY-MM-DD"  
}

## Contents

- class [`SubjectRegistry`](#subjectregistry) — Load, query, and persist subjects.json for a project.
  - [`SubjectRegistry.save`](#subjectregistrysave) — Write the registry to disk in the current versioned format.
  - [`SubjectRegistry.get`](#subjectregistryget) — Return a copy of the subject record, raising KeyError if not found.
  - [`SubjectRegistry.all_ids`](#subjectregistryall_ids) — 
  - [`SubjectRegistry.all_subjects`](#subjectregistryall_subjects) — 
  - [`SubjectRegistry.add`](#subjectregistryadd) — Add a new subject.  Raises ValueError if the ID already exists.
  - [`SubjectRegistry.update`](#subjectregistryupdate) — Update fields on an existing subject.
  - [`SubjectRegistry.remove`](#subjectregistryremove) — Delete a subject from the registry.
  - [`SubjectRegistry.get_credentials`](#subjectregistryget_credentials) — Return this subject's cloud credentials ({zepp:{...}, strava:{...}}).
  - [`SubjectRegistry.set_credentials`](#subjectregistryset_credentials) — Replace this subject's cloud credentials and persist.
  - [`SubjectRegistry.get_sessions`](#subjectregistryget_sessions) — Return this subject's cached session summaries (list of dicts).
  - [`SubjectRegistry.set_sessions`](#subjectregistryset_sessions) — Replace this subject's cached session summaries and persist.
  - [`SubjectRegistry.summary`](#subjectregistrysummary) — Return a human-readable summary (one subject or all).
- [`prompt_add_subject`](#prompt_add_subject) — Interactively collect subject data and add to registry.

<a id="subjectregistry"></a>

## class `SubjectRegistry`

```python
SubjectRegistry(project_root: Optional[str | Path] = None)
```

| input | type | default |
|---|---|---|
| `project_root` | Optional[str \| Path] | `None` |

Load, query, and persist subjects.json for a project.

  
**Parameters**

project_root:  
    Path to the project folder (the one that contains settings.py).  
    If None, defaults to the current working directory.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L88)</sub>

<a id="subjectregistrysave"></a>

### `SubjectRegistry.save`

```python
SubjectRegistry.save() -> None
```

**returns** `None`

Write the registry to disk in the current versioned format.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L157)</sub>

<a id="subjectregistryget"></a>

### `SubjectRegistry.get`

```python
SubjectRegistry.get(subject_id: str) -> dict
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `dict`

Return a copy of the subject record, raising KeyError if not found.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L178)</sub>

<a id="subjectregistryall_ids"></a>

### `SubjectRegistry.all_ids`

```python
SubjectRegistry.all_ids() -> list[str]
```

**returns** `list[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L187)</sub>

<a id="subjectregistryall_subjects"></a>

### `SubjectRegistry.all_subjects`

```python
SubjectRegistry.all_subjects() -> dict[str, dict]
```

**returns** `dict[str, dict]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L190)</sub>

<a id="subjectregistryadd"></a>

### `SubjectRegistry.add`

```python
SubjectRegistry.add(subject_id: str, fields: dict) -> dict
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `fields` | dict | required |

**returns** `dict`

Add a new subject.  Raises ValueError if the ID already exists.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L197)</sub>

<a id="subjectregistryupdate"></a>

### `SubjectRegistry.update`

```python
SubjectRegistry.update(subject_id: str, fields: dict) -> dict
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `fields` | dict | required |

**returns** `dict`

Update fields on an existing subject.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L210)</sub>

<a id="subjectregistryremove"></a>

### `SubjectRegistry.remove`

```python
SubjectRegistry.remove(subject_id: str) -> None
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `None`

Delete a subject from the registry.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L218)</sub>

<a id="subjectregistryget_credentials"></a>

### `SubjectRegistry.get_credentials`

```python
SubjectRegistry.get_credentials(subject_id: str) -> dict
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `dict`

Return this subject's cloud credentials ({zepp:{...}, strava:{...}}).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L236)</sub>

<a id="subjectregistryset_credentials"></a>

### `SubjectRegistry.set_credentials`

```python
SubjectRegistry.set_credentials(subject_id: str, credentials: dict) -> None
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `credentials` | dict | required |

**returns** `None`

Replace this subject's cloud credentials and persist.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L240)</sub>

<a id="subjectregistryget_sessions"></a>

### `SubjectRegistry.get_sessions`

```python
SubjectRegistry.get_sessions(subject_id: str) -> list
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `list`

Return this subject's cached session summaries (list of dicts).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L245)</sub>

<a id="subjectregistryset_sessions"></a>

### `SubjectRegistry.set_sessions`

```python
SubjectRegistry.set_sessions(subject_id: str, sessions: list) -> None
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `sessions` | list | required |

**returns** `None`

Replace this subject's cached session summaries and persist.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L249)</sub>

<a id="subjectregistrysummary"></a>

### `SubjectRegistry.summary`

```python
SubjectRegistry.summary(subject_id: Optional[str] = None) -> str
```

| input | type | default |
|---|---|---|
| `subject_id` | Optional[str] | `None` |

**returns** `str`

Return a human-readable summary (one subject or all).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L258)</sub>

### `prompt_add_subject`

```python
prompt_add_subject(registry: SubjectRegistry) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `registry` | SubjectRegistry | required |

**returns** `Optional[str]`

Interactively collect subject data and add to registry.

Returns the new subject ID on success, None if the user aborted.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/subject_registry.py#L297)</sub>
