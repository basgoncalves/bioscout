# `bioscout.model.scale_muscle_forces`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale_muscle_forces.py)

bioscout.model.scale_muscle_forces - allometric and athlete-specific Fmax scaling (session.yaml `fmax_scaling`).

Maximum isometric force is proportional to PCSA = V / Lopt. OpenSim's ScaleTool  
changes segment lengths (and so Lopt/Lts) and segment masses, but it never  
touches max_isometric_force. A generic 75 kg model scaled to a 91 kg athlete  
therefore keeps 75 kg muscles. This module restores the missing strength from  
MRI-based volume data:

Handsfield et al. (2014) J Biomech 47:631-638, n = 24 healthy adults (Fig. 5)  
    V_tot = 47 * m * h + 1285        R2 = 0.92   (cm3; m in kg, h in m)  [default]  
    V_tot = 91 * m + 588             R2 = 0.85  
    V_tot = 119 * h - 13361          R2 = 0.64   (h in cm)  
    V_tot is the total unilateral lower-limb muscle volume. Individual muscle  
    volumes are a near-constant fraction of V_tot (Fig. 2A), so every muscle  
    scales with the same volume ratio.

Handsfield et al. (2017) Scand J Med Sci Sports 27:1050-1060, elite sprinters  
    Muscle volume per height-mass was 22 % larger in total than in the 2014  
    non-sprinters, and the increase was not uniform (Table 1). SPRINTER_PCT_DIFF  
    holds the per-muscle % differences, available as an optional "trained athlete"  
    profile (sprinters, not powerlifters: use it as a documented proxy).

Scaling rule applied to each muscle i:

    V_ratio   = V_tot(subject) / V_tot(reference)  
    F_i'      = F_i * V_ratio / L_ratio * A_i * extra

    L_ratio   = length scale of the muscle (Lopt' / Lopt, taken from the model  
                pair when given; 1.0 otherwise, i.e. volume ratio only)  
    A_i       = 1 + SPRINTER_PCT_DIFF[muscle] / 100 when athlete="sprinter", else 1  
    extra     = free multiplier (e.g. the old mvic factor), default 1

Reference: the Rajagopal-family generics (Rajagopal, Lernagopal, GPK) were built  
from the Handsfield 2014 volumes for a 1.70 m, 75.337 kg subject, which are the  
defaults below.

## Contents

- [`total_muscle_volume`](#total_muscle_volume) — Total unilateral lower-limb muscle volume (cm3), Handsfield et al. 2014.
- [`volume_ratio`](#volume_ratio) — 
- [`handsfield_name`](#handsfield_name) — 'glmax2_r' -> 'gluteus_maximus'; 'addmagDist_l' -> 'adductor_magnus'.
- [`athlete_factor`](#athlete_factor) — 1 + % difference / 100 for the muscle, or 1 (no profile / unmapped muscle).
- [`scale_max_isometric_force`](#scale_max_isometric_force) — Write model_out with scaled max_isometric_force; return {muscle: factor}.

### `total_muscle_volume`

```python
total_muscle_volume(
    mass_kg: float,
    height_m: float | None = None,
    method: str = 'height_mass'
) -> float
```

| input | type | default |
|---|---|---|
| `mass_kg` | float | required |
| `height_m` | float \| None | `None` |
| `method` | str | `'height_mass'` |

**returns** `float`

Total unilateral lower-limb muscle volume (cm3), Handsfield et al. 2014.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale_muscle_forces.py#L45)</sub>

### `volume_ratio`

```python
volume_ratio(
    mass_kg,
    height_m,
    ref_mass_kg=REF_MASS_KG,
    ref_height_m=REF_HEIGHT_M,
    method='height_mass'
) -> float
```

| input | type | default |
|---|---|---|
| `mass_kg` | – | required |
| `height_m` | – | required |
| `ref_mass_kg` | – | `REF_MASS_KG` |
| `ref_height_m` | – | `REF_HEIGHT_M` |
| `method` | – | `'height_mass'` |

**returns** `float`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale_muscle_forces.py#L57)</sub>

### `handsfield_name`

```python
handsfield_name(osim_muscle: str) -> str | None
```

| input | type | default |
|---|---|---|
| `osim_muscle` | str | required |

**returns** `str \| None`

'glmax2_r' -> 'gluteus_maximus'; 'addmagDist_l' -> 'adductor_magnus'.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale_muscle_forces.py#L117)</sub>

### `athlete_factor`

```python
athlete_factor(osim_muscle: str, athlete: str | None = None) -> float
```

| input | type | default |
|---|---|---|
| `osim_muscle` | str | required |
| `athlete` | str \| None | `None` |

**returns** `float`

1 + % difference / 100 for the muscle, or 1 (no profile / unmapped muscle).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale_muscle_forces.py#L126)</sub>

### `scale_max_isometric_force`

```python
scale_max_isometric_force(
    model_in: str,
    model_out: str,
    mass_kg: float,
    height_m: float | None,
    ref_mass_kg: float = REF_MASS_KG,
    ref_height_m: float = REF_HEIGHT_M,
    method: str = 'height_mass',
    generic_model: str | None = None,
    athlete: str | None = None,
    extra: float = 1.0
) -> dict
```

| input | type | default |
|---|---|---|
| `model_in` | str | required |
| `model_out` | str | required |
| `mass_kg` | float | required |
| `height_m` | float \| None | required |
| `ref_mass_kg` | float | `REF_MASS_KG` |
| `ref_height_m` | float | `REF_HEIGHT_M` |
| `method` | str | `'height_mass'` |
| `generic_model` | str \| None | `None` |
| `athlete` | str \| None | `None` |
| `extra` | float | `1.0` |

**returns** `dict`

Write model_out with scaled max_isometric_force; return {muscle: factor}.

generic_model: the unscaled generic .osim. If given, each muscle's Lopt ratio  
(scaled / generic) is used as L_ratio, so F scales with PCSA = V / L.  
Without it, F scales with the volume ratio only.  
Text edit only; no OpenSim needed. Only max_isometric_force is changed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/scale_muscle_forces.py#L146)</sub>
