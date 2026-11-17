# `bioscout.utils.text_prints`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/text_prints.py)

Console/log formatting helpers -- the shape bioscout's output already has.

Today the codebase writes its progress with ad-hoc ``print()`` calls, and the  
convention that emerged is a bracketed tag naming the stage: ``[scale] ...``,  
``[Session] ...``, ``[simulate so] ...``. This module is the seed for making  
that one thing instead of several hundred (docs/RESTRUCTURE_PLAN.md, stage 11).

SEED MODULE: nothing has been migrated onto it yet, deliberately. Rewriting  
every print in the package in one pass would bury a real behaviour change in  
thousands of cosmetic lines; the plan is to adopt these as each module is next  
touched for its own reasons.

    from bioscout.utils.text_prints import tagged, warn, rule

    tagged("scale", f"wrote {path}")          # [scale] wrote ...  
    warn("scale", "MeasurementSet is empty")  # [scale] [WARNING] ...

## Contents

- [`tagged`](#tagged) — ``[tag] message`` -- the house style for a progress line.
- [`warn`](#warn) — ``[tag] [WARNING] message`` -- something is off, the run continues.
- [`fail`](#fail) — ``[tag] [ERROR] message`` -- to stderr, because it ended something.
- [`rule`](#rule) — A section rule, optionally with a centred title.
- [`kv`](#kv) — ``a=1  b=2`` from a dict or pairs -- the run-header style.

### `tagged`

```python
tagged(tag, message, stream=None)
```

| input | type | default |
|---|---|---|
| `tag` | – | required |
| `message` | – | required |
| `stream` | – | `None` |

``[tag] message`` -- the house style for a progress line.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/text_prints.py#L25)</sub>

### `warn`

```python
warn(tag, message, stream=None)
```

| input | type | default |
|---|---|---|
| `tag` | – | required |
| `message` | – | required |
| `stream` | – | `None` |

``[tag] [WARNING] message`` -- something is off, the run continues.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/text_prints.py#L30)</sub>

### `fail`

```python
fail(tag, message, stream=None)
```

| input | type | default |
|---|---|---|
| `tag` | – | required |
| `message` | – | required |
| `stream` | – | `None` |

``[tag] [ERROR] message`` -- to stderr, because it ended something.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/text_prints.py#L35)</sub>

### `rule`

```python
rule(title='', width=72, char='=')
```

| input | type | default |
|---|---|---|
| `title` | – | `''` |
| `width` | – | `72` |
| `char` | – | `'='` |

A section rule, optionally with a centred title.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/text_prints.py#L40)</sub>

### `kv`

```python
kv(pairs, sep='  ')
```

| input | type | default |
|---|---|---|
| `pairs` | – | required |
| `sep` | – | `'  '` |

``a=1  b=2`` from a dict or pairs -- the run-header style.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/text_prints.py#L49)</sub>
