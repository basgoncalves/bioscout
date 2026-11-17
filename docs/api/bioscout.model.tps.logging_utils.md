# `bioscout.model.tps.logging_utils`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/logging_utils.py)

Centralised logging.

The original pipeline used bare ``print`` calls scattered through the code,  
which made it impossible to silence output or capture it in a host application  
(e.g. the BioScout GUI console). Here every module obtains a named logger via  
:func:`get_logger`; the host can configure handlers/levels once.

## Contents

- [`add_file_handler`](#add_file_handler) — Also write the package's logs to ``path``. Idempotent per path.
- [`get_logger`](#get_logger) — Return a package logger. Adds a default handler once, only if the host application has not configured logging itself.

### `add_file_handler`

```python
add_file_handler(path: str | Path, name: str = 'tps_personalise') -> Path
```

| input | type | default |
|---|---|---|
| `path` | str \| Path | required |
| `name` | str | `'tps_personalise'` |

**returns** `Path`

Also write the package's logs to ``path``. Idempotent per path.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/logging_utils.py#L17)</sub>

### `get_logger`

```python
get_logger(name: str = 'tps_personalise') -> logging.Logger
```

| input | type | default |
|---|---|---|
| `name` | str | `'tps_personalise'` |

**returns** `logging.Logger`

Return a package logger. Adds a default handler once, only if the host  
application has not configured logging itself.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/logging_utils.py#L33)</sub>
