# `bioscout.model.torsion_tool`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/torsion_tool.py)

Impose target femoral and tibial torsion on an OpenSim model.

A model scaled from a generic skeleton carries the template's neck-shaft angle,  
anteversion and tibial torsion no matter how the subject is built -- scaling  
stretches a bone, it does not twist it (see  
:mod:`bioscout.model.measure`, which reports those angles). This module twists  
it, in the spirit of the Torsion Tool (Veerkamp et al., J Biomech 2021):

* **anteversion (AVA)** -- rotation about the femoral shaft axis, ramping from  
  0 at the base of the neck to the full angle at the knee.  
* **neck-shaft angle (NSA)** -- rotation of the head and neck about the axis  
  perpendicular to the neck/shaft plane, ramping from 0 at the neck base to the  
  full angle at the head.  
* **tibial torsion (TT)** -- rotation about the tibial long axis, ramping from  
  0 at the knee to the full angle at the ankle.

Everything riding on the bone is carried along: the joint frames, muscle and  
ligament path points, wrap objects, and the bone meshes themselves (written out  
deformed, so the model draws -- and re-measures -- as the angles you asked for).

Markers are deliberately NOT moved: after a twist the marker set no longer  
matches the skin, so re-register it from a static trial rather than trusting  
rotated landmarks.

The targets are absolute. The model is measured, a twist is applied, and the  
result is measured again; a secant correction and a final check mean the output  
is verified rather than assumed -- ``--tol`` sets how close is close enough.

CLI::

    python -m bioscout.model.torsion_tool IN.osim -o OUT.osim \  
        [--nsa 125] [--ava 20] [--tt 30] [--side r l] [--tol 0.5] [--json]

## Contents

