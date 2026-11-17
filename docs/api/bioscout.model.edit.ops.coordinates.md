# `bioscout.model.edit.ops.coordinates`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/coordinates.py)

Coordinate ranges and locking.

``set_range`` is the op behind "the generic model will not let the athlete get  
that deep". It takes DEGREES, because every range you will ever read off a  
figure, a paper or an IK output is in degrees, while ``.osim`` and  
``edit_model_range_coordinates`` are in radians -- a units mismatch that turns a  
138 deg hip into a 138 rad one with no error.

It also refuses to SHRINK a range by default. Narrowing a bound silently clips  
motion the athlete performed, which shows up much later as a kinematic  
difference between models rather than as an error.

## Contents

- [`set_range`](#set_range) — 
- [`lock`](#lock) — 

### `set_range`

```python
set_range(model, out, coordinate, lo=None, hi=None, mirror=True, allow_shrink=False, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `coordinate` | – | required |
| `lo` | – | `None` |
| `hi` | – | `None` |
| `mirror` | – | `True` |
| `allow_shrink` | – | `False` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/coordinates.py#L51)</sub>

### `lock`

```python
lock(model, out, coordinates, unlock=False, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `coordinates` | – | required |
| `unlock` | – | `False` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/coordinates.py#L119)</sub>
