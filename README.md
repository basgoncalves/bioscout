<p align="center">
  <img src="https://raw.githubusercontent.com/basgoncalves/bioscout/main/bioscout/utils/logo.png" width="140" alt="BioScout Logo"/>
</p>

<h1 align="center">BioScout</h1>

<p align="center"><strong>A Python toolbox for musculoskeletal modelling.</strong></p>

<p align="center">
Runs a full OpenSim + CEINMS pipeline from motion capture to muscle and joint contact forces,
validates the results against the literature, and organises everything by subject / session / trial.<br>
Successor to <a href="https://pypi.org/project/msk-modelling-python/">msk_modelling_python</a>.<br>
see <a href="LICENSE">License</a>
</p>

---

## What it does

- **Full OpenSim pipeline** — C3D → IK → ID → Muscle Analysis → Static Optimisation → muscle moments → Joint Reaction Analysis, per trial.
- **EMG-informed muscle forces** — CEINMS calibration (once per session) and execution (per trial), compared against static optimisation and measured EMG.
- **Joint contact forces** — SO vs CEINMS joint reaction forces, normalised to body weight, with **literature validation bands** overlaid (hip, knee) and gait-event marks.
- **Model checking** — an independent `moment_arm_inspection` module to sweep moment arms, flag discontinuities, and validate model moment arms against the literature.
- **Batch processing** — run a whole subject/session from one `settings.py` with a single command; idempotent (resumes) unless you force a rebuild.
- **Notebook tester** — `bioscout/notebook.ipynb` exercises each pipeline stage on one trial and regenerates any figure without re-solving.

See [CHANGELOG.md](CHANGELOG.md) for release notes.

---

## Requirements

| Dependency | Version | Install via |
|---|---|---|
| Python | 3.9 – 3.11 | conda |
| OpenSim | 4.6+ | `pip install opensim` (or `conda install -c opensim-org opensim`) |
| numpy, pandas, scipy, matplotlib | latest | pip (auto with bioscout) |
| CEINMS | 2.x | separate install — only needed for the EMG-informed branch |

---

## Installation

**1 — Create a Python 3.11 environment** (OpenSim is not yet available for 3.12+):

```bash
conda create -n bioscout_env python=3.11 -y
conda activate bioscout_env
```

**2 — Install OpenSim:**

```bash
pip install opensim              # or: conda install -c opensim-org opensim -y
python -c "import opensim; print(opensim.__version__)"
```

**3 — Install BioScout:**

```bash
pip install bioscout             # stable release from PyPI
```

For development, install editable so your edits take effect immediately:

```bash
git clone https://github.com/basgoncalves/bioscout
cd bioscout
pip install -e .
```

**4 — Verify:**

```bash
python -m bioscout --install     # prints a dependency status table
```

---

## Project layout

A project is a folder with a `settings.py` and a `simulations/` tree organised
**subject → session → trial**. Each trial keeps its raw inputs and every stage's
outputs in dedicated subfolders:

```
my_project/
├── settings.py                     ← subjects, session, trials, DOFs, JRA columns
├── models/
│   └── <Subject>/<Session>/scaled.osim ...
└── simulations/
    └── <Subject>/<Session>/<Trial>/
        ├── inputs/                 ← c3d, marker_experimental.trc, grf.mot, GRF.xml, emg*.mot, grf_events.png
        ├── trial_settings.xml      ← per-trial paths, body_mass, time window, trial_type + <events>
        ├── external_biomechanics/  ← IK + ID (.sto) + kinematics_moments.png, residuals.png
        ├── muscle_analysis/        ← muscle lengths / moment arms
        ├── static_optimisation/    ← SO forces + activations + SO_results.png, SO_muscle_groups.png, SO_reserves_inspection.png
        ├── ceinms/                 ← CEINMS execution outputs (+ emg_vs_activations.png, SO/CEINMS/EMG comparison)
        └── joint_contact_forces/   ← JRA (SO & CEINMS) + JRA_SO_vs_CEINMS.png with literature bands
```

Session-level CEINMS calibration lives in `simulations/<Subject>/<Session>/ceinms_calibration/`.

**Trial layout & attribute names.** The canonical folder layout is owned by the
package (`bioscout.layout.Inputs`); a project only needs its own `Inputs` in
`settings.py` if it wants to *override* the default paths (`Analyse` falls back
to the package layout otherwise). On an `Analyse`/trial object the terse layout
fields have readable aliases (read/write proxies onto the same value):

