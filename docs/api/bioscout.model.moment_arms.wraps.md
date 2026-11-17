# `bioscout.model.moment_arms.wraps`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/wraps.py)

Read and edit wrap-surface radii — pure ``xml.etree``, no OpenSim needed.

In OpenSim a wrap surface is the geometric stand-in for muscle bulk: the path  
is held off the bone by the cylinder, so the cylinder's radius sets how far the  
line of action sits from the joint axis. Growing it is therefore the *mechanism*  
by which a larger muscle produces a larger moment arm, not a proxy for it — which  
is why this, rather than translating attachment points, is the primary edit here.

Kept free of ``opensim`` so the file surgery can be unit-tested and so a model  
can be inspected on a machine without an OpenSim install.

## Contents

- class [`WrapInfo`](#wrapinfo) — One wrap surface and where it lives.
  - [`WrapInfo.scalable`](#wrapinfoscalable) — True when this surface has a single radius we can grow.
- [`muscle_wraps`](#muscle_wraps) — ``{muscle: [wrap object names]}`` for every muscle that wraps.
- [`read_wraps`](#read_wraps) — Every wrap surface in the model, keyed by name.
- [`set_wrap_radii`](#set_wrap_radii) — Write absolute radii. Returns ``{wrap: (old, new)}`` for those changed.
- [`scale_wrap_radii`](#scale_wrap_radii) — Multiply radii by per-wrap factors. Returns ``{wrap: (old, new)}``.
- [`set_wrap_quadrant`](#set_wrap_quadrant) — Restrict which side of a wrap surface the path may run on.

<a id="wrapinfo"></a>

## class `WrapInfo`

One wrap surface and where it lives.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/wraps.py#L29)</sub>

<a id="wrapinfoscalable"></a>

### `WrapInfo.scalable`

```python
WrapInfo.scalable() -> bool
```

**returns** `bool`

True when this surface has a single radius we can grow.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/wraps.py#L39)</sub>

### `muscle_wraps`

```python
muscle_wraps(root: ET.Element) -> Dict[str, List[str]]
```

| input | type | default |
|---|---|---|
| `root` | ET.Element | required |

**returns** `Dict[str, List[str]]`

``{muscle: [wrap object names]}`` for every muscle that wraps.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/wraps.py#L56)</sub>

### `read_wraps`

```python
read_wraps(model: str | Path) -> Dict[str, WrapInfo]
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |

**returns** `Dict[str, WrapInfo]`

Every wrap surface in the model, keyed by name.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/wraps.py#L69)</sub>

### `set_wrap_radii`

```python
set_wrap_radii(
    model: str | Path,
    out_path: str | Path,
    radii: Dict[str, float]
) -> Dict[str, tuple]
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |
| `out_path` | str \| Path | required |
| `radii` | Dict[str, float] | required |

**returns** `Dict[str, tuple]`

Write absolute radii. Returns ``{wrap: (old, new)}`` for those changed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/wraps.py#L104)</sub>

### `scale_wrap_radii`

```python
scale_wrap_radii(
    model: str | Path,
    out_path: str | Path,
    factors: Dict[str, float]
) -> Dict[str, tuple]
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |
| `out_path` | str \| Path | required |
| `factors` | Dict[str, float] | required |

**returns** `Dict[str, tuple]`

Multiply radii by per-wrap factors. Returns ``{wrap: (old, new)}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/wraps.py#L133)</sub>

### `set_wrap_quadrant`

```python
set_wrap_quadrant(
    model: str | Path,
    out_path: str | Path,
    quadrants: Dict[str, str]
) -> Dict[str, tuple]
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |
| `out_path` | str \| Path | required |
| `quadrants` | Dict[str, str] | required |

**returns** `Dict[str, tuple]`

Restrict which side of a wrap surface the path may run on.

``{wrap name: quadrant}`` -> ``{wrap: (old, new)}`` for those changed.

This is a CONTINUITY edit, not a magnitude one, and it is the only op here  
that is. Every other edit in this module changes how far the path sits from  
the joint axis; this one changes *which side of the surface it is allowed  
to sit on*, and leaves the geometry untouched.

Why that matters: a path with no via point between its origin and insertion  
can wrap either way round a surface whose ``quadrant`` is ``all``. As the  
joint moves, the shortest-path solution jumps from one side to the other and  
the moment arm steps discontinuously from +r to -r. GPK's  
``obt_internus1_r`` does exactly this -- a two-point path over a 27.7 mm  
sphere centred on the hip joint centre, stepping -27.2 -> +27.2 mm at  
-17 deg hip adduction. Growing or shrinking the sphere cannot help; the  
step is a degeneracy in which side is chosen, not in how big the surface is.

Note the quadrant belongs to the WRAP OBJECT, not to one muscle's PathWrap,  
so restricting it constrains every muscle that wraps on that surface. Check  
``read_wraps(model)[name].muscles`` before using it -- a surface with one  
user is a per-muscle fix, a shared one is not.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/wraps.py#L149)</sub>
