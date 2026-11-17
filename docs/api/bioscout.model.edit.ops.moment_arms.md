# `bioscout.model.edit.ops.moment_arms`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/moment_arms.py)

Moment-arm operations — wrap radii and path points.

Delegates to :mod:`bioscout.model.moment_arms`, which already has the right  
mechanism and the right argument: in OpenSim the wrap surface IS the geometric  
stand-in for muscle bulk, so growing its radius is how a bigger muscle holds its  
line of action further from the joint axis. Nothing here re-derives that.

Two routes, deliberately separate ops rather than one with a mode flag:

``ma_scale_wraps``   pure XML, no OpenSim, no solver. You name the factor. Fast,  
                     exactly reproducible, and the only route that works on a  
                     machine without the bindings. This is what you want when  
                     transplanting a known edit onto a re-scaled model.  
``ma_target``        solves for a moment-arm target by bisecting the radius,  
                     with a path-translation fallback for wrap-less muscles.  
                     Needs OpenSim. This is what you want when the requirement  
                     is "+25 % moment arm", not "x1.25 radius" -- the two are  
                     not the same number.

All three of those change the moment arm's MAGNITUDE. None of them can repair a  
DISCONTINUITY, and asking one to is a category error -- `ma_target --scale 1.0`  
requests the arm the muscle already has and correctly writes an unchanged file.  
For a path that jumps from one side of a surface to the other there is:

``wrap_quadrant``    restrict which side of a wrap surface the path may run on.  
                     Pure XML, no solver, no geometry change.

## Contents

- [`ma_scale_wraps`](#ma_scale_wraps) — 
- [`ma_target`](#ma_target) — 
- [`ma_translate_path`](#ma_translate_path) — 
- [`wrap_quadrant`](#wrap_quadrant) — 
- [`wrap_repoint`](#wrap_repoint) — 
- [`wrap_add`](#wrap_add) — 
- [`wrap_detach`](#wrap_detach) — 

### `ma_scale_wraps`

```python
ma_scale_wraps(model, out, wraps, factor=1.25, mirror=True, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `wraps` | – | required |
| `factor` | – | `1.25` |
| `mirror` | – | `True` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/moment_arms.py#L62)</sub>

### `ma_target`

```python
ma_target(model, out, coordinate, muscles, scale=None, offset_mm=None, mirror=True, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `coordinate` | – | required |
| `muscles` | – | required |
| `scale` | – | `None` |
| `offset_mm` | – | `None` |
| `mirror` | – | `True` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/moment_arms.py#L120)</sub>

### `ma_translate_path`

```python
ma_translate_path(model, out, muscle, offset_mm, bodies=None, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `muscle` | – | required |
| `offset_mm` | – | required |
| `bodies` | – | `None` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/moment_arms.py#L194)</sub>

### `wrap_quadrant`

```python
wrap_quadrant(model, out, wraps, quadrant, mirror=True, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `wraps` | – | required |
| `quadrant` | – | required |
| `mirror` | – | `True` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/moment_arms.py#L248)</sub>

### `wrap_repoint`

```python
wrap_repoint(model, out, muscle, old, new, mirror=True, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `muscle` | – | required |
| `old` | – | required |
| `new` | – | required |
| `mirror` | – | `True` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/moment_arms.py#L333)</sub>

### `wrap_add`

```python
wrap_add(
    model,
    out,
    body,
    wrap_name,
    kind='cylinder',
    radius=None,
    length=None,
    translation=None,
    rotation=None,
    quadrant='all',
    muscles=None,
    **_
)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `body` | – | required |
| `wrap_name` | – | required |
| `kind` | – | `'cylinder'` |
| `radius` | – | `None` |
| `length` | – | `None` |
| `translation` | – | `None` |
| `rotation` | – | `None` |
| `quadrant` | – | `'all'` |
| `muscles` | – | `None` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/moment_arms.py#L414)</sub>

### `wrap_detach`

```python
wrap_detach(model, out, muscle, wrap, mirror=True, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `muscle` | – | required |
| `wrap` | – | required |
| `mirror` | – | `True` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/moment_arms.py#L468)</sub>
