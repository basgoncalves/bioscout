# `bioscout.model.tps.model_compat`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/model_compat.py)

Check whether a bone-landmark template can be reused across generic models.

The bone landmarks (``ASIS_r``, ``femur_r_center``, ``knee_r_med`` …) are stored  
as marker locations **expressed in a model's body frames**. That template is  
therefore only valid for another generic model if the two models put their  
pelvis/femur/tibia/patella frames in the same place.

For the Arnold-lineage models used in this project (GPK, Catelli, Lernagopal and  
Rajagopal2015) that happens to be true: each attaches the *same* bone meshes  
(``r_femur.vtp``, ``l_pelvis.vtp`` …) to the corresponding body at identity  
transform with scale ``1 1 1``, which pins the body frame to the mesh frame. So  
one template covers all four — but that is a property to *verify per model*, not  
to assume, which is what this module is for.

    >>> from bioscout.model.tps.model_compat import compare_bone_frames  
    >>> rep = compare_bone_frames(gpk, rajagopal)  
    >>> rep.compatible, rep.summary()

The check is conservative: anything it cannot prove identical is reported as a  
mismatch, and the caller decides whether to proceed.

## Contents

- class [`BodyGeometry`](#bodygeometry) — What a model attaches to one body, in that body's own frame.
- class [`CompatibilityReport`](#compatibilityreport) — 
  - [`CompatibilityReport.compatible`](#compatibilityreportcompatible) — 
  - [`CompatibilityReport.summary`](#compatibilityreportsummary) — 
- [`read_bone_geometry`](#read_bone_geometry) — Map ``body -> BodyGeometry`` for the bodies that matter to the TPS.
- [`compare_bone_frames`](#compare_bone_frames) — Verify that ``target_model`` shares ``reference_model``'s bone frames.
- [`assert_template_compatible`](#assert_template_compatible) — Log the compatibility report; raise on failure when ``strict``.

<a id="bodygeometry"></a>

## class `BodyGeometry`

What a model attaches to one body, in that body's own frame.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/model_compat.py#L54)</sub>

<a id="compatibilityreport"></a>

## class `CompatibilityReport`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/model_compat.py#L88)</sub>

<a id="compatibilityreportcompatible"></a>

### `CompatibilityReport.compatible`

```python
CompatibilityReport.compatible() -> bool
```

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/model_compat.py#L98)</sub>

<a id="compatibilityreportsummary"></a>

### `CompatibilityReport.summary`

```python
CompatibilityReport.summary() -> str
```

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/model_compat.py#L106)</sub>

### `read_bone_geometry`

```python
read_bone_geometry(
    model: str | Path,
    bodies: Sequence[str] = DEFAULT_BODIES
) -> Dict[str, BodyGeometry]
```

| input | type | default |
|---|---|---|
| `model` | str \| Path | required |
| `bodies` | Sequence[str] | `DEFAULT_BODIES` |

**returns** `Dict[str, BodyGeometry]`

Map ``body -> BodyGeometry`` for the bodies that matter to the TPS.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/model_compat.py#L61)</sub>

### `compare_bone_frames`

```python
compare_bone_frames(
    reference_model: str | Path,
    target_model: str | Path,
    bodies: Sequence[str] = DEFAULT_BODIES,
    atol: float = 1e-09
) -> CompatibilityReport
```

| input | type | default |
|---|---|---|
| `reference_model` | str \| Path | required |
| `target_model` | str \| Path | required |
| `bodies` | Sequence[str] | `DEFAULT_BODIES` |
| `atol` | float | `1e-09` |

**returns** `CompatibilityReport`

Verify that ``target_model`` shares ``reference_model``'s bone frames.

Two bodies are treated as sharing a frame when both models attach the same  
bone mesh file(s) to that body with the same scale factors and the same  
(identity, in practice) local transform. That is a sufficient condition:  
the mesh vertices are in a fixed anatomical frame, so pinning the same mesh  
unscaled and untranslated pins the same body frame.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/model_compat.py#L127)</sub>

### `assert_template_compatible`

```python
assert_template_compatible(
    reference_model: str | Path,
    target_model: str | Path,
    bodies: Sequence[str] = DEFAULT_BODIES,
    strict: bool = True
) -> CompatibilityReport
```

| input | type | default |
|---|---|---|
| `reference_model` | str \| Path | required |
| `target_model` | str \| Path | required |
| `bodies` | Sequence[str] | `DEFAULT_BODIES` |
| `strict` | bool | `True` |

**returns** `CompatibilityReport`

Log the compatibility report; raise on failure when ``strict``.

Call this before reusing a bone-landmark template built on  
``reference_model`` to personalise ``target_model``. Running the TPS with an  
incompatible template does not error — it silently produces a warp fitted  
between mismatched frames, i.e. a plausible-looking but wrong model. Failing  
loudly here is the whole point.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/model_compat.py#L177)</sub>
