# `bioscout.lab.load_tracking.zepp_cloud`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/zepp_cloud.py)

Zepp / Huami cloud importer.

Pulls workouts straight from your Zepp (Amazfit) cloud account — no manual  
per-workout export. Because the GTR 3 Pro has no USB data link, "automatic" means  
reading the cloud, not the device.

  
**Auth note (important for SSO logins)**

The Huami API authenticates with an ``apptoken`` header. If you sign in to Zepp  
with Google / Apple / Xiaomi (SSO), there is no email/password the API can use, so  
you must capture the token **once**:

    * Rooted Android: read  
      ``/data/data/com.huami.watch.hmwatchmanager/shared_prefs/hm_id_sdk_android.xml``  
    * Not rooted: run HTTP Toolkit / Fiddler / mitmproxy, open the Zepp app, and  
      copy the ``apptoken`` header from any request to ``api-mifit-*.huami.com``.

The token is long-lived; paste it into your credentials file (see ``connect`` /  
README). Region is the server suffix in that host, e.g. ``de2`` (EU), ``us2`` (US).

API shape (reverse-engineered; credit: rolandsz/Mi-Fit-and-Zepp-workout-exporter):  
    GET https://api-mifit-{region}.huami.com/v1/sport/run/history.json  
        header apptoken, param source=run.mifit.huami.com  → data.summary[ {...} ]  
    GET https://api-mifit-{region}.huami.com/v1/sport/run/detail.json  
        header apptoken, params trackid, source            → data{ time, heart_rate, ... }

This is an unofficial API and may change without notice.

## Contents

- class [`ZeppCloudClient`](#zeppcloudclient) — Minimal client for the Huami workout API using a captured apptoken.
  - [`ZeppCloudClient.get_history`](#zeppcloudclientget_history) — 
  - [`ZeppCloudClient.get_detail`](#zeppcloudclientget_detail) — 
  - [`ZeppCloudClient.pull`](#zeppcloudclientpull) — Pull workouts → SessionData. ``enrich`` adds the HR trace per workout.
- [`decode_heart_rate`](#decode_heart_rate) — Decode Huami ``heart_rate`` string ("t,v;t,v;…", delta-encoded).
- [`huami_summary_to_session`](#huami_summary_to_session) — Build a SessionData from one Huami history summary dict (no detail trace).
- [`enrich_session_with_detail`](#enrich_session_with_detail) — Attach the HR time series from a Huami detail dict, if present.
- [`pull_zepp`](#pull_zepp) — Convenience: build a client and pull sessions in one call.

<a id="zeppcloudclient"></a>

## class `ZeppCloudClient`

```python
ZeppCloudClient(
    token: str,
    region: str = 'de2',
    source: str = DEFAULT_SOURCE,
    timeout: float = 30.0
)
```

| input | type | default |
|---|---|---|
| `token` | str | required |
| `region` | str | `'de2'` |
| `source` | str | `DEFAULT_SOURCE` |
| `timeout` | float | `30.0` |

Minimal client for the Huami workout API using a captured apptoken.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/zepp_cloud.py#L143)</sub>

<a id="zeppcloudclientget_history"></a>

### `ZeppCloudClient.get_history`

```python
ZeppCloudClient.get_history() -> list[dict]
```

**returns** `list[dict]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/zepp_cloud.py#L163)</sub>

<a id="zeppcloudclientget_detail"></a>

### `ZeppCloudClient.get_detail`

```python
ZeppCloudClient.get_detail(trackid, source: Optional[str] = None) -> dict
```

| input | type | default |
|---|---|---|
| `trackid` | – | required |
| `source` | Optional[str] | `None` |

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/zepp_cloud.py#L175)</sub>

<a id="zeppcloudclientpull"></a>

### `ZeppCloudClient.pull`

```python
ZeppCloudClient.pull(
    limit: Optional[int] = None,
    enrich: bool = True
) -> list[SessionData]
```

| input | type | default |
|---|---|---|
| `limit` | Optional[int] | `None` |
| `enrich` | bool | `True` |

**returns** `list[SessionData]`

Pull workouts → SessionData. ``enrich`` adds the HR trace per workout.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/zepp_cloud.py#L184)</sub>

### `decode_heart_rate`

```python
decode_heart_rate(hr_str: Optional[str]) -> tuple[np.ndarray, np.ndarray]
```

| input | type | default |
|---|---|---|
| `hr_str` | Optional[str] | required |

**returns** `tuple[np.ndarray, np.ndarray]`

Decode Huami ``heart_rate`` string ("t,v;t,v;…", delta-encoded).

Each ``t,v`` pair is (time-delta seconds, HR-delta bpm); both accumulate.  
Returns (time_s, hr_bpm) arrays. Empty arrays if unparseable.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/zepp_cloud.py#L79)</sub>

### `huami_summary_to_session`

```python
huami_summary_to_session(summary: dict) -> SessionData
```

| input | type | default |
|---|---|---|
| `summary` | dict | required |

**returns** `SessionData`

Build a SessionData from one Huami history summary dict (no detail trace).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/zepp_cloud.py#L104)</sub>

### `enrich_session_with_detail`

```python
enrich_session_with_detail(session: SessionData, detail: dict) -> SessionData
```

| input | type | default |
|---|---|---|
| `session` | SessionData | required |
| `detail` | dict | required |

**returns** `SessionData`

Attach the HR time series from a Huami detail dict, if present.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/zepp_cloud.py#L129)</sub>

### `pull_zepp`

```python
pull_zepp(
    token: str,
    region: str = 'de2',
    source: str = DEFAULT_SOURCE,
    limit: Optional[int] = None,
    enrich: bool = True
) -> list[SessionData]
```

| input | type | default |
|---|---|---|
| `token` | str | required |
| `region` | str | `'de2'` |
| `source` | str | `DEFAULT_SOURCE` |
| `limit` | Optional[int] | `None` |
| `enrich` | bool | `True` |

**returns** `list[SessionData]`

Convenience: build a client and pull sessions in one call.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/zepp_cloud.py#L204)</sub>