| alias | field | | alias | field |
|---|---|---|---|---|
| `model_path` | `model_dir` | | `grf` | `grf_mot` |
| `joint_angles` | `ik` | | `joint_reaction_so` | `jra` |
| `inverse_dynamics` | `id` | | `joint_reaction_ceinms` | `jra_ceinms` |
| `static_optimisation_forces` | `so_forces` | | `static_optimisation_activations` | `so_activations` |

The short names remain the canonical keys serialised into `trial_settings.xml`.

---

## Configuring a project — `settings.py`

Subjects, the session, and the trials to run are declared in the project's
`settings.py` (`class BatchSettings`):

```python
class BatchSettings:
    SESSION      = "25_03_31"
    session_list = [SESSION]
    trial_list   = ["Walking_02", "Squat_BW_01", "Squat_35kg_01"]

    ALL_SUBJECTS = [
        Subject("Athlete_03_Cateli",     label="Scaled (Cateli)",     session=SESSION, ...),
        Subject("Athlete_03_GPK_MRI",    label="MRI (GPK)",           session=SESSION, ...),
        # ...
    ]
    RUN_SUBJECTS  = None     # None/[] = all;  or ["Athlete_03_GPK"]
    SKIP_SUBJECTS = []
    SUBJECTS      = select_subjects(ALL_SUBJECTS, RUN_SUBJECTS, SKIP_SUBJECTS)

    dof_list      = ["hip_flexion_r", "hip_flexion_l", ...]   # bilateral set processed by IK/ID/CEINMS
    MUSCLE_GROUPS = { ... }
    # JRA_COLUMNS(model) resolves the per-model joint-contact-force columns.

class SummarySettings:
    # DOFs to PLOT / SUMMARISE (e.g. in kinematics_moments.png). Left/right merge
    # onto one column (right=blue, left=red); include the pelvis if you want it.
    dofs = ["pelvis_tilt", "hip_flexion_r", "hip_flexion_l", "knee_angle_r", ...]
```

Put each trial's raw data under `simulations/<Subject>/<Session>/<Trial>/inputs/`
(a `--export` run can also regenerate these from the C3D).

---

## Running the pipeline

**Command line** — run the full pipeline (SO + CEINMS) for one subject:

```bash
cd /path/to/my_project
python -m bioscout --run_subject Athlete_03_Cateli
```

Restrict scope, force a rebuild, or re-export inputs from C3D:

```bash
python -m bioscout --run_subject Athlete_03_Cateli --session 25_03_31 --trial Walking_02
python -m bioscout --run_subject Athlete_03_Cateli --REPLACE      # overwrite existing outputs
python -m bioscout --run_subject Athlete_03_Cateli --export       # regenerate inputs/ from c3d first
```

`--session` and `--trial` accept comma-separated lists; `--run_subject` with no
name runs every subject in `settings.py`. Runs are **idempotent** — a stage is
skipped when its output already exists unless `--REPLACE` is given.

### Running individual steps on one trial

`python -m bioscout.utils.analyse <trial_dir> [method ...]` calls any `Analyse`
method by name on a single trial (the nearest parent `settings.py` is bound
automatically). Handy for re-running one stage or regenerating a figure without
a full batch:

```bash
# full SO branch on one trial (start at IK)
python -m bioscout.utils.analyse "simulations/Athlete_03_Lernagopal/25_03_31/Walking_02" run_ik run_id run_ma run_so run_jra
# (subset, e.g. just kinematics/kinetics)
python -m bioscout.utils.analyse "simulations/Athlete_03_Lernagopal/25_03_31/Walking_02" run_ik run_id

# CEINMS branch. EMG normalisation and calibration are SESSION-level (they need
# every trial's EMG for the MVC reference, and calibrate once per subject/session).
# The CLI recognises session-scoped verbs (normalise_emg, calibrate, ...) and runs
# them on the trial's parent session — point it at ANY trial in the session:
python -m bioscout.utils.analyse "simulations/Athlete_03_Lernagopal/25_03_31/Walking_02" normalise_emg calibrate

# Then execute CEINMS per trial (SO outputs + calibrated model must already exist) and JRA:
python -m bioscout.utils.analyse "simulations/Athlete_03_Lernagopal/25_03_31/Walking_02" run_ceinms_exe run_jra_ceinms

```

`run_jra_ceinms` reads the CEINMS `MuscleForces.sto` from the execution output,
runs the JointReaction analysis, writes
`joint_contact_forces/Analyse_JRA_ReactionLoads_CEINMS.sto`, and (when the SO JRA
also exists) the `JRA_SO_vs_CEINMS.png` comparison figure with literature bands.

> Note: `normalise_emg`/`calibrate` are methods of the **Session**, not the trial,
> so the CLI resolves `<Subject>/<Session>/` from the trial path and calls them
> there. (The trial-level `run_emg_normalise` is a legacy path that writes a
> different file — prefer `normalise_emg`.)

