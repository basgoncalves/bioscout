# BioScout API reference

Every public module, function and class, generated from the docstrings by `python -m bioscout.devtools.api_docs`. Click a module for its functions; each function shows its call, its inputs (type, default), what it returns, its docstring and a link to the source.

Quick links: [`bioscout`](#bioscout) · [`bioscout.session`](#bioscoutsession) · [`bioscout.core`](#bioscoutcore) · [`bioscout.simulate`](#bioscoutsimulate) · [`bioscout.model`](#bioscoutmodel) · [`bioscout.results`](#bioscoutresults) · [`bioscout.emg`](#bioscoutemg) · [`bioscout.plot`](#bioscoutplot) · [`bioscout.utils`](#bioscoututils) · [`bioscout.lab`](#bioscoutlab) · [`bioscout.pipeline`](#bioscoutpipeline) · [`bioscout.cli`](#bioscoutcli) · [`bioscout.devtools`](#bioscoutdevtools) · [`bioscout.project_config`](#bioscoutproject_config) · [`bioscout.scale_interactive`](#bioscoutscale_interactive) · [`bioscout.settings`](#bioscoutsettings) · [`bioscout.user_settings`](#bioscoutuser_settings)

## Where to start

| you want to... | look at |
|---|---|
| open a session and run stages | [`bioscout.session.recording.Session`](bioscout.session.recording.md#session), [`bioscout.session.iteration.Iteration`](bioscout.session.iteration.md#iteration) (`run`, `scale_model`, `run_emg_normalise`) |
| work on one trial of one iteration | [`bioscout.core.analysis.Analyse`](bioscout.core.analysis.md#analyse) (`run_ik`, `run_id`, `run_ma`, `run_so`, `run_jra`, `run_jra_contributions`, `plot_*`) |
| understand session.yaml keys | [`bioscout.session.config`](bioscout.session.config.md) (`SessionKeys`, `IterationKeys`) |
| SO reserve / residual actuators | [`bioscout.simulate.so_actuators`](bioscout.simulate.so_actuators.md) (`plan`, `percent_spec`, `percent_reserves`) |
| muscle contributions to JCF | [`bioscout.core.jcf_contributions`](bioscout.core.jcf_contributions.md) (`decompose`, `build_groups`, `summarise`) |
| folder layout resolvers | [`bioscout.session.layout`](bioscout.session.layout.md) |
| figures | [`bioscout.plot`](bioscout.plot.md) (`task_figure.TaskStrip`, `emg_figure`, `jcf_coverage`, ...) |

## bioscout

| module | what it is | members |
|---|---|---|
| [`bioscout`](bioscout.md) |  | 1 |

## bioscout.session

| module | what it is | members |
|---|---|---|
| [`bioscout.session`](bioscout.session.md) | Everything ``bioscout session`` backs: a capture session on disk. | 0 |
| [`bioscout.session.config`](bioscout.session.config.md) | session.yaml — the per-session configuration, read and written. | 18 |
| [`bioscout.session.events`](bioscout.session.events.md) | Gait/task events from editable definitions, not from code. | 6 |
| [`bioscout.session.exportC3D`](bioscout.session.exportC3D.md) |  | 16 |
| [`bioscout.session.form`](bioscout.session.form.md) | The model behind the session editor: read a ``session.yaml``, edit it safely. | 1 |
| [`bioscout.session.gait_events`](bioscout.session.gait_events.md) | Gait events in session.yaml -- one format, read and written in one place. | 5 |
| [`bioscout.session.grf_check`](bioscout.session.grf_check.md) | Audit each trial's force-plate -> foot assignment in GRF.xml. | 2 |
| [`bioscout.session.iteration`](bioscout.session.iteration.md) | Iteration — one model iteration of a recording session: the runnable unit. | 1 |
| [`bioscout.session.layout`](bioscout.session.layout.md) | Where things live inside a session folder — old and new layouts. | 5 |
| [`bioscout.session.motion_detect`](bioscout.session.motion_detect.md) | Find the time range of the actual movement in a capture. | 4 |
| [`bioscout.session.movement_detector`](bioscout.session.movement_detector.md) | movement_detector — detecting and segmenting sports movements. | 17 |
| [`bioscout.session.movement_detector.classifier`](bioscout.session.movement_detector.classifier.md) | classifier.py — frame-level task classification + state-machine transitions. | 1 |
| [`bioscout.session.movement_detector.cycle_runs`](bioscout.session.movement_detector.cycle_runs.md) | cycle_runs — turn a multi-cycle capture into one runnable folder per cycle. | 2 |
| [`bioscout.session.movement_detector.detector`](bioscout.session.movement_detector.detector.md) | detector.py — public API: MotionSegment, DetectorConfig, detect_segments(). | 5 |
| [`bioscout.session.movement_detector.features`](bioscout.session.movement_detector.features.md) | features.py — extract kinematic time-series features from a pose dict. | 1 |
| [`bioscout.session.movement_detector.gap_fill`](bioscout.session.movement_detector.gap_fill.md) | gap_fill.py — fill missing frames in a pose landmark dict using cubic-spline (or linear) interpolation. | 1 |
| [`bioscout.session.movement_detector.mesh_convert`](bioscout.session.movement_detector.mesh_convert.md) | mesh_convert — turn scanned / exported surface meshes into STL. | 5 |
| [`bioscout.session.movement_detector.mesh_from_video`](bioscout.session.movement_detector.mesh_from_video.md) | mesh_from_video — a closed body mesh from a fixed-camera turntable video. | 15 |
| [`bioscout.session.movement_detector.mesh_rig`](bioscout.session.movement_detector.mesh_rig.md) | mesh_rig — turn a single whole-body surface mesh into a rigged OpenSim model. | 13 |
| [`bioscout.session.movement_detector.mocap`](bioscout.session.movement_detector.mocap.md) | mocap.py — trial-level movement classification from MOCAP data. | 17 |
| [`bioscout.session.movement_detector.session`](bioscout.session.movement_detector.session.md) | Run movement detection over a whole exported session. | 1 |
| [`bioscout.session.paths`](bioscout.session.paths.md) | One rule for every path in ``session.yaml``, and a report of which one applied. | 4 |
| [`bioscout.session.recording`](bioscout.session.recording.md) | Session — one recording session folder (the one holding session.yaml). | 2 |
| [`bioscout.session.stage`](bioscout.session.stage.md) | Put the captures a session needs into ``1_c3dfiles/``. | 3 |
| [`bioscout.session.validation`](bioscout.session.validation.md) | Trial-folder checks used by the GUI's calibration-session widget. | 2 |
| [`bioscout.session.windows`](bioscout.session.windows.md) | Per-trial ``time_range`` and ``side`` in session.yaml, from the exported data. | 7 |

## bioscout.core

| module | what it is | members |
|---|---|---|
| [`bioscout.core`](bioscout.core.md) | Project / Subject / Session / Trial and the analysis engine. | 0 |
| [`bioscout.core.analysis`](bioscout.core.analysis.md) | bioscout.core.analysis — the analysis object model. | 10 |
| [`bioscout.core.analysis_runner`](bioscout.core.analysis_runner.md) | Analysis runner that integrates with existing analysis modules. | 3 |
| [`bioscout.core.batch`](bioscout.core.batch.md) | Fire a multi-subject analysis into the background and give the shell back. | 2 |
| [`bioscout.core.jcf_contributions`](bioscout.core.jcf_contributions.md) | Muscle contributions to the joint contact force (JCF), by force superposition. | 16 |
| [`bioscout.core.project_analysis`](bioscout.core.project_analysis.md) | project_analysis.py — project-level analysis across subjects and sessions. | 9 |
| [`bioscout.core.scaffold`](bioscout.core.scaffold.md) | Create a BioScout project folder -- `bioscout init`, and `Project(path)` on a new folder. | 2 |
| [`bioscout.core.status`](bioscout.core.status.md) | What is on disk, per session -- the read-only page you check a run against. | 4 |
| [`bioscout.core.subject_registry`](bioscout.core.subject_registry.md) | subject_registry.py ------------------ Manages the per-project subjects.json file. | 2 |

## bioscout.simulate

| module | what it is | members |
|---|---|---|
| [`bioscout.simulate`](bioscout.simulate.md) | Everything ``bioscout simulate`` backs: run a simulation on an existing model. | 0 |
| [`bioscout.simulate.ceinms`](bioscout.simulate.ceinms.md) | bioscout.simulate.ceinms — the CEINMS toolbox: Python helpers AND the binaries. | 0 |
| [`bioscout.simulate.ceinms.commands`](bioscout.simulate.ceinms.commands.md) | bioscout.simulate.ceinms.commands — Running the CEINMS executables: the terminal wrapper, calibration, execution, the weight loop and CEINMSoptimise. | 7 |
| [`bioscout.simulate.ceinms.configs`](bioscout.simulate.ceinms.configs.md) | bioscout.simulate.ceinms.configs — Builders for every CEINMS XML: the subject model, the excitation generator, calibration cfg/setup, input data, and the execut | 11 |
| [`bioscout.simulate.ceinms.modes`](bioscout.simulate.ceinms.modes.md) | CEINMS execution modes — how many solves, and what the result *is*. | 9 |
| [`bioscout.simulate.ceinms.plot`](bioscout.simulate.ceinms.plot.md) | bioscout.simulate.ceinms.plot — Figures made from CEINMS output — calibration parameters, model comparisons, moment tracking, optimisation results and muscle fo | 10 |
| [`bioscout.simulate.ceinms.shared`](bioscout.simulate.ceinms.shared.md) | bioscout.simulate.ceinms — CEINMS (Calibrated EMG-Informed Neuromusculoskeletal Modelling) helpers: build the excitation generator, subject/calibration/executio | 4 |
| [`bioscout.simulate.fast_ma`](bioscout.simulate.fast_ma.md) | Fast muscle analysis: MTU length + moment arms only, by finite differences. | 4 |
| [`bioscout.simulate.gapfill`](bioscout.simulate.gapfill.md) | Marker gap filling for .trc files — spline for short gaps, rigid-cluster (pattern) fill for long ones. | 8 |
| [`bioscout.simulate.grf_setup`](bioscout.simulate.grf_setup.md) | GRF.xml (OpenSim ExternalLoads) from a GRF .mot -- plain XML, no OpenSim. | 1 |
| [`bioscout.simulate.iaa_files`](bioscout.simulate.iaa_files.md) | Induced acceleration analysis (IAA) files -- one layout for both engines. | 9 |
| [`bioscout.simulate.jra_files`](bioscout.simulate.jra_files.md) | Joint-reaction (contact-force) output names, in ONE place. | 8 |
| [`bioscout.simulate.mew`](bioscout.simulate.mew.md) | mew (muscle extrapolation web) -- a Python-native, always-answers muscle force estimator. | 0 |
| [`bioscout.simulate.mew.analyser`](bioscout.simulate.mew.analyser.md) | Mew -- the public facade. | 1 |
| [`bioscout.simulate.mew.bioscout_adapter`](bioscout.simulate.mew.bioscout_adapter.md) | The bioscout seam. The ONLY module that imports bioscout, and lazily. | 10 |
| [`bioscout.simulate.mew.calibrate`](bioscout.simulate.mew.calibrate.md) | Subject calibration: fit MTU parameters theta to a subject's own trials. | 8 |
| [`bioscout.simulate.mew.compare`](bioscout.simulate.mew.compare.md) | Compare mew output against Static Optimisation and CEINMS. | 7 |
| [`bioscout.simulate.mew.excitation`](bioscout.simulate.mew.excitation.md) | EMG -> muscle excitation. | 5 |
| [`bioscout.simulate.mew.geometry`](bioscout.simulate.mew.geometry.md) | MTU geometry: moment arms r(q) and MTU length l_mt(q). | 6 |
| [`bioscout.simulate.mew.io_ports`](bioscout.simulate.mew.io_ports.md) | File I/O and resampling — the only place that touches disk formats. | 6 |
| [`bioscout.simulate.mew.jcf`](bioscout.simulate.mew.jcf.md) | Joint contact forces from bioscout.simulate.mew muscle forces. | 4 |
| [`bioscout.simulate.mew.ml`](bioscout.simulate.mew.ml.md) | Optional ML layers. Torch is not required for anything else in the package. | 5 |
| [`bioscout.simulate.mew.mtu`](bioscout.simulate.mew.mtu.md) | Hill-type muscle-tendon unit: activation dynamics and force generation. | 12 |
| [`bioscout.simulate.mew.pipeline`](bioscout.simulate.mew.pipeline.md) | One call, one folder: muscle forces + joint contact forces + comparisons. | 1 |
| [`bioscout.simulate.mew.solver`](bioscout.simulate.mew.solver.md) | The one solver. Static optimisation, EMG-informed and hybrid are weights. | 4 |
| [`bioscout.simulate.mew.tiers`](bioscout.simulate.mew.tiers.md) | Tier selection and moment sources -- the "always answers" machinery. | 6 |
| [`bioscout.simulate.mew.types`](bioscout.simulate.mew.types.md) | Data contracts for :mod:`mew`. | 5 |
| [`bioscout.simulate.mrs`](bioscout.simulate.mrs.md) | bioscout.simulate.mrs -- the KU Leuven Muscle Redundancy Solver, driven from BioScout. | 0 |
| [`bioscout.simulate.mrs.cli`](bioscout.simulate.mrs.cli.md) | bioscout.simulate.mrs.cli -- `bioscout simulate mrs check` and `bioscout simulate mrs run <trial>`. | 2 |
| [`bioscout.simulate.mrs.config`](bioscout.simulate.mrs.config.md) | bioscout.simulate.mrs.config -- the Misc struct for the KU Leuven Muscle Redundancy Solver, built in Python and handed to MATLAB as JSON. | 1 |
| [`bioscout.simulate.mrs.io`](bioscout.simulate.mrs.io.md) | bioscout.simulate.mrs.io -- MRS_Results.mat -> OpenSim .sto + a parameter JSON. | 2 |
| [`bioscout.simulate.mrs.runner`](bioscout.simulate.mrs.runner.md) | bioscout.simulate.mrs.runner -- call MATLAB, run the solver, export the results. | 4 |
| [`bioscout.simulate.opensim`](bioscout.simulate.opensim.md) | OpenSim pipeline stages and the input prep that feeds them. | 26 |
| [`bioscout.simulate.pyosim_backend`](bioscout.simulate.pyosim_backend.md) | pyosim back end for bioscout's per-trial steps. | 9 |
| [`bioscout.simulate.so_actuators`](bioscout.simulate.so_actuators.md) | SO reserve/residual actuators: which source is used, and helpers. | 10 |
| [`bioscout.simulate.so_files`](bioscout.simulate.so_files.md) | Static-optimisation output names, in ONE place. | 6 |

## bioscout.model

| module | what it is | members |
|---|---|---|
| [`bioscout.model`](bioscout.model.md) | Model integrity: does every ``.osim`` still find its bones? | 0 |
| [`bioscout.model.cli`](bioscout.model.cli.md) | Command line for ``bioscout.model``. | 3 |
| [`bioscout.model.edit`](bioscout.model.edit.md) | bioscout.model.edit =================== | 2 |
| [`bioscout.model.edit.cli`](bioscout.model.edit.cli.md) | Command line for model_edit — guided when you have no arguments, flat when you do. | 3 |
| [`bioscout.model.edit.introspect`](bioscout.model.edit.introspect.md) | What is *in* a model — read without OpenSim, so a UI can be built offline. | 9 |
| [`bioscout.model.edit.naming`](bioscout.model.edit.naming.md) | Where an operation's output goes — one rule, in one place. | 3 |
| [`bioscout.model.edit.ops`](bioscout.model.edit.ops.md) | Importing this package populates :data:`bioscout.model.edit.spec.REGISTRY`. | 0 |
| [`bioscout.model.edit.ops.coordinates`](bioscout.model.edit.ops.coordinates.md) | Coordinate ranges and locking. | 2 |
| [`bioscout.model.edit.ops.inspect`](bioscout.model.edit.ops.inspect.md) | Read-only checks. None of these write a model. | 5 |
| [`bioscout.model.edit.ops.markers`](bioscout.model.edit.ops.markers.md) | Marker placement and marker-set edits. | 2 |
| [`bioscout.model.edit.ops.moment_arms`](bioscout.model.edit.ops.moment_arms.md) | Moment-arm operations — wrap radii and path points. | 7 |
| [`bioscout.model.edit.ops.reserves`](bioscout.model.edit.ops.reserves.md) | Reserve and residual actuators -- the force set static optimisation needs. | 1 |
| [`bioscout.model.edit.ops.scale`](bioscout.model.edit.ops.scale.md) | Dimensional scaling and mass — the two halves of "make it this subject". | 3 |
| [`bioscout.model.edit.ops.strength`](bioscout.model.edit.ops.strength.md) | Muscle force and muscle-tendon parameters. | 2 |
| [`bioscout.model.edit.osim_ops`](bioscout.model.edit.osim_ops.md) | Model-editing operations backed by the OpenSim API. | 16 |
| [`bioscout.model.edit.prompt`](bioscout.model.edit.prompt.md) | Interactive prompt helpers, in one place. | 5 |
| [`bioscout.model.edit.recipe`](bioscout.model.edit.recipe.md) | A model build, written down. | 5 |
| [`bioscout.model.edit.run`](bioscout.model.edit.run.md) | Applying an operation: validate, resolve the output path, delegate. | 6 |
| [`bioscout.model.edit.spec`](bioscout.model.edit.spec.md) | The contract every model operation obeys, and the registry they live in. | 6 |
| [`bioscout.model.geometry`](bioscout.model.geometry.md) | Where an ``.osim`` model's bone meshes actually resolve to — or don't. | 7 |
| [`bioscout.model.inspect`](bioscout.model.inspect.md) | muscle_inspect | 0 |
| [`bioscout.model.inspect.compare_settings`](bioscout.model.inspect.compare_settings.md) | compare_settings.py | 1 |
| [`bioscout.model.inspect.core`](bioscout.model.inspect.core.md) | muscle_inspect.core -- compatibility aggregator. | 1 |
| [`bioscout.model.inspect.cross_body`](bioscout.model.inspect.cross_body.md) | Cross-body wrap penetration fix, driven by coordinate sweeps (no .mot needed). | 1 |
| [`bioscout.model.inspect.discontinuity`](bioscout.model.inspect.discontinuity.md) | Discontinuity detection for 1-D waveforms (no OpenSim dependency). | 2 |
| [`bioscout.model.inspect.fl_fv_report`](bioscout.model.inspect.fl_fv_report.md) | Build the fibre force-length-velocity figure from a session. | 8 |
| [`bioscout.model.inspect.fl_fv_surface`](bioscout.model.inspect.fl_fv_surface.md) | Fibre operating point on the Hill force-length-velocity surface. | 9 |
| [`bioscout.model.inspect.geometry`](bioscout.model.inspect.geometry.md) | Pure-numpy cylinder geometry (no OpenSim dependency). | 3 |
| [`bioscout.model.inspect.literature_jcf`](bioscout.model.inspect.literature_jcf.md) | Literature joint-contact-force / muscle-force curves for validation overlays. | 6 |
| [`bioscout.model.inspect.logutil`](bioscout.model.inspect.logutil.md) | Timestamped logging + simple timing helpers (no OpenSim dependency). | 4 |
| [`bioscout.model.inspect.model_ma_check`](bioscout.model.inspect.model_ma_check.md) | Moment-arm discontinuity check straight from a MODEL and a motion. | 2 |
| [`bioscout.model.inspect.moment_arm_motion`](bioscout.model.inspect.moment_arm_motion.md) | Moment-arm QC over the ACTUAL TRIAL MOTION (not a ROM sweep). | 1 |
| [`bioscout.model.inspect.moment_arms`](bioscout.model.inspect.moment_arms.md) | Moment-arm and muscle-length sweeps over coordinate range of motion. | 5 |
| [`bioscout.model.inspect.multi_model`](bioscout.model.inspect.multi_model.md) | Compare SEVERAL models against each other and against the literature. | 4 |
| [`bioscout.model.inspect.muscle_checker`](bioscout.model.inspect.muscle_checker.md) | Motion-driven muscle-path checker -- Python port of the MATLAB `muscleChecker`. | 14 |
| [`bioscout.model.inspect.muscle_length_validation`](bioscout.model.inspect.muscle_length_validation.md) | Literature moment-arm AND muscle-architecture validation (reusable). | 8 |
| [`bioscout.model.inspect.paths`](bioscout.model.inspect.paths.md) | Locations of the literature data bundled with this package, and of the per-model report folders written next to a model on disk. | 3 |
| [`bioscout.model.inspect.plotting`](bioscout.model.inspect.plotting.md) | Plot moment-arm / muscle-length sweeps, before vs after correction. | 2 |
| [`bioscout.model.inspect.radius_reduce`](bioscout.model.inspect.radius_reduce.md) | Radius-reduction fallback (MATLAB Phase 3, priority 2). | 3 |
| [`bioscout.model.inspect.run_moment_arm_inspection`](bioscout.model.inspect.run_moment_arm_inspection.md) | Adjust the moment arms of an OpenSim model, plot before/after, and validate vs literature. | 1 |
| [`bioscout.model.inspect.run_muscle_checker`](bioscout.model.inspect.run_muscle_checker.md) | run_muscle_checker.py  --  motion-driven muscle-path checker (matches MATLAB muscleChecker) | 1 |
| [`bioscout.model.inspect.strength`](bioscout.model.inspect.strength.md) | Isometric joint-strength validation. | 5 |
| [`bioscout.model.inspect.validate_against_literature`](bioscout.model.inspect.validate_against_literature.md) | validate_against_literature.py  --  standalone literature validation. | 1 |
| [`bioscout.model.inspect.validation`](bioscout.model.inspect.validation.md) | Literature moment-arm validation (reusable). | 3 |
| [`bioscout.model.inspect.wrap_fixer`](bioscout.model.inspect.wrap_fixer.md) | Detect and fix muscle path points that lie inside wrap cylinders. | 7 |
| [`bioscout.model.io`](bioscout.model.io.md) | File input/output shared across ``bioscout.model``: meshes, models, landmarks. | 7 |
| [`bioscout.model.measure`](bioscout.model.measure.md) | Measurements from bone meshes (STL) — model-independent building blocks. | 30 |
| [`bioscout.model.moment_arms`](bioscout.model.moment_arms.md) | bioscout.model.moment_arms =========================== | 0 |
| [`bioscout.model.moment_arms.cli`](bioscout.model.moment_arms.cli.md) | ``bioscout --change-moment-arms`` — guided moment-arm adjustment. | 1 |
| [`bioscout.model.moment_arms.core`](bioscout.model.moment_arms.core.md) | Wire the solver to real OpenSim moment-arm sweeps. | 9 |
| [`bioscout.model.moment_arms.inspection`](bioscout.model.moment_arms.inspection.md) | Check a moment-arm edit the moment it is made. | 4 |
| [`bioscout.model.moment_arms.paths`](bioscout.model.moment_arms.paths.md) | Translate a muscle's path points — the fallback for muscles without a wrap. | 3 |
| [`bioscout.model.moment_arms.solve`](bioscout.model.moment_arms.solve.md) | Solve for the wrap radius that produces a requested moment-arm change. | 3 |
| [`bioscout.model.moment_arms.volumes`](bioscout.model.moment_arms.volumes.md) | Turn segmented muscle volumes into a wrap-radius factor. | 4 |
| [`bioscout.model.moment_arms.wraps`](bioscout.model.moment_arms.wraps.md) | Read and edit wrap-surface radii — pure ``xml.etree``, no OpenSim needed. | 6 |
| [`bioscout.model.mri2msk`](bioscout.model.mri2msk.md) | MRI2MSK: personalised musculoskeletal models from MRI bone segmentations. | 0 |
| [`bioscout.model.mri2msk.cli`](bioscout.model.mri2msk.cli.md) | `bioscout model mri2msk`: the MRI2MSK steps from the command line. | 1 |
| [`bioscout.model.mri2msk.geometry`](bioscout.model.mri2msk.geometry.md) | Mesh I/O and pure-numpy transform helpers (no OpenSim dependency). | 11 |
| [`bioscout.model.mri2msk.gui`](bioscout.model.mri2msk.gui.md) | MRI2MSK GUI - BioScout-style (dark CustomTkinter). | 4 |
| [`bioscout.model.mri2msk.gui_postwarp`](bioscout.model.mri2msk.gui_postwarp.md) | Post-Warp Pipeline page (BioScout session) for the MRI2MSK GUI. | 1 |
| [`bioscout.model.mri2msk.landmarks`](bioscout.model.mri2msk.landmarks.md) | Automatic landmark generation for the OpenSim Creator Mesh Warper. | 11 |
| [`bioscout.model.mri2msk.model_warper`](bioscout.model.mri2msk.model_warper.md) | Python re-implementation of the OpenSim Creator Model Warper (step 5). | 7 |
| [`bioscout.model.mri2msk.osim_utils`](bioscout.model.mri2msk.osim_utils.md) | OpenSim-API helpers (port of the torsion-correction helpers in MRI2MSK.m). | 13 |
| [`bioscout.model.mri2msk.pipeline`](bioscout.model.mri2msk.pipeline.md) | MRI2MSK warping pipeline - Python port of the executeStepXX functions in MRI2MSK.m. | 23 |
| [`bioscout.model.mri2msk.postwarp`](bioscout.model.mri2msk.postwarp.md) | Post-Warp pipeline on a BioScout session. | 10 |
| [`bioscout.model.mri2msk.staple`](bioscout.model.mri2msk.staple.md) | Python port of the parts of STAPLE / GIBOC-core used by MRI2MSK step 1. | 0 |
| [`bioscout.model.mri2msk.staple.algorithms`](bioscout.model.mri2msk.staple.algorithms.md) | STAPLE joint coordinate systems used by MRI2MSK step 1. | 16 |
| [`bioscout.model.mri2msk.staple.fitting`](bioscout.model.mri2msk.staple.fitting.md) | Fitting routines from GIBOC-core/SubFunctions/FittingFun (+ LSGE lsplane). | 5 |
| [`bioscout.model.mri2msk.staple.trimesh_core`](bioscout.model.mri2msk.staple.trimesh_core.md) | Triangulation core: a minimal stand-in for MATLAB's ``triangulation`` object plus the GIBOC-core ``Tri*`` mesh functions used by STAPLE. | 26 |
| [`bioscout.model.mri2msk.ui_theme`](bioscout.model.mri2msk.ui_theme.md) | BioScout-style look for the MRI2MSK GUI (dark CustomTkinter). | 12 |
| [`bioscout.model.muscle_optimize`](bioscout.model.muscle_optimize.md) | The Modenese (2015) muscle-parameter optimiser. | 5 |
| [`bioscout.model.opensim_base`](bioscout.model.opensim_base.md) | Low-level OpenSim wrapper plumbing shared by ``model/`` and ``simulate/``. | 2 |
| [`bioscout.model.osim_model`](bioscout.model.osim_model.md) | bioscout.model.osim_model -- edit an .osim like an object (plain XML, no OpenSim). | 6 |
| [`bioscout.model.report`](bioscout.model.report.md) | Compare the DIMENSIONS and SEGMENT MASSES of several ``.osim`` models. | 6 |
| [`bioscout.model.scale`](bioscout.model.scale.md) | Model scaling: measurements/ScaleTool helpers (``measurements``) and the GUI's ``ModelScaler`` wrapper (``model_scaler``). Backs ``bioscout model scale``. | 0 |
| [`bioscout.model.scale.measurements`](bioscout.model.scale.measurements.md) | Build a real ScaleTool MeasurementSet for the powerlifting marker protocol. | 17 |
| [`bioscout.model.scale.model_scaler`](bioscout.model.scale.model_scaler.md) | OpenSim Model Scaling Tool integration. | 1 |
| [`bioscout.model.scale.osim_scale`](bioscout.model.scale.osim_scale.md) | ScaleTool driving: build a scaled model, and place its markers. | 6 |
| [`bioscout.model.scale.pyosim_scale`](bioscout.model.scale.pyosim_scale.md) | Model scaling with bioscout.pyosim, for iterations with ``engine: pyosim``. | 2 |
| [`bioscout.model.scale_muscle_forces`](bioscout.model.scale_muscle_forces.md) | bioscout.model.scale_muscle_forces - allometric and athlete-specific Fmax scaling (session.yaml `fmax_scaling`). | 5 |
| [`bioscout.model.torsion_tool`](bioscout.model.torsion_tool.md) | Impose target femoral and tibial torsion on an OpenSim model. | 6 |
| [`bioscout.model.tps`](bioscout.model.tps.md) | bioscout.model.tps ======================== | 0 |
| [`bioscout.model.tps.axes`](bioscout.model.tps.axes.md) | Anatomical axis construction and rigid alignment of each body to OpenSim. | 3 |
| [`bioscout.model.tps.bioscout_adapter`](bioscout.model.tps.bioscout_adapter.md) | BioScout integration — the only BioScout-aware file in this package. | 5 |
| [`bioscout.model.tps.cli`](bioscout.model.tps.cli.md) | Command-line entry point. | 2 |
| [`bioscout.model.tps.config`](bioscout.model.tps.config.md) | Configuration objects. | 2 |
| [`bioscout.model.tps.geometry`](bioscout.model.tps.geometry.md) | Pure geometric helpers (numpy only). | 9 |
| [`bioscout.model.tps.landmarks`](bioscout.model.tps.landmarks.md) | Loaders for landmark / marker data. | 4 |
| [`bioscout.model.tps.landmarks_cli`](bioscout.model.tps.landmarks_cli.md) | ``tps-landmarks`` — derive bone landmarks from MRI segmentation masks. | 2 |
| [`bioscout.model.tps.landmarks_from_mri`](bioscout.model.tps.landmarks_from_mri.md) | Derive bone landmarks directly from MRI segmentation masks. | 5 |
| [`bioscout.model.tps.logging_utils`](bioscout.model.tps.logging_utils.md) | Centralised logging. | 2 |
| [`bioscout.model.tps.model_compat`](bioscout.model.tps.model_compat.md) | Check whether a bone-landmark template can be reused across generic models. | 5 |
| [`bioscout.model.tps.osim_format`](bioscout.model.tps.osim_format.md) | Read/write helpers that work on **both** OpenSim 3.x and 4.x ``.osim`` XML. | 7 |
| [`bioscout.model.tps.osim_model`](bioscout.model.tps.osim_model.md) | Parse an OpenSim ``.osim`` file into tidy DataFrames. | 6 |
| [`bioscout.model.tps.pipeline`](bioscout.model.tps.pipeline.md) | High-level personalisation orchestrator. | 2 |
| [`bioscout.model.tps.recording`](bioscout.model.tps.recording.md) | Write transformed geometry back to disk. | 1 |
| [`bioscout.model.tps.scaling`](bioscout.model.tps.scaling.md) | Subject-specific scaling helpers. | 4 |
| [`bioscout.model.tps.tps`](bioscout.model.tps.tps.md) | Thin-plate-spline transform for a single body. | 1 |
| [`bioscout.model.verify`](bioscout.model.verify.md) | Verify that every ``.osim`` in a tree can find every mesh it references. | 6 |

## bioscout.results

| module | what it is | members |
|---|---|---|
| [`bioscout.results`](bioscout.results.md) | bioscout.results — load, analyse, plot and export simulation results. | 3 |
| [`bioscout.results.actions`](bioscout.results.actions.md) | Built-in ResultSet actions. Each is a plain function ``f(rs, ...)`` registered with :func:`bioscout.results.action` -- copy one to write your own. | 6 |
| [`bioscout.results.export`](bioscout.results.export.md) | Every time-varying result of a project -> analysis-ready CSVs. | 4 |
| [`bioscout.results.io`](bioscout.results.io.md) | Read an OpenSim / CEINMS storage file. | 1 |
| [`bioscout.results.kinds`](bioscout.results.kinds.md) | Which result files exist, and what each one is called. | 5 |
| [`bioscout.results.load`](bioscout.results.load.md) | Results files -> DataFrames. The one reader used by ``session.results(...)``, :func:`bioscout.results.load` and the CSV export. | 4 |
| [`bioscout.results.plotting`](bioscout.results.plotting.md) | Matplotlib for ResultSet.plot -- imported only when a plot is asked for. | 4 |
| [`bioscout.results.resultset`](bioscout.results.resultset.md) | ResultSet: one result variable across any number of sessions, iterations, trials and cycles -- a DataFrame with a few helpers, extensible with actions. | 3 |
| [`bioscout.results.scan`](bioscout.results.scan.md) | Find sessions and their result files. Reads folder names and session.yaml / cycles.csv only -- never a result file. | 5 |
| [`bioscout.results.windows`](bioscout.results.windows.md) | Cut one result file into windows (stance / cycle / whole trial) and optionally time-normalise each to ``points`` samples. | 4 |

## bioscout.emg

| module | what it is | members |
|---|---|---|
| [`bioscout.emg`](bioscout.emg.md) | EMG domain code: filtering, channel mapping, MVC normalisation, analysis. | 0 |
| [`bioscout.emg.analysis`](bioscout.emg.analysis.md) | EMG frequency content and muscle synergies. | 10 |
| [`bioscout.emg.channels`](bioscout.emg.channels.md) | Inspect a c3d's analog channels and write the emg_map for session.yaml. | 5 |
| [`bioscout.emg.emg`](bioscout.emg.emg.md) | bioscout.emg.emg — unified EMG processing surface. | 4 |
| [`bioscout.emg.filter`](bioscout.emg.filter.md) | EMG filter settings: what was actually applied, and where it came from. | 5 |
| [`bioscout.emg.normalise`](bioscout.emg.normalise.md) |  | 10 |

## bioscout.plot

| module | what it is | members |
|---|---|---|
| [`bioscout.plot`](bioscout.plot.md) | bioscout.plot — project-independent comparison figures. | 4 |
| [`bioscout.plot.activation_dynamics`](bioscout.plot.activation_dynamics.md) | bioscout.plot.activation_dynamics - effect of CEINMS c1, c2 and shape factor A on excitation -> activation (Lloyd & Besier 2003). | 4 |
| [`bioscout.plot.collings`](bioscout.plot.collings.md) | Collings-style rank-shift figures for muscle force. | 12 |
| [`bioscout.plot.compare`](bioscout.plot.compare.md) | bioscout.plot.compare — one comparison figure, any two things. | 1 |
| [`bioscout.plot.config`](bioscout.plot.config.md) | bioscout.plot.config — figure settings that live IN bioscout, not in a project. | 6 |
| [`bioscout.plot.emg_figure`](bioscout.plot.emg_figure.md) | emg_processing.png in the vertical task layout (vGRF on top). | 2 |
| [`bioscout.plot.figures`](bioscout.plot.figures.md) | bioscout.plot.figures - one catalogue for every plot in this project. | 15 |
| [`bioscout.plot.jcf_coverage`](bioscout.plot.jcf_coverage.md) | Where the joint contact forces of one trial land on the bones. | 3 |
| [`bioscout.plot.jcf_direction`](bioscout.plot.jcf_direction.md) | Polar plot of joint contact force DIRECTION and magnitude, on the model's bones. | 27 |
| [`bioscout.plot.kinematics`](bioscout.plot.kinematics.md) | Joint angles and IK marker errors, compared across a session's iterations. | 16 |
| [`bioscout.plot.muscle_moments_task`](bioscout.plot.muscle_moments_task.md) | Muscle vs ID moments in the context of the task: poses, GRF and joint angles. | 2 |
| [`bioscout.plot.summary`](bioscout.plot.summary.md) | BioScout — Summary module ========================== | 4 |
| [`bioscout.plot.task_figure`](bioscout.plot.task_figure.md) | Vertical trial figures with the TASK on top. | 6 |
| [`bioscout.plot.tidy`](bioscout.plot.tidy.md) | bioscout.plot.tidy — the one table shape every bioscout figure understands. | 7 |
| [`bioscout.plot.work`](bioscout.plot.work.md) | bioscout.plot.work — muscle work, from .sto files to a tidy table. | 7 |

## bioscout.utils

| module | what it is | members |
|---|---|---|
| [`bioscout.utils`](bioscout.utils.md) |  | 2 |
| [`bioscout.utils.analyse`](bioscout.utils.analyse.md) | Command-line entry point: run Analyse methods on a trial folder. | 1 |
| [`bioscout.utils.file_edit`](bioscout.utils.file_edit.md) | bioscout.utils.file_edit — one document model for every config file we edit. | 9 |
| [`bioscout.utils.filters`](bioscout.utils.filters.md) | Generic zero-phase signal filtering -- the primitives, with no domain in them. | 3 |
| [`bioscout.utils.helpers`](bioscout.utils.helpers.md) | Helper functions for batch processing pipeline | 3 |
| [`bioscout.utils.io`](bioscout.utils.io.md) | bioscout.utils.io — motion-capture file I/O (TRC / MOT / STO / C3D) and XML helpers. Extracted from utils/__init__.py. | 18 |
| [`bioscout.utils.logger`](bioscout.utils.logger.md) | Logging utility for the Powerlifting Model Analysis App. | 1 |
| [`bioscout.utils.paths`](bioscout.utils.paths.md) | Path helpers for the setup files bioscout writes. | 5 |
| [`bioscout.utils.plotting`](bioscout.utils.plotting.md) | bioscout.utils.plotting — figure/axis helpers (layout, saving, interactive export). Extracted from utils/__init__.py. | 8 |
| [`bioscout.utils.resource_cleanup`](bioscout.utils.resource_cleanup.md) | Utility for managing system resources during recording/analysis. | 5 |
| [`bioscout.utils.shared`](bioscout.utils.shared.md) | bioscout.utils.shared — small, dependency-light helpers needed across several utils modules (analyse, analysis, emg, plotting, …). | 19 |
| [`bioscout.utils.stats`](bioscout.utils.stats.md) | bioscout.utils.stats — small, dependency-free numeric helpers used across the analysis pipeline (curve agreement metrics). Extracted from utils/__init__.py so t | 9 |
| [`bioscout.utils.text_prints`](bioscout.utils.text_prints.md) | Console/log formatting helpers -- the shape bioscout's output already has. | 5 |
| [`bioscout.utils.xml_utils`](bioscout.utils.xml_utils.md) | XML Utilities - Pretty printing and formatting XML files. Version: 1.0.0 | 2 |

## bioscout.lab

| module | what it is | members |
|---|---|---|
| [`bioscout.lab`](bioscout.lab.md) | EXPERIMENTAL (3.x): the `bioscout lab` verb -- video and wearable tracking. | 0 |
| [`bioscout.lab.load_tracking`](bioscout.lab.load_tracking.md) | BioScout — Load Tracking module ================================ | 0 |
| [`bioscout.lab.load_tracking.connect`](bioscout.lab.load_tracking.connect.md) | Cloud-credentials loading + helpers for pulling sessions into a LoadTracker. | 3 |
| [`bioscout.lab.load_tracking.contraction`](bioscout.lab.load_tracking.contraction.md) | Contraction-type work breakdown (heuristic). | 3 |
| [`bioscout.lab.load_tracking.fatigue`](bioscout.lab.load_tracking.fatigue.md) | Per-muscle fatigue model. | 4 |
| [`bioscout.lab.load_tracking.importers`](bioscout.lab.load_tracking.importers.md) | Session importers for the load-tracking module. | 5 |
| [`bioscout.lab.load_tracking.metrics`](bioscout.lab.load_tracking.metrics.md) | Sports-science load metrics for the load-tracking module. | 12 |
| [`bioscout.lab.load_tracking.ml_interface`](bioscout.lab.load_tracking.ml_interface.md) | Pluggable muscle-force / loading estimator interface. | 3 |
| [`bioscout.lab.load_tracking.muscle_map`](bioscout.lab.load_tracking.muscle_map.md) | Activity → muscle-group load distribution. | 2 |
| [`bioscout.lab.load_tracking.report`](bioscout.lab.load_tracking.report.md) | PDF report for the load-tracking module. | 1 |
| [`bioscout.lab.load_tracking.sample_data`](bioscout.lab.load_tracking.sample_data.md) | Synthetic sample-data generator for the load-tracking module. | 1 |
| [`bioscout.lab.load_tracking.shot_analysis`](bioscout.lab.load_tracking.shot_analysis.md) | BioScout — Shot Analysis (prototype) ==================================== | 19 |
| [`bioscout.lab.load_tracking.strava_api`](bioscout.lab.load_tracking.strava_api.md) | Strava importer. | 3 |
| [`bioscout.lab.load_tracking.tracker`](bioscout.lab.load_tracking.tracker.md) | LoadTracker — orchestrator for the load-tracking module. | 3 |
| [`bioscout.lab.load_tracking.tracking_store`](bioscout.lab.load_tracking.tracking_store.md) | Per-subject tracking store. | 4 |
| [`bioscout.lab.load_tracking.zepp_cloud`](bioscout.lab.load_tracking.zepp_cloud.md) | Zepp / Huami cloud importer. | 5 |
| [`bioscout.lab.record`](bioscout.lab.record.md) | Recording module for the Analysis App. | 0 |
| [`bioscout.lab.record.screen_record`](bioscout.lab.record.screen_record.md) | Screen recording utility with area selection, trimming, and preview capabilities. | 1 |
| [`bioscout.lab.record.video`](bioscout.lab.record.video.md) |  | 4 |
| [`bioscout.lab.record.video_analyzer`](bioscout.lab.record.video_analyzer.md) | Video analysis script for generating joint angles and MOT files from recorded video. | 1 |
| [`bioscout.lab.record.video_recorder`](bioscout.lab.record.video_recorder.md) | Video recording script using webcam or IP camera with pose estimation. | 1 |
| [`bioscout.lab.record.webvideo`](bioscout.lab.record.webvideo.md) | Make recorded videos playable in a web browser. | 4 |
| [`bioscout.lab.subject_profile`](bioscout.lab.subject_profile.md) | subject_profile.py — per-subject profiles for video analysis. | 3 |
| [`bioscout.lab.tools`](bioscout.lab.tools.md) | tools.py -- one OpenSim / CEINMS tool at a time, for the BioScout Web "Simulate" page. | 15 |
| [`bioscout.lab.web_engine`](bioscout.lab.web_engine.md) | web_engine.py -- the lab engine: OpenSim for the BioScout Web lab demo. | 18 |

## bioscout.pipeline

| module | what it is | members |
|---|---|---|
| [`bioscout.pipeline`](bioscout.pipeline.md) | bioscout.pipeline — project-level orchestration driven by settings flags. | 4 |

## bioscout.cli

| module | what it is | members |
|---|---|---|
| [`bioscout.cli`](bioscout.cli.md) | The bioscout command line: ten verbs instead of sixty-six flags. | 4 |

## bioscout.devtools

| module | what it is | members |
|---|---|---|
| [`bioscout.devtools`](bioscout.devtools.md) | The `bioscout utils` VERB's implementation: environment, deps, docs, editor. | 0 |
| [`bioscout.devtools.api_docs`](bioscout.devtools.api_docs.md) | Build the browsable API reference in docs/api/ (GitHub-rendered Markdown). | 11 |
| [`bioscout.devtools.bench`](bioscout.devtools.bench.md) | Overnight pipeline benchmark: where does the time go, and what scales? | 3 |
| [`bioscout.devtools.dependency_installer`](bioscout.devtools.dependency_installer.md) | dependency_installer.py ----------------------- Checks and installs bioscout dependencies. | 4 |
| [`bioscout.devtools.envcheck`](bioscout.devtools.envcheck.md) | Is bioscout running in the environment it expects, and if not, build it. | 13 |
| [`bioscout.devtools.md2pdf`](bioscout.devtools.md2pdf.md) | Markdown -> PDF, with no LaTeX distribution required. | 3 |
| [`bioscout.devtools.qrgen`](bioscout.devtools.qrgen.md) | Make a QR code for a link — ``bioscout utils qr_code``. | 1 |
| [`bioscout.devtools.run_check`](bioscout.devtools.run_check.md) | bioscout.devtools.run_check — the anti-silent-failure toolbox. | 6 |
| [`bioscout.devtools.settings_updater`](bioscout.devtools.settings_updater.md) | Migrate a project's settings.py to the current schema version. | 2 |

## bioscout.project_config

| module | what it is | members |
|---|---|---|
| [`bioscout.project_config`](bioscout.project_config.md) | bioscout.project_config — lab facts as data (docs/IMPLEMENTATIONS §2.9). | 5 |

## bioscout.scale_interactive

| module | what it is | members |
|---|---|---|
| [`bioscout.scale_interactive`](bioscout.scale_interactive.md) | `bioscout scale` — scale a model by answering questions, no project needed. | 6 |

## bioscout.settings

| module | what it is | members |
|---|---|---|
| [`bioscout.settings`](bioscout.settings.md) | Project settings — BUNDLED TEMPLATE (powerlifting squat study). | 9 |

## bioscout.user_settings

| module | what it is | members |
|---|---|---|
| [`bioscout.user_settings`](bioscout.user_settings.md) | bioscout's own settings for this computer (not a project's): ``bioscout -settings``. | 5 |
