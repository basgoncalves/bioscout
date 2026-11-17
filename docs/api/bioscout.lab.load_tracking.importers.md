# `bioscout.lab.load_tracking.importers`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/importers.py)

Session importers for the load-tracking module.

Parses fitness-tracker exports into a unified :class:`SessionData` object.

  
**Supported formats**

    * ``.fit``  — Garmin/ANT FIT (Amazfit/Zepp export, Garmin, Wahoo …). Needs the  
                  optional ``fitparse`` package; install with ``pip install fitparse``.  
    * ``.tcx``  — Training Center XML (Zepp export, Garmin Connect, Strava …).  
    * ``.gpx``  — GPS Exchange (Zepp export, most apps). HR/cadence via the  
                  Garmin TrackPointExtension namespace when present.  
    * ``.csv``  — Two flavours auto-detected:  
                    1. Per-sample CSV with a timestamp + heart-rate column.  
                    2. A "manifest" CSV: one row per session (date, sport,  
                       duration_min, avg_hr, rpe, …) — useful for gym sessions and  
                       for Zepp's GDPR data export.

Amazfit GTR 3 Pro: in the Zepp app open a workout → ⋯ menu → export as  
GPX / TCX / FIT. Non-GPS sessions (e.g. strength) can be entered via a manifest CSV.

## Contents

- class [`AthleteProfile`](#athleteprofile) — Per-athlete parameters needed for HR-based load metrics.
  - [`AthleteProfile.resolved_hr_max`](#athleteprofileresolved_hr_max) — 
  - [`AthleteProfile.resolved_hr_rest`](#athleteprofileresolved_hr_rest) — 
- class [`SessionData`](#sessiondata) — One training session, normalised across source formats.
  - [`SessionData.date`](#sessiondatadate) — 
  - [`SessionData.duration_min`](#sessiondataduration_min) — 
  - [`SessionData.finalize`](#sessiondatafinalize) — Fill missing session scalars from the time series.
- [`normalize_activity`](#normalize_activity) — Map an arbitrary sport label to a canonical activity type.
- [`load_session_file`](#load_session_file) — Parse one file into a list of :class:`SessionData` (usually length 1).
- [`load_sessions`](#load_sessions) — Load sessions from a folder, a glob, or a list of files/folders.

<a id="athleteprofile"></a>

## class `AthleteProfile`

Per-athlete parameters needed for HR-based load metrics.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/importers.py#L120)</sub>

<a id="athleteprofileresolved_hr_max"></a>

### `AthleteProfile.resolved_hr_max`

```python
AthleteProfile.resolved_hr_max() -> float
```

**returns** `float`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/importers.py#L130)</sub>

<a id="athleteprofileresolved_hr_rest"></a>

### `AthleteProfile.resolved_hr_rest`

```python
AthleteProfile.resolved_hr_rest() -> float
```

**returns** `float`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/importers.py#L137)</sub>

<a id="sessiondata"></a>

## class `SessionData`

One training session, normalised across source formats.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/importers.py#L145)</sub>

<a id="sessiondatadate"></a>

### `SessionData.date`

```python
SessionData.date()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/importers.py#L173)</sub>

<a id="sessiondataduration_min"></a>

### `SessionData.duration_min`

```python
SessionData.duration_min() -> float
```

**returns** `float`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/importers.py#L177)</sub>

<a id="sessiondatafinalize"></a>

### `SessionData.finalize`

```python
SessionData.finalize() -> 'SessionData'
```

**returns** `'SessionData'`

Fill missing session scalars from the time series.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/importers.py#L184)</sub>

### `normalize_activity`

```python
normalize_activity(raw: Optional[str]) -> str
```

| input | type | default |
|---|---|---|
| `raw` | Optional[str] | required |

**returns** `str`

Map an arbitrary sport label to a canonical activity type.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/importers.py#L103)</sub>

### `load_session_file`

```python
load_session_file(path: str) -> list[SessionData]
```

| input | type | default |
|---|---|---|
| `path` | str | required |

**returns** `list[SessionData]`

Parse one file into a list of :class:`SessionData` (usually length 1).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/importers.py#L543)</sub>

### `load_sessions`

```python
load_sessions(paths) -> list[SessionData]
```

| input | type | default |
|---|---|---|
| `paths` | – | required |

**returns** `list[SessionData]`

Load sessions from a folder, a glob, or a list of files/folders.

Sessions are returned sorted by start time. Files that fail to parse are  
skipped with a warning printed to stdout (so one bad file doesn't abort a batch).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/importers.py#L552)</sub>