`s.normalise_emg()` writes `inputs/emg_filtered_normalised.mot` for every trial
(session-max on the filtered envelope) and `s.calibrate()` produces
`ceinms_calibration/subjectCalibrated.xml`. `run_ceinms_exe` then needs those
plus the SO outputs (`run_ma run_so`). It writes the CEINMS execution outputs
plus the SO-vs-CEINMS-vs-EMG comparison figures
(`ceinms/emg_vs_activations.png`: gray = EMG, red = SO, blue = CEINMS).

### Re-cropping to edited gait events (no re-export)

Editing the `<events>` in a trial's `trial_settings.xml` does **not** by itself
change the analysis window on a re-run — the stored `start_time`/`end_time` take
precedence. Call `recrop_to_events` first to re-derive and persist the window
from the (edited or re-detected) events, then re-run the solve steps:

```bash
# uses the current (hand-edited) events, refreshes inputs/grf_events.png, re-solves
python -m bioscout.utils.analyse "simulations/Athlete_03_Cateli/25_03_31/Walking_02" recrop_to_events run_ik run_id run_ma run_so run_jra
```

Raw inputs are untouched (no export); IK/ID/MA/SO/JRA simply solve within the new
window. The `grf_events.png` labels and the `<event n="…">` tags in
`trial_settings.xml` are numbered in time order for easy cross-checking.

**Re-detecting after the forces changed.** A plain re-export KEEPS existing foot
events (it trusts mocap-labelled events and only auto-detects when there are
none). If the GRF actually changed and you want fresh events, force it:

```bash
python -m bioscout.utils.analyse ".../Walking_02" redetect_events run_ik run_id run_ma run_so run_jra
```

`redetect_events` re-detects from the GRF, overwrites the events, re-derives the
window, and refreshes `grf_events.png`.

**Choosing which leg to summarise.** `SummarySettings.analysis_leg` (`"both"`,
`"r"`, or `"l"`) sets the default leg drawn in `kinematics_moments.png`. Override
per trial by adding `<analysis_leg>r</analysis_leg>` to that trial's
`trial_settings.xml` — midline DOFs (pelvis/lumbar) are always kept.

### Resetting trials to inputs-only

`--reset` strips generated outputs (IK/ID/MA/SO/JRA results, `setup_*.xml`,
`MuscleAnalysis/`, `Execution*/`, filtered EMG, plots, CEINMS calibration, …)
back to the raw inputs, so a trial re-runs clean. It **keeps** each trial's
`inputs/` folder (the C3D lives inside it) and `trial_settings.xml`, and makes a
**timestamped backup** (`simulations_backup_<ts>/`) before deleting anything.

`--reset` follows the same scoping as everything else — pass `--trial` to reset
one trial, `--session` for a whole session, or no scope to reset the entire
`simulations/` folder:

```bash
# reset only, no run
python -m bioscout --reset --trial Walking_02            # one trial (keeps whole inputs/)
python -m bioscout --reset --session 25_03_31            # a whole session
python -m bioscout --reset                               # the entire simulations/ folder
python -m bioscout --reset --trial Walking_02 --reset-dry-run   # preview, touch nothing
python -m bioscout --reset --trial Walking_02 --reset-raw       # prune inputs/ to just the c3d + trial_settings.xml

# reset-then-run: combine with --run_subject (resets exactly the trials it will run)
python -m bioscout --run_subject Athlete_03_Cateli --session 25_03_31 --trial Walking_02 --reset --REPLACE

# add --export to also regenerate inputs/ (markers/GRF/EMG) from the C3D
python -m bioscout --run_subject Athlete_03_Cateli --session 25_03_31 --trial Walking_02 --reset --export --REPLACE
```

When scoped to a trial, sibling trials and session-level files are left
untouched. Because `inputs/` is preserved, a plain `--reset` already gives a
clean recompute; add `--export` only when you also want inputs rebuilt from the
C3D.

**Python API** — the same batch entry point, plus the typed hierarchy:

```python
import bioscout
proj = bioscout.Project(r"/path/to/my_project")

# whole subject/session
bioscout.pipeline.run_subject(project_dir=proj.path, subject="Athlete_03_Cateli",
                              sessions="25_03_31", do_so=True, do_ceinms=True)

# reset first, then run (reset=True strips outputs to inputs-only, with a backup)
bioscout.pipeline.run_subject(project_dir=proj.path, subject="Athlete_03_Cateli",
                              sessions="25_03_31", trials="Walking_02",
                              reset=True, export=True, replace=True)

# reset only (no run) — scope with subjects=/session=/trials=; omit all for the whole tree
bioscout.pipeline.reset_simulations(project_dir=proj.path, session="25_03_31",
                                    trials="Walking_02")          # dry_run=True to preview

# one trial, step by step (a Trial is an Analyse subclass)
trial = proj.subject("Athlete_03_Cateli").get_session("25_03_31").trial("Walking_02")
trial.run_ik(); trial.run_id(); trial.run_ma(); trial.run_so()
trial.calculate_muscle_moments(forces_type="so")
trial.run_jra()
```

