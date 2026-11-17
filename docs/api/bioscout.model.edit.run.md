# `bioscout.model.edit.run`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/run.py)

Applying an operation: validate, resolve the output path, delegate.

This is the only place that turns a dict of user-supplied strings into a call.  
Everything upstream (prompt, argparse, recipe, GUI) produces the same dict and  
goes through here, so a value is coerced and checked once rather than once per  
front end.

## Contents

- class [`MissingParam`](#missingparam) — 
- class [`BadParam`](#badparam) — 
- [`coerce`](#coerce) — Turn one raw value into the type the op expects, or raise :class:`BadParam`.
- [`validate`](#validate) — Coerce and check every parameter. Returns the cleaned dict.
- [`plan`](#plan) — Resolve what :func:`apply` would do, without doing it.
- [`apply`](#apply) — Run one operation.

<a id="missingparam"></a>

## class `MissingParam`(ValueError)

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/run.py#L20)</sub>

<a id="badparam"></a>

## class `BadParam`(ValueError)

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/run.py#L24)</sub>

### `coerce`

```python
coerce(param, value)
```

| input | type | default |
|---|---|---|
| `param` | – | required |
| `value` | – | required |

Turn one raw value into the type the op expects, or raise :class:`BadParam`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/run.py#L49)</sub>

### `validate`

```python
validate(op: Op, params: Dict[str, Any], model=None) -> Dict[str, Any]
```

| input | type | default |
|---|---|---|
| `op` | Op | required |
| `params` | Dict[str, Any] | required |
| `model` | – | `None` |

**returns** `Dict[str, Any]`

Coerce and check every parameter. Returns the cleaned dict.

Unknown keys are an error rather than being ignored: a typo'd key in a YAML  
recipe that is silently dropped means the run does something other than what  
the file says, and the file is the record of what you did.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/run.py#L76)</sub>

### `plan`

```python
plan(
    name: str,
    model,
    out=None,
    out_dir=None,
    overwrite=False,
    **params
) -> Dict[str, Any]
```

| input | type | default |
|---|---|---|
| `name` | str | required |
| `model` | – | required |
| `out` | – | `None` |
| `out_dir` | – | `None` |
| `overwrite` | – | `False` |
| `**params` | – | – |

**returns** `Dict[str, Any]`

Resolve what :func:`apply` would do, without doing it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/run.py#L106)</sub>

### `apply`

```python
apply(
    name: str,
    model,
    out=None,
    out_dir=None,
    overwrite=False,
    dry_run=False,
    **params
) -> OpResult
```

| input | type | default |
|---|---|---|
| `name` | str | required |
| `model` | – | required |
| `out` | – | `None` |
| `out_dir` | – | `None` |
| `overwrite` | – | `False` |
| `dry_run` | – | `False` |
| `**params` | – | – |

**returns** `OpResult`

Run one operation.

``model`` is the input .osim. ``out`` is optional when the op declares a  
suffix; see :mod:`bioscout.model.edit.naming` for the rule.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/run.py#L124)</sub>
