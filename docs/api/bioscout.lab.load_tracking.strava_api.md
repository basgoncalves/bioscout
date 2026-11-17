# `bioscout.lab.load_tracking.strava_api`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/strava_api.py)

Strava importer.

The robust, official path: set Zepp to auto-sync workouts to Strava  
(Zepp app → Profile → Add account → Strava), then pull everything through  
Strava's stable API. Once configured, new Amazfit workouts flow Zepp → Strava  
→ BioScout with no manual export.

  
**One-time setup**

1. Create a Strava API application: https://www.strava.com/settings/api  
   → note the ``Client ID`` and ``Client Secret``.  
2. Do the OAuth dance once to get a **refresh token** with ``activity:read_all``  
   scope (any helper works; e.g. open in a browser:  
   ``https://www.strava.com/oauth/authorize?client_id=ID&response_type=code&  
   redirect_uri=http://localhost&approval_prompt=force&scope=activity:read_all``  
   then exchange the ``code`` at ``https://www.strava.com/oauth/token``).  
3. Put client_id / client_secret / refresh_token in your credentials file  
   (see ``connect`` / README). BioScout refreshes the short-lived access token  
   automatically on each run.

API:  GET /api/v3/athlete/activities  and  /api/v3/activities/{id}/streams

## Contents

- class [`StravaClient`](#stravaclient) — 
  - [`StravaClient.refresh`](#stravaclientrefresh) — 
  - [`StravaClient.get_activities`](#stravaclientget_activities) — 
  - [`StravaClient.get_streams`](#stravaclientget_streams) — 
  - [`StravaClient.pull`](#stravaclientpull) — 
- [`strava_activity_to_session`](#strava_activity_to_session) — Convert a Strava activity (+ optional streams dict) to SessionData.
- [`pull_strava`](#pull_strava) — Convenience: build a client and pull sessions in one call.

<a id="stravaclient"></a>

## class `StravaClient`

```python
StravaClient(
    client_id,
    client_secret,
    refresh_token,
    access_token: Optional[str] = None,
    timeout: float = 30.0
)
```

| input | type | default |
|---|---|---|
| `client_id` | – | required |
| `client_secret` | – | required |
| `refresh_token` | – | required |
| `access_token` | Optional[str] | `None` |
| `timeout` | float | `30.0` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/strava_api.py#L91)</sub>

<a id="stravaclientrefresh"></a>

### `StravaClient.refresh`

```python
StravaClient.refresh() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/strava_api.py#L109)</sub>

<a id="stravaclientget_activities"></a>

### `StravaClient.get_activities`

```python
StravaClient.get_activities(
    after: Optional[int] = None,
    per_page: int = 100,
    max_pages: int = 10
) -> list[dict]
```

| input | type | default |
|---|---|---|
| `after` | Optional[int] | `None` |
| `per_page` | int | `100` |
| `max_pages` | int | `10` |

**returns** `list[dict]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/strava_api.py#L129)</sub>

<a id="stravaclientget_streams"></a>

### `StravaClient.get_streams`

```python
StravaClient.get_streams(activity_id) -> dict
```

| input | type | default |
|---|---|---|
| `activity_id` | – | required |

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/strava_api.py#L147)</sub>

<a id="stravaclientpull"></a>

### `StravaClient.pull`

```python
StravaClient.pull(
    after: Optional[int] = None,
    limit: Optional[int] = None,
    with_streams: bool = True
) -> list[SessionData]
```

| input | type | default |
|---|---|---|
| `after` | Optional[int] | `None` |
| `limit` | Optional[int] | `None` |
| `with_streams` | bool | `True` |

**returns** `list[SessionData]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/strava_api.py#L157)</sub>

### `strava_activity_to_session`

```python
strava_activity_to_session(act: dict, streams: Optional[dict] = None) -> SessionData
```

| input | type | default |
|---|---|---|
| `act` | dict | required |
| `streams` | Optional[dict] | `None` |

**returns** `SessionData`

Convert a Strava activity (+ optional streams dict) to SessionData.

``streams`` is the key_by_type response: ``{"heartrate": {"data": [...]}, ...}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/strava_api.py#L50)</sub>

### `pull_strava`

```python
pull_strava(
    client_id,
    client_secret,
    refresh_token,
    after: Optional[int] = None,
    limit: Optional[int] = None,
    with_streams: bool = True
) -> list[SessionData]
```

| input | type | default |
|---|---|---|
| `client_id` | – | required |
| `client_secret` | – | required |
| `refresh_token` | – | required |
| `after` | Optional[int] | `None` |
| `limit` | Optional[int] | `None` |
| `with_streams` | bool | `True` |

**returns** `list[SessionData]`

Convenience: build a client and pull sessions in one call.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/strava_api.py#L175)</sub>
