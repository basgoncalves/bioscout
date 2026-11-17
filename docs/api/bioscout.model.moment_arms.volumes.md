# `bioscout.model.moment_arms.volumes`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/volumes.py)

Turn segmented muscle volumes into a wrap-radius factor.

The point of this module is to replace a hand-picked "scale the moment arm by  
1.3" with a number measured from the subject's own MRI.

Reasoning, first order: a wrap surface stands in for muscle bulk, and for a  
muscle of roughly constant length ``V = pi * r^2 * L``. With ``L`` already  
personalised by the TPS bone geometry, the radius that represents a measured  
volume ``V_subject`` against a reference ``V_ref`` is::

    r_new / r_old = sqrt(V_subject / V_ref)

This is a geometric argument, **not** an established scaling law — state it as  
an assumption in the methods. It also assumes the mask is the whole muscle  
belly and that the generic model's wrap radius corresponds to ``V_ref``.

``nibabel`` is imported lazily so the rest of the package works without it.

## Contents

- class [`MuscleVolume`](#musclevolume) — 
- [`measure_volume`](#measure_volume) — Volume of a binary NIfTI mask, in cm^3.
- [`measure_volumes`](#measure_volumes) — Measure every ``<muscle>_<left|right>.nii.gz`` under ``seg_dir``.
- [`radius_factor_from_volumes`](#radius_factor_from_volumes) — ``sqrt(V_subject / V_reference)`` — the wrap-radius factor.

<a id="musclevolume"></a>

## class `MuscleVolume`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/volumes.py#L45)</sub>

### `measure_volume`

```python
measure_volume(mask_path: str | Path, name: str = '', side: str = '') -> MuscleVolume
```

| input | type | default |
|---|---|---|
| `mask_path` | str \| Path | required |
| `name` | str | `''` |
| `side` | str | `''` |

**returns** `MuscleVolume`

Volume of a binary NIfTI mask, in cm^3.

Uses the affine's voxel dimensions, so it is correct for anisotropic scans.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/volumes.py#L54)</sub>

### `measure_volumes`

```python
measure_volumes(
    seg_dir: str | Path,
    muscles: Optional[Iterable[str]] = None,
    sides: Iterable[str] = ('r', 'l')
) -> Dict[str, MuscleVolume]
```

| input | type | default |
|---|---|---|
| `seg_dir` | str \| Path | required |
| `muscles` | Optional[Iterable[str]] | `None` |
| `sides` | Iterable[str] | `('r', 'l')` |

**returns** `Dict[str, MuscleVolume]`

Measure every ``<muscle>_<left|right>.nii.gz`` under ``seg_dir``.

Returns ``{"<muscle>_<side>": MuscleVolume}``; masks that are absent are  
skipped rather than raising, so a partial segmentation still yields what it  
can.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/volumes.py#L78)</sub>

### `radius_factor_from_volumes`

```python
radius_factor_from_volumes(subject_cm3: float, reference_cm3: float) -> float
```

| input | type | default |
|---|---|---|
| `subject_cm3` | float | required |
| `reference_cm3` | float | required |

**returns** `float`

``sqrt(V_subject / V_reference)`` — the wrap-radius factor.

Raises on non-positive inputs: a zero volume means the mask was empty or  
misnamed, and silently returning 1.0 would hide that.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/moment_arms/volumes.py#L102)</sub>
