# `bioscout.utils.logger`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py)

Logging utility for the Powerlifting Model Analysis App.

## Contents

- class [`AppLogger`](#applogger) — Custom logger for the application.
  - [`AppLogger.capture_std_streams`](#apploggercapture_std_streams) — Tee sys.stdout/stderr into this log so print() output is kept too.
  - [`AppLogger.release_std_streams`](#apploggerrelease_std_streams) — Undo :meth:`capture_std_streams` (if our tee is still on top).
  - [`AppLogger.debug`](#apploggerdebug) — Log debug message.
  - [`AppLogger.info`](#apploggerinfo) — Log info message.
  - [`AppLogger.warning`](#apploggerwarning) — Log warning message.
  - [`AppLogger.error`](#apploggererror) — Log error message.
  - [`AppLogger.critical`](#apploggercritical) — Log critical message.
  - [`AppLogger.exception`](#apploggerexception) — Log an error with the active traceback (call from inside `except`).
  - [`AppLogger.log`](#apploggerlog) — Log at an explicit level.
  - [`AppLogger.set_console_level`](#apploggerset_console_level) — Set console handler log level.
  - [`AppLogger.get_log_file`](#apploggerget_log_file) — Get path to current log file.
  - [`AppLogger.list_logs`](#apploggerlist_logs) — List recent log files.
  - [`AppLogger.set_project_log_dir`](#apploggerset_project_log_dir) — Redirect the file handler to a project-level log directory.
  - [`AppLogger.clear_old_logs`](#apploggerclear_old_logs) — Clear log files older than specified days.

<a id="applogger"></a>

## class `AppLogger`

```python
AppLogger()
```

Custom logger for the application.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L37)</sub>

<a id="apploggercapture_std_streams"></a>

### `AppLogger.capture_std_streams`

```python
AppLogger.capture_std_streams() -> None
```

**returns** `None`

Tee sys.stdout/stderr into this log so print() output is kept too.

For bioscout's OWN entry points (the CLI and the GUI, both through  
``__main__``), which own the console. Library code must never call it.  
Idempotent. Also switches a real console to UTF-8 so the unicode in  
progress messages cannot raise UnicodeEncodeError on a cp1252 console.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L120)</sub>

<a id="apploggerrelease_std_streams"></a>

### `AppLogger.release_std_streams`

```python
AppLogger.release_std_streams() -> None
```

**returns** `None`

Undo :meth:`capture_std_streams` (if our tee is still on top).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L141)</sub>

<a id="apploggerdebug"></a>

### `AppLogger.debug`

```python
AppLogger.debug(message, *args, **kwargs) -> None
```

| input | type | default |
|---|---|---|
| `message` | – | required |
| `*args` | – | – |
| `**kwargs` | – | – |

**returns** `None`

Log debug message.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L169)</sub>

<a id="apploggerinfo"></a>

### `AppLogger.info`

```python
AppLogger.info(message, *args, **kwargs) -> None
```

| input | type | default |
|---|---|---|
| `message` | – | required |
| `*args` | – | – |
| `**kwargs` | – | – |

**returns** `None`

Log info message.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L173)</sub>

<a id="apploggerwarning"></a>

### `AppLogger.warning`

```python
AppLogger.warning(message, *args, **kwargs) -> None
```

| input | type | default |
|---|---|---|
| `message` | – | required |
| `*args` | – | – |
| `**kwargs` | – | – |

**returns** `None`

Log warning message.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L177)</sub>

<a id="apploggererror"></a>

### `AppLogger.error`

```python
AppLogger.error(message, *args, **kwargs) -> None
```

| input | type | default |
|---|---|---|
| `message` | – | required |
| `*args` | – | – |
| `**kwargs` | – | – |

**returns** `None`

Log error message.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L181)</sub>

<a id="apploggercritical"></a>

### `AppLogger.critical`

```python
AppLogger.critical(message, *args, **kwargs) -> None
```

| input | type | default |
|---|---|---|
| `message` | – | required |
| `*args` | – | – |
| `**kwargs` | – | – |

**returns** `None`

Log critical message.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L185)</sub>

<a id="apploggerexception"></a>

### `AppLogger.exception`

```python
AppLogger.exception(message, *args, **kwargs) -> None
```

| input | type | default |
|---|---|---|
| `message` | – | required |
| `*args` | – | – |
| `**kwargs` | – | – |

**returns** `None`

Log an error with the active traceback (call from inside `except`).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L189)</sub>

<a id="apploggerlog"></a>

### `AppLogger.log`

```python
AppLogger.log(level: int, message, *args, **kwargs) -> None
```

| input | type | default |
|---|---|---|
| `level` | int | required |
| `message` | – | required |
| `*args` | – | – |
| `**kwargs` | – | – |

**returns** `None`

Log at an explicit level.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L194)</sub>

<a id="apploggerset_console_level"></a>

### `AppLogger.set_console_level`

```python
AppLogger.set_console_level(level: int) -> None
```

| input | type | default |
|---|---|---|
| `level` | int | required |

**returns** `None`

Set console handler log level.

  
**Args**

    level: logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L198)</sub>

<a id="apploggerget_log_file"></a>

### `AppLogger.get_log_file`

```python
AppLogger.get_log_file() -> str
```

**returns** `str`

Get path to current log file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L209)</sub>

<a id="apploggerlist_logs"></a>

### `AppLogger.list_logs`

```python
AppLogger.list_logs(limit: int = 10) -> list
```

| input | type | default |
|---|---|---|
| `limit` | int | `10` |

**returns** `list`

List recent log files.

  
**Args**

    limit: Maximum number of logs to return

  
**Returns**

    List of log file paths

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L213)</sub>

<a id="apploggerset_project_log_dir"></a>

### `AppLogger.set_project_log_dir`

```python
AppLogger.set_project_log_dir(project_log_dir) -> None
```

| input | type | default |
|---|---|---|
| `project_log_dir` | – | required |

**returns** `None`

Redirect the file handler to a project-level log directory.

Call this from __main__.py after the settings file is loaded in batch  
mode so that analysis logs land in PROJECT_ROOT/logs rather than the  
app install directory.

  
**Args**

    project_log_dir: Path or str — the target log directory  
                     (typically settings.LOG_DIR).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L229)</sub>

<a id="apploggerclear_old_logs"></a>

### `AppLogger.clear_old_logs`

```python
AppLogger.clear_old_logs(days: int = 7) -> None
```

| input | type | default |
|---|---|---|
| `days` | int | `7` |

**returns** `None`

Clear log files older than specified days.

  
**Args**

    days: Number of days to keep

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/logger.py#L285)</sub>
