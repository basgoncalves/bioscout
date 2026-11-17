# `bioscout.simulate.mew.bioscout_adapter`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/bioscout_adapter.py)

The bioscout seam. The ONLY module that imports bioscout, and lazily.

Two entry points:

* :func:`analyser_from_trial_dir` -- pure path convention, no bioscout import.  
  Works on any folder that follows bioscout's LAYOUT_DIRS.  
* :func:`analyser_from_iteration` -- takes a live ``bioscout.session``  
  Iteration and pulls body mass, emg_map, side and time_range from session.yaml.

Output goes where bioscout already looks: ``<trial>/ceinms/Optimised/  
MuscleForces.sto``. ``ml_model.ceinms_forces_path()``, the plotting code and  
``summarize_results.py`` then work unchanged.

## Contents

- [`find_session_dir`](#find_session_dir) — Walk up from a trial folder to the session dir (the one with session.yaml).
- [`experimental_dir`](#experimental_dir) — ``<session>/2_experimental/<trial>`` -- where the RAW inputs live once.
- [`read_session_yaml`](#read_session_yaml) — body_mass, emg_map, per-trial side/type from session.yaml. No bioscout needed.
- [`find_ceinms_forces`](#find_ceinms_forces) — The CEINMS MuscleForces.sto for a trial, across every output layout.
- [`output_dir`](#output_dir) — ``<trial>/mew/`` -- this package's own output folder.
- [`discover_trial`](#discover_trial) — Which canonical inputs this trial folder actually has.
- [`forces_output_path`](#forces_output_path) — Where to write, matching what bioscout/ml_model already read.
- [`analyser_from_trial_dir`](#analyser_from_trial_dir) — Build a Mew from a bioscout-layout trial folder.
- [`analyser_from_iteration`](#analyser_from_iteration) — Build from a live bioscout ``Iteration``, honouring session.yaml.
- [`run_iteration`](#run_iteration) — Solve every trial of a bioscout iteration. Returns {trial: result | Exception}.

### `find_session_dir`

```python
find_session_dir(trial_dir) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `trial_dir` | – | required |

**returns** `Optional[str]`

Walk up from a trial folder to the session dir (the one with session.yaml).

Layout is ``<session>/3_iterations/<iteration>/<trial>``, so it is normally  
three levels up -- but the search is by CONTENT (session.yaml or an  
experimental root), not by depth, so a flat or renamed layout still works.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/bioscout_adapter.py#L61)</sub>

### `experimental_dir`

```python
experimental_dir(trial_dir) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `trial_dir` | – | required |

**returns** `Optional[str]`

``<session>/2_experimental/<trial>`` -- where the RAW inputs live once.

bioscout keeps grf.mot / emg / GRF.xml at the SESSION level and shares them  
across iterations; only derived output lives under the trial. Missing this  
is the difference between reaching tier 2 and silently running tier 1.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/bioscout_adapter.py#L80)</sub>

### `read_session_yaml`

```python
read_session_yaml(trial_dir) -> Dict
```

| input | type | default |
|---|---|---|
| `trial_dir` | – | required |

**returns** `Dict`

body_mass, emg_map, per-trial side/type from session.yaml. No bioscout needed.

Returns ``{}`` when there is no session.yaml or no pyyaml -- every caller  
treats the contents as optional refinement, never as a requirement.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/bioscout_adapter.py#L98)</sub>

### `find_ceinms_forces`

```python
find_ceinms_forces(trial_dir, ceinms_cfg=None) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `trial_dir` | – | required |
| `ceinms_cfg` | – | `None` |

**returns** `Optional[str]`

The CEINMS MuscleForces.sto for a trial, across every output layout.

Preference order, and the reason for it:

1. the arm whose tag matches ``session.yaml``'s ``ceinms: alpha/beta/gamma``  
   -- on a multi-arm run that is the PRODUCTION result, and picking it by  
   name beats picking by timestamp (a later sweep arm is not the answer)  
2. the untagged ``Optimised/`` then ``Execution/`` -- a single-mode run  
3. legacy ``<trial>/Optimised/`` from before the ceinms/ subfolder  
4. any tagged arm, most recently written -- with nothing to disambiguate,  
   newest is the least surprising guess

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/bioscout_adapter.py#L150)</sub>

### `output_dir`

```python
output_dir(trial_dir, create=True) -> str
```

| input | type | default |
|---|---|---|
| `trial_dir` | – | required |
| `create` | – | `True` |

**returns** `str`

``<trial>/mew/`` -- this package's own output folder.

Kept separate from ``ceinms/`` and ``static_optimisation/`` so a  
mew run never overwrites a CEINMS or SO result. Writing into  
``ceinms/Optimised/`` is opt-in (``--ceinms-compat``) for when you WANT the  
existing plotting and summary code to pick these forces up.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/bioscout_adapter.py#L193)</sub>

### `discover_trial`

```python
discover_trial(trial_dir) -> Dict[str, Optional[str]]
```

| input | type | default |
|---|---|---|
| `trial_dir` | – | required |

**returns** `Dict[str, Optional[str]]`

Which canonical inputs this trial folder actually has.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/bioscout_adapter.py#L207)</sub>

### `forces_output_path`

```python
forces_output_path(trial_dir) -> str
```

| input | type | default |
|---|---|---|
| `trial_dir` | – | required |

**returns** `str`

Where to write, matching what bioscout/ml_model already read.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/bioscout_adapter.py#L246)</sub>

### `analyser_from_trial_dir`

```python
analyser_from_trial_dir(
    trial_dir,
    model,
    height=None,
    mass=None,
    emg_map=None,
    theta_file=None,
    **kw
)
```

| input | type | default |
|---|---|---|
| `trial_dir` | – | required |
| `model` | – | required |
| `height` | – | `None` |
| `mass` | – | `None` |
| `emg_map` | – | `None` |
| `theta_file` | – | `None` |
| `**kw` | – | – |

Build a Mew from a bioscout-layout trial folder.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/bioscout_adapter.py#L254)</sub>

### `analyser_from_iteration`

```python
analyser_from_iteration(iteration, trial, height=None, theta_file=None, **kw)
```

| input | type | default |
|---|---|---|
| `iteration` | – | required |
| `trial` | – | required |
| `height` | – | `None` |
| `theta_file` | – | `None` |
| `**kw` | – | – |

Build from a live bioscout ``Iteration``, honouring session.yaml.

from bioscout.session import Session  
it = Session(session_dir).iteration("rajagopal_fai")  
ma = Mew.from_bioscout(it, "Run_baselineA1")

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/bioscout_adapter.py#L281)</sub>

### `run_iteration`

```python
run_iteration(
    iteration,
    trials=None,
    write=True,
    extra=True,
    height=None,
    tier=None,
    verbose=True
) -> Dict[str, object]
```

| input | type | default |
|---|---|---|
| `iteration` | – | required |
| `trials` | – | `None` |
| `write` | – | `True` |
| `extra` | – | `True` |
| `height` | – | `None` |
| `tier` | – | `None` |
| `verbose` | – | `True` |

**returns** `Dict[str, object]`

Solve every trial of a bioscout iteration. Returns {trial: result | Exception}.

Never raises for one bad trial -- a batch that stops at trial 3 of 40 is the  
failure mode this whole package is reacting against.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/bioscout_adapter.py#L369)</sub>
