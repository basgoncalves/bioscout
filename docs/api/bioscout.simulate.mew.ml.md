# `bioscout.simulate.mew.ml`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py)

Optional ML layers. Torch is not required for anything else in the package.

Three distinct jobs, deliberately kept apart:

1. ``SurrogateSolver``  -- predict activations/forces directly. Fast; used as a  
   warm start (``Mew.ml_prior``, solver weight ``eps``) or, at the  
   extreme, in place of the solve for real-time use.  
2. ``GRFPredictor``     -- predict ground reaction forces from kinematics + mass,  
   so tier 0 can become a real inverse dynamics instead of a template.  
3. ``ActivationPredictor`` -- predict missing EMG channels from the ones present.

All three train on the SAME labels: tier-3 (or CEINMS) output from trials that  
DID have every input. That is the loop that makes the offline pipeline generate  
its own real-time model.

``FAIS_machine_learning/code/ml_model.py`` is the working prototype of (1); the  
intent is that it moves in here as ``SurrogateSolver`` rather than living as a  
parallel script.

## Contents

- class [`MLLayer`](#mllayer) — Common interface: everything is optional and says so if it is not trained.
  - [`MLLayer.require_trained`](#mllayerrequire_trained) — 
- class [`SurrogateSolver`](#surrogatesolver) — Predict activations (and hence forces) from kinematics + moments + EMG.
  - [`SurrogateSolver.activations`](#surrogatesolveractivations) — 
  - [`SurrogateSolver.from_fais_model`](#surrogatesolverfrom_fais_model) — Load the existing FAIS ml_model.py pickle. Bridge while porting.
- class [`GRFPredictor`](#grfpredictor) — Kinematics + mass -> ground reaction forces -> real inverse dynamics.
  - [`GRFPredictor.grf`](#grfpredictorgrf) — 
  - [`GRFPredictor.moments`](#grfpredictormoments) — Signature matches tiers.MomentSource so it plugs straight in.
- class [`ActivationPredictor`](#activationpredictor) — Fill in muscles with no electrode from the channels that do exist.
  - [`ActivationPredictor.fill`](#activationpredictorfill) — 
- [`torch_available`](#torch_available) — 

<a id="mllayer"></a>

## class `MLLayer`

Common interface: everything is optional and says so if it is not trained.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py#L35)</sub>

<a id="mllayerrequire_trained"></a>

### `MLLayer.require_trained`

```python
MLLayer.require_trained()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py#L41)</sub>

<a id="surrogatesolver"></a>

## class `SurrogateSolver`(MLLayer)

```python
SurrogateSolver(model=None, muscles: Optional[Sequence[str]] = None)
```

| input | type | default |
|---|---|---|
| `model` | – | `None` |
| `muscles` | Optional[Sequence[str]] | `None` |

Predict activations (and hence forces) from kinematics + moments + EMG.

Used as a PRIOR by default rather than a replacement: the physics solver  
still runs, warm-started, and the moment residual still tells you whether  
the prediction was any good. That keeps the ML honest -- a surrogate that  
drifts shows up as a rising residual instead of as plausible-looking forces.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py#L48)</sub>

<a id="surrogatesolveractivations"></a>

### `SurrogateSolver.activations`

```python
SurrogateSolver.activations(q, muscles: List[str], times: np.ndarray) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `q` | – | required |
| `muscles` | List[str] | required |
| `times` | np.ndarray | required |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py#L64)</sub>

<a id="surrogatesolverfrom_fais_model"></a>

### `SurrogateSolver.from_fais_model`

```python
SurrogateSolver.from_fais_model(pickle_path)
```

| input | type | default |
|---|---|---|
| `pickle_path` | – | required |

Load the existing FAIS ml_model.py pickle. Bridge while porting.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py#L73)</sub>

<a id="grfpredictor"></a>

## class `GRFPredictor`(MLLayer)

```python
GRFPredictor(model=None)
```

| input | type | default |
|---|---|---|
| `model` | – | `None` |

Kinematics + mass -> ground reaction forces -> real inverse dynamics.

The single highest-value model in the package: it is what turns a  
camera-only capture from tier 0 into tier 1.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py#L78)</sub>

<a id="grfpredictorgrf"></a>

### `GRFPredictor.grf`

```python
GRFPredictor.grf(q, subject) -> 'object'
```

| input | type | default |
|---|---|---|
| `q` | – | required |
| `subject` | – | required |

**returns** `'object'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py#L91)</sub>

<a id="grfpredictormoments"></a>

### `GRFPredictor.moments`

```python
GRFPredictor.moments(times, dofs, inputs, subject) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `times` | – | required |
| `dofs` | – | required |
| `inputs` | – | required |
| `subject` | – | required |

**returns** `np.ndarray`

Signature matches tiers.MomentSource so it plugs straight in.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py#L95)</sub>

<a id="activationpredictor"></a>

## class `ActivationPredictor`(MLLayer)

```python
ActivationPredictor(model=None)
```

| input | type | default |
|---|---|---|
| `model` | – | `None` |

Fill in muscles with no electrode from the channels that do exist.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py#L103)</sub>

<a id="activationpredictorfill"></a>

### `ActivationPredictor.fill`

```python
ActivationPredictor.fill(a_emg: np.ndarray, mask: np.ndarray) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `a_emg` | np.ndarray | required |
| `mask` | np.ndarray | required |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py#L112)</sub>

### `torch_available`

```python
torch_available() -> bool
```

**returns** `bool`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/ml.py#L27)</sub>
