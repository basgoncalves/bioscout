# `bioscout.lab.load_tracking.connect`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/connect.py)

Cloud-credentials loading + helpers for pulling sessions into a LoadTracker.

Credentials live in a small JSON file (default  
``~/.bioscout/load_credentials.json``) so secrets stay out of the codebase and  
the command line:

    {  
      "zepp":   { "token": "DQVBQE…WHtrY", "region": "de2" },  
      "strava": { "client_id": "12345",  
                  "client_secret": "abc…",  
                  "refresh_token": "def…" }  
    }

Either block is optional — include only the source(s) you use.

## Contents

- [`default_credentials_path`](#default_credentials_path) — 
- [`load_credentials`](#load_credentials) — Load the credentials JSON. Returns {} if the file is missing.
- [`pull_into_tracker`](#pull_into_tracker) — Pull from whichever sources are present in *creds*. Returns counts/errors.

### `default_credentials_path`

```python
default_credentials_path() -> Path
```

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/connect.py#L26)</sub>

### `load_credentials`

```python
load_credentials(path: Optional[str] = None) -> dict
```

| input | type | default |
|---|---|---|
| `path` | Optional[str] | `None` |

**returns** `dict`

Load the credentials JSON. Returns {} if the file is missing.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/connect.py#L30)</sub>

### `pull_into_tracker`

```python
pull_into_tracker(
    tracker,
    creds: dict,
    zepp: bool = True,
    strava: bool = True,
    limit: Optional[int] = None
) -> dict
```

| input | type | default |
|---|---|---|
| `tracker` | – | required |
| `creds` | dict | required |
| `zepp` | bool | `True` |
| `strava` | bool | `True` |
| `limit` | Optional[int] | `None` |

**returns** `dict`

Pull from whichever sources are present in *creds*. Returns counts/errors.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/connect.py#L39)</sub>
