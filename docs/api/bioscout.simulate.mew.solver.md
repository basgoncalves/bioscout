# `bioscout.simulate.mew.solver`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/solver.py)

The one solver. Static optimisation, EMG-informed and hybrid are weights.

Objective, per frame, over activations ``a`` in [0,1]^nm:

    J(a) = alpha * || W (R F(a) - M_target) ||^2      moment tracking  
         + beta  * || a ||^2                          effort  
         + gamma * || S (a - a_emg) ||^2              EMG tracking (mapped muscles)  
         + delta * || a - a_prev ||^2                 temporal smoothing  
         + eps   * || a - a_prior ||^2                ML / warm-start prior

With a rigid tendon, F(a) = gain * a + passive is AFFINE in a, so the whole  
objective is a bounded linear least squares -- microseconds per frame via  
``scipy.optimize.lsq_linear``. That is the fast path and the default.

Residual actuators: the moment a solution cannot produce is reported rather  
than forced. A large residual is the honest signal that the model could not  
explain the data, and it is what drives the confidence score down.

## Contents

- class [`SolverWeights`](#solverweights) — Weights ARE the mode. See MODE_PRESETS.
  - [`SolverWeights.as_dict`](#solverweightsas_dict) — 
- class [`SolveResult`](#solveresult) — 
- class [`FrameSolver`](#framesolver) — Solve one trial frame by frame, warm-starting from the previous frame.
  - [`FrameSolver.solve`](#framesolversolve) — Parameters ---------- l_mt          (nt, nm)        MTU lengths (m) v_mt          (nt, nm)        MTU velocities (m/s) moment_arms   (nt, ndof, nm)  moment arms (m) moment_target (nt, ndof)      moments to track (Nm) a_emg         (nt, nm)        EMG-derived activation, or None emg_mask      (nm,) bool      which muscles EMG actually informs a_prior       (nt, nm)        ML prior, or None
- [`solve_trial`](#solve_trial) — Convenience wrapper: pick a preset (or pass explicit weights) and solve.

<a id="solverweights"></a>

## class `SolverWeights`

Weights ARE the mode. See MODE_PRESETS.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/solver.py#L30)</sub>

<a id="solverweightsas_dict"></a>

### `SolverWeights.as_dict`

```python
SolverWeights.as_dict()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/solver.py#L39)</sub>

<a id="solveresult"></a>

## class `SolveResult`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/solver.py#L54)</sub>

<a id="framesolver"></a>

## class `FrameSolver`

```python
FrameSolver(
    mtu: RigidTendonMTU,
    weights: SolverWeights,
    dof_weights: Optional[np.ndarray] = None,
    max_force_scale: float = 1.0,
    passes: Optional[int] = None,
    tol: float = 0.001
)
```

| input | type | default |
|---|---|---|
| `mtu` | RigidTendonMTU | required |
| `weights` | SolverWeights | required |
| `dof_weights` | Optional[np.ndarray] | `None` |
| `max_force_scale` | float | `1.0` |
| `passes` | Optional[int] | `None` |
| `tol` | float | `0.001` |

Solve one trial frame by frame, warm-starting from the previous frame.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/solver.py#L66)</sub>

<a id="framesolversolve"></a>

### `FrameSolver.solve`

```python
FrameSolver.solve(
    l_mt,
    v_mt,
    moment_arms,
    moment_target,
    a_emg=None,
    emg_mask=None,
    a_prior=None,
    dt=None
) -> SolveResult
```

| input | type | default |
|---|---|---|
| `l_mt` | – | required |
| `v_mt` | – | required |
| `moment_arms` | – | required |
| `moment_target` | – | required |
| `a_emg` | – | `None` |
| `emg_mask` | – | `None` |
| `a_prior` | – | `None` |
| `dt` | – | `None` |

**returns** `SolveResult`

  
**Parameters**

l_mt          (nt, nm)        MTU lengths (m)  
v_mt          (nt, nm)        MTU velocities (m/s)  
moment_arms   (nt, ndof, nm)  moment arms (m)  
moment_target (nt, ndof)      moments to track (Nm)  
a_emg         (nt, nm)        EMG-derived activation, or None  
emg_mask      (nm,) bool      which muscles EMG actually informs  
a_prior       (nt, nm)        ML prior, or None

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/solver.py#L85)</sub>

### `solve_trial`

```python
solve_trial(
    mtu,
    l_mt,
    v_mt,
    moment_arms,
    moment_target,
    mode='emg_informed',
    weights=None,
    a_emg=None,
    emg_mask=None,
    a_prior=None,
    dof_weights=None,
    dt=None
) -> SolveResult
```

| input | type | default |
|---|---|---|
| `mtu` | – | required |
| `l_mt` | – | required |
| `v_mt` | – | required |
| `moment_arms` | – | required |
| `moment_target` | – | required |
| `mode` | – | `'emg_informed'` |
| `weights` | – | `None` |
| `a_emg` | – | `None` |
| `emg_mask` | – | `None` |
| `a_prior` | – | `None` |
| `dof_weights` | – | `None` |
| `dt` | – | `None` |

**returns** `SolveResult`

Convenience wrapper: pick a preset (or pass explicit weights) and solve.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/solver.py#L214)</sub>