- class [`Twist`](#twist) — A tapered rotation about a line, as a callable on points.
  - [`Twist.fraction`](#twistfraction) — 
  - [`Twist.rotation_at`](#twistrotation_at) — 
  - [`Twist.points`](#twistpoints) — Move an (N, 3) array, one rotation per point (vectorised).
- [`femur_twists`](#femur_twists) — ``(_Chain, geometry dict)`` for one femur, for the given angle changes.
- [`tibia_twist`](#tibia_twist) — ``(Twist | None, geometry dict)`` for one tibia.
- [`apply_torsion`](#apply_torsion) — Write a copy of ``model_path`` whose torsion matches the targets.
- [`build_parser`](#build_parser) — 
- [`main`](#main) — 

<a id="twist"></a>

## class `Twist`

```python
Twist(origin, axis, angle_deg: float, start, end, ramp_axis=None)
```

| input | type | default |
|---|---|---|
| `origin` | – | required |
| `axis` | – | required |
| `angle_deg` | float | required |
| `start` | – | required |
| `end` | – | required |
| `ramp_axis` | – | `None` |

A tapered rotation about a line, as a callable on points.

The rotation angle ramps linearly from 0 where a point projects onto  
``start`` along ``ramp_axis`` to ``angle_deg`` at ``end``, and is held  
constant outside that span -- so the proximal fragment stays put, the  
shaft twists gradually, and the distal fragment moves as one piece.

origin: a point on the rotation axis (it, and the whole axis, stay fixed).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/torsion_tool.py#L65)</sub>

<a id="twistfraction"></a>

### `Twist.fraction`

```python
Twist.fraction(p) -> float
```

| input | type | default |
|---|---|---|
| `p` | – | required |

**returns** `float`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/torsion_tool.py#L86)</sub>

<a id="twistrotation_at"></a>

### `Twist.rotation_at`

```python
Twist.rotation_at(p)
```

| input | type | default |
|---|---|---|
| `p` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/torsion_tool.py#L93)</sub>

<a id="twistpoints"></a>

### `Twist.points`

```python
Twist.points(P)
```

| input | type | default |
|---|---|---|
| `P` | – | required |

Move an (N, 3) array, one rotation per point (vectorised).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/torsion_tool.py#L102)</sub>

### `femur_twists`

```python
femur_twists(
    model,
    side: str,
    state,
    model_path=None,
    mesh=None,
    d_nsa: float = 0.0,
    d_ava: float = 0.0,
    search=None
)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `side` | str | required |
| `state` | – | required |
| `model_path` | – | `None` |
| `mesh` | – | `None` |
| `d_nsa` | float | `0.0` |
| `d_ava` | float | `0.0` |
| `search` | – | `None` |

``(_Chain, geometry dict)`` for one femur, for the given angle changes.

The neck axis and the shaft axis come from the femur mesh (the same fit  
:func:`bioscout.model.measure.femoral_geometry` measures with), so the  
twist is defined on the bone rather than on the joint frames alone.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/torsion_tool.py#L145)</sub>

### `tibia_twist`

```python
tibia_twist(model, side: str, state, d_tt: float = 0.0)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `side` | str | required |
| `state` | – | required |
| `d_tt` | float | `0.0` |

``(Twist | None, geometry dict)`` for one tibia.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/torsion_tool.py#L196)</sub>

### `apply_torsion`

```python
apply_torsion(
    model_path,
    out_path,
    nsa: Optional[float] = None,
    ava: Optional[float] = None,
    tt: Optional[float] = None,
    sides: Sequence[str] = ('r', 'l'),
    tol: float = 0.5,
    max_passes: int = 3,
    outer_passes: int = 3,
    search: Optional[Sequence] = None,
    plots: bool = True,
    name_suffix: str = '_torsion',
    verbose: bool = True,
    relative: bool = False,
    defaults: Optional[Dict[str, float]] = None
) -> dict
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `out_path` | – | required |
| `nsa` | Optional[float] | `None` |
| `ava` | Optional[float] | `None` |
| `tt` | Optional[float] | `None` |
| `sides` | Sequence[str] | `('r', 'l')` |
| `tol` | float | `0.5` |
| `max_passes` | int | `3` |
| `outer_passes` | int | `3` |
| `search` | Optional[Sequence] | `None` |
| `plots` | bool | `True` |
| `name_suffix` | str | `'_torsion'` |
| `verbose` | bool | `True` |
| `relative` | bool | `False` |
| `defaults` | Optional[Dict[str, float]] | `None` |

**returns** `dict`

Write a copy of ``model_path`` whose torsion matches the targets.

nsa, ava, tt: absolute targets in degrees (``None`` leaves that angle as it  
    is). Signs follow :mod:`bioscout.model.measure`: anteversion positive =  
    anteverted, tibial torsion positive = external.  
tol: stop once every requested angle is within this many degrees.  
max_passes: secant steps allowed per angle. The first applies the naive  
    delta, later ones a correction from the gain just observed -- which is  
    what makes the ramp's exact sign and gain irrelevant.  
outer_passes: how many times to run the whole NSA-AVA-TT sequence. The  
    angles share the shaft axis, so one more sweep cleans up the small  
    interaction between them.  
plots: also write the moment-arm comparison (original vs twisted vs  
    literature) into ``<out>_moment_arms/``.  
name_suffix: appended to the model's name tag, so the GUI navigator tells  
    the two models apart.

relative: follow Veerkamp et al. (2021) instead of solving for an absolute  
    target. nsa/ava/tt are then the SUBJECT's measured angles and  
    ``defaults`` the GENERIC model's, measured by the SAME method; the  
    difference is applied once, open loop, with no re-measurement. This is  
    the procedure's own safeguard: any bias in how an angle is measured  
    cancels in the subtraction, so it never matters that the tool's  
    mesh-based measurement of the generic disagrees with, say, a markup  
    measurement on MRI. Absolute mode (the default) instead drives the  
    tool's own measurement onto the target, which mixes the two methods.  
defaults: {"nsa":..., "ava":..., "tt":...} for ``relative`` -- the generic  
    model's angles. Measure them once with the same method used on the  
    subjects and keep them fixed for the cohort.

Returns a report: the angles before and after, per side, and what moved.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/torsion_tool.py#L454)</sub>

### `build_parser`

```python
build_parser() -> argparse.ArgumentParser
```

**returns** `argparse.ArgumentParser`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/torsion_tool.py#L669)</sub>

### `main`

```python
main(argv: Optional[Sequence[str]] = None) -> int
```

| input | type | default |
|---|---|---|
| `argv` | Optional[Sequence[str]] | `None` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/torsion_tool.py#L706)</sub>
