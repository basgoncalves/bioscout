# `bioscout.model.edit.ops.scale`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/scale.py)

Dimensional scaling and mass — the two halves of "make it this subject".

They are separate ops because they come apart in practice. An MRI/TPS model has  
personalised geometry, so ``linear_scaling`` is off and ScaleTool's ModelScaler  
never runs -- which also means nothing ever applies the subject's mass and the  
model quietly keeps the generic's 75.34 kg while every joint contact force is  
normalised by the real body mass. ``set_mass`` is the op that fixes that without  
touching a single segment length.

## Contents

- [`scale`](#scale) — 
- [`set_mass`](#set_mass) — 
- [`mass_from_static_grf`](#mass_from_static_grf) — 

### `scale`

```python
scale(
    model,
    out,
    static_trc,
    mass=None,
    marker_set=None,
    linear_scaling=True,
    marker_placer=True,
    time_range=None,
    setup_dir=None,
    **_
)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `static_trc` | – | required |
| `mass` | – | `None` |
| `marker_set` | – | `None` |
| `linear_scaling` | – | `True` |
| `marker_placer` | – | `True` |
| `time_range` | – | `None` |
| `setup_dir` | – | `None` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/scale.py#L46)</sub>

### `set_mass`

```python
set_mass(model, out, mass, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `mass` | – | required |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/scale.py#L104)</sub>

### `mass_from_static_grf`

```python
mass_from_static_grf(model, out, grf_mot, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `grf_mot` | – | required |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/scale.py#L132)</sub>
