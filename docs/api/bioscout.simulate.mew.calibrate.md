# `bioscout.simulate.mew.calibrate`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/calibrate.py)

Subject calibration: fit MTU parameters theta to a subject's own trials.

Same objective as the solver, one level up. The inner loop solves activations  
given theta; the outer loop moves theta to make the inner loop's job easier --  
smaller moment residual and better EMG agreement.

Bounds are expressed as FRACTIONS of the generic value, matching bioscout's  
``session.yaml`` ``calibration:`` block, so an existing calibration config maps  
straight across.

## Contents

- class [`CalibrationSpec`](#calibrationspec) — What is free, over which trials, and how hard to try.
- class [`TrialData`](#trialdata) — One calibration trial, pre-computed so the outer loop never re-reads disk.
- [`default_groups`](#default_groups) — Group muscles by name stem so calibration fits ~8 numbers, not ~400.
- [`prepare`](#prepare) — Run an analyser's input pipeline without solving, to build TrialData.
- [`objective`](#objective) — Total cost across trials: normalised moment residual + EMG disagreement.
- [`calibrate`](#calibrate) — Fit theta. Returns calibrated MuscleParameters; save with :func:`save`.
- [`save`](#save) — 
- [`load`](#load) — 

<a id="calibrationspec"></a>

## class `CalibrationSpec`

What is free, over which trials, and how hard to try.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/calibrate.py#L35)</sub>

<a id="trialdata"></a>

## class `TrialData`

One calibration trial, pre-computed so the outer loop never re-reads disk.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/calibrate.py#L65)</sub>

### `default_groups`

```python
default_groups(muscles: Sequence[str]) -> Dict[str, List[str]]
```

| input | type | default |
|---|---|---|
| `muscles` | Sequence[str] | required |

**returns** `Dict[str, List[str]]`

Group muscles by name stem so calibration fits ~8 numbers, not ~400.

``vasmed_r``/``vaslat_r``/``vasint_r`` share a group; left and right stay  
separate (they are genuinely different in a patient population, which is the  
whole point in FAIS).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/calibrate.py#L48)</sub>

### `prepare`

```python
prepare(analyser, trial_names=None) -> List[TrialData]
```

| input | type | default |
|---|---|---|
| `analyser` | – | required |
| `trial_names` | – | `None` |

**returns** `List[TrialData]`

Run an analyser's input pipeline without solving, to build TrialData.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/calibrate.py#L76)</sub>

### `objective`

```python
objective(params, trials: List[TrialData], weights, tendon='rigid') -> float
```

| input | type | default |
|---|---|---|
| `params` | – | required |
| `trials` | List[TrialData] | required |
| `weights` | – | required |
| `tendon` | – | `'rigid'` |

**returns** `float`

Total cost across trials: normalised moment residual + EMG disagreement.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/calibrate.py#L118)</sub>

### `calibrate`

```python
calibrate(
    params: MuscleParameters,
    trials: List[TrialData],
    spec: Optional[CalibrationSpec] = None,
    tendon='rigid',
    verbose=True
) -> MuscleParameters
```

| input | type | default |
|---|---|---|
| `params` | MuscleParameters | required |
| `trials` | List[TrialData] | required |
| `spec` | Optional[CalibrationSpec] | `None` |
| `tendon` | – | `'rigid'` |
| `verbose` | – | `True` |

**returns** `MuscleParameters`

Fit theta. Returns calibrated MuscleParameters; save with :func:`save`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/calibrate.py#L134)</sub>

### `save`

```python
save(params: MuscleParameters, path) -> str
```

| input | type | default |
|---|---|---|
| `params` | MuscleParameters | required |
| `path` | – | required |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/calibrate.py#L168)</sub>

### `load`

```python
load(path) -> MuscleParameters
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `MuscleParameters`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/calibrate.py#L176)</sub>
