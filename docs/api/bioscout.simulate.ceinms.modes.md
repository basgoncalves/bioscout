# `bioscout.simulate.ceinms.modes`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py)

CEINMS execution modes — how many solves, and what the result *is*.

CEINMS execution needs three objective weights (Sartori et al. 2014, Eq. 1):

    F_obj = alpha * E_trackMOM + beta * E_sumEXC + gamma * E_trackEMG

`alpha` weights joint-moment tracking, `beta` is an EFFORT penalty (sum of  
squared excitations), `gamma` is the EMG-TRACKING weight. Only the RATIOS  
beta/alpha and gamma/alpha are identifiable — scaling an objective cannot move  
its minimum — which is why alpha is conventionally fixed at 1.

Choosing gamma is not a solved problem, and the choice is not cosmetic: on the  
powerlifting dataset this module was written for, gamma moved hip contact force  
by several body weights. So `bioscout` does not pretend there is one right way  
to run CEINMS. It offers five, and asks you to say which one you used.

    single      one solve at the (alpha, beta, gamma) you name  
    bounds      three solves: lower, production, upper -> an estimate + a band  
    full_loop   a grid over the ranges you name -> a range + a median  
    lcurve      Sartori's L-curve sweep, production taken from the knee  
    optimise    CEINMSoptimise searches the weights itself (slow)

Set it in session.yaml::

    ceinms:  
      mode: bounds  
      alpha: 1  
      beta: 1  
      gamma: 30  
      gamma_bounds: [10, 100]

or in a project settings file as ``CEINMSSettings.mode``. Default is `single`,  
so existing projects keep their behaviour.

WHAT EACH MODE LEAVES ON DISK  
    Every mode writes one output folder per solve, named  
    ``Execution_a<alpha>_b<beta>_g<gamma>``, and a manifest  
    ``ceinms/ceinms_modes_manifest.json`` listing them with the production arm  
    flagged. The PRODUCTION arm is always solved LAST, so whatever the trial's  
    `jra_forces_ceinms` points at when the mode returns is the production  
    result -- a run that dies half way leaves a tree that is incomplete rather  
    than one that silently describes the wrong weighting.

A NOTE ON `lcurve`, WHICH IS WHY THE OTHER MODES EXIST  
    The L-curve procedure locates the knee of the trade-off between normalised  
    moment-tracking and EMG-tracking error. It is the published method and it  
    is implemented here faithfully, tie-break included. It is also, on some  
    datasets, NOT IDENTIFIABLE: when the curve is nearly flat past the elbow,  
    both axes are normalised to their own extremes and the knee tracks the  
    RANGE SWEPT rather than the data. Measured on this project's squat trials,  
    the knee came out at exactly one tenth of the upper bound of the gamma  
    range, in five nested ranges out of five.

    `lcurve` therefore reports `knee_gamma_over_range_top` in its manifest. If  
    that ratio is the same across two different sweeps, the knee is an artefact  
    of your grid and you should use `bounds` or `full_loop` and report a band  
    instead of a point.

## Contents