The per-trial stages are, in order:

```
IK → ID → Muscle Analysis → Static Optimisation → muscle moments → JRA        (SO branch)
EMG normalise → CEINMS calibrate (session) → CEINMS execute → muscle moments → JRA   (CEINMS branch)
```

To clean a subject/session back to `inputs/` + `trial_settings.xml` (with a backup):

```python
bioscout.pipeline.reset_simulations(project_dir=proj.path, subjects="Athlete_03_Cateli",
                                    session="25_03_31", backup=True, dry_run=True)  # dry_run first!
```

---

## Figures & validation

Every stage writes its figures into the trial subfolders, and any figure can be
regenerated **without re-solving** (they only read the `.sto` outputs):

```python
trial.plot_kin_mom_summary()    # kinematics (top) + moments (bottom) for SummarySettings.dofs
trial.plot_residuals()          # pelvis residual forces/moments as % of |GRF| (10/25% bands)
trial.plot_so()                 # muscle forces + activations, one legible figure per leg
trial.plot_so_reserves()        # SO reserve actuators as % of each ID moment (10/25% bands)
trial.plot_jra_comparison()     # SO vs CEINMS joint contact forces (×BW) + literature bands
trial.plot_ceinms_execution_comparison()   # forces & activations: SO vs CEINMS vs EMG
```

The muscle-group figures (`SO_muscle_groups.png`) annotate each panel with R²/RMSE
of the mean activation vs measured EMG. `ceinms/emg_vs_activations.png` uses
gray = EMG, red = SO, blue = CEINMS. All figures regenerate from the `.sto`
outputs, e.g. from the CLI:

```bash
python -m bioscout.utils.analyse ".../Walking_02" plot_kin_mom_summary plot_residuals plot_so plot_so_reserves
```

**Literature validation.** `plot_jra_comparison` overlays digitised literature
contact-force bands on the resultant panels for gait-like trials — hip (Bergmann,
Hoang, Giarmatzis) and knee (Richards) — mapped onto the trial's gait cycle. The
overlay data lives in `bioscout.moment_arm_inspection.literature_jcf` and can be
plotted on its own:

```python
from bioscout.moment_arm_inspection import literature_jcf as ljcf
ljcf.plot_jcf_validation("hip_ref.png", entity="hip")
```

**Model moment arms.** The independent `moment_arm_inspection` module sweeps a
model's moment arms, flags discontinuities/wrap errors, and validates against
literature moment-arm bands:

```bash
python -m bioscout.moment_arm_inspection inspect  --model scaled.osim
python -m bioscout.moment_arm_inspection validate --model scaled.osim
```

**Trial type & events.** Each trial has a `trial_type` (`walking`, `running`,
`squat`, `jump`, `generic`) and its gait events **self-contained** in
`trial_settings.xml` under `<events type="…">` (each `<event n="…" name="…"
time="…"/>` is numbered in time order). The event schema per type determines the
0–100 % window used for literature overlays and the event marks drawn on figures.
`inputs/grf_events.png` plots per-foot vertical GRF with those events (▲ contact,
▼ toe-off; generic landmarks like Start/End shown as neutral markers).

To re-derive the analysis window after editing the events, without re-exporting,
use `recrop_to_events` (see "Re-cropping to edited gait events" above).

---

## Notebook — testing the pipeline

`bioscout/notebook.ipynb` is a scratchpad for exercising individual pipeline
parts on one trial: setup → per-step SO branch → CEINMS branch → figure
regeneration → trial-type/events → batch run → moment-arm & literature
validation. Point `PROJECT_DIR` at a project, pick a subject/trial, and run cells
selectively.

---

## Migration from msk_modelling_python

```bash
pip uninstall msk-modelling-python
pip install bioscout
```

```python
# Old
import msk_modelling_python as msk
# New
import bioscout as msk
```

---

## Future add-ons

- **Player / movement tracking (computer vision).** Markerless kinematics from a
  phone or laptop camera via pose estimation, feeding the same OpenSim pipeline.
- **Real-time muscle forces.** A pre-trained ML model that maps camera-derived
  kinematics to muscle and joint contact forces in (semi-)real time, integrating
  the computer-vision and OpenSim/CEINMS pipelines.
