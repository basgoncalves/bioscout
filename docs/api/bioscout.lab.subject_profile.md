# `bioscout.lab.subject_profile`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py)

subject_profile.py — per-subject profiles for video analysis.

A *subject profile* stores everything we know about an athlete that helps the  
pipeline: anthropometry (height, mass, sex, age), limb-segment proportions used  
to sanity-check pose detection, a saved pixel-per-metre calibration, paths to  
the subject's OpenSim / CEINMS model files, and per-subject detection settings.

Storage layout (scales to hundreds of subjects, dozens of tasks each)::

    <root>/                              ~/.powerlifting_app/subjects  by default  
        <subject_id>/  
            profile.json                 the data below  
            models/                       subject-specific .osim / CEINMS files  
            tasks/<task_name>/...         (reserved for per-task outputs)

One folder per subject keeps a subject's models and results together and avoids a  
single giant registry file that would be slow/fragile at that scale. The  
dropdown index is built by globbing ``<root>/*/profile.json`` (cheap, lazy).

The module is pure-stdlib so it can be imported and unit-tested without the GUI.

## Contents

- class [`SubjectProfile`](#subjectprofile) — All persisted data for one subject.
  - [`SubjectProfile.effective_segment_fractions`](#subjectprofileeffective_segment_fractions) — Measured proportions where available, else population defaults.
  - [`SubjectProfile.expected_segment_px`](#subjectprofileexpected_segment_px) — Expected length of a body segment in pixels, if height + scale known.
  - [`SubjectProfile.to_dict`](#subjectprofileto_dict) — 
  - [`SubjectProfile.from_dict`](#subjectprofilefrom_dict) — 
- class [`SubjectStore`](#subjectstore) — Directory-backed collection of subject profiles.
  - [`SubjectStore.subject_dir`](#subjectstoresubject_dir) — 
  - [`SubjectStore.profile_path`](#subjectstoreprofile_path) — 
  - [`SubjectStore.models_dir`](#subjectstoremodels_dir) — 
  - [`SubjectStore.list_ids`](#subjectstorelist_ids) — 
  - [`SubjectStore.list_names`](#subjectstorelist_names) — {id: display name} for populating a dropdown — cheap header read.
  - [`SubjectStore.index`](#subjectstoreindex) — Return {display_name: id} for the dropdown (names are unique-ified).
  - [`SubjectStore.load`](#subjectstoreload) — 
  - [`SubjectStore.save`](#subjectstoresave) — 
  - [`SubjectStore.create`](#subjectstorecreate) — 
  - [`SubjectStore.delete`](#subjectstoredelete) — 
- class [`ProjectSubjectStore`](#projectsubjectstore) — `SubjectStore`-compatible facade over a project's subjects.json.
  - [`ProjectSubjectStore.index`](#projectsubjectstoreindex) — Return {display_name: id} for the dropdown (names unique-ified).
  - [`ProjectSubjectStore.load`](#projectsubjectstoreload) — 
  - [`ProjectSubjectStore.save`](#projectsubjectstoresave) — 
  - [`ProjectSubjectStore.create`](#projectsubjectstorecreate) — 
  - [`ProjectSubjectStore.delete`](#projectsubjectstoredelete) — 
  - [`ProjectSubjectStore.models_dir`](#projectsubjectstoremodels_dir) — 

<a id="subjectprofile"></a>

## class `SubjectProfile`

All persisted data for one subject.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L62)</sub>

<a id="subjectprofileeffective_segment_fractions"></a>

### `SubjectProfile.effective_segment_fractions`

```python
SubjectProfile.effective_segment_fractions() -> Dict[str, float]
```

**returns** `Dict[str, float]`

Measured proportions where available, else population defaults.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L107)</sub>

<a id="subjectprofileexpected_segment_px"></a>

### `SubjectProfile.expected_segment_px`

```python
SubjectProfile.expected_segment_px(segment: str) -> Optional[float]
```

| input | type | default |
|---|---|---|
| `segment` | str | required |

**returns** `Optional[float]`

Expected length of a body segment in pixels, if height + scale known.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L113)</sub>

<a id="subjectprofileto_dict"></a>

### `SubjectProfile.to_dict`

```python
SubjectProfile.to_dict() -> dict
```

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L123)</sub>

<a id="subjectprofilefrom_dict"></a>

### `SubjectProfile.from_dict`

```python
SubjectProfile.from_dict(d: dict) -> 'SubjectProfile'
```

| input | type | default |
|---|---|---|
| `d` | dict | required |

**returns** `'SubjectProfile'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L127)</sub>

<a id="subjectstore"></a>

## class `SubjectStore`

```python
SubjectStore(root: Optional[Path] = None)
```

| input | type | default |
|---|---|---|
| `root` | Optional[Path] | `None` |

Directory-backed collection of subject profiles.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L138)</sub>

<a id="subjectstoresubject_dir"></a>

### `SubjectStore.subject_dir`

```python
SubjectStore.subject_dir(subject_id: str) -> Path
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L148)</sub>

<a id="subjectstoreprofile_path"></a>

### `SubjectStore.profile_path`

```python
SubjectStore.profile_path(subject_id: str) -> Path
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L151)</sub>

<a id="subjectstoremodels_dir"></a>

### `SubjectStore.models_dir`

```python
SubjectStore.models_dir(subject_id: str) -> Path
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L154)</sub>

<a id="subjectstorelist_ids"></a>

### `SubjectStore.list_ids`

```python
SubjectStore.list_ids() -> List[str]
```

**returns** `List[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L160)</sub>

<a id="subjectstorelist_names"></a>

### `SubjectStore.list_names`

```python
SubjectStore.list_names() -> List[str]
```

**returns** `List[str]`

{id: display name} for populating a dropdown — cheap header read.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L167)</sub>

<a id="subjectstoreindex"></a>

### `SubjectStore.index`

```python
SubjectStore.index() -> Dict[str, str]
```

**returns** `Dict[str, str]`

Return {display_name: id} for the dropdown (names are unique-ified).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L178)</sub>

<a id="subjectstoreload"></a>

### `SubjectStore.load`

```python
SubjectStore.load(subject_id: str) -> Optional[SubjectProfile]
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `Optional[SubjectProfile]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L196)</sub>

<a id="subjectstoresave"></a>

### `SubjectStore.save`

```python
SubjectStore.save(profile: SubjectProfile) -> Path
```

| input | type | default |
|---|---|---|
| `profile` | SubjectProfile | required |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L206)</sub>

<a id="subjectstorecreate"></a>

### `SubjectStore.create`

```python
SubjectStore.create(name: str, **kwargs) -> SubjectProfile
```

| input | type | default |
|---|---|---|
| `name` | str | required |
| `**kwargs` | – | – |

**returns** `SubjectProfile`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L214)</sub>

<a id="subjectstoredelete"></a>

### `SubjectStore.delete`

```python
SubjectStore.delete(subject_id: str) -> bool
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L225)</sub>

<a id="projectsubjectstore"></a>

## class `ProjectSubjectStore`

```python
ProjectSubjectStore(project_root: Optional[Path] = None)
```

| input | type | default |
|---|---|---|
| `project_root` | Optional[Path] | `None` |

`SubjectStore`-compatible facade over a project's subjects.json.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L260)</sub>

<a id="projectsubjectstoreindex"></a>

### `ProjectSubjectStore.index`

```python
ProjectSubjectStore.index() -> Dict[str, str]
```

**returns** `Dict[str, str]`

Return {display_name: id} for the dropdown (names unique-ified).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L306)</sub>

<a id="projectsubjectstoreload"></a>

### `ProjectSubjectStore.load`

```python
ProjectSubjectStore.load(subject_id: str) -> Optional[SubjectProfile]
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `Optional[SubjectProfile]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L325)</sub>

<a id="projectsubjectstoresave"></a>

### `ProjectSubjectStore.save`

```python
ProjectSubjectStore.save(profile: SubjectProfile) -> Path
```

| input | type | default |
|---|---|---|
| `profile` | SubjectProfile | required |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L332)</sub>

<a id="projectsubjectstorecreate"></a>

### `ProjectSubjectStore.create`

```python
ProjectSubjectStore.create(name: str, **kwargs) -> SubjectProfile
```

| input | type | default |
|---|---|---|
| `name` | str | required |
| `**kwargs` | – | – |

**returns** `SubjectProfile`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L345)</sub>

<a id="projectsubjectstoredelete"></a>

### `ProjectSubjectStore.delete`

```python
ProjectSubjectStore.delete(subject_id: str) -> bool
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L355)</sub>

<a id="projectsubjectstoremodels_dir"></a>

### `ProjectSubjectStore.models_dir`

```python
ProjectSubjectStore.models_dir(subject_id: str) -> Path
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/subject_profile.py#L362)</sub>