- class [`ModeError`](#modeerror) — 
- class [`ExecutionMode`](#executionmode) — The chosen CEINMS execution mode, and everything that follows from it.
  - [`ExecutionMode.mode`](#executionmodemode) — 
  - [`ExecutionMode.arms`](#executionmodearms) — The solves this mode will run, PRODUCTION LAST. For `lcurve` this is the sweep only — the production arm is appended once the knee is known, which is why it cannot be listed up front.
  - [`ExecutionMode.description`](#executionmodedescription) — 
  - [`ExecutionMode.n_solves`](#executionmoden_solves) — 
  - [`ExecutionMode.run`](#executionmoderun) — Execute every arm, production last, and write the manifest.
  - [`ExecutionMode.aggregate`](#executionmodeaggregate) — 
  - [`ExecutionMode.knee`](#executionmodeknee) — 
  - [`ExecutionMode.describe`](#executionmodedescribe) — One-line description of a mode, or of all of them.
- [`fmt`](#fmt) — Weight -> the string used in folder names. Matches the existing `Execution_a{alpha}_b{beta}_g{gamma}` convention, so a `single` run keeps the exact folder name it had before modes existed.
- [`resolve`](#resolve) — -> (mode, arms). `arms` is a list of dicts, PRODUCTION LAST::
- [`read_components`](#read_components) — -> (E_trackMOM, E_sumEXC, E_trackEMG, alpha, beta, gamma) summed over frames, or None.
- [`lcurve_knee`](#lcurve_knee) — Sartori's knee from a swept grid.
- [`manifest_path`](#manifest_path) — 
- [`run`](#run) — Execute every arm the mode calls for, production LAST, and write the manifest. `single_fn()` is the trial's one-shot execution, which reads trial.alpha/beta/gamma — so an arm is applied by setting those and calling it, which is also why the originals are restored in a finally block.
- [`aggregate_band`](#aggregate_band) — Turn per-arm results into what the mode promises the reader.

<a id="modeerror"></a>

## class `ModeError`(ValueError)

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L96)</sub>

<a id="executionmode"></a>

## class `ExecutionMode`(object)

```python
ExecutionMode(trial)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |

The chosen CEINMS execution mode, and everything that follows from it.

Reachable as ``bioscout.simulate.ceinms.ExecutionMode`` -- `ceinms.py`  
re-exports it, so there is one API surface even though the logic lives  
here.

WHY THE LOGIC LIVES IN ITS OWN MODULE RATHER THAN IN ceinms.py  
    `ceinms.py` imports opensim, scipy, matplotlib and pandas at module  
    top, is shadowed by the same-named `utils/ceinms/` package, and is  
    loaded by that package inside a `try/except Exception` that degrades to  
    "binary package only". `utils/__init__` likewise starts with  
    `ceinms = None`.

    Mode selection must not inherit any of that. If resolving `mode:  
    bounds` depended on OpenSim importing, a missing DLL would turn a  
    three-arm sensitivity run into a one-arm run WITHOUT an error -- the  
    config option would be silently ignored. This module imports only the  
    standard library (numpy arrives lazily, inside the two functions that  
    need it), so `mode` is parsed and validated the same way whether or not  
    the solver can start.

    >>> ExecutionMode.describe()          # works with no OpenSim present

Usage::

    m = ExecutionMode(trial)  
    print(m.mode, len(m.arms))  
    manifest = m.run(trial.run_ceinms_exe_single)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L485)</sub>

<a id="executionmodemode"></a>

### `ExecutionMode.mode`

```python
ExecutionMode.mode()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L525)</sub>

<a id="executionmodearms"></a>

### `ExecutionMode.arms`

```python
ExecutionMode.arms()
```

The solves this mode will run, PRODUCTION LAST. For `lcurve` this is  
the sweep only — the production arm is appended once the knee is known,  
which is why it cannot be listed up front.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L529)</sub>

<a id="executionmodedescription"></a>

### `ExecutionMode.description`

```python
ExecutionMode.description()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L536)</sub>

<a id="executionmoden_solves"></a>

### `ExecutionMode.n_solves`

```python
ExecutionMode.n_solves()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L540)</sub>

<a id="executionmoderun"></a>

### `ExecutionMode.run`

```python
ExecutionMode.run(single_fn, log=None)
```

| input | type | default |
|---|---|---|
| `single_fn` | – | required |
| `log` | – | `None` |

Execute every arm, production last, and write the manifest.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L547)</sub>

<a id="executionmodeaggregate"></a>

### `ExecutionMode.aggregate`

```python
ExecutionMode.aggregate(values_by_arm)
```

| input | type | default |
|---|---|---|
| `values_by_arm` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L554)</sub>

<a id="executionmodeknee"></a>

### `ExecutionMode.knee`

```python
ExecutionMode.knee(records, tol=0.01)
```

| input | type | default |
|---|---|---|
| `records` | – | required |
| `tol` | – | `0.01` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L558)</sub>

<a id="executionmodedescribe"></a>

### `ExecutionMode.describe`

```python
ExecutionMode.describe(mode=None)
```

| input | type | default |
|---|---|---|
| `mode` | – | `None` |

One-line description of a mode, or of all of them.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L562)</sub>

### `fmt`

```python
fmt(v)
```

| input | type | default |
|---|---|---|
| `v` | – | required |

Weight -> the string used in folder names. Matches the existing  
`Execution_a{alpha}_b{beta}_g{gamma}` convention, so a `single` run keeps  
the exact folder name it had before modes existed.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L105)</sub>

### `resolve`

```python
resolve(trial)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |

-> (mode, arms). `arms` is a list of dicts, PRODUCTION LAST::

    {"alpha":1, "beta":1, "gamma":10, "tag":"g10", "production":False}

The production arm carries ``tag=None``: its outputs keep the plain,  
untagged filenames, so downstream code that knows nothing about modes  
reads the production result by default.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L137)</sub>

### `read_components`

```python
read_components(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

-> (E_trackMOM, E_sumEXC, E_trackEMG, alpha, beta, gamma) summed over  
frames, or None.

Hand-parsed on purpose. `ObjectiveFunctionComponentsAndWeightings.sto`  
declares `datacolumns 7` and then lists every muscle in its name row, so a  
reader that trusts the header sees the mismatch and drops every data row —  
silently returning an empty frame rather than raising.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L199)</sub>

### `lcurve_knee`

```python
lcurve_knee(records, tol=0.01)
```

| input | type | default |
|---|---|---|
| `records` | – | required |
| `tol` | – | `0.01` |

Sartori's knee from a swept grid.

`records` is [{"beta","gamma","E_trackMOM","E_sumEXC","E_trackEMG"}, ...].  
-> dict with the chosen beta/gamma and the diagnostics that say whether to  
believe it, or None.

Two details are theirs, not inventions. Terms are normalised to their own  
maximum over the sweep. And the 'best' curve takes, at each gamma, the  
lowest normalised E_trackMOM — but among betas within `tol` of that  
minimum it takes the one with the LOWEST E_sumEXC, because low E_sumEXC  
"ensured excitation peaks were distributed across all MTUs and prevented  
them from saturating". Without that tie-break beta = 0 wins every point by  
construction (removing the effort penalty can only help moment tracking)  
and the procedure always returns beta = 0, which their Table 2 never does.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L261)</sub>

### `manifest_path`

```python
manifest_path(trial)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L317)</sub>

### `run`

```python
run(trial, single_fn, log=None)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |
| `single_fn` | – | required |
| `log` | – | `None` |

Execute every arm the mode calls for, production LAST, and write the  
manifest. `single_fn()` is the trial's one-shot execution, which reads  
trial.alpha/beta/gamma — so an arm is applied by setting those and calling  
it, which is also why the originals are restored in a finally block.

-> the manifest dict.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L358)</sub>

### `aggregate_band`

```python
aggregate_band(values_by_arm)
```

| input | type | default |
|---|---|---|
| `values_by_arm` | – | required |

Turn per-arm results into what the mode promises the reader.

`values_by_arm` maps an arm label to a value (or an array-like). Returns  
``{"production", "low", "high", "median", "n"}``.

`production` is the estimate you quote — the value from the production  
arm, NOT the median. The other arms are brackets chosen to expose a  
sensitivity, not samples of equal standing, so averaging over them would  
invent a central tendency that means nothing. `median` is reported anyway  
because `full_loop` sweeps a grid dense enough for it to be descriptive.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/ceinms/modes.py#L459)</sub>
