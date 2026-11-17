# `bioscout.lab.load_tracking.tracker`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracker.py)

LoadTracker — orchestrator for the load-tracking module.

Ties the pieces together:  
    import sessions  →  per-session load (metrics)  →  per-muscle distribution  
    (ml_interface)  →  aggregate metrics + per-muscle fatigue  →  PDF report.

  
**Typical use**

    from bioscout.lab.load_tracking import LoadTracker, AthleteProfile

    tracker = LoadTracker(athlete=AthleteProfile(name="Bas", age=30,  
                                                 hr_max=190, hr_rest=55))  
    tracker.add_files("C:/data/zepp_exports/")      # folder, glob, or list  
    tracker.compute()  
    tracker.report("load_report.pdf")               # writes the PDF  
    print(tracker.summary_text())                   # console summary

## Contents

- class [`LoadResults`](#loadresults) — 
- class [`LoadTracker`](#loadtracker) — 
  - [`LoadTracker.add_files`](#loadtrackeradd_files) — Add sessions from a folder/glob/list. Returns number of sessions added.
  - [`LoadTracker.add_session`](#loadtrackeradd_session) — 
  - [`LoadTracker.add_zepp`](#loadtrackeradd_zepp) — Pull sessions straight from your Zepp/Huami cloud account.
  - [`LoadTracker.add_strava`](#loadtrackeradd_strava) — Pull activities from Strava (Zepp → Strava auto-sync).
  - [`LoadTracker.compute`](#loadtrackercompute) — 
  - [`LoadTracker.report`](#loadtrackerreport) — 
  - [`LoadTracker.summary_text`](#loadtrackersummary_text) — 
- [`textwrap_indent`](#textwrap_indent) — 

<a id="loadresults"></a>

## class `LoadResults`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracker.py#L31)</sub>

<a id="loadtracker"></a>

## class `LoadTracker`

```python
LoadTracker(
    athlete: Optional[AthleteProfile] = None,
    estimator: Optional[MuscleForceEstimator] = None
)
```

| input | type | default |
|---|---|---|
| `athlete` | Optional[AthleteProfile] | `None` |
| `estimator` | Optional[MuscleForceEstimator] | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracker.py#L44)</sub>

<a id="loadtrackeradd_files"></a>

### `LoadTracker.add_files`

```python
LoadTracker.add_files(paths) -> int
```

| input | type | default |
|---|---|---|
| `paths` | – | required |

**returns** `int`

Add sessions from a folder/glob/list. Returns number of sessions added.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracker.py#L53)</sub>

<a id="loadtrackeradd_session"></a>

### `LoadTracker.add_session`

```python
LoadTracker.add_session(session: SessionData) -> None
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |

**returns** `None`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracker.py#L60)</sub>

<a id="loadtrackeradd_zepp"></a>

### `LoadTracker.add_zepp`

```python
LoadTracker.add_zepp(
    token: str,
    region: str = 'de2',
    limit: Optional[int] = None,
    enrich: bool = True
) -> int
```

| input | type | default |
|---|---|---|
| `token` | str | required |
| `region` | str | `'de2'` |
| `limit` | Optional[int] | `None` |
| `enrich` | bool | `True` |

**returns** `int`

Pull sessions straight from your Zepp/Huami cloud account.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracker.py#L64)</sub>

<a id="loadtrackeradd_strava"></a>

### `LoadTracker.add_strava`

```python
LoadTracker.add_strava(
    client_id,
    client_secret,
    refresh_token,
    after=None,
    limit: Optional[int] = None,
    with_streams: bool = True
) -> int
```

| input | type | default |
|---|---|---|
| `client_id` | – | required |
| `client_secret` | – | required |
| `refresh_token` | – | required |
| `after` | – | `None` |
| `limit` | Optional[int] | `None` |
| `with_streams` | bool | `True` |

**returns** `int`

Pull activities from Strava (Zepp → Strava auto-sync).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracker.py#L73)</sub>

<a id="loadtrackercompute"></a>

### `LoadTracker.compute`

```python
LoadTracker.compute() -> LoadResults
```

**returns** `LoadResults`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracker.py#L85)</sub>

<a id="loadtrackerreport"></a>

### `LoadTracker.report`

```python
LoadTracker.report(output_path: str, title: Optional[str] = None) -> str
```

| input | type | default |
|---|---|---|
| `output_path` | str | required |
| `title` | Optional[str] | `None` |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracker.py#L107)</sub>

<a id="loadtrackersummary_text"></a>

### `LoadTracker.summary_text`

```python
LoadTracker.summary_text() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracker.py#L113)</sub>

### `textwrap_indent`

```python
textwrap_indent(notes) -> list[str]
```

| input | type | default |
|---|---|---|
| `notes` | – | required |

**returns** `list[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/tracker.py#L149)</sub>
