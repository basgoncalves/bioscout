# `bioscout.simulate.mew.mtu`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py)

Hill-type muscle-tendon unit: activation dynamics and force generation.

numpy only. Everything is vectorised over muscles, so one call evaluates the  
whole model at one frame (or, where noted, all frames at once).

Default is a RIGID TENDON, which makes muscle force a closed-form function of  
``(l_mt, v_mt, a)`` with no per-frame root-find. That is what keeps the solver  
linear-in-activation (see solver.py) and the real-time path viable. An elastic  
tendon path is provided for offline accuracy work.

## Contents

- class [`MuscleParameters`](#muscleparameters) — The vector theta. One entry per muscle, arrays ordered like ``names``.
  - [`MuscleParameters.n`](#muscleparametersn) — 
  - [`MuscleParameters.index`](#muscleparametersindex) — 
  - [`MuscleParameters.subset`](#muscleparameterssubset) — 
  - [`MuscleParameters.copy`](#muscleparameterscopy) — 
  - [`MuscleParameters.defaults`](#muscleparametersdefaults) — Generic parameters; used when a value cannot be read from the model.
  - [`MuscleParameters.to_dict`](#muscleparametersto_dict) — 
  - [`MuscleParameters.from_dict`](#muscleparametersfrom_dict) — 
- class [`MuscleState`](#musclestate) — The MTU at one frame, LINEARISED in activation: F = gain * a + passive.
- class [`RigidTendonMTU`](#rigidtendonmtu) — Rigid tendon: fibre length follows MTU length directly.
  - [`RigidTendonMTU.fibre_length`](#rigidtendonmtufibre_length) — 
  - [`RigidTendonMTU.cos_pennation`](#rigidtendonmtucos_pennation) — 
  - [`RigidTendonMTU.state`](#rigidtendonmtustate) — Linearised state at this frame. ``a`` is ignored for a rigid tendon.
  - [`RigidTendonMTU.force`](#rigidtendonmtuforce) — Tendon force (N) for activations ``a`` at a precomputed state.
  - [`RigidTendonMTU.force_from_length`](#rigidtendonmtuforce_from_length) — 
  - [`RigidTendonMTU.operating_range`](#rigidtendonmtuoperating_range) — Where each muscle sits on the force-length curve across a trial.
- class [`ElasticTendonMTU`](#elastictendonmtu) — Elastic tendon via per-frame fibre-length equilibrium.
  - [`ElasticTendonMTU.equilibrium_fibre_length`](#elastictendonmtuequilibrium_fibre_length) — 
  - [`ElasticTendonMTU.state`](#elastictendonmtustate) — Equilibrium fibre length at activation ``a``, linearised there.
  - [`ElasticTendonMTU.force_from_length`](#elastictendonmtuforce_from_length) — 
- [`scale_parameters`](#scale_parameters) — Scale generic MTU parameters to a participant from height and mass alone.
- [`emg_to_activation`](#emg_to_activation) — Nonlinear EMG-to-activation transfer (Lloyd & Besier 2003).
- [`activation_dynamics`](#activation_dynamics) — First-order activation dynamics over a whole excitation time series.
- [`f_active_length`](#f_active_length) — Active force-length. Gaussian approximation, ~Thelen 2003 (kshape 0.45).
- [`f_passive_length`](#f_passive_length) — Passive force-length, exponential (Thelen 2003). Zero below l_norm = 1.
- [`f_velocity`](#f_velocity) — Force-velocity. ``v_norm`` in optimal-fibre-lengths per second, divided by v_max: negative = shortening.
- [`f_tendon`](#f_tendon) — Normalised tendon force from tendon strain (Thelen 2003 exponential).
- [`build_mtu`](#build_mtu) — ``"rigid"`` | ``"elastic"`` | ``"auto"``.

<a id="muscleparameters"></a>

## class `MuscleParameters`

The vector theta. One entry per muscle, arrays ordered like ``names``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L23)</sub>

<a id="muscleparametersn"></a>

### `MuscleParameters.n`

```python
MuscleParameters.n() -> int
```

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L38)</sub>

<a id="muscleparametersindex"></a>

### `MuscleParameters.index`

```python
MuscleParameters.index(muscle) -> int
```

| input | type | default |
|---|---|---|
| `muscle` | – | required |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L41)</sub>

<a id="muscleparameterssubset"></a>

### `MuscleParameters.subset`

```python
MuscleParameters.subset(names: Sequence[str]) -> 'MuscleParameters'
```

| input | type | default |
|---|---|---|
| `names` | Sequence[str] | required |

**returns** `'MuscleParameters'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L44)</sub>

<a id="muscleparameterscopy"></a>

### `MuscleParameters.copy`

```python
MuscleParameters.copy() -> 'MuscleParameters'
```

**returns** `'MuscleParameters'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L53)</sub>

<a id="muscleparametersdefaults"></a>

### `MuscleParameters.defaults`

```python
MuscleParameters.defaults(
    names: Sequence[str],
    f_max=None,
    l_opt=None,
    l_ts=None,
    alpha_0=None
) -> 'MuscleParameters'
```

| input | type | default |
|---|---|---|
| `names` | Sequence[str] | required |
| `f_max` | – | `None` |
| `l_opt` | – | `None` |
| `l_ts` | – | `None` |
| `alpha_0` | – | `None` |

**returns** `'MuscleParameters'`

Generic parameters; used when a value cannot be read from the model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L60)</sub>

<a id="muscleparametersto_dict"></a>

### `MuscleParameters.to_dict`

```python
MuscleParameters.to_dict() -> dict
```

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L78)</sub>

<a id="muscleparametersfrom_dict"></a>

### `MuscleParameters.from_dict`

```python
MuscleParameters.from_dict(d: dict) -> 'MuscleParameters'
```

| input | type | default |
|---|---|---|
| `d` | dict | required |

**returns** `'MuscleParameters'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L85)</sub>

<a id="musclestate"></a>

## class `MuscleState`

The MTU at one frame, LINEARISED in activation: F = gain * a + passive.

Splitting the state out this way is what makes the solver fast: the joint  
moment is then linear in ``a`` and the frame solves as a bounded least  
squares.

With a rigid tendon the split is exact. With an elastic tendon the fibre  
length itself depends on activation, so the state is built at a GUESSED  
activation and the solver iterates (see ``FrameSolver(..., passes=)``) --  
exact at convergence, and still one linear solve per pass.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L221)</sub>

<a id="rigidtendonmtu"></a>

## class `RigidTendonMTU`

```python
RigidTendonMTU(params: MuscleParameters)
```

| input | type | default |
|---|---|---|
| `params` | MuscleParameters | required |

Rigid tendon: fibre length follows MTU length directly.

l_m = (l_mt - l_ts) / cos(pennation), with pennation from the constant  
muscle-thickness assumption  l_m*sin(alpha) = l_opt*sin(alpha_0).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L243)</sub>

<a id="rigidtendonmtufibre_length"></a>

### `RigidTendonMTU.fibre_length`

```python
RigidTendonMTU.fibre_length(l_mt: np.ndarray) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `l_mt` | np.ndarray | required |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L255)</sub>

<a id="rigidtendonmtucos_pennation"></a>

### `RigidTendonMTU.cos_pennation`

```python
RigidTendonMTU.cos_pennation(l_m: np.ndarray) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `l_m` | np.ndarray | required |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L261)</sub>

<a id="rigidtendonmtustate"></a>

### `RigidTendonMTU.state`

```python
RigidTendonMTU.state(
    l_mt: np.ndarray,
    v_mt: np.ndarray,
    a=None,
    l_m_prev=None,
    dt=None
) -> MuscleState
```

| input | type | default |
|---|---|---|
| `l_mt` | np.ndarray | required |
| `v_mt` | np.ndarray | required |
| `a` | – | `None` |
| `l_m_prev` | – | `None` |
| `dt` | – | `None` |

**returns** `MuscleState`

Linearised state at this frame. ``a`` is ignored for a rigid tendon.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L268)</sub>

<a id="rigidtendonmtuforce"></a>

### `RigidTendonMTU.force`

```python
RigidTendonMTU.force(a: np.ndarray, state: MuscleState) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `a` | np.ndarray | required |
| `state` | MuscleState | required |

**returns** `np.ndarray`

Tendon force (N) for activations ``a`` at a precomputed state.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L291)</sub>

<a id="rigidtendonmtuforce_from_length"></a>

### `RigidTendonMTU.force_from_length`

```python
RigidTendonMTU.force_from_length(a, l_mt, v_mt) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `a` | – | required |
| `l_mt` | – | required |
| `v_mt` | – | required |

**returns** `np.ndarray`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L295)</sub>

<a id="rigidtendonmtuoperating_range"></a>

### `RigidTendonMTU.operating_range`

```python
RigidTendonMTU.operating_range(l_mt: np.ndarray) -> 'dict'
```

| input | type | default |
|---|---|---|
| `l_mt` | np.ndarray | required |

**returns** `'dict'`

Where each muscle sits on the force-length curve across a trial.

THE most useful diagnostic in the package. A muscle stuck far down the  
ascending limb cannot generate force whatever the solver does, so the  
moment goes to the reserves and the result looks like a solver failure  
when it is really a tendon-slack-length problem. Long-tendon muscles  
(soleus, gastrocs: tendon/fibre > 6) are where this bites.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L299)</sub>

<a id="elastictendonmtu"></a>

## class `ElasticTendonMTU`(RigidTendonMTU)

```python
ElasticTendonMTU(params: MuscleParameters, tol=1e-06, max_iter=30)
```

| input | type | default |
|---|---|---|
| `params` | MuscleParameters | required |
| `tol` | – | `1e-06` |
| `max_iter` | – | `30` |

Elastic tendon via per-frame fibre-length equilibrium.

Slower (a scalar root-find per muscle per frame) and NOT linear in  
activation, so the solver falls back to SLSQP. Use for offline accuracy  
work; benchmark against the rigid path before trusting the extra cost.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L319)</sub>

<a id="elastictendonmtuequilibrium_fibre_length"></a>

### `ElasticTendonMTU.equilibrium_fibre_length`

```python
ElasticTendonMTU.equilibrium_fibre_length(a, l_mt, v_mt=None)
```

| input | type | default |
|---|---|---|
| `a` | – | required |
| `l_mt` | – | required |
| `v_mt` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L331)</sub>

<a id="elastictendonmtustate"></a>

### `ElasticTendonMTU.state`

```python
ElasticTendonMTU.state(l_mt, v_mt, a=None, l_m_prev=None, dt=None) -> MuscleState
```

| input | type | default |
|---|---|---|
| `l_mt` | – | required |
| `v_mt` | – | required |
| `a` | – | `None` |
| `l_m_prev` | – | `None` |
| `dt` | – | `None` |

**returns** `MuscleState`

Equilibrium fibre length at activation ``a``, linearised there.

Fibre velocity cannot come from ``v_mt`` here -- with a compliant tendon  
the fibre and the whole MTU move differently, and at the ankle they can  
move in OPPOSITE directions. It is estimated from the previous frame's  
equilibrium fibre length instead, which is causal and is what a forward  
EMG-driven simulation does. The first frame falls back to ``v_mt``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L357)</sub>

<a id="elastictendonmtuforce_from_length"></a>

### `ElasticTendonMTU.force_from_length`

```python
ElasticTendonMTU.force_from_length(a, l_mt, v_mt=None)
```

| input | type | default |
|---|---|---|
| `a` | – | required |
| `l_mt` | – | required |
| `v_mt` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L386)</sub>

### `scale_parameters`

```python
scale_parameters(
    params: MuscleParameters,
    height=None,
    mass=None,
    ref_mass=REF_MASS,
    ref_height=REF_HEIGHT
) -> MuscleParameters
```

| input | type | default |
|---|---|---|
| `params` | MuscleParameters | required |
| `height` | – | `None` |
| `mass` | – | `None` |
| `ref_mass` | – | `REF_MASS` |
| `ref_height` | – | `REF_HEIGHT` |

**returns** `MuscleParameters`

Scale generic MTU parameters to a participant from height and mass alone.

Force scales with physiological cross-sectional area, i.e. muscle VOLUME  
divided by fibre LENGTH. Muscle volume scales with body mass (Handsfield  
2014 reports volume ~ mass * height); fibre and tendon lengths scale with  
a linear dimension, i.e. height. Hence::

    l_opt, l_ts  <-  * (height / ref_height)  
    f_max        <-  * (mass*height) / (ref_mass*ref_height) / (height/ref_height)  
                  =  * (mass / ref_mass)

which is why F_max ends up essentially mass-proportional and lengths  
height-proportional. Written out rather than collapsed, because the two  
factors are separately arguable and someone will want to change one.

This is a PRIOR, not a personalisation. It exists so the pipeline never  
blocks on a calibration session; calibrate.py supersedes it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L101)</sub>

### `emg_to_activation`

```python
emg_to_activation(u: np.ndarray, shape_A: np.ndarray) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `u` | np.ndarray | required |
| `shape_A` | np.ndarray | required |

**returns** `np.ndarray`

Nonlinear EMG-to-activation transfer (Lloyd & Besier 2003).

    a = (exp(A*u) - 1) / (exp(A) - 1),   A in [-3, 0)

A -> 0 is linear; A -> -3 is strongly concave (low excitations produce  
relatively more activation).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L135)</sub>

### `activation_dynamics`

```python
activation_dynamics(
    u: np.ndarray,
    dt: float,
    params: MuscleParameters,
    a0: Optional[np.ndarray] = None
) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `u` | np.ndarray | required |
| `dt` | float | required |
| `params` | MuscleParameters | required |
| `a0` | Optional[np.ndarray] | `None` |

**returns** `np.ndarray`

First-order activation dynamics over a whole excitation time series.

``u`` is (nt, nm) neural excitation in 0-1. Returns activations (nt, nm).  
Uses the standard asymmetric time constants: activation is faster than  
deactivation.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L148)</sub>

### `f_active_length`

```python
f_active_length(l_norm: np.ndarray) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `l_norm` | np.ndarray | required |

**returns** `np.ndarray`

Active force-length. Gaussian approximation, ~Thelen 2003 (kshape 0.45).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L171)</sub>

### `f_passive_length`

```python
f_passive_length(l_norm: np.ndarray, k_pe=4.0, eps_0m=0.6) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `l_norm` | np.ndarray | required |
| `k_pe` | – | `4.0` |
| `eps_0m` | – | `0.6` |

**returns** `np.ndarray`

Passive force-length, exponential (Thelen 2003). Zero below l_norm = 1.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L177)</sub>

### `f_velocity`

```python
f_velocity(v_norm: np.ndarray, a_f=0.25, f_len=1.4) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `v_norm` | np.ndarray | required |
| `a_f` | – | `0.25` |
| `f_len` | – | `1.4` |

**returns** `np.ndarray`

Force-velocity. ``v_norm`` in optimal-fibre-lengths per second, divided  
by v_max: negative = shortening.

Hill hyperbola while shortening, saturating branch while lengthening.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L185)</sub>

### `f_tendon`

```python
f_tendon(strain: np.ndarray, k_t=35.0, eps_0t=0.033) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `strain` | np.ndarray | required |
| `k_t` | – | `35.0` |
| `eps_0t` | – | `0.033` |

**returns** `np.ndarray`

Normalised tendon force from tendon strain (Thelen 2003 exponential).

The exponent is clipped before exp(): during bisection the trial fibre  
length can imply an absurd tendon strain, and np.exp overflows to inf,  
which poisons the comparison the bisection is making. Above the physical  
strain range the curve is continued LINEARLY -- still monotonic, so the  
bisection converges, and never reached at the solution.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L198)</sub>

### `build_mtu`

```python
build_mtu(params: MuscleParameters, tendon='auto')
```

| input | type | default |
|---|---|---|
| `params` | MuscleParameters | required |
| `tendon` | – | `'auto'` |

``"rigid"`` | ``"elastic"`` | ``"auto"``.

``auto`` currently resolves to RIGID, and that is an evidence-based choice  
rather than a default nobody revisited. On FAIS 022/Run_baselineA1 the  
elastic path did NOT improve agreement with OpenSim SO (stance-limb median  
peak ratio 0.99 elastic vs 0.97 rigid; force-weighted R2 slightly worse),  
while costing ~4 linearisation passes per frame. Both are wrong in the same  
way and for the same reason -- generic, uncalibrated tendon slack lengths --  
so paying for tendon compliance buys nothing until l_ts is calibrated.  
Revisit this once tier 3 works: ``tendon="elastic"`` is fully implemented.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/mtu.py#L400)</sub>
