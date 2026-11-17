# `bioscout.core.analysis`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py)

bioscout.core.analysis — the analysis object model.

This module lives next to :class:`bioscout.utils.Analyse` and gathers the  
typed objects that wrap it:

    Project ─▶ Subject ─▶ Session ─▶ Trial   (a Trial *is* an Analyse)

It used to live in two top-level modules (``bioscout/subject.py`` and  
``bioscout/project.py``); they are now thin shims that re-export from here so  
all the analysis-side code sits together under ``utils``.

Quick start::

    import bioscout  
    proj = bioscout.Project()                  # cwd is the project root  
    proj.utils, proj.settings, proj.dir

    s = proj.subject("Athlete_03_Cateli")  
    trial = s.sessions[0].trials[0]            # a Trial == an Analyse  
    trial.run_ik(replace=True)

    from bioscout import build_model_config  
    model_config = build_model_config(proj.subjects)

Paths resolve against ``bioscout.utils`` (MODELS_DIR / SIMULATIONS_DIR /  
SETUP_DIR), which ``bioscout.Project`` points at the  
project folder.

## Contents

- class [`Subject`](#subject) — One SUBJECT-SESSION config: the identity (``subject``/``name``) plus the models/paths used for ONE session. Because scaled models are session-specific, each registry row is a single (subject, session) — a subject analysed across several sessions has one row per session (same ``subject``, different ``session``/models). ``subject`` is an alias for ``name`` (settings may alias the class itself to ``Session`` for readability).
  - [`Subject.model_for`](#subjectmodel_for) — Model filename for a solver ('SO' or 'CEINMS').
  - [`Subject.model_path`](#subjectmodel_path) — Absolute path to the .osim for a solver.
  - [`Subject.generic_model_path`](#subjectgeneric_model_path) — Absolute path to this subject's unscaled generic/template .osim.
  - [`Subject.trial_path`](#subjecttrial_path) — Absolute path to simulations/<name>/<session>/<trial>.
  - [`Subject.setup_dir`](#subjectsetup_dir) — Absolute path to this subject's OpenSim setup-file folder.
  - [`Subject.analyse`](#subjectanalyse) — Return an ``Analyse`` object for a trial, with the right model + setup folder wired in for the chosen solver.
  - [`Subject.line_style`](#subjectline_style) — 
  - [`Subject.curve_label`](#subjectcurve_label) — 
  - [`Subject.to_config`](#subjectto_config) — Return model_config-style entries for the given solver(s).
  - [`Subject.sessions`](#subjectsessions) — List of Session objects for this subject (folders under simulations/<name>/). If a default session is set, just that one.
  - [`Subject.get_session`](#subjectget_session) — Session by name, within THIS subject.
  - [`Subject.trials`](#subjecttrials) — List of Trial objects for one session (default: self.session).
  - [`Subject.make_trial`](#subjectmake_trial) — Return a Trial (an Analyse) for an absolute trial path, with this subject's model + setup folder wired in for the chosen solver.
  - [`Subject.from_model_folder`](#subjectfrom_model_folder) — Build a Subject by inspecting the .osim files in a model folder.
- class [`Project`](#project) — A BioScout project bound to a folder.
  - [`Project.trial_path`](#projecttrial_path) — Absolute path to simulations/<subject>/<session>/<trial>.
  - [`Project.analyse`](#projectanalyse) — Return an ``Analyse`` object for one trial folder.
  - [`Project.results_dir`](#projectresults_dir) — Make and return results/<*parts>.
  - [`Project.discover_subjects`](#projectdiscover_subjects) — Auto-build Subjects by scanning a folder — this project's models/ by default, ``models_dir`` to scan somewhere else (see bioscout.discover_subjects).
  - [`Project.migrate_settings`](#projectmigrate_settings) — Update this project's settings.py to the current schema, keeping its values (see bioscout.migrate_settings).
  - [`Project.subjects`](#projectsubjects) — The project's Subject objects (from settings.BatchSettings.SUBJECTS).
  - [`Project.subject`](#projectsubject) — Subject by folder name or label.
  - [`Project.sessions`](#projectsessions) — Every ``simulations/<subject>/<session>/`` holding a session.yaml, as :class:`bioscout.Session`, sorted. ``subjects`` / ``sessions`` filter by folder name (a name or a list; None = all)::
  - [`Project.session`](#projectsession) — One recording session by folder names::
  - [`Project.results`](#projectresults) — Results of every session -- same call as :attr:`bioscout.Session.results`, plus ``subject=`` / ``session=``::
  - [`Project.run`](#projectrun) — Run the pipeline over :meth:`sessions`. ``run_kw`` goes to :meth:`bioscout.Session.run` -- ``iterations=``, ``trials=``, the stage flags (``do_scale``, ``do_exbiomec``, ``do_muscle_analysis``, ``do_so``, ``do_mew``, ``do_ceinms``, ``export``) and ``replace=``. Nothing runs unless you ask for it. One failing session is logged and skipped. Returns ``{subject: {session: <Session.run result>}}``.
  - [`Project.reset`](#projectreset) — Reset :meth:`sessions` back to inputs-only (see :meth:`bioscout.Session.reset`); each session is backed up first. Returns ``{subject: {session: <reset info>}}``.
  - [`Project.migrate`](#projectmigrate) — Rewrite every session.yaml to the current schema (see :meth:`bioscout.Session.migrate`): project_dir, model_generic / model_scaled / markerset relative to the iteration folder. ``dry_run`` (default) only prints the diffs. Returns ``{subject: {session: ok}}``.
  - [`Project.trial`](#projecttrial) — Configured Trial for a subject (name or Subject) / session / trial.
- class [`Analyse`](#analyse) — Contains paths from the user settings and functions to implement in the OpenSim/Ceinms analysis
  - [`Analyse.model_path`](#analysemodel_path) — 
  - [`Analyse.model_path`](#analysemodel_path) — 
  - [`Analyse.joint_angles`](#analysejoint_angles) — 
  - [`Analyse.joint_angles`](#analysejoint_angles) — 
  - [`Analyse.inverse_dynamics`](#analyseinverse_dynamics) — 
  - [`Analyse.inverse_dynamics`](#analyseinverse_dynamics) — 
  - [`Analyse.static_optimisation_forces`](#analysestatic_optimisation_forces) — 
  - [`Analyse.static_optimisation_forces`](#analysestatic_optimisation_forces) — 
  - [`Analyse.static_optimisation_activations`](#analysestatic_optimisation_activations) — 
  - [`Analyse.static_optimisation_activations`](#analysestatic_optimisation_activations) — 
  - [`Analyse.grf`](#analysegrf) — 
  - [`Analyse.grf`](#analysegrf) — 
  - [`Analyse.joint_reaction_so`](#analysejoint_reaction_so) — 
  - [`Analyse.joint_reaction_so`](#analysejoint_reaction_so) — 
  - [`Analyse.joint_reaction_ceinms`](#analysejoint_reaction_ceinms) — 
  - [`Analyse.joint_reaction_ceinms`](#analysejoint_reaction_ceinms) — 
  - [`Analyse.convert_to_dict`](#analyseconvert_to_dict) — Convert a specific attribute of the trial to a dictionary
  - [`Analyse.load_settings`](#analyseload_settings) — Load all settings for the trial from an xml in trial.path
  - [`Analyse.load_results`](#analyseload_results) — Load results from a specific output file in the trial directory based on the tag
  - [`Analyse.get`](#analyseget) — 
  - [`Analyse.get_time_range_from_eventDetector`](#analyseget_time_range_from_eventdetector) — Get time range from event detector
  - [`Analyse.get_time_range`](#analyseget_time_range) — 
  - [`Analyse.get_trial_type`](#analyseget_trial_type) — Canonical trial type for event interpretation and overlays.
  - [`Analyse.set_events`](#analyseset_events) — Set the trial's gait/task events and persist them in trial_settings.xml.
  - [`Analyse.get_task_events`](#analyseget_task_events) — Task landmarks from the trial's events, using the trial-type schema.
  - [`Analyse.get_gait_events`](#analyseget_gait_events) — Back-compat wrapper: gait landmarks in the old shape.
  - [`Analyse.detect_events_from_grf`](#analysedetect_events_from_grf) — Detect foot-contact / foot-off events from the vertical GRF.
  - [`Analyse.detect_events_from_kinematics`](#analysedetect_events_from_kinematics) — Detect foot contacts/offs from marker kinematics (no force plates).
  - [`Analyse.detect_events`](#analysedetect_events) — Detect gait events via 'grf', 'kinematics', or 'auto'.
  - [`Analyse.plot_grf_events`](#analyseplot_grf_events) — Plot per-foot vertical GRF with the trial's gait events, into inputs/.
  - [`Analyse.inspect_moment_arms`](#analyseinspect_moment_arms) — Standalone QC of the model's moment arms over THIS trial's MOTION: plots each spanning muscle's moment arm vs its joint-angle coordinate over the recorded pose trajectory and flags wrap discontinuities. Reads the MuscleAnalysis output (run :meth:`run_ma` first) + the IK joint angles — no OpenSim, no literature. This is the motion-driven counterpart to the ``muscle_inspect`` model validation (which sweeps each coordinate over its full ROM). Saves ``moment_arm_motion_check.png`` next to the IK, and returns ``{"figure", "flagged", "dofs"}``.
  - [`Analyse.recrop_to_events`](#analyserecrop_to_events) — Re-derive the analysis window (start/end time) from the trial's events and persist it — WITHOUT re-exporting the raw inputs.
  - [`Analyse.redetect_events`](#analyseredetect_events) — Force-re-detect gait events from the GRF (overwriting existing events), then re-derive/persist the analysis window and refresh grf_events.png.
  - [`Analyse.plot_emg_processing`](#analyseplot_emg_processing) — Per-channel EMG figure: raw signal vs filtered + session-normalised.
  - [`Analyse.get_markers`](#analyseget_markers) — return a dataFrame with the name of each marker in the model and it's parent body
  - [`Analyse.update_trial_attribute`](#analyseupdate_trial_attribute) — Update a specific attribute of the trial and save to XML
  - [`Analyse.delete_trial_attribute`](#analysedelete_trial_attribute) — Delete a specific attribute of the trial and save to XML
  - [`Analyse.copy_input_files`](#analysecopy_input_files) — Copy input files from a template subject to the trial directory if they don't already exist or if replace is True.
  - [`Analyse.update_model`](#analyseupdate_model) — Update the model path for the trial and save to XML
  - [`Analyse.increase_muscle_force`](#analyseincrease_muscle_force) — Increase muscle force in the scaled model by a given factor.
  - [`Analyse.get_body_mass`](#analyseget_body_mass) — Retrieve body mass from the scaled model using OpenSim API funtion getTotalMass, and update the trial settings if it differs from the current body mass.
  - [`Analyse.get_body_mass_from_grf`](#analyseget_body_mass_from_grf) — Calculate body mass from GRF data if available.
  - [`Analyse.get_muscle_list`](#analyseget_muscle_list) — Retrieve list of muscles from the model_dir.
  - [`Analyse.edit_model_range_coordinates`](#analyseedit_model_range_coordinates) — Change the range of motion for a specific degree of freedom in the model.
  - [`Analyse.scale_emg`](#analysescale_emg) — Scale EMG data by a given factor and save to a new file.
  - [`Analyse.export_c3d`](#analyseexport_c3d) — Export C3D file using the exportC3D script, which extracts EMG data and saves it in a format compatible with CEINMS.
  - [`Analyse.load_model`](#analyseload_model) — Load an OpenSim model with its printBasicInfo() dump suppressed.
  - [`Analyse.prune_empty_exports`](#analyseprune_empty_exports) — Delete exported inputs that contain no data, and say so once.
  - [`Analyse.run_ik`](#analyserun_ik) — 
  - [`Analyse.run_id`](#analyserun_id) — 
  - [`Analyse.run_ma`](#analyserun_ma) — 
  - [`Analyse.run_so`](#analyserun_so) — 
  - [`Analyse.run_mrs`](#analyserun_mrs) — Muscle Redundancy Solver (KU Leuven) for this trial, via MATLAB.
  - [`Analyse.run_energetics`](#analyserun_energetics) — Run Metabolic Cost (Energetics) analysis for this trial.
  - [`Analyse.rra_paths`](#analyserra_paths) — Absolute paths of everything the RRA stage reads and writes.
  - [`Analyse.rra_grf_window`](#analyserra_grf_window) — Longest span of this trial with ground reaction force on at least one plate (total vertical GRF > ``threshold`` N), as (t0, t1), or None. RRA (unlike ID) must not see frames where a foot is on the ground without a measured force: it then carries body weight on the pelvis residuals and shifts the COM / tracks the pelvis to compensate.
  - [`Analyse.run_rra`](#analyserun_rra) — Residual Reduction Algorithm for this trial, then the downstream pipeline re-run on its result, for comparison with the plain IK/ID/SO::
  - [`Analyse.plot_rra_moments`](#analyseplot_rra_moments) — Task-vertical figure (poses + vGRF on top, as kinematics_moments.png): the six pelvis residuals -- ID (solid) vs the RRA residual actuators (dashed) -- then one row per summary DOF with the ID joint moment (solid) vs the RRA reserve-actuator moment (dashed); right red, left blue, midline black. -> rra_moments.png, rra_residuals.csv, rra_tracking_error.csv.
  - [`Analyse.plot_rra_kinematics`](#analyseplot_rra_kinematics) — IK vs RRA joint angles, one task-vertical row per DOF (right red, left blue, midline black; RRA dashed) with the RMS difference in the row title -> rra_kinematics.png.
  - [`Analyse.plot_rra_masses`](#analyseplot_rra_masses) — Segment masses and mass centres, original vs RRA-adjusted model -> rra_masses.png + rra_masses.csv.
  - [`Analyse.plot_rra_jcf`](#analyseplot_rra_jcf) — Joint contact forces: SO (solid) vs SO after RRA (dashed), with the in-vivo implant force when the trial has one -> rra_jcf.png.
  - [`Analyse.plot_rra_so_forces`](#analyseplot_rra_so_forces) — SO muscle forces original vs after RRA for the ``top`` muscles by peak force, plus the residual/reserve actuator totals -> rra_so_forces.png.
  - [`Analyse.forward_paths`](#analyseforward_paths) — Absolute paths of everything the forward-simulation stage reads/writes.
  - [`Analyse.run_forward`](#analyserun_forward) — Muscle-driven forward simulation of this trial::
  - [`Analyse.plot_forward_kinematics`](#analyseplot_forward_kinematics) — Tracked (black) vs CMC (blue) vs open-loop forward (red dashed) per DOF -> forward_kinematics.png, and forward_tracking.csv.
  - [`Analyse.plot_forward_muscle_forces`](#analyseplot_forward_muscle_forces) — SO (grey) vs CMC (blue) muscle forces for the ``top`` muscles by SO peak, plus |reserves + residuals| -> forward_muscle_forces.png.
  - [`Analyse.plot_forward_jcf`](#analyseplot_forward_jcf) — Joint contact forces SO (solid) vs CMC (dashed), with in vivo -> forward_jcf.png.
  - [`Analyse.run_jra`](#analyserun_jra) — 
  - [`Analyse.run_iaa`](#analyserun_iaa) — Induced acceleration analysis on the SO forces -> <trial>/induced_accelerations/<engine>/.
  - [`Analyse.so_result_summary`](#analyseso_result_summary) — One-line SO result summary for the log: peak |resultant| joint reaction (contact) force at hip / knee / ankle, in body-weights when body_mass is known (else N). Best-effort, reads the SO JRA output on disk.
  - [`Analyse.run_jra_ceinms`](#analyserun_jra_ceinms) — 
  - [`Analyse.plot_jcf_coverage`](#analyseplot_jcf_coverage) — Contact-loading figures: where the JRA forces land on the bones, by gait event, one png per ``plane`` and per JRA source (``labels``: "SO", "CEINMS"; default every JRA .sto found in joint_contact_forces/). Writes ``joint_contact_forces/jrf_<label>_coverage_<plane>.png``. Best-effort: a failure is logged, never raised.
  - [`Analyse.run_jra_contributions`](#analyserun_jra_contributions) — Muscle contributions to this trial's joint contact forces.
  - [`Analyse.plot_jra_comparison`](#analyseplot_jra_comparison) — SO vs CEINMS joint reaction (contact) forces for the joints in settings.BatchSettings.JRA_COLUMNS, in the vertical task layout (poses + vGRF on top), one row per joint with its |resultant| per leg. Saved into joint_contact_forces/ as ``jrf_so.png`` / ``jrf_so_vs_ceinms.png``.
  - [`Analyse.run_emg_filter`](#analyserun_emg_filter) — Per-trial: filter raw EMG -> emg_filtered.mot.
  - [`Analyse.run_emg_normalise`](#analyserun_emg_normalise) — 
  - [`Analyse.convert_mot_to_sto`](#analyseconvert_mot_to_sto) — 
  - [`Analyse.muscles_per_coordinate`](#analysemuscles_per_coordinate) — 
  - [`Analyse.calculate_muscle_moments`](#analysecalculate_muscle_moments) — Calculate muscle moments by multiplying muscle forces by their moment arms for each coordinate.
  - [`Analyse.compare_marker_locations`](#analysecompare_marker_locations) — 
  - [`Analyse.check_moment_arms`](#analysecheck_moment_arms) — Using the openSim.py function checkMomentArms to plot moment arms for each coordinate and muscle, and compare to expected patterns based on muscle geometry.
  - [`Analyse.adjust_moment_arms`](#analyseadjust_moment_arms) — Iteratively increases wrapping-surface radii for muscles that have moment-arm discontinuities beyond the first `skip_frames` frames, then re-runs the moment-arm check.  Stops when no qualifying discontinuities remain or `max_iter` is reached. The modified model is saved in place; a .bak copy is created on the first iteration.
  - [`Analyse.calculate_emg_activation_errors`](#analysecalculate_emg_activation_errors) — Calculate errors between EMG activations and CEINMS excitations, and save to a new file.
  - [`Analyse.calculate_mean_marker_error`](#analysecalculate_mean_marker_error) — Load the _ik_marker_errors.sto file and calculate the mean marker error across all markers and time frames, and save to a new file.
  - [`Analyse.calculate_moment_errors`](#analysecalculate_moment_errors) — Calculate errors between muscle moments calculated from SO or CEINMS forces and the inverse dynamics joint moments, and save to a new file.
  - [`Analyse.scale_moment_arm`](#analysescale_moment_arm) — Scale the moment arm of the given muscle(s) by *factor* and save a new .sto.
  - [`Analyse.plot_create_subplot`](#analyseplot_create_subplot) — 
  - [`Analyse.plot_moment_arms`](#analyseplot_moment_arms) — 
  - [`Analyse.plot_ik`](#analyseplot_ik) — 
  - [`Analyse.plot_id`](#analyseplot_id) — 
  - [`Analyse.plot_ik_id_summary`](#analyseplot_ik_id_summary) — Combined IK+ID inspection figure: one panel per coordinate showing the joint ANGLE (solid line, left axis, deg) and the matching ID MOMENT / residual (dashed line, right axis, Nm or N) overlaid. Right leg blue, left leg red. Uses the same proximal->distal joint-row layout as plot_id. Saved next to the ID result as ``<id>_summary.png``.
  - [`Analyse.plot_kin_mom_summary`](#analyseplot_kin_mom_summary) — Compact kinematics+moments figure for the summary DOFs only.
  - [`Analyse.plot_so`](#analyseplot_so) — Static-Optimization results — one figure, one subplot per muscle.
  - [`Analyse.emg_channel_map`](#analyseemg_channel_map) — {emg_channel: [model_muscles]} for this trial.
  - [`Analyse.plot_muscle_moments`](#analyseplot_muscle_moments) — ID moment vs the moment the muscles carry, per reserved coordinate.
  - [`Analyse.plot_residuals`](#analyseplot_residuals) — Pelvis residual inspection for Inverse Dynamics.
  - [`Analyse.muscle_inspect`](#analysemuscle_inspect) — Motion-driven muscle-path check of this trial's model over its kinematics.
  - [`Analyse.validate_trial`](#analysevalidate_trial) — End-of-analysis model validation for this trial → ``<trial>/validation/``.
  - [`Analyse.plot_jra`](#analyseplot_jra) — 
  - [`Analyse.plot_emg`](#analyseplot_emg) — 
  - [`Analyse.plot_summary`](#analyseplot_summary) — Plot summary of results for a trial and settings DOFs, including:
  - [`Analyse.create_ceinms_model`](#analysecreate_ceinms_model) — 
  - [`Analyse.create_ceinms_input_data`](#analysecreate_ceinms_input_data) — 
  - [`Analyse.create_ceinms_calibration_cfg`](#analysecreate_ceinms_calibration_cfg) — Create ceinms_cfg_calibration.xml for CEINMS calibration.
  - [`Analyse.create_excitation_generator`](#analysecreate_excitation_generator) — 
  - [`Analyse.create_ceinms_cfg_from_excitation_generator`](#analysecreate_ceinms_cfg_from_excitation_generator) — Create ceinms_cfg_optimise.xml based on excitationGenerator.xml
  - [`Analyse.create_ceinms_calibration_setup`](#analysecreate_ceinms_calibration_setup) — 
  - [`Analyse.create_ceinms_optimise_setup`](#analysecreate_ceinms_optimise_setup) — 
  - [`Analyse.ceinms_is_calibrated`](#analyseceinms_is_calibrated) — Does EXECUTION use the calibrated subject model?
  - [`Analyse.ceinms_execution_subject`](#analyseceinms_execution_subject) — The subject XML CEINMS execution must read for this trial.
  - [`Analyse.ceinms_exe_tag`](#analyseceinms_exe_tag) — `_uncal` for an uncalibrated solve, else ''.
  - [`Analyse.ceinms_exe_out_rel`](#analyseceinms_exe_out_rel) — Trial-root-relative execution output folder, tag and weights included.
  - [`Analyse.create_ceinms_exe_setup`](#analysecreate_ceinms_exe_setup) — 
  - [`Analyse.create_ceinms_exe_cfg`](#analysecreate_ceinms_exe_cfg) — 
  - [`Analyse.get_muscle_excitation_mapping`](#analyseget_muscle_excitation_mapping) — Check if a muscle is present in the excitation mapping of the excitation generator XML.
  - [`Analyse.run_ceinms_calibration`](#analyserun_ceinms_calibration) — Run the full CEINMS calibration pipeline for this session.
  - [`Analyse.run_ceinms_exe`](#analyserun_ceinms_exe) — Run CEINMS execution in whatever MODE this session asks for.
  - [`Analyse.run_ceinms_exe_single`](#analyserun_ceinms_exe_single) — 
  - [`Analyse.plot_ceinms_emg_activations`](#analyseplot_ceinms_emg_activations) — CEINMS validation: per EMG channel, the normalised EMG excitation vs the CEINMS activations of the muscles driven by that channel.
  - [`Analyse.run_ceinms_optimise`](#analyserun_ceinms_optimise) — 
  - [`Analyse.run_ceinms_exe_loop`](#analyserun_ceinms_exe_loop) — 
  - [`Analyse.check_best_ceinms_results`](#analysecheck_best_ceinms_results) — loop through ceinms exe results and find best alpha, beta, gamma based on RMS error for joint moments and EMG vs CEINMS excitations
  - [`Analyse.add_so_columns_to_ceinms_results`](#analyseadd_so_columns_to_ceinms_results) — Give the CEINMS force file the SAME actuator columns SO's has, so the CEINMS JointReaction is set up exactly like SO's (2026-10-22).
  - [`Analyse.plot_ceinms_execution_comparison`](#analyseplot_ceinms_execution_comparison) — CEINMS-vs-SO muscle results in the muscle_individual.png layout.
  - [`Analyse.plot_ceinms_calibration_results`](#analyseplot_ceinms_calibration_results) — 
  - [`Analyse.plot_ceinms_vs_so_muscle_moments`](#analyseplot_ceinms_vs_so_muscle_moments) — 
- [`build_model_config`](#build_model_config) — Build a Plot-compatible ``model_config`` dict from a list of Subjects.
- [`sessions_from_subjects`](#sessions_from_subjects) — Legacy batch ``SESSIONS`` dict ({abs_session_path: static_trial}) derived from Subjects — what ``BatchSettings.sessions`` consumes.
- [`subjects_from_subjects`](#subjects_from_subjects) — Legacy ``SUBJECTS`` dict ({name: {session, static_trial, group}}) derived from Subjects — for code/GUI paths that still read SUBJECTS.
- [`discover_subjects`](#discover_subjects) — Auto-build a list of :class:`Subject` from the project's models folder.
- [`check_settings_version`](#check_settings_version) — Compare a project's ``settings.__version__`` to the package schema version.
- [`migrate_settings`](#migrate_settings) — Update a project's settings.py to the current schema, keeping its values.
- [`ensure_editor_paths`](#ensure_editor_paths) — Make Pylance/Pyright resolve the project's own modules (e.g. `import settings`) by adding "." to python.analysis.extraPaths in the project's .vscode/settings.json.

<a id="subject"></a>

## class `Subject`

One SUBJECT-SESSION config: the identity (``subject``/``name``) plus the  
models/paths used for ONE session. Because scaled models are session-specific,  
each registry row is a single (subject, session) — a subject analysed across  
several sessions has one row per session (same ``subject``, different  
``session``/models). ``subject`` is an alias for ``name`` (settings may alias  
the class itself to ``Session`` for readability).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L306)</sub>

<a id="subjectmodel_for"></a>

### `Subject.model_for`

```python
Subject.model_for(force_type='SO') -> Optional[str]
```

| input | type | default |
|---|---|---|
| `force_type` | – | `'SO'` |

**returns** `Optional[str]`

Model filename for a solver ('SO' or 'CEINMS').

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L349)</sub>

<a id="subjectmodel_path"></a>

### `Subject.model_path`

```python
Subject.model_path(force_type='SO', session=None) -> str
```

| input | type | default |
|---|---|---|
| `force_type` | – | `'SO'` |
| `session` | – | `None` |

**returns** `str`

Absolute path to the .osim for a solver.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L353)</sub>

<a id="subjectgeneric_model_path"></a>

### `Subject.generic_model_path`

```python
Subject.generic_model_path() -> Optional[str]
```

**returns** `Optional[str]`

Absolute path to this subject's unscaled generic/template .osim.

``generic_model`` may be an absolute path or a relative name/sub-path.  
A relative value is resolved against, in order: ``models/<name>/``,  
``models/``, ``<project>/generic models/``, then the project root — so  
templates kept in a ``generic models/`` folder resolve without an  
absolute path. Returns None if the subject has no generic model set.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L359)</sub>

<a id="subjecttrial_path"></a>

### `Subject.trial_path`

```python
Subject.trial_path(trial, session=None) -> str
```

| input | type | default |
|---|---|---|
| `trial` | – | required |
| `session` | – | `None` |

**returns** `str`

Absolute path to simulations/<name>/<session>/<trial>.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L386)</sub>

<a id="subjectsetup_dir"></a>

### `Subject.setup_dir`

```python
Subject.setup_dir() -> str
```

**returns** `str`

Absolute path to this subject's OpenSim setup-file folder.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L392)</sub>

<a id="subjectanalyse"></a>

### `Subject.analyse`

```python
Subject.analyse(trial, force_type='SO', session=None, configure=True)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |
| `force_type` | – | `'SO'` |
| `session` | – | `None` |
| `configure` | – | `True` |

Return an ``Analyse`` object for a trial, with the right model +  
setup folder wired in for the chosen solver.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L399)</sub>

<a id="subjectline_style"></a>

### `Subject.line_style`

```python
Subject.line_style(force_type='SO') -> str
```

| input | type | default |
|---|---|---|
| `force_type` | – | `'SO'` |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L419)</sub>

<a id="subjectcurve_label"></a>

### `Subject.curve_label`

```python
Subject.curve_label(force_type='SO') -> str
```

| input | type | default |
|---|---|---|
| `force_type` | – | `'SO'` |

**returns** `str`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L422)</sub>

<a id="subjectto_config"></a>

### `Subject.to_config`

```python
Subject.to_config(force_types=('SO',)) -> dict
```

| input | type | default |
|---|---|---|
| `force_types` | – | `('SO',)` |

**returns** `dict`

Return model_config-style entries for the given solver(s).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L425)</sub>

<a id="subjectsessions"></a>

### `Subject.sessions`

```python
Subject.sessions()
```

List of Session objects for this subject (folders under  
simulations/<name>/). If a default session is set, just that one.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L439)</sub>

<a id="subjectget_session"></a>

### `Subject.get_session`

```python
Subject.get_session(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

Session by name, within THIS subject.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L463)</sub>

<a id="subjecttrials"></a>

### `Subject.trials`

```python
Subject.trials(session=None, force_type='SO')
```

| input | type | default |
|---|---|---|
| `session` | – | `None` |
| `force_type` | – | `'SO'` |

List of Trial objects for one session (default: self.session).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L469)</sub>

<a id="subjectmake_trial"></a>

### `Subject.make_trial`

```python
Subject.make_trial(trial_path, force_type='SO', configure=True)
```

| input | type | default |
|---|---|---|
| `trial_path` | – | required |
| `force_type` | – | `'SO'` |
| `configure` | – | `True` |

Return a Trial (an Analyse) for an absolute trial path, with this  
subject's model + setup folder wired in for the chosen solver.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L482)</sub>

<a id="subjectfrom_model_folder"></a>

### `Subject.from_model_folder`

```python
Subject.from_model_folder(name, folder, session=None, **overrides)
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `folder` | – | required |
| `session` | – | `None` |
| `**overrides` | – | – |

Build a Subject by inspecting the .osim files in a model folder.

Picks ``model_so`` = a strength-increased model (filename contains  
'increased' / '3.00' / 'x3'); ``model_ceinms`` = the matching base model.  
Any keyword in ``overrides`` (color, label, setup_folder, …) wins.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L503)</sub>

<a id="project"></a>

## class `Project`

```python
Project(project_dir=None, verbose=True, setup_editor=True, scaffold_settings=False)
```

| input | type | default |
|---|---|---|
| `project_dir` | – | `None` |
| `verbose` | – | `True` |
| `setup_editor` | – | `True` |
| `scaffold_settings` | – | `False` |

A BioScout project bound to a folder.

The folder is expected to hold ``models/``, ``simulations/``, ``results/``  
and, optionally, a ``project.yaml`` (lab facts) or a legacy per-project  
``settings.py``. Construction wires the package to it. A folder with  
neither runs on bioscout's bundled defaults — see  
``docs/IMPLEMENTATIONS.md`` §2.9.

  
**Attributes**

dir : Path        the project root  
utils : module    bioscout.utils, with OpenSim/CEINMS loaded and dirs set  
settings : module the resolved settings (project's settings.py, or  
                  bioscout's bundled template, with project.yaml  
                  overlaid on top either way)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1059)</sub>

<a id="projecttrial_path"></a>

### `Project.trial_path`

```python
Project.trial_path(subject, session, trial)
```

| input | type | default |
|---|---|---|
| `subject` | – | required |
| `session` | – | required |
| `trial` | – | required |

Absolute path to simulations/<subject>/<session>/<trial>.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1235)</sub>

<a id="projectanalyse"></a>

### `Project.analyse`

```python
Project.analyse(subject, session, trial)
```

| input | type | default |
|---|---|---|
| `subject` | – | required |
| `session` | – | required |
| `trial` | – | required |

Return an ``Analyse`` object for one trial folder.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1239)</sub>

<a id="projectresults_dir"></a>

### `Project.results_dir`

```python
Project.results_dir(*parts)
```

| input | type | default |
|---|---|---|
| `*parts` | – | – |

Make and return results/<*parts>.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1243)</sub>

<a id="projectdiscover_subjects"></a>

### `Project.discover_subjects`

```python
Project.discover_subjects(session=None, models_dir=None, **kw)
```

| input | type | default |
|---|---|---|
| `session` | – | `None` |
| `models_dir` | – | `None` |
| `**kw` | – | – |

Auto-build Subjects by scanning a folder — this project's models/ by  
default, ``models_dir`` to scan somewhere else (see  
bioscout.discover_subjects).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1249)</sub>

<a id="projectmigrate_settings"></a>

### `Project.migrate_settings`

```python
Project.migrate_settings(write=False, verbose=True)
```

| input | type | default |
|---|---|---|
| `write` | – | `False` |
| `verbose` | – | `True` |

Update this project's settings.py to the current schema, keeping  
its values (see bioscout.migrate_settings).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1256)</sub>

<a id="projectsubjects"></a>

### `Project.subjects`

```python
Project.subjects() -> 'list[Subject]'
```

**returns** `'list[Subject]'`

The project's Subject objects (from settings.BatchSettings.SUBJECTS).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1263)</sub>

<a id="projectsubject"></a>

### `Project.subject`

```python
Project.subject(name) -> 'Subject'
```

| input | type | default |
|---|---|---|
| `name` | – | required |

**returns** `'Subject'`

Subject by folder name or label.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1267)</sub>

<a id="projectsessions"></a>

### `Project.sessions`

```python
Project.sessions(subjects=None, sessions=None) -> 'list[Session]'
```

| input | type | default |
|---|---|---|
| `subjects` | – | `None` |
| `sessions` | – | `None` |

**returns** `'list[Session]'`

Every ``simulations/<subject>/<session>/`` holding a session.yaml, as  
:class:`bioscout.Session`, sorted. ``subjects`` / ``sessions`` filter by  
folder name (a name or a list; None = all)::

    for s in proj.sessions(subjects="H1_orthoload"):  
        s.iteration("gpk").run(do_so=True)

Opened without a second bootstrap -- this Project already did it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1275)</sub>

<a id="projectsession"></a>

### `Project.session`

```python
Project.session(subject, session) -> 'Session'
```

| input | type | default |
|---|---|---|
| `subject` | – | required |
| `session` | – | required |

**returns** `'Session'`

One recording session by folder names::

sess = PROJECT.session("K2L", "11_03_24")  
tpl  = PROJECT.session("_template", "session_01")   # hidden subjects too

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1304)</sub>

<a id="projectresults"></a>

### `Project.results`

```python
Project.results() -> 'Results'
```

**returns** `'Results'`

Results of every session -- same call as :attr:`bioscout.Session.results`,  
plus ``subject=`` / ``session=``::

    PROJECT.results("jcf_so", subject="K2L", trial="Gehen*", window="stance")

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1325)</sub>

<a id="projectrun"></a>

### `Project.run`

```python
Project.run(subjects=None, sessions=None, verbose=True, **run_kw)
```

| input | type | default |
|---|---|---|
| `subjects` | – | `None` |
| `sessions` | – | `None` |
| `verbose` | – | `True` |
| `**run_kw` | – | – |

Run the pipeline over :meth:`sessions`. ``run_kw`` goes to  
:meth:`bioscout.Session.run` -- ``iterations=``, ``trials=``, the stage  
flags (``do_scale``, ``do_exbiomec``, ``do_muscle_analysis``, ``do_so``,  
``do_mew``, ``do_ceinms``, ``export``) and ``replace=``. Nothing runs  
unless you ask for it. One failing session is logged and skipped.  
Returns ``{subject: {session: <Session.run result>}}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1337)</sub>

<a id="projectreset"></a>

### `Project.reset`

```python
Project.reset(
    subjects=None,
    sessions=None,
    trials=None,
    backup=True,
    dry_run=False,
    verbose=True
)
```

| input | type | default |
|---|---|---|
| `subjects` | – | `None` |
| `sessions` | – | `None` |
| `trials` | – | `None` |
| `backup` | – | `True` |
| `dry_run` | – | `False` |
| `verbose` | – | `True` |

Reset :meth:`sessions` back to inputs-only (see  
:meth:`bioscout.Session.reset`); each session is backed up first.  
Returns ``{subject: {session: <reset info>}}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1357)</sub>

<a id="projectmigrate"></a>

### `Project.migrate`

```python
Project.migrate(subjects=None, sessions=None, dry_run=True)
```

| input | type | default |
|---|---|---|
| `subjects` | – | `None` |
| `sessions` | – | `None` |
| `dry_run` | – | `True` |

Rewrite every session.yaml to the current schema (see  
:meth:`bioscout.Session.migrate`): project_dir, model_generic /  
model_scaled / markerset relative to the iteration folder. ``dry_run``  
(default) only prints the diffs. Returns ``{subject: {session: ok}}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1374)</sub>

<a id="projecttrial"></a>

### `Project.trial`

```python
Project.trial(subject, trial, session=None, force_type='SO')
```

| input | type | default |
|---|---|---|
| `subject` | – | required |
| `trial` | – | required |
| `session` | – | `None` |
| `force_type` | – | `'SO'` |

Configured Trial for a subject (name or Subject) / session / trial.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1391)</sub>

<a id="analyse"></a>

## class `Analyse`

```python
Analyse(trialPath=None)
```

| input | type | default |
|---|---|---|
| `trialPath` | – | `None` |

Contains paths from the user settings and functions to implement in the OpenSim/Ceinms analysis

subject_name: Name of the subject (or the trial path if session_name and trial_name are None)

Usage:  
    - Create an instance of the Analyse class with the trial path:

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1623)</sub>

<a id="analysemodel_path"></a>

### `Analyse.model_path`

```python
Analyse.model_path()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1641)</sub>

<a id="analysemodel_path"></a>

### `Analyse.model_path`

```python
Analyse.model_path(v)
```

| input | type | default |
|---|---|---|
| `v` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1643)</sub>

<a id="analysejoint_angles"></a>

### `Analyse.joint_angles`

```python
Analyse.joint_angles()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1646)</sub>

<a id="analysejoint_angles"></a>

### `Analyse.joint_angles`

```python
Analyse.joint_angles(v)
```

| input | type | default |
|---|---|---|
| `v` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1648)</sub>

<a id="analyseinverse_dynamics"></a>

### `Analyse.inverse_dynamics`

```python
Analyse.inverse_dynamics()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1651)</sub>

<a id="analyseinverse_dynamics"></a>

### `Analyse.inverse_dynamics`

```python
Analyse.inverse_dynamics(v)
```

| input | type | default |
|---|---|---|
| `v` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1653)</sub>

<a id="analysestatic_optimisation_forces"></a>

### `Analyse.static_optimisation_forces`

```python
Analyse.static_optimisation_forces()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1656)</sub>

<a id="analysestatic_optimisation_forces"></a>

### `Analyse.static_optimisation_forces`

```python
Analyse.static_optimisation_forces(v)
```

| input | type | default |
|---|---|---|
| `v` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1658)</sub>

<a id="analysestatic_optimisation_activations"></a>

### `Analyse.static_optimisation_activations`

```python
Analyse.static_optimisation_activations()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1661)</sub>

<a id="analysestatic_optimisation_activations"></a>

### `Analyse.static_optimisation_activations`

```python
Analyse.static_optimisation_activations(v)
```

| input | type | default |
|---|---|---|
| `v` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1663)</sub>

<a id="analysegrf"></a>

### `Analyse.grf`

```python
Analyse.grf()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1666)</sub>

<a id="analysegrf"></a>

### `Analyse.grf`

```python
Analyse.grf(v)
```

| input | type | default |
|---|---|---|
| `v` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1668)</sub>

<a id="analysejoint_reaction_so"></a>

### `Analyse.joint_reaction_so`

```python
Analyse.joint_reaction_so()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1671)</sub>

<a id="analysejoint_reaction_so"></a>

### `Analyse.joint_reaction_so`

```python
Analyse.joint_reaction_so(v)
```

| input | type | default |
|---|---|---|
| `v` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1673)</sub>

<a id="analysejoint_reaction_ceinms"></a>

### `Analyse.joint_reaction_ceinms`

```python
Analyse.joint_reaction_ceinms()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1676)</sub>

<a id="analysejoint_reaction_ceinms"></a>

### `Analyse.joint_reaction_ceinms`

```python
Analyse.joint_reaction_ceinms(v)
```

| input | type | default |
|---|---|---|
| `v` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1678)</sub>

<a id="analyseconvert_to_dict"></a>

### `Analyse.convert_to_dict`

```python
Analyse.convert_to_dict(attr_name)
```

| input | type | default |
|---|---|---|
| `attr_name` | – | required |

Convert a specific attribute of the trial to a dictionary

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2039)</sub>

<a id="analyseload_settings"></a>

### `Analyse.load_settings`

```python
Analyse.load_settings(settingsXML)
```

| input | type | default |
|---|---|---|
| `settingsXML` | – | required |

Load all settings for the trial from an xml in trial.path

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2064)</sub>

<a id="analyseload_results"></a>

### `Analyse.load_results`

```python
Analyse.load_results(tag, time_normalise=False)
```

| input | type | default |
|---|---|---|
| `tag` | – | required |
| `time_normalise` | – | `False` |

Load results from a specific output file in the trial directory based on the tag

Options available same as settings.Inputs output file names (e.g 'ik', 'id', 'so_forces', 'ceinms_forces', etc.)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2329)</sub>

<a id="analyseget"></a>

### `Analyse.get`

```python
Analyse.get(attr_name)
```

| input | type | default |
|---|---|---|
| `attr_name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2355)</sub>

<a id="analyseget_time_range_from_eventdetector"></a>

### `Analyse.get_time_range_from_eventDetector`

```python
Analyse.get_time_range_from_eventDetector()
```

Get time range from event detector

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2361)</sub>

<a id="analyseget_time_range"></a>

### `Analyse.get_time_range`

```python
Analyse.get_time_range()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2374)</sub>

<a id="analyseget_trial_type"></a>

### `Analyse.get_trial_type`

```python
Analyse.get_trial_type()
```

Canonical trial type for event interpretation and overlays.

Priority: an explicit ``<trial_type>`` in trial_settings.xml, then the  
detector hint (``_trial_type``), then inference from the trial name.  
Always one of EVENT_SCHEMAS' keys (falls back to 'generic').

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2454)</sub>

<a id="analyseset_events"></a>

### `Analyse.set_events`

```python
Analyse.set_events(events, save=True)
```

| input | type | default |
|---|---|---|
| `events` | – | required |
| `save` | – | `True` |

Set the trial's gait/task events and persist them in trial_settings.xml.

``events`` may be a list of ``(name, time)`` tuples / ``{'name','time'}``  
dicts, or a ``{name: time}`` mapping. Times are seconds. Writes the  
``<events>`` subtree (no separate CSV needed).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2484)</sub>

<a id="analyseget_task_events"></a>

### `Analyse.get_task_events`

```python
Analyse.get_task_events()
```

Task landmarks from the trial's events, using the trial-type schema.

Events come from the ``<events>`` subtree in trial_settings.xml  
(the single source of truth). Returns a dict:  
  ``type``        canonical trial type (EVENT_SCHEMAS key)  
  ``schema``      the schema used  
  ``landmarks``   {canonical_name: [sorted times]}  
  ``window``      (t0, t1) that maps to 0-100% of the normalised axis  
  ``marks``       [times] to draw as vertical lines (e.g. foot_off, take_off)  
  ``axis``        axis label (e.g. '% gait cycle')  
  ``gait_like``   whether gait-based literature curves may be overlaid  
Returns None if the trial has no events.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2504)</sub>

<a id="analyseget_gait_events"></a>

### `Analyse.get_gait_events`

```python
Analyse.get_gait_events()
```

Back-compat wrapper: gait landmarks in the old shape.

Prefer get_task_events(). Returns  
``{'window': (t0,t1), 'foot_contact': [...], 'toe_off': [...]}``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2580)</sub>

<a id="analysedetect_events_from_grf"></a>

### `Analyse.detect_events_from_grf`

```python
Analyse.detect_events_from_grf(threshold=20.0, min_stance_s=0.05, write=False)
```

| input | type | default |
|---|---|---|
| `threshold` | – | `20.0` |
| `min_stance_s` | – | `0.05` |
| `write` | – | `False` |

Detect foot-contact / foot-off events from the vertical GRF.

Force-plate equivalent of the kinematic detector in movement_detector.  
Reads inputs/grf.mot and the plate->foot map from the GRF ExternalLoads  
(self.setup_grf: calcn_r / calcn_l), sums the vertical force per foot,  
and marks each stance onset (contact) and offset (foot off) where Fy  
crosses ``threshold`` N for at least ``min_stance_s`` seconds.

Returns a time-sorted list of ``{'name','time'}`` (e.g. 'Right Foot  
Contact'). With ``write=True`` they are persisted via set_events(). Note  
this returns EVERY detected step; pick a single stride for a gait cycle.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2594)</sub>

<a id="analysedetect_events_from_kinematics"></a>

### `Analyse.detect_events_from_kinematics`

```python
Analyse.detect_events_from_kinematics(
    heel=None,
    toe=None,
    ref=None,
    min_step_s=0.35,
    write=False
)
```

| input | type | default |
|---|---|---|
| `heel` | – | `None` |
| `toe` | – | `None` |
| `ref` | – | `None` |
| `min_step_s` | – | `0.35` |
| `write` | – | `False` |

Detect foot contacts/offs from marker kinematics (no force plates).

Coordinate method of Zeni et al. (2008, Gait Posture): along the walking  
(progression) axis, relative to a pelvis/sacrum reference, Foot Strike =  
heel marker most anterior, Foot Off = toe marker most posterior.  
Parameter-free and robust; works overground or on a treadmill and for  
trials with no / only partial force plates. Validated on this project to  
match the GRF events within a few frames (toe-offs almost exactly).

For a velocity / "degrees-of-freedom" variant that is more robust across  
pathologies — and that transfers to the markerless video pipeline via  
foot keypoints — see the Multi-Condition algorithm (Duret et al. 2025,  
J NeuroEng Rehabil; github.com/FDuRPC/GaitEvent_MultiCondition_algo).

heel/toe: {'r':name,'l':name} marker names (default RHEE/RTOE, LHEE/LTOE).  
ref: pelvis reference marker names (default SACR*/PSIS).  
Returns time-sorted [{'name','time'}]; write=True persists via set_events.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2670)</sub>

<a id="analysedetect_events"></a>

### `Analyse.detect_events`

```python
Analyse.detect_events(method='auto', write=False, **kw)
```

| input | type | default |
|---|---|---|
| `method` | – | `'auto'` |
| `write` | – | `False` |
| `**kw` | – | – |

Detect gait events via 'grf', 'kinematics', or 'auto'.

'auto' tries force plates first (true L/R via GRF.xml) and falls back to  
marker kinematics (Zeni) when there is no / partial GRF — e.g. overground  
trials where the feet miss the plates. Returns time-sorted  
[{'name','time'}]; write=True persists via set_events().

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2760)</sub>

<a id="analyseplot_grf_events"></a>

### `Analyse.plot_grf_events`

```python
Analyse.plot_grf_events(save=True, threshold=40.0)
```

| input | type | default |
|---|---|---|
| `save` | – | `True` |
| `threshold` | – | `40.0` |

Plot per-foot vertical GRF with the trial's gait events, into inputs/.

Uses the trial's events (events_list / <events> subtree) if present, else  
detects them with detect_events_from_grf(). Saves inputs/grf_events.png.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2786)</sub>

<a id="analyseinspect_moment_arms"></a>

### `Analyse.inspect_moment_arms`

```python
Analyse.inspect_moment_arms(dofs=None, side=None, out_dir=None, **kw)
```

| input | type | default |
|---|---|---|
| `dofs` | – | `None` |
| `side` | – | `None` |
| `out_dir` | – | `None` |
| `**kw` | – | – |

Standalone QC of the model's moment arms over THIS trial's MOTION: plots  
each spanning muscle's moment arm vs its joint-angle coordinate over the  
recorded pose trajectory and flags wrap discontinuities. Reads the  
MuscleAnalysis output (run :meth:`run_ma` first) + the IK joint angles — no  
OpenSim, no literature. This is the motion-driven counterpart to the  
``muscle_inspect`` model validation (which sweeps each coordinate over its  
full ROM). Saves ``moment_arm_motion_check.png`` next to the IK, and returns  
``{"figure", "flagged", "dofs"}``.

    it.trial('Deadlift_35kg_01').inspect_moment_arms()

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2865)</sub>

<a id="analyserecrop_to_events"></a>

### `Analyse.recrop_to_events`

```python
Analyse.recrop_to_events(redetect=False)
```

| input | type | default |
|---|---|---|
| `redetect` | – | `False` |

Re-derive the analysis window (start/end time) from the trial's events  
and persist it — WITHOUT re-exporting the raw inputs.

Use this after you have edited the ``<events>`` in trial_settings.xml (or  
want them re-detected) so a plain re-run of IK/ID/MA/SO/JRA solves only  
within the NEW window. A normal re-run does NOT pick up edited events on  
its own, because start_time/end_time already exist in the XML and take  
precedence; this method refreshes them. Also rewrites inputs/grf_events.png.

``redetect=True`` first re-detects the events from the GRF and overwrites  
them; otherwise the current (possibly hand-edited) events are used as-is.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2891)</sub>

<a id="analyseredetect_events"></a>

### `Analyse.redetect_events`

```python
Analyse.redetect_events()
```

Force-re-detect gait events from the GRF (overwriting existing events),  
then re-derive/persist the analysis window and refresh grf_events.png.

Use after the forces changed — a plain export/re-run KEEPS existing foot  
events and will not re-detect. CLI-friendly (no args): equivalent to  
``recrop_to_events(redetect=True)``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2927)</sub>

<a id="analyseplot_emg_processing"></a>

### `Analyse.plot_emg_processing`

```python
Analyse.plot_emg_processing(save=True, channels=None, ncol=3, norm_source=None)
```

| input | type | default |
|---|---|---|
| `save` | – | `True` |
| `channels` | – | `None` |
| `ncol` | – | `3` |
| `norm_source` | – | `None` |

Per-channel EMG figure: raw signal vs filtered + session-normalised.

Reads inputs/emg.mot (raw bipolar) and inputs/emg_filtered_normalised.mot  
(the [0-1] CEINMS excitation). Saves inputs/emg_processing.png. The  
normalised file is written by the session EMG normalisation, so run that  
first (Session.run_emg_normalise / prepare_ceinms).

``norm_source`` (optional) is a ``{channel: trial_name}`` map of which  
trial provided the session max (MVC reference) for each channel; when  
given it is shown in red under each subplot title.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L2936)</sub>

<a id="analyseget_markers"></a>

### `Analyse.get_markers`

```python
Analyse.get_markers()
```

return a dataFrame with the name of each marker in the model and it's parent body

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3024)</sub>

<a id="analyseupdate_trial_attribute"></a>

### `Analyse.update_trial_attribute`

```python
Analyse.update_trial_attribute(attr_name, new_value)
```

| input | type | default |
|---|---|---|
| `attr_name` | – | required |
| `new_value` | – | required |

Update a specific attribute of the trial and save to XML

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3043)</sub>

<a id="analysedelete_trial_attribute"></a>

### `Analyse.delete_trial_attribute`

```python
Analyse.delete_trial_attribute(attr_name)
```

| input | type | default |
|---|---|---|
| `attr_name` | – | required |

Delete a specific attribute of the trial and save to XML

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3049)</sub>

<a id="analysecopy_input_files"></a>

### `Analyse.copy_input_files`

```python
Analyse.copy_input_files(src_subject, replace=False)
```

| input | type | default |
|---|---|---|
| `src_subject` | – | required |
| `replace` | – | `False` |

Copy input files from a template subject to the trial directory if they don't already exist or if replace is True.

src_subject: name of the subject to copy input files from (should be located in SIMULATIONS_DIR/subject/session/)  
replace: whether to replace existing files in the trial directory (default is False)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3058)</sub>

<a id="analyseupdate_model"></a>

### `Analyse.update_model`

```python
Analyse.update_model(new_model_name)
```

| input | type | default |
|---|---|---|
| `new_model_name` | – | required |

Update the model path for the trial and save to XML

new_model_name: str with just the name of the new model file (should be located in MODELS_DIR/subject/session/)

  
**Example usage**

    analysis = utils.Analyse(trialPath='main_dir/Subject/Session/trial')  
    analysis.update_model('scaled_opt_N10_muscles_copied.osim')

  
**Output**

    Updated model path to main_dir/models/Subject/Session/scaled_opt_N10_muscles_copied.osim for trial at main_dir/Subject/Session/trial

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3086)</sub>

<a id="analyseincrease_muscle_force"></a>

### `Analyse.increase_muscle_force`

```python
Analyse.increase_muscle_force(factor: float = 1.0, muscle_list: list = ['all'])
```

| input | type | default |
|---|---|---|
| `factor` | float | `1.0` |
| `muscle_list` | list | `['all']` |

Increase muscle force in the scaled model by a given factor.

  
**Args**

    factor (float): Factor to increase muscle force by. Default is 1.5.  
    replace (bool): Whether to replace existing modified model. Default is False.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3110)</sub>

<a id="analyseget_body_mass"></a>

### `Analyse.get_body_mass`

```python
Analyse.get_body_mass()
```

Retrieve body mass from the scaled model using OpenSim API funtion getTotalMass, and update the trial settings if it differs from the current body mass.

  
**Returns**

    float: Body mass in kg.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3163)</sub>

<a id="analyseget_body_mass_from_grf"></a>

### `Analyse.get_body_mass_from_grf`

```python
Analyse.get_body_mass_from_grf(update=False)
```

| input | type | default |
|---|---|---|
| `update` | – | `False` |

Calculate body mass from GRF data if available.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3206)</sub>

<a id="analyseget_muscle_list"></a>

### `Analyse.get_muscle_list`

```python
Analyse.get_muscle_list()
```

Retrieve list of muscles from the model_dir.

  
**Returns**

    list: List of muscle names.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3226)</sub>

<a id="analyseedit_model_range_coordinates"></a>

### `Analyse.edit_model_range_coordinates`

```python
Analyse.edit_model_range_coordinates(coordinate_name, new_range: list)
```

| input | type | default |
|---|---|---|
| `coordinate_name` | – | required |
| `new_range` | list | required |

Change the range of motion for a specific degree of freedom in the model.

  
**Args**

    coordinate_name (str): Name of the coordinate to modify.   
    new_range (list): New range of motion as [min, max] in radians.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3250)</sub>

<a id="analysescale_emg"></a>

### `Analyse.scale_emg`

```python
Analyse.scale_emg(scale_factor=1.0)
```

| input | type | default |
|---|---|---|
| `scale_factor` | – | `1.0` |

Scale EMG data by a given factor and save to a new file.

  
**Args**

    scale_factor (float): Factor to scale EMG data by. Default is 1.0.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3268)</sub>

<a id="analyseexport_c3d"></a>

### `Analyse.export_c3d`

```python
Analyse.export_c3d(create_folder=None, emg_string_list=None, event_method='auto')
```

| input | type | default |
|---|---|---|
| `create_folder` | – | `None` |
| `emg_string_list` | – | `None` |
| `event_method` | – | `'auto'` |

Export C3D file using the exportC3D script, which extracts EMG data and saves it in a format compatible with CEINMS.

    create_folder: True/False to force subfolder creation; None (default) = auto-detect:  
                   uses create_folder=True when the C3D is outside self.path so that  
                   outputs land in the trial subdir regardless of where the C3D lives.

    emg_string_list: list of strings to identify EMG channels in the C3D file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3302)</sub>

<a id="analyseload_model"></a>

### `Analyse.load_model`

```python
Analyse.load_model(path=None)
```

| input | type | default |
|---|---|---|
| `path` | – | `None` |

Load an OpenSim model with its printBasicInfo() dump suppressed.

``osim.Model(...)`` writes a fixed "MODEL: / coordinates: N / forces: N  
/ ..." block to std::cout on construction. That bypasses OpenSim's  
logger entirely, so opensim_log_level has no effect on it — only the  
fd-level redirect in _osim_quiet_ctx() can swallow it. Several helpers  
(get_body_mass, get_muscle_list, get_markers, ...) load the model  
per call, so a single trial printed the block several times.

Deliberately NOT cached: callers such as increase_muscle_force() and  
adjust_moment_arms() mutate the model they are handed, so handing back a  
shared instance would let one stage's edits leak into another's.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3483)</sub>

<a id="analyseprune_empty_exports"></a>

### `Analyse.prune_empty_exports`

```python
Analyse.prune_empty_exports()
```

Delete exported inputs that contain no data, and say so once.

A marker-only or EMG-only capture legitimately produces some of  
marker_experimental.trc / grf.mot / GRF.xml / grf_events.png with  
nothing in them. Removing them keeps the trial folder honest: the  
session runner's "no experimental inputs" check then correctly skips  
the trial instead of failing inside IK/ID.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3515)</sub>

<a id="analyserun_ik"></a>

### `Analyse.run_ik`

```python
Analyse.run_ik(replace=None)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3570)</sub>

<a id="analyserun_id"></a>

### `Analyse.run_id`

```python
Analyse.run_id(replace=None)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3638)</sub>

<a id="analyserun_ma"></a>

### `Analyse.run_ma`

```python
Analyse.run_ma(replace=None)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3707)</sub>

<a id="analyserun_so"></a>

### `Analyse.run_so`

```python
Analyse.run_so(replace=None, update_actuators=True)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |
| `update_actuators` | – | `True` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3730)</sub>

<a id="analyserun_mrs"></a>

### `Analyse.run_mrs`

```python
Analyse.run_mrs(replace=None, dofs=None, muscles=None, calibrate=None, emg=False, **kw)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |
| `dofs` | – | `None` |
| `muscles` | – | `None` |
| `calibrate` | – | `None` |
| `emg` | – | `False` |
| `**kw` | – | – |

Muscle Redundancy Solver (KU Leuven) for this trial, via MATLAB.

dofs/muscles default to every coordinate in the ID file / MRS's own  
muscle selection. `calibrate` is a list of muscles whose optimal fibre  
length and tendon slack length are estimated. `emg=True` adds the  
EMG-constrained term using this trial's normalised EMG.  
Needs MATLAB and a MuscleRedundancySolver checkout: see docs/MRS.md.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3872)</sub>

<a id="analyserun_energetics"></a>

### `Analyse.run_energetics`

```python
Analyse.run_energetics()
```

Run Metabolic Cost (Energetics) analysis for this trial.

Wraps utils.openSim.run_energetics, which attaches an Umberger (2010)  
metabolic-energy probe set to the scaled model and runs a ProbeReporter.  
Needs the IK coordinates (kinematics) and, ideally, the Static  
Optimization activations (StaticOptimization_activation.sto) so the  
probe evaluates real per-frame muscle activations.

Output: energetics_ProbeReporter_probes.sto in the trial folder.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3920)</sub>

<a id="analyserra_paths"></a>

### `Analyse.rra_paths`

```python
Analyse.rra_paths()
```

Absolute paths of everything the RRA stage reads and writes.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L3972)</sub>

<a id="analyserra_grf_window"></a>

### `Analyse.rra_grf_window`

```python
Analyse.rra_grf_window(threshold=20.0)
```

| input | type | default |
|---|---|---|
| `threshold` | – | `20.0` |

Longest span of this trial with ground reaction force on at least  
one plate (total vertical GRF > ``threshold`` N), as (t0, t1), or None.  
RRA (unlike ID) must not see frames where a foot is on the ground  
without a measured force: it then carries body weight on the pelvis  
residuals and shifts the COM / tracks the pelvis to compensate.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L4004)</sub>

<a id="analyserun_rra"></a>

### `Analyse.run_rra`

```python
Analyse.run_rra(
    replace=None,
    adjust_com=True,
    adjusted_com_body='torso',
    lowpass_cutoff=6.0,
    actuators=None,
    tasks=None,
    template=None,
    time_range=None,
    window='grf',
    rerun=('id', 'so', 'jra'),
    plots=True
)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |
| `adjust_com` | – | `True` |
| `adjusted_com_body` | – | `'torso'` |
| `lowpass_cutoff` | – | `6.0` |
| `actuators` | – | `None` |
| `tasks` | – | `None` |
| `template` | – | `None` |
| `time_range` | – | `None` |
| `window` | – | `'grf'` |
| `rerun` | – | `('id', 'so', 'jra')` |
| `plots` | – | `True` |

Residual Reduction Algorithm for this trial, then the downstream  
pipeline re-run on its result, for comparison with the plain IK/ID/SO::

    <trial>/residual_reduction/  
        outputs/                 RRATool: RRA_Kinematics_q.sto, RRA_Actuation_force.sto,  
                                 <model>_rra_adjusted.osim, setup/actuators/tasks, out.log  
        external_biomechanics/   ID re-run: joint_angles.mot (= RRA kinematics),  
                                 inverse_dynamics.sto           [rerun has "id"]  
        static_optimisation/     SO re-run on the adjusted model  [rerun has "so"]  
        joint_contact_forces/    JRA on that SO                     [rerun has "jra"]  
        rra_moments.png          pelvis residuals + joint moments: ID vs RRA actuators  
        rra_kinematics.png       IK vs RRA kinematics per DOF (+ RMS diff)  
        rra_masses.png           segment masses / COM (on the torso mesh), original vs adjusted  
        rra_so_forces.png        SO muscle forces, original vs after RRA  
        rra_jcf.png              joint contact forces, SO vs SO-after-RRA (+ in vivo when present)

``time_range`` defaults to the trial window narrowed to the span with  
GRF on a plate (``window="grf"``; ``window=None`` keeps the full  
window). ``lowpass_cutoff`` filters the tracked kinematics (6 Hz, as  
ID does; None = the template's setting).

Templates come from the session setup folder (``setup_dir``):  
``setup_RRA.xml``, ``actuators_RRA.xml``, ``tasks_RRA.xml``; the  
keyword arguments override them. Nothing outside residual_reduction/  
is touched: to adopt the RRA result for an iteration, point its  
``model_scaled`` at the adjusted model and copy the RRA kinematics  
over joint_angles.mot yourself.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L4058)</sub>

<a id="analyseplot_rra_moments"></a>

### `Analyse.plot_rra_moments`

```python
Analyse.plot_rra_moments(dofs=None)
```

| input | type | default |
|---|---|---|
| `dofs` | – | `None` |

Task-vertical figure (poses + vGRF on top, as kinematics_moments.png):  
the six pelvis residuals -- ID (solid) vs the RRA residual actuators  
(dashed) -- then one row per summary DOF with the ID joint moment  
(solid) vs the RRA reserve-actuator moment (dashed); right red, left  
blue, midline black. -> rra_moments.png, rra_residuals.csv,  
rra_tracking_error.csv.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L4248)</sub>

<a id="analyseplot_rra_kinematics"></a>

### `Analyse.plot_rra_kinematics`

```python
Analyse.plot_rra_kinematics(dofs=None)
```

| input | type | default |
|---|---|---|
| `dofs` | – | `None` |

IK vs RRA joint angles, one task-vertical row per DOF (right red,  
left blue, midline black; RRA dashed) with the RMS difference in the  
row title -> rra_kinematics.png.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L4360)</sub>

<a id="analyseplot_rra_masses"></a>

### `Analyse.plot_rra_masses`

```python
Analyse.plot_rra_masses()
```

Segment masses and mass centres, original vs RRA-adjusted model ->  
rra_masses.png + rra_masses.csv.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L4478)</sub>

<a id="analyseplot_rra_jcf"></a>

### `Analyse.plot_rra_jcf`

```python
Analyse.plot_rra_jcf()
```

Joint contact forces: SO (solid) vs SO after RRA (dashed), with the  
in-vivo implant force when the trial has one -> rra_jcf.png.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L4582)</sub>

<a id="analyseplot_rra_so_forces"></a>

### `Analyse.plot_rra_so_forces`

```python
Analyse.plot_rra_so_forces(top=16)
```

| input | type | default |
|---|---|---|
| `top` | – | `16` |

SO muscle forces original vs after RRA for the ``top`` muscles by  
peak force, plus the residual/reserve actuator totals -> rra_so_forces.png.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L4594)</sub>

<a id="analyseforward_paths"></a>

### `Analyse.forward_paths`

```python
Analyse.forward_paths()
```

Absolute paths of everything the forward-simulation stage reads/writes.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L4637)</sub>

<a id="analyserun_forward"></a>

### `Analyse.run_forward`

```python
Analyse.run_forward(
    replace=None,
    kinematics='rra',
    model='rra',
    actuators=None,
    tasks=None,
    time_range=None,
    window='grf',
    lowpass_cutoff=6.0,
    cmc_time_window=0.01,
    replay=True,
    jra=True,
    plots=True,
    duration=None
)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |
| `kinematics` | – | `'rra'` |
| `model` | – | `'rra'` |
| `actuators` | – | `None` |
| `tasks` | – | `None` |
| `time_range` | – | `None` |
| `window` | – | `'grf'` |
| `lowpass_cutoff` | – | `6.0` |
| `cmc_time_window` | – | `0.01` |
| `replay` | – | `True` |
| `jra` | – | `True` |
| `plots` | – | `True` |
| `duration` | – | `None` |

Muscle-driven forward simulation of this trial::

    <trial>/forward_simulation/  
        cmc/                    CMCTool: tracks the kinematics by forward-  
                                integrating the muscle-driven model ->  
                                CMC_controls.xml (excitations), CMC_states.sto,  
                                CMC_Actuation_force.sto, CMC_pErr.sto, out.log  
        forward/                ForwardTool: CMC excitations replayed open-loop  
                                from CMC's initial state -> forward_states.sto  
        joint_contact_forces/   JRA on the CMC muscle forces          [jra=True]  
        forward_tracking.csv    RMS / peak |error| per coordinate: CMC and  
                                open-loop forward vs the tracked kinematics  
        forward_kinematics.png  tracked vs CMC vs open-loop per DOF  
        forward_muscle_forces.png  SO vs CMC muscle forces  
        forward_jcf.png         joint contact forces SO vs CMC (+ in vivo)

``kinematics`` / ``model``: "rra" uses residual_reduction/ outputs when  
they exist (RRA kinematics, COM-adjusted model -- the standard  
RRA -> CMC -> forward chain), falling back to IK / the scaled model;  
"ik" forces the plain ones; or pass a path. ``actuators`` defaults to the  
trial's SO actuators (residuals + reserves, appended to the muscles) so  
CMC forces compare 1:1 with SO; ``tasks`` to setupFiles/tasks_CMC.xml,  
else tasks_RRA.xml. Window as run_rra (``window="grf"``).  
Nothing outside forward_simulation/ is touched.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L4671)</sub>

<a id="analyseplot_forward_kinematics"></a>

### `Analyse.plot_forward_kinematics`

```python
Analyse.plot_forward_kinematics(kinematics=None, dofs=None)
```

| input | type | default |
|---|---|---|
| `kinematics` | – | `None` |
| `dofs` | – | `None` |

Tracked (black) vs CMC (blue) vs open-loop forward (red dashed) per  
DOF -> forward_kinematics.png, and forward_tracking.csv.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L4920)</sub>

<a id="analyseplot_forward_muscle_forces"></a>

### `Analyse.plot_forward_muscle_forces`

```python
Analyse.plot_forward_muscle_forces(top=16)
```

| input | type | default |
|---|---|---|
| `top` | – | `16` |

SO (grey) vs CMC (blue) muscle forces for the ``top`` muscles by SO  
peak, plus |reserves + residuals| -> forward_muscle_forces.png.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L4968)</sub>

<a id="analyseplot_forward_jcf"></a>

### `Analyse.plot_forward_jcf`

```python
Analyse.plot_forward_jcf()
```

Joint contact forces SO (solid) vs CMC (dashed), with in vivo -> forward_jcf.png.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5012)</sub>

<a id="analyserun_jra"></a>

### `Analyse.run_jra`

```python
Analyse.run_jra(replace=None)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5023)</sub>

<a id="analyserun_iaa"></a>

### `Analyse.run_iaa`

```python
Analyse.run_iaa(
    engine=None,
    replace=None,
    constraint='rolling',
    force_threshold=20.0,
    plot=True
)
```

| input | type | default |
|---|---|---|
| `engine` | – | `None` |
| `replace` | – | `None` |
| `constraint` | – | `'rolling'` |
| `force_threshold` | – | `20.0` |
| `plot` | – | `True` |

Induced acceleration analysis on the SO forces -> <trial>/induced_accelerations/<engine>/.

engine: "opensim" (InducedAccelerations, potentials x SO forces), "pyosim" (the same  
constrained equations in numpy) or "both" (+ iaa_opensim_vs_pyosim.png). Default: the  
iteration's engine. Needs IK, the GRF xml and the SO force file (run do_so first).  
Layout and columns: bioscout.simulate.iaa_files.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5090)</sub>

<a id="analyseso_result_summary"></a>

### `Analyse.so_result_summary`

```python
Analyse.so_result_summary()
```

One-line SO result summary for the log: peak |resultant| joint reaction  
(contact) force at hip / knee / ankle, in body-weights when body_mass is  
known (else N). Best-effort, reads the SO JRA output on disk.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5141)</sub>

<a id="analyserun_jra_ceinms"></a>

### `Analyse.run_jra_ceinms`

```python
Analyse.run_jra_ceinms(replace=None)
```

| input | type | default |
|---|---|---|
| `replace` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5202)</sub>

<a id="analyseplot_jcf_coverage"></a>

### `Analyse.plot_jcf_coverage`

```python
Analyse.plot_jcf_coverage(labels=None, planes=('sagittal', 'frontal'))
```

| input | type | default |
|---|---|---|
| `labels` | – | `None` |
| `planes` | – | `('sagittal', 'frontal')` |

Contact-loading figures: where the JRA forces land on the bones, by  
gait event, one png per ``plane`` and per JRA source (``labels``: "SO",  
"CEINMS"; default every JRA .sto found in joint_contact_forces/). Writes  
``joint_contact_forces/jrf_<label>_coverage_<plane>.png``. Best-effort:  
a failure is logged, never raised.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5285)</sub>

<a id="analyserun_jra_contributions"></a>

### `Analyse.run_jra_contributions`

```python
Analyse.run_jra_contributions(
    forces_type='both',
    per_muscle=False,
    replace=None,
    keep_sto=False,
    plot=True,
    n_jobs=None,
    groups=None
)
```

| input | type | default |
|---|---|---|
| `forces_type` | – | `'both'` |
| `per_muscle` | – | `False` |
| `replace` | – | `None` |
| `keep_sto` | – | `False` |
| `plot` | – | `True` |
| `n_jobs` | – | `None` |
| `groups` | – | `None` |

Muscle contributions to this trial's joint contact forces.

The JointReaction is linear in the applied forces, so the JCF splits  
exactly into a non-muscle baseline (gravity + inertia + GRF + residuals  
+ reserves) plus one term per muscle group. See  
``bioscout.core.jcf_contributions`` and docs/JCF_CONTRIBUTIONS.md.

forces_type: 'so' | 'ceinms' | 'cmc' | 'both' (= so + ceinms).  
groups: {source name: [muscle columns]} to decompose by; default  
settings.BatchSettings.MUSCLE_GROUPS (+ jcf_contributions.EXTRA_GROUPS).  
Writes joint_contact_forces/contributions_<type>.sto (closure check  
and body weight in its header) and contributions_<type>.png (stacked  
|JCF| figure) -- no folder. keep_sto is ignored. Returns {type: DataFrame}.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5350)</sub>

<a id="analyseplot_jra_comparison"></a>

### `Analyse.plot_jra_comparison`

```python
Analyse.plot_jra_comparison(
    so_only=False,
    save_name='jrf_so_vs_ceinms.png',
    title='Joint Reaction (Contact) Forces: SO vs CEINMS',
    compare=None,
    labels=('SO', 'CEINMS'),
    save_path=None
)
```

| input | type | default |
|---|---|---|
| `so_only` | – | `False` |
| `save_name` | – | `'jrf_so_vs_ceinms.png'` |
| `title` | – | `'Joint Reaction (Contact) Forces: SO vs CEINMS'` |
| `compare` | – | `None` |
| `labels` | – | `('SO', 'CEINMS')` |
| `save_path` | – | `None` |

SO vs CEINMS joint reaction (contact) forces for the joints in  
settings.BatchSettings.JRA_COLUMNS, in the vertical task layout (poses +  
vGRF on top), one row per joint with its |resultant| per leg. Saved into  
joint_contact_forces/ as ``jrf_so.png`` / ``jrf_so_vs_ceinms.png``.

so_only=True ignores any CEINMS output and produces an SO-only figure  
(used right after run_jra so a JCF plot exists even when CEINMS has not  
run / produced no output).

``compare`` is a path to any second JRA .sto to draw dashed against the  
SO one instead of CEINMS (e.g. the JRA after RRA); ``labels`` names the  
two; ``save_path`` overrides the output file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5481)</sub>

<a id="analyserun_emg_filter"></a>

### `Analyse.run_emg_filter`

```python
Analyse.run_emg_filter()
```

Per-trial: filter raw EMG -> emg_filtered.mot.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5796)</sub>

<a id="analyserun_emg_normalise"></a>

### `Analyse.run_emg_normalise`

```python
Analyse.run_emg_normalise()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5928)</sub>

<a id="analyseconvert_mot_to_sto"></a>

### `Analyse.convert_mot_to_sto`

```python
Analyse.convert_mot_to_sto(attr=None)
```

| input | type | default |
|---|---|---|
| `attr` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5952)</sub>

<a id="analysemuscles_per_coordinate"></a>

### `Analyse.muscles_per_coordinate`

```python
Analyse.muscles_per_coordinate(osimModel=None, coord_name=None)
```

| input | type | default |
|---|---|---|
| `osimModel` | – | `None` |
| `coord_name` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5967)</sub>

<a id="analysecalculate_muscle_moments"></a>

### `Analyse.calculate_muscle_moments`

```python
Analyse.calculate_muscle_moments(forces_type='so')
```

| input | type | default |
|---|---|---|
| `forces_type` | – | `'so'` |

Calculate muscle moments by multiplying muscle forces by their moment arms for each coordinate.

forces_type: 'so' for static optimization forces, 'ceinms' for CEINMS muscle forces (default is 'so')

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L5986)</sub>

<a id="analysecompare_marker_locations"></a>

### `Analyse.compare_marker_locations`

```python
Analyse.compare_marker_locations()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6053)</sub>

<a id="analysecheck_moment_arms"></a>

### `Analyse.check_moment_arms`

```python
Analyse.check_moment_arms()
```

Using the openSim.py function checkMomentArms to plot moment arms for each coordinate and muscle, and compare to expected patterns based on muscle geometry.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6068)</sub>

<a id="analyseadjust_moment_arms"></a>

### `Analyse.adjust_moment_arms`

```python
Analyse.adjust_moment_arms(
    radius_step: float = 0.002,
    max_iter: int = 20,
    skip_frames: int = 2
)
```

| input | type | default |
|---|---|---|
| `radius_step` | float | `0.002` |
| `max_iter` | int | `20` |
| `skip_frames` | int | `2` |

Iteratively increases wrapping-surface radii for muscles that have moment-arm  
discontinuities beyond the first `skip_frames` frames, then re-runs the moment-arm  
check.  Stops when no qualifying discontinuities remain or `max_iter` is reached.  
The modified model is saved in place; a .bak copy is created on the first iteration.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6090)</sub>

<a id="analysecalculate_emg_activation_errors"></a>

### `Analyse.calculate_emg_activation_errors`

```python
Analyse.calculate_emg_activation_errors()
```

Calculate errors between EMG activations and CEINMS excitations, and save to a new file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6182)</sub>

<a id="analysecalculate_mean_marker_error"></a>

### `Analyse.calculate_mean_marker_error`

```python
Analyse.calculate_mean_marker_error()
```

Load the _ik_marker_errors.sto file and calculate the mean marker error across all markers and time frames, and save to a new file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6192)</sub>

<a id="analysecalculate_moment_errors"></a>

### `Analyse.calculate_moment_errors`

```python
Analyse.calculate_moment_errors(forces_type='so')
```

| input | type | default |
|---|---|---|
| `forces_type` | – | `'so'` |

Calculate errors between muscle moments calculated from SO or CEINMS forces and the inverse dynamics joint moments, and save to a new file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6204)</sub>

<a id="analysescale_moment_arm"></a>

### `Analyse.scale_moment_arm`

```python
Analyse.scale_moment_arm(coordinate_name, muscles, factor)
```

| input | type | default |
|---|---|---|
| `coordinate_name` | – | required |
| `muscles` | – | required |
| `factor` | – | required |

Scale the moment arm of the given muscle(s) by *factor* and save a new .sto.

  
**Parameters**

sto_path : path to the MomentArm .sto file (e.g. _MuscleAnalysis_MomentArm_hip_flexion_r.sto)  
muscles  : muscle name or list of muscle names matching column headers  
factor   : multiplicative scale factor (e.g. 1.5 increases moment arm by 50 %)

  
**Returns**

Path to the written output file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6243)</sub>

<a id="analyseplot_create_subplot"></a>

### `Analyse.plot_create_subplot`

```python
Analyse.plot_create_subplot(n_muscles, fig=None)
```

| input | type | default |
|---|---|---|
| `n_muscles` | – | required |
| `fig` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6283)</sub>

<a id="analyseplot_moment_arms"></a>

### `Analyse.plot_moment_arms`

```python
Analyse.plot_moment_arms(coord_name: str = None, fig=None)
```

| input | type | default |
|---|---|---|
| `coord_name` | str | `None` |
| `fig` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6298)</sub>

<a id="analyseplot_ik"></a>

### `Analyse.plot_ik`

```python
Analyse.plot_ik(columns_to_plot='all')
```

| input | type | default |
|---|---|---|
| `columns_to_plot` | – | `'all'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6342)</sub>

<a id="analyseplot_id"></a>

### `Analyse.plot_id`

```python
Analyse.plot_id(columns_to_plot='all')
```

| input | type | default |
|---|---|---|
| `columns_to_plot` | – | `'all'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6404)</sub>

<a id="analyseplot_ik_id_summary"></a>

### `Analyse.plot_ik_id_summary`

```python
Analyse.plot_ik_id_summary(columns_to_plot='all')
```

| input | type | default |
|---|---|---|
| `columns_to_plot` | – | `'all'` |

Combined IK+ID inspection figure: one panel per coordinate showing the  
joint ANGLE (solid line, left axis, deg) and the matching ID MOMENT /  
residual (dashed line, right axis, Nm or N) overlaid. Right leg blue,  
left leg red. Uses the same proximal->distal joint-row layout as plot_id.  
Saved next to the ID result as ``<id>_summary.png``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6522)</sub>

<a id="analyseplot_kin_mom_summary"></a>

### `Analyse.plot_kin_mom_summary`

```python
Analyse.plot_kin_mom_summary(dofs=None, compare=None, save_path=None)
```

| input | type | default |
|---|---|---|
| `dofs` | – | `None` |
| `compare` | – | `None` |
| `save_path` | – | `None` |

Compact kinematics+moments figure for the summary DOFs only.

Vertical task layout (poses + vGRF on top), then one row per DOF base:  
ID moment solid (left axis) and joint angle dotted (right axis), left and  
right merged in one row (right red, left blue, midline black).  
DOFs come from SummarySettings.dofs unless overridden. Saved to the  
external_biomechanics folder as ``kinematics_moments.png``. Replaces the  
old joint_angles.png / inverse_dynamics.png / inverse_dynamics_summary.png.

``compare=(ik_path, id_path, label)`` overlays a second IK/ID pair  
(dashed, same colours) -- e.g. the RRA re-run; ``save_path`` overrides  
the output file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6625)</sub>

<a id="analyseplot_so"></a>

### `Analyse.plot_so`

```python
Analyse.plot_so()
```

Static-Optimization results — one figure, one subplot per muscle.

Per muscle: force (red, N), activation (grey line, 0-1 on a twin axis),  
and — for muscles with a measured EMG channel (via  
CEINMSSettings.emg_muscle_mapping) — the normalised EMG shaded grey in the  
background. Uses the model's real muscle set, so pelvis residuals  
(FX/FY/..) and reserve actuators are excluded. Saved as muscle_individual.png  
(no trial name) next to the SO results.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6808)</sub>

<a id="analyseemg_channel_map"></a>

### `Analyse.emg_channel_map`

```python
Analyse.emg_channel_map()
```

{emg_channel: [model_muscles]} for this trial.

session.yaml's ``emg_map`` (injected as ``self.emg_map`` by  
Session._apply_session_config) wins, then CEINMSSettings, then  
BatchSettings. The session must win: two sessions of the same study can  
have different electrode sets and channel names.

When the session defines several NAMED maps, ``self.emg_map`` is  
already the one THIS iteration selected — the resolution happens in  
``Iteration.trial_config``, so every consumer here sees one flat map.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L6908)</sub>

<a id="analyseplot_muscle_moments"></a>

### `Analyse.plot_muscle_moments`

```python
Analyse.plot_muscle_moments()
```

ID moment vs the moment the muscles carry, per reserved coordinate.

``static_optimisation/muscle_moments_<side>.png`` (+ ``muscle_moments.csv``):  
poses and vGRF on top, then one row per reserved coordinate of that leg --  
ID (black), muscles = ID - reserve (blue), reserve (purple), joint angle  
(grey); errors as % of the ID moment's RANGE. See  
bioscout.simulate.so_files.plot_muscle_moments.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7030)</sub>

<a id="analyseplot_residuals"></a>

### `Analyse.plot_residuals`

```python
Analyse.plot_residuals()
```

Pelvis residual inspection for Inverse Dynamics.

Vertical task layout (poses + vGRF on top, bioscout.plot.task_figure),  
then six rows: the three pelvis residual FORCES (pelvis_tx/ty/tz_force)  
and three residual MOMENTS (pelvis_tilt/list/rotation_moment), each  
absolute (left axis) and as a PERCENTAGE of the instantaneous resultant |GRF| (forces) or |GRF|·h  
proxy (moments use |GRF| too), with green (±10%) and gold (±25%) shaded  
bands — the standard residual-acceptance thresholds. Saved to the  
external_biomechanics folder as ``residuals.png``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7050)</sub>

<a id="analysemuscle_inspect"></a>

### `Analyse.muscle_inspect`

```python
Analyse.muscle_inspect(
    motion=None,
    coordinate_names=None,
    muscle_filter=None,
    filter_freq=6.0,
    max_iterations=3,
    min_jump_mm=1.0,
    make_plots=True
)
```

| input | type | default |
|---|---|---|
| `motion` | – | `None` |
| `coordinate_names` | – | `None` |
| `muscle_filter` | – | `None` |
| `filter_freq` | – | `6.0` |
| `max_iterations` | – | `3` |
| `min_jump_mm` | – | `1.0` |
| `make_plots` | – | `True` |

Motion-driven muscle-path check of this trial's model over its kinematics.

Runs ``bioscout.model.inspect`` on ``self.model_dir`` (the trial's OpenSim  
model) driven by ``motion`` (default: this trial's IK joint_angles, i.e.  
``self.ik``). It detects muscle path points inside wrap cylinders that make  
moment arms / muscle lengths discontinuous, projects them out, and writes a  
corrected ``<model>_modWO.osim`` next to the original model plus before/after  
length-waveform figures.

Outputs go to ``<trial>/muscle_inspect/``. Returns  
``(success, corrected_model_path, log_path)``. Needs the `opensim` package.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7131)</sub>

<a id="analysevalidate_trial"></a>

### `Analyse.validate_trial`

```python
Analyse.validate_trial(side='_r')
```

| input | type | default |
|---|---|---|
| `side` | – | `'_r'` |

End-of-analysis model validation for this trial → ``<trial>/validation/``.

Runs ``bioscout.model.inspect`` over THIS trial's kinematics and against  
the literature:  
  1. muscle-path check over the trial's joint_angles (flags/repairs path  
     points inside wrap cylinders that give discontinuous moment arms),  
  2. moment-arm / fibre-length validation vs digitised literature bands,  
  3. joint-contact-force literature bands for the trial TYPE (gait) if any.

Everything is best-effort (wrapped) so it never breaks the pipeline.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7193)</sub>

<a id="analyseplot_jra"></a>

### `Analyse.plot_jra`

```python
Analyse.plot_jra(origin='SO')
```

| input | type | default |
|---|---|---|
| `origin` | – | `'SO'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7287)</sub>

<a id="analyseplot_emg"></a>

### `Analyse.plot_emg`

```python
Analyse.plot_emg()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7347)</sub>

<a id="analyseplot_summary"></a>

### `Analyse.plot_summary`

```python
Analyse.plot_summary()
```

Plot summary of results for a trial and settings DOFs, including:

        - row 1 IK angles  
        - row 2 ID moments + Muscle contributions to moments (Static Optimisation)  
        - row 3 ID moments + Muscle contributions to moments (CEINMS)  
        - row 4 EMG vs SO excitations vs CEINMS excitations (with RMSE and R2 metrics)  
        - row 5 JRA reaction loads (SO vs CEINMS)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7382)</sub>

<a id="analysecreate_ceinms_model"></a>

### `Analyse.create_ceinms_model`

```python
Analyse.create_ceinms_model()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7631)</sub>

<a id="analysecreate_ceinms_input_data"></a>

### `Analyse.create_ceinms_input_data`

```python
Analyse.create_ceinms_input_data()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7711)</sub>

<a id="analysecreate_ceinms_calibration_cfg"></a>

### `Analyse.create_ceinms_calibration_cfg`

```python
Analyse.create_ceinms_calibration_cfg(calibration_trial_names=None)
```

| input | type | default |
|---|---|---|
| `calibration_trial_names` | – | `None` |

Create ceinms_cfg_calibration.xml for CEINMS calibration.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7797)</sub>

<a id="analysecreate_excitation_generator"></a>

### `Analyse.create_excitation_generator`

```python
Analyse.create_excitation_generator()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7821)</sub>

<a id="analysecreate_ceinms_cfg_from_excitation_generator"></a>

### `Analyse.create_ceinms_cfg_from_excitation_generator`

```python
Analyse.create_ceinms_cfg_from_excitation_generator()
```

Create ceinms_cfg_optimise.xml based on excitationGenerator.xml

  
**Args**

    excitation_file: Path to excitationGenerator.xml  
    output_file: Path for output ceinms_cfg_optimise.xml

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7840)</sub>

<a id="analysecreate_ceinms_calibration_setup"></a>

### `Analyse.create_ceinms_calibration_setup`

```python
Analyse.create_ceinms_calibration_setup()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7934)</sub>

<a id="analysecreate_ceinms_optimise_setup"></a>

### `Analyse.create_ceinms_optimise_setup`

```python
Analyse.create_ceinms_optimise_setup()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7943)</sub>

<a id="analyseceinms_is_calibrated"></a>

### `Analyse.ceinms_is_calibrated`

```python
Analyse.ceinms_is_calibrated()
```

Does EXECUTION use the calibrated subject model?

`_overrides` FIRST: session.yaml lands there and is authoritative -- the  
lesson `ceinms.modes._set_weights` records after a bounds run silently  
solved every arm at one gamma. Reading the plain attribute alone would  
report `calibrated` for an iteration session.yaml had switched off.

Default True: trials built outside `Session.trial()` never carry the  
flag and must keep the existing behaviour.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L7989)</sub>

<a id="analyseceinms_execution_subject"></a>

### `Analyse.ceinms_execution_subject`

```python
Analyse.ceinms_execution_subject()
```

The subject XML CEINMS execution must read for this trial.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8012)</sub>

<a id="analyseceinms_exe_tag"></a>

### `Analyse.ceinms_exe_tag`

```python
Analyse.ceinms_exe_tag()
```

`_uncal` for an uncalibrated solve, else ''.

Without it a calibrated and an uncalibrated solve of the same trial and  
weights both write `Execution_a1_b1_g30` and one overwrites the other,  
leaving a result that reads as calibrated whichever ran last.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8018)</sub>

<a id="analyseceinms_exe_out_rel"></a>

### `Analyse.ceinms_exe_out_rel`

```python
Analyse.ceinms_exe_out_rel()
```

Trial-root-relative execution output folder, tag and weights included.

One definition: the setup XML, the JRA forces path and every reader go  
through this, so the folder cannot be named two different ways.  
Still matches `Execution_*`, which is how `ceinms.modes` finds a solve.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8027)</sub>

<a id="analysecreate_ceinms_exe_setup"></a>

### `Analyse.create_ceinms_exe_setup`

```python
Analyse.create_ceinms_exe_setup()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8037)</sub>

<a id="analysecreate_ceinms_exe_cfg"></a>

### `Analyse.create_ceinms_exe_cfg`

```python
Analyse.create_ceinms_exe_cfg()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8064)</sub>

<a id="analyseget_muscle_excitation_mapping"></a>

### `Analyse.get_muscle_excitation_mapping`

```python
Analyse.get_muscle_excitation_mapping(muscle_name)
```

| input | type | default |
|---|---|---|
| `muscle_name` | – | required |

Check if a muscle is present in the excitation mapping of the excitation generator XML.

  
**Args**

    muscle_name (str): Name of the muscle to check.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8080)</sub>

<a id="analyserun_ceinms_calibration"></a>

### `Analyse.run_ceinms_calibration`

```python
Analyse.run_ceinms_calibration()
```

Run the full CEINMS calibration pipeline for this session.

Steps (each is idempotent — skipped if output exists and replace=False):  
  1. create_ceinms_model        — build uncalibrated XML from .osim  
  2. create_excitation_generator — EMG→muscle mapping XML  
  3. create_ceinms_input_data   — motion/force data for this trial  
  4. create_ceinms_calibration_cfg — collects all sibling trial inputs  
  5. create_ceinms_calibration_setup  
  6. run calibration executable

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8100)</sub>

<a id="analyserun_ceinms_exe"></a>

### `Analyse.run_ceinms_exe`

```python
Analyse.run_ceinms_exe()
```

Run CEINMS execution in whatever MODE this session asks for.

The mode decides how many solves happen and what the result IS -- one  
curve, a curve plus a sensitivity band, a range with a median, or a  
weighting taken from an L-curve knee. See  
``bioscout.simulate.ceinms.modes`` for the definitions and  
``ceinms.mode`` in session.yaml for how to pick one.

This is a dispatcher only. `single` (the default, and what every  
project did before modes existed) calls straight through to  
``run_ceinms_exe_single`` -- same solve, same folder name, same  
outputs. Every other mode drives that same method once per arm, so  
there is exactly one code path that actually runs CEINMS.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8284)</sub>

<a id="analyserun_ceinms_exe_single"></a>

### `Analyse.run_ceinms_exe_single`

```python
Analyse.run_ceinms_exe_single()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8319)</sub>

<a id="analyseplot_ceinms_emg_activations"></a>

### `Analyse.plot_ceinms_emg_activations`

```python
Analyse.plot_ceinms_emg_activations(save=True, ncol=3)
```

| input | type | default |
|---|---|---|
| `save` | – | `True` |
| `ncol` | – | `3` |

CEINMS validation: per EMG channel, the normalised EMG excitation vs  
the CEINMS activations of the muscles driven by that channel.

For each channel in ``CEINMSSettings.emg_muscle_mapping`` (channel ->  
[muscles]): gray thick = the normalised EMG excitation; blue = CEINMS  
activations (thin per muscle, thick = mean); red = SO activations (thin  
per muscle, thick = mean). All on a 0-1 axis over the analysis window.  
Colours follow settings.PlottingSettings (utils.plot_style): EMG, CEINMS,  
static_optimisation. Saved to ceinms/emg_vs_activations.png.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8413)</sub>

<a id="analyserun_ceinms_optimise"></a>

### `Analyse.run_ceinms_optimise`

```python
Analyse.run_ceinms_optimise()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8492)</sub>

<a id="analyserun_ceinms_exe_loop"></a>

### `Analyse.run_ceinms_exe_loop`

```python
Analyse.run_ceinms_exe_loop()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8509)</sub>

<a id="analysecheck_best_ceinms_results"></a>

### `Analyse.check_best_ceinms_results`

```python
Analyse.check_best_ceinms_results()
```

loop through ceinms exe results and find best alpha, beta, gamma based on RMS error for joint moments and EMG vs CEINMS excitations 

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8534)</sub>

<a id="analyseadd_so_columns_to_ceinms_results"></a>

### `Analyse.add_so_columns_to_ceinms_results`

```python
Analyse.add_so_columns_to_ceinms_results()
```

Give the CEINMS force file the SAME actuator columns SO's has, so the  
CEINMS JointReaction is set up exactly like SO's (2026-10-22).

* every ``<coord>_reserve`` / coordinate actuator of the trial's  
  ``static_optimisation/actuators_so.xml``: ID moment of that coordinate  
  MINUS the CEINMS muscle moment (sum F x moment arm). So muscles +  
  reserves = ID, as in SO, also for coordinates CEINMS did not track  
  (they get the whole ID moment).  
* every other non-muscle SO column (pelvis residuals FX..MZ, GRF ...):  
  SO's value interpolated by TIME onto the CEINMS time grid (until  
  2026-10-22 these were pasted by ROW, ~0.4 s out of step, and SO's  
  reserves were copied as if they balanced CEINMS's muscles).

Rewrites jra_forces_ceinms in place; earlier added columns are replaced.  
Returns True when the file now carries the SO actuator set.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8549)</sub>

<a id="analyseplot_ceinms_execution_comparison"></a>

### `Analyse.plot_ceinms_execution_comparison`

```python
Analyse.plot_ceinms_execution_comparison()
```

CEINMS-vs-SO muscle results in the muscle_individual.png layout.

One subplot per muscle: FORCE in red (CEINMS solid, SO dashed; N on the  
left axis) and ACTIVATION in grey (CEINMS solid, SO dashed; 0-1 on the  
right axis), with the normalised EMG shaded grey for muscles that have a  
measured channel. R² of each model's activation vs EMG is shown in the  
title (C=CEINMS, S=SO). Saved into ``ceinms/`` as  
``a{alpha}_b{beta}_g{gamma}_results.png`` plus a companion muscle-groups  
figure ``a{alpha}_b{beta}_g{gamma}_muscle_groups.png``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8638)</sub>

<a id="analyseplot_ceinms_calibration_results"></a>

### `Analyse.plot_ceinms_calibration_results`

```python
Analyse.plot_ceinms_calibration_results()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8755)</sub>

<a id="analyseplot_ceinms_vs_so_muscle_moments"></a>

### `Analyse.plot_ceinms_vs_so_muscle_moments`

```python
Analyse.plot_ceinms_vs_so_muscle_moments()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L8764)</sub>

### `build_model_config`

```python
build_model_config(subjects, force_types=('SO', 'CEINMS')) -> dict
```

| input | type | default |
|---|---|---|
| `subjects` | – | required |
| `force_types` | – | `('SO', 'CEINMS')` |

**returns** `dict`

Build a Plot-compatible ``model_config`` dict from a list of Subjects.

Result: ``{curve_label: {subject, color, force_type, line_style}}`` — exactly  
what ``bioscout.utils.Plot`` reads from ``settings.model_config``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L523)</sub>

### `sessions_from_subjects`

```python
sessions_from_subjects(subjects, simulations_dir=None, default_static='static1') -> dict
```

| input | type | default |
|---|---|---|
| `subjects` | – | required |
| `simulations_dir` | – | `None` |
| `default_static` | – | `'static1'` |

**returns** `dict`

Legacy batch ``SESSIONS`` dict ({abs_session_path: static_trial}) derived  
from Subjects — what ``BatchSettings.sessions`` consumes.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L543)</sub>

### `subjects_from_subjects`

```python
subjects_from_subjects(subjects) -> dict
```

| input | type | default |
|---|---|---|
| `subjects` | – | required |

**returns** `dict`

Legacy ``SUBJECTS`` dict ({name: {session, static_trial, group}}) derived  
from Subjects — for code/GUI paths that still read SUBJECTS.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L558)</sub>

### `discover_subjects`

```python
discover_subjects(models_dir=None, session=None, names=None, palette=None, **common)
```

| input | type | default |
|---|---|---|
| `models_dir` | – | `None` |
| `session` | – | `None` |
| `names` | – | `None` |
| `palette` | – | `None` |
| `**common` | – | – |

Auto-build a list of :class:`Subject` from the project's models folder.

Scans ``models_dir`` (defaults to ``bioscout.utils.MODELS_DIR``); each  
sub-folder becomes a Subject, with SO/CEINMS models guessed from its .osim  
files (see :meth:`Subject.from_model_folder`). Looks inside  
``models/<name>/<session>/`` when ``session`` is given and present.

``names`` restricts to specific subjects; ``palette`` overrides colours;  
extra keywords (e.g. ``setup_folder=...``) are applied to every Subject.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L827)</sub>

### `check_settings_version`

```python
check_settings_version(settings, project_dir=None, verbose=True)
```

| input | type | default |
|---|---|---|
| `settings` | – | required |
| `project_dir` | – | `None` |
| `verbose` | – | `True` |

Compare a project's ``settings.__version__`` to the package schema version.

Returns True if they match (or can't be compared), False on mismatch.  
Does NOT modify anything — migrating a heavily-customised project  
``settings.py`` can drop custom fields, so updating is left to an explicit,  
backed-up call (``bioscout.devtools.settings_updater.write_updated_settings``)  
or the GUI's "Update Settings" button.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L919)</sub>

### `migrate_settings`

```python
migrate_settings(project, write=False, verbose=True)
```

| input | type | default |
|---|---|---|
| `project` | – | required |
| `write` | – | `False` |
| `verbose` | – | `True` |

Update a project's settings.py to the current schema, keeping its values.

Same engine as the GUI's "Update Settings" button  
(``bioscout.devtools.settings_updater``): regenerates the file from the latest  
package template and re-injects the project's own values.

``write=False`` (default) returns ``(new_text, preserved_lines)`` for preview.  
``write=True`` writes settings.py in place (backing up the original first)  
and returns the list of preserved-value descriptions.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L984)</sub>

### `ensure_editor_paths`

```python
ensure_editor_paths(project_dir, verbose=True)
```

| input | type | default |
|---|---|---|
| `project_dir` | – | required |
| `verbose` | – | `True` |

Make Pylance/Pyright resolve the project's own modules (e.g. `import  
settings`) by adding "." to python.analysis.extraPaths in the project's  
.vscode/settings.json.

Relative ("."), so it is portable across machines. Idempotent and  
non-destructive: creates the file if missing, otherwise only adds the keys  
that aren't already there. Never raises (editor convenience only).

Takes effect when the project folder is opened as a VS Code workspace  
folder (File ▸ Add Folder to Workspace…).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/analysis.py#L1012)</sub>
