# `bioscout.simulate.mew.pipeline`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/pipeline.py)

One call, one folder: muscle forces + joint contact forces + comparisons.

    from bioscout.simulate.mew import analyse_trial  
    out = analyse_trial(trial_dir, model="022_Rajagopal2015_FAI.osim", jcf=True)

Everything lands in ``<trial>/mew/`` so nothing a CEINMS or SO run  
produced is ever overwritten. Pass ``ceinms_compat=True`` to ALSO write  
``ceinms/Optimised/MuscleForces.sto``, which is what the existing bioscout  
plotting and ``summarize_results.py`` read.

## Contents

- [`analyse_trial`](#analyse_trial) — Solve a trial and write every output into ``<trial>/mew/``.

### `analyse_trial`

```python
analyse_trial(
    trial_dir,
    model,
    height=None,
    mass=None,
    tier=None,
    smoothing=None,
    filter_hz=None,
    jcf=False,
    jcf_joints=('hip_r', 'hip_l', 'knee_r', 'knee_l'),
    compare=True,
    plot=True,
    ceinms_compat=False,
    theta_file=None,
    verbose=True
) -> Dict[str, object]
```

| input | type | default |
|---|---|---|
| `trial_dir` | – | required |
| `model` | – | required |
| `height` | – | `None` |
| `mass` | – | `None` |
| `tier` | – | `None` |
| `smoothing` | – | `None` |
| `filter_hz` | – | `None` |
| `jcf` | – | `False` |
| `jcf_joints` | – | `('hip_r', 'hip_l', 'knee_r', 'knee_l')` |
| `compare` | – | `True` |
| `plot` | – | `True` |
| `ceinms_compat` | – | `False` |
| `theta_file` | – | `None` |
| `verbose` | – | `True` |

**returns** `Dict[str, object]`

Solve a trial and write every output into ``<trial>/mew/``.

Returns a dict with the result, the paths written, the comparison tables and  
the JCF report. Joint contact forces need bioscout + opensim importable;  
without them the muscle forces are still written and ``jcf_error`` says why  
that step was skipped -- a missing OpenSim must never cost you the part that  
did work.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/pipeline.py#L25)</sub>
