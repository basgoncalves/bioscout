# `bioscout.model.inspect.logutil`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/logutil.py)

Timestamped logging + simple timing helpers (no OpenSim dependency).

## Contents

- [`setup_logging`](#setup_logging) — Configure a single clean stream handler. Returns the package logger.
- [`timed`](#timed) — Log start/end of a block and the elapsed seconds.
- [`fmt_hms`](#fmt_hms) — 
- [`add_file_handler`](#add_file_handler) — Also write the log to `path` (same format as the console handler).

### `setup_logging`

```python
setup_logging(level: int = logging.INFO, quiet_opensim: bool = True) -> logging.Logger
```

| input | type | default |
|---|---|---|
| `level` | int | `logging.INFO` |
| `quiet_opensim` | bool | `True` |

**returns** `logging.Logger`

Configure a single clean stream handler. Returns the package logger.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/logutil.py#L11)</sub>

### `timed`

```python
timed(label: str, logger: logging.Logger = LOG)
```

| input | type | default |
|---|---|---|
| `label` | str | required |
| `logger` | logging.Logger | `LOG` |

Log start/end of a block and the elapsed seconds.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/logutil.py#L29)</sub>

### `fmt_hms`

```python
fmt_hms(seconds: float) -> str
```

| input | type | default |
|---|---|---|
| `seconds` | float | required |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/logutil.py#L39)</sub>

### `add_file_handler`

```python
add_file_handler(path, logger: logging.Logger = LOG)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `logger` | logging.Logger | `LOG` |

Also write the log to `path` (same format as the console handler).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/logutil.py#L45)</sub>
