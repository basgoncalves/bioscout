# `bioscout.lab.load_tracking.tracking_store`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py)

Per-subject tracking store.

Bridges the load_tracking engine and the project's ``subjects.json`` (managed by  
``utils.subject_registry.SubjectRegistry``). Responsibilities:

    * Build an :class:`AthleteProfile` from a subject's registry record.  
    * Import sessions (files / Zepp / Strava) for a subject, compute load metrics,  
      store lightweight **summaries** in subjects.json and cache the raw per-sample  
      traces on disk under ``<project>/Models/<subject_id>/tracking/<id>.json``.  
    * Reload cached sessions as :class:`SessionData` for the dashboard.  
    * Export a subject's sessions to CSV.

subjects.json stays small (summaries only); the bulky HR/GPS arrays live in the  
per-subject cache files.

## Contents

- class [`TrackingStore`](#trackingstore) — 
  - [`TrackingStore.tracking_dir`](#trackingstoretracking_dir) — 
  - [`TrackingStore.athlete_for`](#trackingstoreathlete_for) — 
  - [`TrackingStore.save_raw`](#trackingstoresave_raw) — 
  - [`TrackingStore.load_raw`](#trackingstoreload_raw) — 
  - [`TrackingStore.load_all_sessions`](#trackingstoreload_all_sessions) — Reconstruct all cached SessionData for a subject (sorted by time).
  - [`TrackingStore.import_sessions`](#trackingstoreimport_sessions) — Cache raw traces + merge session summaries into subjects.json.
  - [`TrackingStore.import_files`](#trackingstoreimport_files) — 
  - [`TrackingStore.import_zepp`](#trackingstoreimport_zepp) — 
  - [`TrackingStore.import_strava`](#trackingstoreimport_strava) — 
  - [`TrackingStore.export_csv`](#trackingstoreexport_csv) — 
- [`serialize_session`](#serialize_session) — 
- [`deserialize_session`](#deserialize_session) — 
- [`session_id`](#session_id) — Stable id for caching/dedup: source basename or activity+epoch.

<a id="trackingstore"></a>

## class `TrackingStore`

```python
TrackingStore(registry, project_root)
```

| input | type | default |
|---|---|---|
| `registry` | – | required |
| `project_root` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L74)</sub>

<a id="trackingstoretracking_dir"></a>

### `TrackingStore.tracking_dir`

```python
TrackingStore.tracking_dir(subject_id: str) -> Path
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L80)</sub>

<a id="trackingstoreathlete_for"></a>

### `TrackingStore.athlete_for`

```python
TrackingStore.athlete_for(subject_id: str) -> AthleteProfile
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `AthleteProfile`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L86)</sub>

<a id="trackingstoresave_raw"></a>

### `TrackingStore.save_raw`

```python
TrackingStore.save_raw(subject_id: str, s: SessionData) -> str
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `s` | SessionData | required |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L100)</sub>

<a id="trackingstoreload_raw"></a>

### `TrackingStore.load_raw`

```python
TrackingStore.load_raw(subject_id: str, sid: str) -> Optional[SessionData]
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `sid` | str | required |

**returns** `Optional[SessionData]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L107)</sub>

<a id="trackingstoreload_all_sessions"></a>

### `TrackingStore.load_all_sessions`

```python
TrackingStore.load_all_sessions(subject_id: str) -> list[SessionData]
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |

**returns** `list[SessionData]`

Reconstruct all cached SessionData for a subject (sorted by time).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L114)</sub>

<a id="trackingstoreimport_sessions"></a>

### `TrackingStore.import_sessions`

```python
TrackingStore.import_sessions(subject_id: str, sessions: list) -> int
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `sessions` | list | required |

**returns** `int`

Cache raw traces + merge session summaries into subjects.json.

De-duplicates by session id (re-importing the same workout updates it).  
Returns the number of new/updated sessions.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L146)</sub>

<a id="trackingstoreimport_files"></a>

### `TrackingStore.import_files`

```python
TrackingStore.import_files(subject_id: str, paths) -> int
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `paths` | – | required |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L163)</sub>

<a id="trackingstoreimport_zepp"></a>

### `TrackingStore.import_zepp`

```python
TrackingStore.import_zepp(
    subject_id: str,
    token: str,
    region: str = 'de2',
    limit: Optional[int] = None
) -> int
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `token` | str | required |
| `region` | str | `'de2'` |
| `limit` | Optional[int] | `None` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L167)</sub>

<a id="trackingstoreimport_strava"></a>

### `TrackingStore.import_strava`

```python
TrackingStore.import_strava(
    subject_id: str,
    client_id,
    client_secret,
    refresh_token,
    limit: Optional[int] = None
) -> int
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `client_id` | – | required |
| `client_secret` | – | required |
| `refresh_token` | – | required |
| `limit` | Optional[int] | `None` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L172)</sub>

<a id="trackingstoreexport_csv"></a>

### `TrackingStore.export_csv`

```python
TrackingStore.export_csv(subject_id: str, path) -> str
```

| input | type | default |
|---|---|---|
| `subject_id` | str | required |
| `path` | – | required |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L179)</sub>

### `serialize_session`

```python
serialize_session(s: SessionData) -> dict
```

| input | type | default |
|---|---|---|
| `s` | SessionData | required |

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L39)</sub>

### `deserialize_session`

```python
deserialize_session(d: dict) -> SessionData
```

| input | type | default |
|---|---|---|
| `d` | dict | required |

**returns** `SessionData`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L49)</sub>

### `session_id`

```python
session_id(s: SessionData) -> str
```

| input | type | default |
|---|---|---|
| `s` | SessionData | required |

**returns** `str`

Stable id for caching/dedup: source basename or activity+epoch.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracking_store.py#L63)</sub>
