# `bioscout.simulate.mew.tiers`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/tiers.py)

Tier selection and moment sources -- the "always answers" machinery.

A missing input does not change the code path; it changes a weight and raises a  
flag. What it CAN change is where the joint moments come from, and that is what  
:class:`MomentSource` makes explicit.

## Contents

- class [`MomentSource`](#momentsource) — Joint moments to track. Every implementation states what it really is.
  - [`MomentSource.moments`](#momentsourcemoments) — 
- class [`MeasuredGRFMoments`](#measuredgrfmoments) — Real inverse dynamics from measured GRF -- the only fully trustworthy source.
  - [`MeasuredGRFMoments.moments`](#measuredgrfmomentsmoments) — 
- class [`PredictedGRFMoments`](#predictedgrfmoments) — GRF predicted from kinematics + mass, then inverse dynamics.
  - [`PredictedGRFMoments.moments`](#predictedgrfmomentsmoments) — 
- class [`ScaledTemplateMoments`](#scaledtemplatemoments) — Mass- and height-scaled normative moment curves for the detected task.
  - [`ScaledTemplateMoments.moments`](#scaledtemplatemomentsmoments) — 
- [`select_tier`](#select_tier) — Highest tier the inputs support, plus the moment source, weights, warnings.
- [`score_confidence`](#score_confidence) — Tier prior x moment-source factor x how much moment went unexplained.

<a id="momentsource"></a>

## class `MomentSource`

Joint moments to track. Every implementation states what it really is.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/tiers.py#L21)</sub>

<a id="momentsourcemoments"></a>

### `MomentSource.moments`

```python
MomentSource.moments(
    times: np.ndarray,
    dofs: List[str],
    inputs: TrialInputs,
    subject
) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `times` | np.ndarray | required |
| `dofs` | List[str] | required |
| `inputs` | TrialInputs | required |
| `subject` | – | required |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/tiers.py#L27)</sub>

<a id="measuredgrfmoments"></a>

## class `MeasuredGRFMoments`(MomentSource)

Real inverse dynamics from measured GRF -- the only fully trustworthy source.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/tiers.py#L32)</sub>

<a id="measuredgrfmomentsmoments"></a>

### `MeasuredGRFMoments.moments`

```python
MeasuredGRFMoments.moments(times, dofs, inputs, subject)
```

| input | type | default |
|---|---|---|
| `times` | – | required |
| `dofs` | – | required |
| `inputs` | – | required |
| `subject` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/tiers.py#L37)</sub>

<a id="predictedgrfmoments"></a>

## class `PredictedGRFMoments`(MomentSource)

```python
PredictedGRFMoments(predictor=None)
```

| input | type | default |
|---|---|---|
| `predictor` | – | `None` |

GRF predicted from kinematics + mass, then inverse dynamics.

The route to camera-only estimation. Needs a trained predictor from  
:mod:`mew.ml`; raises a clear error rather than guessing.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/tiers.py#L48)</sub>

<a id="predictedgrfmomentsmoments"></a>

### `PredictedGRFMoments.moments`

```python
PredictedGRFMoments.moments(times, dofs, inputs, subject)
```

| input | type | default |
|---|---|---|
| `times` | – | required |
| `dofs` | – | required |
| `inputs` | – | required |
| `subject` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/tiers.py#L61)</sub>

<a id="scaledtemplatemoments"></a>

## class `ScaledTemplateMoments`(MomentSource)

Mass- and height-scaled normative moment curves for the detected task.

Deliberately crude: it exists so tier 0 returns SOMETHING rather than  
failing, and its confidence factor says so. Never present a tier-0 result as  
a measurement.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/tiers.py#L70)</sub>

<a id="scaledtemplatemomentsmoments"></a>

### `ScaledTemplateMoments.moments`

```python
ScaledTemplateMoments.moments(times, dofs, inputs, subject)
```

| input | type | default |
|---|---|---|
| `times` | – | required |
| `dofs` | – | required |
| `inputs` | – | required |
| `subject` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/tiers.py#L92)</sub>

### `select_tier`

```python
select_tier(
    inputs: TrialInputs,
    subject,
    pin: Optional[Tier] = None
) -> Tuple[Tier, MomentSource, SolverWeights, List[str]]
```

| input | type | default |
|---|---|---|
| `inputs` | TrialInputs | required |
| `subject` | – | required |
| `pin` | Optional[Tier] | `None` |

**returns** `Tuple[Tier, MomentSource, SolverWeights, List[str]]`

Highest tier the inputs support, plus the moment source, weights, warnings.

``pin`` forces a tier; if the inputs cannot support it, that is an error --  
silently running a lower tier than asked for is exactly the failure mode  
this package exists to avoid.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/tiers.py#L124)</sub>

### `score_confidence`

```python
score_confidence(
    tier: Tier,
    source: MomentSource,
    residual,
    target,
    n_failed=0,
    n_frames=1
) -> float
```

| input | type | default |
|---|---|---|
| `tier` | Tier | required |
| `source` | MomentSource | required |
| `residual` | – | required |
| `target` | – | required |
| `n_failed` | – | `0` |
| `n_frames` | – | `1` |

**returns** `float`

Tier prior x moment-source factor x how much moment went unexplained.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/tiers.py#L193)</sub>
