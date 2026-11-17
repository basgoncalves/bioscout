# `bioscout.simulate.pyosim_backend`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/pyosim_backend.py)

pyosim back end for bioscout's per-trial steps.

An iteration with ``engine: pyosim`` in session.yaml gets this module from  
``Analyse._get_openSim()`` instead of ``bioscout.simulate.opensim``. It offers the  
same functions with the same arguments, runs them with ``bioscout.pyosim`` (pure  
numpy/scipy, no OpenSim) and writes the same files where the OpenSim versions  
write them, so everything downstream (plots, residual checks, JCF contributions,  
the comparison tables) reads them unchanged:

    run_ik   -> <setup output_motion_file>, _ik_marker_errors.sto  
    run_id   -> <setup dir>/inverse_dynamics.sto  
    run_ma   -> <results_dir>/_MuscleAnalysis_*.sto  
    run_so   -> <resultsDir>/StaticOptimization_force.sto / _activation.sto  
    run_jra  -> <saveFileName> (OpenSim's JointReaction column layout)

It never uses OpenSim (2026-11-03): no `import opensim`, no OpenSim module, no OpenSim  
output. A step pyosim does not implement (RRA, CMC/forward simulation, energetics, ...)  
raises NotImplementedError before writing anything -- it does not fall back to OpenSim.

## Contents

- [`run_ik`](#run_ik) — Inverse kinematics from an OpenSim IK setup (marker file, time range, task set).
- [`run_id`](#run_id) — Inverse dynamics over the whole IK file, coordinates low-passed at 6 Hz (as bioscout's OpenSim ID).
- [`run_ma`](#run_ma) — Muscle-tendon lengths, fibre lengths (rigid tendon) and moment arms.
- [`run_so`](#run_so) — Static optimisation as OpenSim's (active fibre force only, Millard curves, sum a^2). Needs the trial's inverse dynamics: the inverse_dynamics.sto beside the IK file, or one computed here from the IK and the GRF.
- [`run_jra`](#run_jra) — Joint reaction loads on each child body, expressed in the child, from the muscle forces.
- [`run_jra_subsets`](#run_jra_subsets) — {tag: set of muscles} -> {tag: DataFrame} of the joint reaction loads with only those muscles pulling (the others' forces zero), all from one pass: the loads are linear in the muscle forces. Used by the JCF contribution analysis instead of one JRA run per group.
- [`create_setup_IK`](#create_setup_ik) — InverseKinematicsTool setup as bioscout's OpenSim create_setup_IK writes it (one IKMarkerTask per model marker; weight from session.yaml ik_weights / BatchSettings marker_weights by marker or parent body; markers not in the TRC or in markers_to_skip not applied), written as XML without OpenSim.
- [`run_forward`](#run_forward) — Computed muscle control (bioscout.pyosim.cmc) -> <results_dir>/cmc/, OpenSim's CMC file names. The open-loop ForwardTool replay is OpenSim-only: replay=True refuses.
- [`not_implemented`](#not_implemented) — 

### `run_ik`

```python
run_ik(osim_modelPath=None, setup_xml=None, resultsDir=None)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `setup_xml` | – | `None` |
| `resultsDir` | – | `None` |

Inverse kinematics from an OpenSim IK setup (marker file, time range, task set).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/pyosim_backend.py#L55)</sub>

### `run_id`

```python
run_id(osimModelPath=None, ikOutputPath=None, grfXmlPath=None, setupXmlPath=None)
```

| input | type | default |
|---|---|---|
| `osimModelPath` | – | `None` |
| `ikOutputPath` | – | `None` |
| `grfXmlPath` | – | `None` |
| `setupXmlPath` | – | `None` |

Inverse dynamics over the whole IK file, coordinates low-passed at 6 Hz (as bioscout's OpenSim ID).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/pyosim_backend.py#L99)</sub>

### `run_ma`

```python
run_ma(
    osim_modelPath=None,
    ik_output=None,
    grf_xml=None,
    results_dir=None,
    coordinates=None,
    solve_equilibrium=False,
    actuators=None,
    method=None
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `ik_output` | – | `None` |
| `grf_xml` | – | `None` |
| `results_dir` | – | `None` |
| `coordinates` | – | `None` |
| `solve_equilibrium` | – | `False` |
| `actuators` | – | `None` |
| `method` | – | `None` |

Muscle-tendon lengths, fibre lengths (rigid tendon) and moment arms.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/pyosim_backend.py#L110)</sub>

### `run_so`

```python
run_so(
    osim_modelPath=None,
    ik_output=None,
    grf_xml=None,
    setup_xml=None,
    actuators=None,
    resultsDir=None
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `ik_output` | – | `None` |
| `grf_xml` | – | `None` |
| `setup_xml` | – | `None` |
| `actuators` | – | `None` |
| `resultsDir` | – | `None` |

Static optimisation as OpenSim's (active fibre force only, Millard curves, sum a^2).  
Needs the trial's inverse dynamics: the inverse_dynamics.sto beside the IK file, or  
one computed here from the IK and the GRF.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/pyosim_backend.py#L121)</sub>

### `run_jra`

```python
run_jra(
    osim_modelPath=None,
    ik_output=None,
    grf_xml=None,
    setup_xml=None,
    actuators=None,
    muscle_force_path=None,
    saveFileName=None
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `ik_output` | – | `None` |
| `grf_xml` | – | `None` |
| `setup_xml` | – | `None` |
| `actuators` | – | `None` |
| `muscle_force_path` | – | `None` |
| `saveFileName` | – | `None` |

Joint reaction loads on each child body, expressed in the child, from the muscle forces.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/pyosim_backend.py#L140)</sub>

### `run_jra_subsets`

```python
run_jra_subsets(osim_modelPath, ik_output, grf_xml, muscle_force_path, subsets)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | required |
| `ik_output` | – | required |
| `grf_xml` | – | required |
| `muscle_force_path` | – | required |
| `subsets` | – | required |

{tag: set of muscles} -> {tag: DataFrame} of the joint reaction loads with only those  
muscles pulling (the others' forces zero), all from one pass: the loads are linear in the  
muscle forces. Used by the JCF contribution analysis instead of one JRA run per group.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/pyosim_backend.py#L150)</sub>

### `create_setup_IK`

```python
create_setup_IK(
    osim_modelPath=None,
    marker_trc=None,
    ik_output=None,
    taskSetPath=None,
    time_range=None,
    saveXMLPath=None,
    ik_weights=None
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `marker_trc` | – | `None` |
| `ik_output` | – | `None` |
| `taskSetPath` | – | `None` |
| `time_range` | – | `None` |
| `saveXMLPath` | – | `None` |
| `ik_weights` | – | `None` |

InverseKinematicsTool setup as bioscout's OpenSim create_setup_IK writes it (one  
IKMarkerTask per model marker; weight from session.yaml ik_weights / BatchSettings  
marker_weights by marker or parent body; markers not in the TRC or in markers_to_skip  
not applied), written as XML without OpenSim.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/pyosim_backend.py#L163)</sub>

### `run_forward`

```python
run_forward(
    osim_modelPath=None,
    kinematics=None,
    grf_xml=None,
    actuators=None,
    tasks=None,
    results_dir=None,
    time_range=None,
    lowpass_cutoff=6.0,
    cmc_time_window=0.01,
    replay=False,
    **_
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `kinematics` | – | `None` |
| `grf_xml` | – | `None` |
| `actuators` | – | `None` |
| `tasks` | – | `None` |
| `results_dir` | – | `None` |
| `time_range` | – | `None` |
| `lowpass_cutoff` | – | `6.0` |
| `cmc_time_window` | – | `0.01` |
| `replay` | – | `False` |
| `**_` | – | – |

Computed muscle control (bioscout.pyosim.cmc) -> <results_dir>/cmc/, OpenSim's CMC  
file names. The open-loop ForwardTool replay is OpenSim-only: replay=True refuses.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/pyosim_backend.py#L242)</sub>

### `not_implemented`

```python
not_implemented(step)
```

| input | type | default |
|---|---|---|
| `step` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/pyosim_backend.py#L262)</sub>
