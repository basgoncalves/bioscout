# `bioscout.model.tps.scaling`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/scaling.py)

Subject-specific scaling helpers.

Ported from ``simFunctions.py`` and the ``ScalingDF`` class. The OpenSim-touching  
functions import ``opensim`` lazily so this module is importable without it.

NOTE: BioScout already provides model-scaling utilities. When integrating, prefer  
BioScout's versions and keep these only for the bone-dimension scaling-factor  
table (``scaling_factors``), which is specific to the TPS workflow.

## Contents

- [`total_model_mass`](#total_model_mass) — Sum of all body masses in an OpenSim model.
- [`scale_optimal_force_handsfield`](#scale_optimal_force_handsfield) — Scale muscle max isometric force by total-muscle-volume regression.
- [`set_max_contraction_velocity`](#set_max_contraction_velocity) — 
- [`scaling_factors`](#scaling_factors) — Per-segment dimension comparison (osim vs mri) and scale factors.

### `total_model_mass`

```python
total_model_mass(model) -> float
```

| input | type | default |
|---|---|---|
| `model` | – | required |

**returns** `float`

Sum of all body masses in an OpenSim model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/scaling.py#L19)</sub>

### `scale_optimal_force_handsfield`

```python
scale_optimal_force_handsfield(
    model_generic,
    model_scaled,
    height_generic: float,
    height_scaled: float
)
```

| input | type | default |
|---|---|---|
| `model_generic` | – | required |
| `model_scaled` | – | required |
| `height_generic` | float | required |
| `height_scaled` | float | required |

Scale muscle max isometric force by total-muscle-volume regression.

Uses the Handsfield et al. (2014) total-muscle-volume regression  
``Vtotal = 47 * mass * height + 1285`` and the original force-scale factor  
``(Vtotal_scaled/Vtotal_generic) / (lmo_scaled/lmo_generic)``.  
Behaviour identical to the original ``scaleOptimalForceSubjectSpecific``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/scaling.py#L25)</sub>

### `set_max_contraction_velocity`

```python
set_max_contraction_velocity(model, value: float)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `value` | float | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/scaling.py#L51)</sub>

### `scaling_factors`

```python
scaling_factors(osim_df: pd.DataFrame, mri_df: pd.DataFrame) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `osim_df` | pd.DataFrame | required |
| `mri_df` | pd.DataFrame | required |

**returns** `pd.DataFrame`

Per-segment dimension comparison (osim vs mri) and scale factors.

Reproduces ``ScalingDF`` for pelvis/femur/tibia heights, widths and depths.  
Returns a DataFrame with columns ``osim``, ``mri``, ``factors``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/scaling.py#L59)</sub>
