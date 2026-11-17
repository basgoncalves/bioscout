# `bioscout.simulate.opensim`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py)

OpenSim pipeline stages and the input prep that feeds them.

The ``simulate`` verb's engine: IK -> ID -> MA -> SO -> JRA (plus CMC, RRA,  
IAA, energetics, body kinematics), the trc/mot/grf/xml wrangling each stage  
needs, and ``run_emg_normalise`` (a pipeline STAGE -- the EMG domain logic it  
calls lives in ``bioscout.emg``).

Model creation and editing are NOT here: see ``bioscout.model``  
(``opensim_base`` for load_model and the logger plumbing, ``scale/`` for  
ScaleTool, ``edit/`` for .osim edits, ``muscle_optimize`` for Modenese-2015).

Split out of the old ``bioscout/utils/openSim.py`` (docs/RESTRUCTURE_PLAN.md,  
stage 6) -- the code is unchanged, only its address.

## Contents

- [`c3d_to_trc`](#c3d_to_trc) — Export a C3D file using the exportC3D module.
- [`convert_trc_os3_to_os4`](#convert_trc_os3_to_os4) — Convert a .trc file from OpenSim 3 format to OpenSim 4 format.
- [`add_joint_centers_to_trc`](#add_joint_centers_to_trc) — Add hip, knee, and ankle joint centre markers to a TRC file.
- [`validate_markers_used`](#validate_markers_used) — 
- [`compare_marker_locations`](#compare_marker_locations) — Calculates the root mean square error between experimental and virtual markers.
- [`assign_grfs_to_feet`](#assign_grfs_to_feet) — Detect force plates from a GRF .mot file and assign each to left/right foot.
- [`convert_mot_to_sto`](#convert_mot_to_sto) — Convert a .mot file to a .sto file.
- [`create_setup_IK`](#create_setup_ik) — Create an Inverse Kinematics (IK) setup XML file for OpenSim.
- [`run_ik`](#run_ik) — 
- [`find_non_zero_mom_arm_muscles`](#find_non_zero_mom_arm_muscles) — Find the muscles that have non-zero moment arms in the given data.
- [`relativise_setup_xml`](#relativise_setup_xml) — Rewrite absolute paths in an OpenSim/CEINMS setup XML to paths RELATIVE to the setup file's own directory, so the setup is portable (OpenSim resolves relative paths against the setup dir). Best-effort -- no-op on failure.
- [`create_analysis_tool`](#create_analysis_tool) — Creates and configures an OpenSim AnalyzeTool object.
- [`create_setup_ID`](#create_setup_id) — Create an Inverse Dynamics (ID) setup XML file for OpenSim.
- [`run_id`](#run_id) — Example usage: main(osim_modelPath='path/to/model.osim',      ik_output='path/to/ik_output.mot',      grf_xml='path/to/grf.xml',      setup_xml='path/to/setup.xml',      resultsDir='path/to/results')
- [`run_ma`](#run_ma) — Muscle analysis: MTU length + moment arms for the leg coordinates.
- [`reserve_actuator_plan`](#reserve_actuator_plan) — Decide whether SO's reserve actuators come from the MODEL or from a file.
- [`run_so`](#run_so) — 
- [`free_condyle_hinges`](#free_condyle_hinges) — Path of a copy of the model whose condyle hinges are unlocked, written beside it (``<model>_condylesfree.osim``), or the model itself when it has no locked condyle hinge. Pure XML: no OpenSim needed, nothing else in the model is touched, and the copy is only rewritten when it is older than its source.
- [`run_jra`](#run_jra) — 
- [`run_emg_normalise`](#run_emg_normalise) — Normalises EMG data based on a target EMG file. The target EMG file is used to scale the other EMG files in the list.
- [`run_iaa`](#run_iaa) — Induced Acceleration Analysis with OpenSim's InducedAccelerations (AnalyzeTool).
- [`run_rra`](#run_rra) — Residual Reduction Algorithm (OpenSim RRATool) for one trial.
- [`run_forward`](#run_forward) — Muscle-driven forward simulation of one trial, in two OpenSim steps::
- [`run_cmc`](#run_cmc) — Run Computed Muscle Control (CMC) using OpenSim.
- [`run_energetics`](#run_energetics) — Run Metabolic Cost Analysis (Energetics) using OpenSim.
- [`run_body_kinematics`](#run_body_kinematics) — Run Body Kinematics Analysis using OpenSim.

### `c3d_to_trc`

```python
c3d_to_trc(c3d_file_path, emg_string_list=['emg'], create_folder=True)
```

| input | type | default |
|---|---|---|
| `c3d_file_path` | – | required |
| `emg_string_list` | – | `['emg']` |
| `create_folder` | – | `True` |

Export a C3D file using the exportC3D module.

  
**Args**

    c3d_file_path (str): Path to the C3D file to export.  
    emg_string_list (list): List of EMG channel prefixes to filter.  
    create_folder (bool): Whether to create output folder if it doesn't exist.

  
**Returns**

    tuple: (success: bool, message: str)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L39)</sub>

### `convert_trc_os3_to_os4`

```python
convert_trc_os3_to_os4(trc_file_path: str = '', output_trc_file_path: str = '')
```

| input | type | default |
|---|---|---|
| `trc_file_path` | str | `''` |
| `output_trc_file_path` | str | `''` |

Convert a .trc file from OpenSim 3 format to OpenSim 4 format.

  
**Parameters**

trc_file_path (str): Path to the input .trc file in OpenSim 3 format.  
output_trc_file_path (str): Path to save the converted .trc file in OpenSim 4 format.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L66)</sub>

### `add_joint_centers_to_trc`

```python
add_joint_centers_to_trc(input_trc_path=None, output_trc_path=None, marker_map=None)
```

| input | type | default |
|---|---|---|
| `input_trc_path` | – | `None` |
| `output_trc_path` | – | `None` |
| `marker_map` | – | `None` |

Add hip, knee, and ankle joint centre markers to a TRC file.

New markers added (if computable):  
  - RHJC, LHJC (hip joint centres)  
  - RKJC, LKJC (knee joint centres)  
  - RAJC, LAJC (ankle joint centres)

  
**Inputs**

    - input_trc_path: path to input TRC file   
    - output_trc_path: path to output TRC file (if None, will save in same directory with suffix '_with_JointCenters')  
    - marker_map: dictionary specifying marker names for pelvis, knee pairs, ankle pairs, and existing hip markers.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L118)</sub>

### `validate_markers_used`

```python
validate_markers_used(osim_modelPath, ikTool, markers_path, ik_weights=None)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | required |
| `ikTool` | – | required |
| `markers_path` | – | required |
| `ik_weights` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L325)</sub>

### `compare_marker_locations`

```python
compare_marker_locations(marker_experimental_path=None, marker_virtual_path=None)
```

| input | type | default |
|---|---|---|
| `marker_experimental_path` | – | `None` |
| `marker_virtual_path` | – | `None` |

Calculates the root mean square error between experimental and virtual markers.

  
**Args**

    marker_experimental_path (str, optional): Path to the experimental .trc file.  
    marker_virtual_path (str, optional): Path to the virtual .sto markers file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L423)</sub>

### `assign_grfs_to_feet`

```python
assign_grfs_to_feet(
    grf_mot_path=None,
    marker_trc_path=None,
    right_foot_markers=None,
    left_foot_markers=None,
    right_foot_body='calcn_r',
    left_foot_body='calcn_l',
    vert_force_threshold=10.0,
    max_cop_foot_dist_mm=None
)
```

| input | type | default |
|---|---|---|
| `grf_mot_path` | – | `None` |
| `marker_trc_path` | – | `None` |
| `right_foot_markers` | – | `None` |
| `left_foot_markers` | – | `None` |
| `right_foot_body` | – | `'calcn_r'` |
| `left_foot_body` | – | `'calcn_l'` |
| `vert_force_threshold` | – | `10.0` |
| `max_cop_foot_dist_mm` | – | `None` |

Detect force plates from a GRF .mot file and assign each to left/right foot.

Loads the .mot file, auto-detects force-plate columns, then assigns each  
active plate to a foot by comparing median CoP Y with mean foot-marker Y  
from the TRC file.

  
**Parameters**

grf_mot_path : str  
    Path to the GRF .mot file.  
marker_trc_path : str, optional  
    Path to the marker TRC file for anatomical assignment.  
    If not provided, plates are sorted by CoP Y and alternated R/L.  
right_foot_markers : list of str, optional  
    Marker names for right foot. Defaults to common heel/toe names.  
left_foot_markers : list of str, optional  
    Marker names for left foot. Defaults to common heel/toe names.  
right_foot_body : str  
    OpenSim body name for right foot (default 'calcn_r').  
left_foot_body : str  
    OpenSim body name for left foot (default 'calcn_l').  
vert_force_threshold : float  
    Minimum |Fy| in N to consider a plate active (default 10 N).

  
**Returns**

dict  
    {plate_num_str: body_name}  e.g. {'4': 'calcn_r', '5': 'calcn_l'}

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L581)</sub>

### `convert_mot_to_sto`

```python
convert_mot_to_sto(mot_file_path=None)
```

| input | type | default |
|---|---|---|
| `mot_file_path` | – | `None` |

Convert a .mot file to a .sto file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L920)</sub>

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

Create an Inverse Kinematics (IK) setup XML file for OpenSim.

``ik_weights``: {marker or body: weight} over BatchSettings.marker_weights  
(session.yaml ``ik_weights``, session-wide and per iteration); a marker  
name beats its body, and 0 leaves the marker untracked.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L946)</sub>

### `run_ik`

```python
run_ik(osim_modelPath=None, setup_xml=None, resultsDir=None)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `setup_xml` | – | `None` |
| `resultsDir` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L1118)</sub>

### `find_non_zero_mom_arm_muscles`

```python
find_non_zero_mom_arm_muscles(ma_data: pd.DataFrame, muscles: list) -> list
```

| input | type | default |
|---|---|---|
| `ma_data` | pd.DataFrame | required |
| `muscles` | list | required |

**returns** `list`

Find the muscles that have non-zero moment arms in the given data.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L1423)</sub>

### `relativise_setup_xml`

```python
relativise_setup_xml(xml_path)
```

| input | type | default |
|---|---|---|
| `xml_path` | – | required |

Rewrite absolute paths in an OpenSim/CEINMS setup XML to paths RELATIVE to  
the setup file's own directory, so the setup is portable (OpenSim resolves  
relative paths against the setup dir). Best-effort -- no-op on failure.

The implementation is :func:`bioscout.utils.paths.relativise_xml`, shared  
with every other tool that writes a setup. This wrapper keeps the name its  
callers use and the Windows-style separator this one has always written --  
on Windows only: OpenSim on Linux (the hosted lab engine) cannot open a  
backslash path, so there the native "/" is written.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L1438)</sub>

### `create_analysis_tool`

```python
create_analysis_tool(
    marker_trc,
    externalloadsfile,
    osim_modelPath,
    results_directory,
    actuators=None
)
```

| input | type | default |
|---|---|---|
| `marker_trc` | – | required |
| `externalloadsfile` | – | required |
| `osim_modelPath` | – | required |
| `results_directory` | – | required |
| `actuators` | – | `None` |

Creates and configures an OpenSim AnalyzeTool object.

  
**Args**

coordinates_file: Path to the motion data file (e.g., .trc or .mot).  
model_path: Path to the OpenSim model file (.osim).  
results_directory: Path to the directory for storing results.  
force_set_files (optional): List of paths to actuator force set files.

  
**Returns**

OpenSim AnalyzeTool object.

# Example usage:  
    coordinates_file = "your_motion_data.trc"  
    model_path = "your_model.osim"  
    results_directory = "analysis_results"  
    force_set_files = ["actuator1_forces.xml", "actuator2_forces.xml"]  # Optional

    analysis_tool = create_analysis_tool(coordinates_file, model_path, results_directory, force_set_files)

    # Run the analysis  
    analysis_tool.run()

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L1453)</sub>

### `create_setup_ID`

```python
create_setup_ID(
    osim_modelPath=None,
    ik_output=None,
    grf_xml=None,
    id_output=None,
    taskSetPath=None,
    saveXMLPath=None
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `ik_output` | – | `None` |
| `grf_xml` | – | `None` |
| `id_output` | – | `None` |
| `taskSetPath` | – | `None` |
| `saveXMLPath` | – | `None` |

Create an Inverse Dynamics (ID) setup XML file for OpenSim.

This function creates the setup XML that will be used by run_id().

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L1530)</sub>

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

  
**Example usage**

main(osim_modelPath='path/to/model.osim',  
     ik_output='path/to/ik_output.mot',  
     grf_xml='path/to/grf.xml',  
     setup_xml='path/to/setup.xml',  
     resultsDir='path/to/results')

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L1600)</sub>

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

Muscle analysis: MTU length + moment arms for the leg coordinates.

method="opensim" is the default since 2026-11-04 (env BIOSCOUT_MA_METHOD / `bioscout  
-settings` ma_method overrides). method="fast": only  
_MuscleAnalysis_Length.sto and _MuscleAnalysis_MomentArm_<coord>.sto, moment  
arms by central differences of the lengths (OpenSim's own solver for  
multi-wrap muscles, i.e. the gastrocnemii); ~50-100x faster, matches  
OpenSim's MuscleAnalysis within ~1 mm (K2L Gehen_01, 2026-10-08).  
method="opensim": the full OpenSim MuscleAnalysis (fibre outputs, moments;  
needed only with solve_equilibrium=True).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L1747)</sub>

### `reserve_actuator_plan`

```python
reserve_actuator_plan(model, actuators_path, model_path='')
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `actuators_path` | – | required |
| `model_path` | – | `''` |

Decide whether SO's reserve actuators come from the MODEL or from a file.

They must come from exactly ONE of the two. StaticOptimization runs with  
useModelForceSet(True) and ALSO appends whatever force-set files it is  
given, so an actuator present in both is created TWICE: two independent  
actuators on the same coordinate. That halves the effective cost of using a  
reserve and doubles the reserve torque available, and nothing warns.

Present in NEITHER is worse, and quieter. SO then has nothing to absorb the  
difference between the muscle moments and the inverse-dynamics moments, so  
it drives the muscles to whatever it takes. Measured case: a walking hip  
contact force of 26 BW against a true 5.4, gastrocnemius off by 5.9 kN, and  
no error, warning or missing file anywhere -- the only visible symptom was  
the force file carrying 128 columns instead of 144.

-> ("model", note)  skip the append  
   ("file",  note)  append, as before  
Raises RuntimeError when neither source has them, or when they are split  
across both.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L1905)</sub>

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

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L1984)</sub>

### `free_condyle_hinges`

```python
free_condyle_hinges(osim_modelPath, suffix='_condylesfree')
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | required |
| `suffix` | – | `'_condylesfree'` |

Path of a copy of the model whose condyle hinges are unlocked, written  
beside it (``<model>_condylesfree.osim``), or the model itself when it  
has no locked condyle hinge. Pure XML: no OpenSim needed, nothing else in  
the model is touched, and the copy is only rewritten when it is older  
than its source.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L2141)</sub>

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

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L2172)</sub>

### `run_emg_normalise`

```python
run_emg_normalise(target_emg_path=None, normalise_emg_list=None)
```

| input | type | default |
|---|---|---|
| `target_emg_path` | – | `None` |
| `normalise_emg_list` | – | `None` |

Normalises EMG data based on a target EMG file.  
The target EMG file is used to scale the other EMG files in the list.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L2268)</sub>

### `run_iaa`

```python
run_iaa(
    osim_modelPath=None,
    ik_output=None,
    grf_xml=None,
    actuators=None,
    muscle_force_path=None,
    results_dir=None,
    constraint='rolling',
    force_threshold=20.0,
    coordinates='all',
    time_range=None,
    log=print,
    **_old
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `ik_output` | – | `None` |
| `grf_xml` | – | `None` |
| `actuators` | – | `None` |
| `muscle_force_path` | – | `None` |
| `results_dir` | – | `None` |
| `constraint` | – | `'rolling'` |
| `force_threshold` | – | `20.0` |
| `coordinates` | – | `'all'` |
| `time_range` | – | `None` |
| `log` | – | `print` |
| `**_old` | – | – |

Induced Acceleration Analysis with OpenSim's InducedAccelerations (AnalyzeTool).

The SO route of the OpenSim docs: the analysis runs in POTENTIALS mode  
(``compute_potentials_only``: the acceleration each muscle / actuator would  
cause per 1 N or 1 N*m) and each potential is multiplied by that actuator's  
SO force; gravity and velocity come out as they are. Every ExternalForce of  
``grf_xml`` is replaced, in order, by a contact constraint between its body  
and the ground (``constraint``: rolling | point | weld), switched on while  
the force exceeds ``force_threshold`` N.

Writes OpenSim's own output to ``results_dir/raw/`` (+ setup_IAA.xml) and  
the common layout (bioscout.simulate.iaa_files) to ``results_dir``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L2345)</sub>

### `run_rra`

```python
run_rra(
    osim_modelPath=None,
    ik_output=None,
    grf_xml=None,
    actuators=None,
    tasks=None,
    setup_xml=None,
    results_dir=None,
    template_xml=None,
    adjust_com=True,
    adjusted_com_body='torso',
    lowpass_cutoff=None,
    time_range=None,
    replace_force_set=True
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `ik_output` | – | `None` |
| `grf_xml` | – | `None` |
| `actuators` | – | `None` |
| `tasks` | – | `None` |
| `setup_xml` | – | `None` |
| `results_dir` | – | `None` |
| `template_xml` | – | `None` |
| `adjust_com` | – | `True` |
| `adjusted_com_body` | – | `'torso'` |
| `lowpass_cutoff` | – | `None` |
| `time_range` | – | `None` |
| `replace_force_set` | – | `True` |

Residual Reduction Algorithm (OpenSim RRATool) for one trial.

Builds ``setup_xml`` from ``template_xml`` (a setup_RRA.xml with  
MODEL / IK_MOT / GRF_XML placeholders -- any real paths in the template are  
overwritten too), points it at this trial's IK, GRF and the given actuator  
and task files, runs it from ``results_dir`` and returns a dict of the  
files RRA wrote::

    {"setup": ..., "kinematics": <RRA_Kinematics_q.sto>,  
     "actuation": <RRA_Actuation_force.sto>, "states": ...,  
     "model": <adjusted model .osim or None>, "log": <out.log>}

* ``actuators``: residual (FX..MZ on the pelvis) + reserve CoordinateActuators.  
  With ``replace_force_set=True`` (the standard RRA setting) they REPLACE  
  the muscles, so the solve is a pure torque-driven tracking problem. The  
  pelvis PointActuator points are rewritten to the model's pelvis  
  ``mass_center`` so the residual forces act through the pelvis COM.  
* ``tasks``: CMC_TaskSet of tracked coordinates. Tasks naming a coordinate  
  the model does not have are dropped (with a warning) rather than failing.  
* ``adjust_com``: write ``<results_dir>/<model>_rra_adjusted.osim`` with  
  the ``adjusted_com_body`` COM shifted to cancel the mean MX/MZ, and the  
  mass-change recommendation printed in out.log. The adjusted model is NOT  
  applied anywhere automatically.  
* ``lowpass_cutoff``: filter the desired kinematics (Hz); None keeps the  
  template value (-1 = unfiltered).  
* ``time_range``: (t0, t1); defaults to the IK file's span.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L2454)</sub>

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
    use_fast_target=True,
    replay=True,
    replace_force_set=False,
    max_steps=20000,
    step_tol=1e-05
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
| `use_fast_target` | – | `True` |
| `replay` | – | `True` |
| `replace_force_set` | – | `False` |
| `max_steps` | – | `20000` |
| `step_tol` | – | `1e-05` |

Muscle-driven forward simulation of one trial, in two OpenSim steps::

    <results_dir>/cmc/       CMCTool: forward-integrates the model while a  
                             tracking controller (tasks = kinematics, kp/kv  
                             from ``tasks``) solves for muscle excitations  
                             every ``cmc_time_window`` s -> CMC_controls.xml,  
                             CMC_states.sto, CMC_Actuation_force.sto, CMC_pErr.sto  
    <results_dir>/forward/   ForwardTool: the CMC excitations replayed OPEN-LOOP  
                             from CMC's initial state (no tracking) ->  
                             forward_states.sto. How far it drifts from the  
                             measured motion is the check that the excitations  
                             alone reproduce the movement.         [replay=True]

* ``actuators``: force-set file APPENDED to the model (``replace_force_set``  
  False keeps the muscles) -- normally the trial's SO actuators (pelvis  
  residuals + reserves), so CMC's muscle forces compare with SO's.  
* ``tasks``: CMC_TaskSet; tasks naming a coordinate the model does not  
  have, or one that is locked, are dropped (as run_rra does).  
* ``kinematics``: coordinates to track (RRA kinematics preferred, IK otherwise).

Returns a dict of the files written (+ counts / dropped tasks / ok flags).  
Raises RuntimeError when CMC fails; a failed replay is reported, not raised.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L2673)</sub>

### `run_cmc`

```python
run_cmc(
    osim_modelPath=None,
    ik_output=None,
    grf_xml=None,
    emg_file=None,
    actuators=None,
    setup_xml=None,
    results_dir=None
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `ik_output` | – | `None` |
| `grf_xml` | – | `None` |
| `emg_file` | – | `None` |
| `actuators` | – | `None` |
| `setup_xml` | – | `None` |
| `results_dir` | – | `None` |

Run Computed Muscle Control (CMC) using OpenSim.

CMC uses an optimization approach to compute muscle excitations that produce the desired kinematics  
while minimizing a cost function, typically the sum of squared muscle activations.

  
**Args**

    osim_modelPath: Path to the OpenSim model file  
    ik_output: Path to inverse kinematics output file (.mot)  
    grf_xml: Path to ground reaction force XML file  
    emg_file: Path to EMG data file for tracking constraints (optional)  
    actuators: Path to actuators setup file  
    setup_xml: Path to CMC setup XML file (if already created)  
    results_dir: Directory for results output

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L2880)</sub>

### `run_energetics`

```python
run_energetics(
    osim_modelPath=None,
    ik_output=None,
    muscle_activations=None,
    setup_xml=None,
    results_dir=None
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `ik_output` | – | `None` |
| `muscle_activations` | – | `None` |
| `setup_xml` | – | `None` |
| `results_dir` | – | `None` |

Run Metabolic Cost Analysis (Energetics) using OpenSim.

Computes the metabolic cost of a movement using muscle activations and kinematics.  
This uses the Metabolic Cost Analysis tool to estimate energy expenditure.

  
**Args**

    osim_modelPath: Path to the OpenSim model file  
    ik_output: Path to inverse kinematics output file (.mot)  
    muscle_activations: Path to muscle activation file (from CMC or SO)  
    setup_xml: Path to Metabolic Cost Analysis setup XML file  
    results_dir: Directory for results output

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L2950)</sub>

### `run_body_kinematics`

```python
run_body_kinematics(
    osim_modelPath=None,
    ik_output=None,
    bodies=None,
    setup_xml=None,
    results_dir=None
)
```

| input | type | default |
|---|---|---|
| `osim_modelPath` | – | `None` |
| `ik_output` | – | `None` |
| `bodies` | – | `None` |
| `setup_xml` | – | `None` |
| `results_dir` | – | `None` |

Run Body Kinematics Analysis using OpenSim.

Computes body kinematics (position, velocity, acceleration) for specified bodies  
during a movement based on the inverse kinematics solution.

  
**Args**

    osim_modelPath: Path to the OpenSim model file  
    ik_output: Path to inverse kinematics output file (.mot)  
    bodies: List of body names to analyze (default: all bodies)  
    setup_xml: Path to Body Kinematics setup XML file  
    results_dir: Directory for results output

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/opensim.py#L3118)</sub>
