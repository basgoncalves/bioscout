# `bioscout.model.edit.ops.inspect`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/inspect.py)

Read-only checks. None of these write a model.

They are ops rather than a separate API so that a recipe can end with one — a  
build that does not verify itself is a build you have to remember to verify.

## Contents

- [`info`](#info) — 
- [`check_paths`](#check_paths) — 
- [`compare`](#compare) — 
- [`diff`](#diff) — 
- [`inspect_change`](#inspect_change) — 

### `info`

```python
info(model, out, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/inspect.py#L22)</sub>

### `check_paths`

```python
check_paths(model, out, coordinates=None, n=40, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `coordinates` | – | `None` |
| `n` | – | `40` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/inspect.py#L45)</sub>

### `compare`

```python
compare(model, out, against, out_file=None, figures=None, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `against` | – | required |
| `out_file` | – | `None` |
| `figures` | – | `None` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/inspect.py#L76)</sub>

### `diff`

```python
diff(model, out, against, tol=1e-12, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `against` | – | required |
| `tol` | – | `1e-12` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/inspect.py#L104)</sub>

### `inspect_change`

```python
inspect_change(model, out, against, coordinates, n=40, full=True, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `against` | – | required |
| `coordinates` | – | required |
| `n` | – | `40` |
| `full` | – | `True` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/inspect.py#L181)</sub>
