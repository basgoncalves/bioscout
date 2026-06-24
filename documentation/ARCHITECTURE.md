# BioScout — Architecture & API Reference

> Biomechanical analysis and movement scouting for coaches and athletes.
> Open-source Python toolbox for musculoskeletal modelling, motion-capture analysis,
> and real-time movement assessment. Successor to `msk_modelling_python`.
> Version 1.3.0 · MIT · https://github.com/basgoncalves/bioscout

---

## 1. Overview

BioScout is organised around three pipelines that share a common project/subject
data model:

1. **OpenSim pipeline** — C3D → scaling → IK → ID → static optimisation → muscle
   analysis → energetics → CEINMS EMG-informed muscle forces.
2. **Computer-vision pipeline** — pose detection from camera/video, movement
   segmentation, and prototype shot analysis.
3. **Load tracking** — wearable/fitness-tracker import → load & fatigue metrics →
   per-muscle distribution → PDF report (with a pluggable seam to the ML/OpenSim
   muscle-force layer).

Everything is reachable three ways: a **CTk desktop GUI**, a **CLI**
(`python -m bioscout ...`), and a **Python API** (`import bioscout`).

```
                        ┌─────────────────────────────┐
   GUI (customtkinter)  │      bioscout.gui            │
   CLI (__main__.py)    │   MainWindow + widgets/      │
   Python API           └──────────────┬──────────────┘
                                        │
        ┌───────────────────────────────┼───────────────────────────────┐
        │                               │                               │
   ┌────▼─────┐                   ┌─────▼──────┐                  ┌──────▼──────┐
   │  core/   │  orchestration    │  utils/    │  OpenSim/CEINMS  │ load_track/ │
   │ runner,  │◄──────────────────│ openSim,   │  EMG, scaling    │ importers,  │
   │ sessions │                   │ ceinms,    │                  │ metrics,    │
   └────┬─────┘                   │ model_scaler                  │ report      │
        │                         └─────┬──────┘                  └─────────────┘
   ┌────▼────────┐            ┌─────────▼─────────┐         ┌──────────────────┐
   │ movement_   │            │  record/          │         │ project.py /     │
   │ detector/   │            │  video, screen    │         │ subject.py /     │
   │ pose → segs │            │  capture, pose    │         │ settings.py      │
   └─────────────┘            └───────────────────┘         └──────────────────┘
```

---

## 2. Package layout

| Package | Responsibility |
|---|---|
| `bioscout/` | Top-level package; eager public API (`Project`, `Subject`, `Session`, `init_project`). |
| `bioscout.__main__` | CLI entry point — argument parsing and dispatch. |
| `bioscout.project` | One-call project bootstrap/wiring for notebooks and scripts. |
| `bioscout.subject` | `Subject`/`Session` data objects; model + setup wiring per athlete. |
| `bioscout.settings` | Unified settings: `BatchSettings`, `CEINMSSettings`, `SummarySettings`, `UISettings`, `RecordingSettings`, `Inputs`. |
| `bioscout.core` | Pipeline orchestration: `AnalysisRunner`, `SessionManager`, project-level result aggregation. |
| `bioscout.utils` | OpenSim/CEINMS/EMG/model-scaling helpers, logging, XML, summaries. |
| `bioscout.load_tracking` | Wearable import, load/fatigue metrics, muscle mapping, PDF report. |
| `bioscout.movement_detector` | Pose-landmark → movement segmentation/classification. |
| `bioscout.record` | Webcam/IP-camera and screen capture with pose estimation. |
| `bioscout.gui` | `customtkinter` desktop app: `MainWindow` + `widgets/`. |
| `bioscout.config` | Config manager and bundled YAML/XML defaults. |
| `bioscout.models` | Bundled `.osim` models. |
| `bioscout.setup_files` | Bundled OpenSim setup XML templates. |

---

## 3. Entry points

Defined in `setup.py` (`console_scripts`):

| Command | Maps to | Purpose |
|---|---|---|
| `bioscout-gui` | `bioscout:launch_gui` | Launch the desktop GUI. |
| `bioscout` | `bioscout.__main__:main` | CLI dispatcher (same as `python -m bioscout`). |

---

## 4. Command-line API (`python -m bioscout`)

Default with no flags launches the GUI. Key flags (from `__main__.py`):

**Project / pipeline**

| Flag | Argument | Description |
|---|---|---|
| `-g`, `--gui` | — | Launch the GUI (default). |
| `--init` | `PROJECT_PATH` | Scaffold a new project (folders, settings template, models, setup files). |
| `--add_player` | `[PROJECT_PATH]` | Interactively add a player to `players.json`. |
| `-b`, `--batch` | `settings.py` | Run a full pipeline in batch from a settings file. |
| `--install` | — | Print dependency status table and offer to install what's missing. |
| `-p`, `--project` | `PROJECT_PATH` | Target project for other commands. |

**Summaries**

| Flag | Argument | Description |
|---|---|---|
| `--summary` | `[SETTINGS_OR_PROJECT]` | Build per-trial / overall kinematics/kinetics/muscle reports. |
| `--overall` | — | Overall (cross-trial) summary. |
| `-s`, `--subject` | `PLAYER_ID` | Restrict to one subject. |
| `-t`, `--trial` | `TRIAL_PATH` | Restrict to one trial. |

**Shot analysis (computer vision)**

| Flag | Argument | Description |
|---|---|---|
| `--shots` | `VIDEO` | Run prototype basketball shot analysis on a video. |
| `--shooting-hand` | `right`/`left` | Shooter's hand. |
| `--poses` | `POSES_JSON` | Reuse pre-computed pose landmarks. |
| `--fps`, `--min-gap`, `--n-points` | — | Sampling / segmentation tuning. |
| `--yolo-model` | `WEIGHTS.pt` | YOLO ball+hoop detector for robust scoring. |
| `--hoop` | `CX,CY,W,H` | Manual rim box (HSV ball method). |
| `--hoop-side` | `auto`/… | Rim side hint. |

**Load tracking (wearables)**

| Flag | Argument | Description |
|---|---|---|
| `--load-report` | path/folder | Build a load & fatigue PDF from session files. |
| `--load-out` | `PDF` | Output path for the report. |
| `--hr-max`, `--hr-rest`, `--age`, `--sex` | — | Athlete profile for HR-based metrics (TRIMP etc.). |
| `--zepp-pull` | — | Pull sessions from Zepp/Amazfit cloud. |
| `--strava-pull` | — | Pull activities from Strava. |
| `--creds` | `JSON` | Credentials file for cloud pulls. |

---

## 5. Python API

### 5.1 Top-level (`import bioscout`)

```python
from bioscout import (
    Project, init_project, check_settings_version, migrate_settings,
    Subject, Session, build_model_config, discover_subjects,
)
```

**Project bootstrap** — point BioScout at a project folder:

```python
import bioscout
proj = bioscout.Project()              # cwd is the project root
proj.utils, proj.settings, proj.dir    # wired helpers, settings, root path

# functional equivalent
utils, settings = bioscout.init_project()
```

`check_settings_version` / `migrate_settings` keep a project's settings file in
sync with the package schema version.

**Subject / Session** — one object per athlete (or model variant):

```python
from bioscout import Subject

athlete = Subject(
    name="Athlete_03", label="A3", session="25_03_31",
    model_so="scaled_increased_3.00.osim",   # static-optimisation model
    model_ceinms="scaled.osim",              # EMG-informed (CEINMS) model
    setup_folder="Purzel", color="green",
)
a = athlete.analyse("Squat_BW_01", force_type="SO")  # model + setup wired
athlete.model_path("CEINMS")                          # absolute .osim path
```

- `build_model_config(subjects, force_types=("SO","CEINMS"))` → config dict.
- `discover_subjects(models_dir, session, names, ...)` → auto-build subjects from disk.
- `Session` groups trials for a subject.

### 5.2 Orchestration (`bioscout.core`)

| Object | Role |
|---|---|
| `AnalysisRunner` | Runs the pipeline; configured by `AnalysisConfig`. |
| `AnalysisStep` (Enum) | The ordered pipeline stages (scaling, IK, ID, SO, muscle analysis, …). |
| `AnalysisConfig` | Which steps to run, paths, options. |
| `SessionManager` | Discover/validate sessions and trials. |
| `TrialValidator` | Check a trial has the required inputs/outputs. |

Result aggregation (`core.project_analysis`):
`load_trial_result`, `load_player_results`, `load_group_results`,
`time_normalise`, `compute_mean_curve`, `compare_groups`, `compare_players`,
`list_all_players`, `list_groups`.

### 5.3 OpenSim / CEINMS / EMG helpers (`bioscout.utils`)

- `utils.openSim` — model editing & musculoskeletal ops: `scale_body_masses`,
  `increase_isometric_force`, `lock_model_coordinates`, `coord_moment_arms`,
  `add_wrapping_surfaces`, `add_muscles_to_model`, `checkMuscleMomentArms`,
  `optimMuscleParams` (Modenese 2015), `compare_osim_models`, `export_c3d`, …
- `utils.ceinms` — full EMG-informed force pipeline: `create_ceinms_model`,
  `create_excitation_generator`, `create_calibrationCfg`/`...SetupXML`,
  `calibrate`, `executable`/`executable_loop`, `optimise`, plotting helpers.
- `utils.emg_normalise` — `filter_emg`, `load_sto`/`write_sto_file`,
  `emg_amplitude_normalise`, `time_normalise_df`, `plot_emg_results`.
- `utils.model_scaler.ModelScaler` — scaling driver.
- Plus `logger`, `xml_utils`, `summary`, `player_profile`/`player_registry`,
  `post_process_trc_markers`, `dependency_installer`, `resource_cleanup`.

### 5.4 Load tracking (`bioscout.load_tracking`)

```python
from bioscout.load_tracking import LoadTracker, AthleteProfile

tracker = LoadTracker(athlete=AthleteProfile(age=30, hr_max=190, hr_rest=55))
tracker.add_files("path/to/sessions/")    # folder or list of files
tracker.compute()
tracker.report("load_report.pdf")
```

Public API: `SessionData`, `AthleteProfile`, `LoadTracker`,
`MuscleForceEstimator`, `HeuristicMuscleEstimator`, `load_session_file`,
`load_sessions`, `load_credentials`, `pull_into_tracker`, `SUPPORTED_EXTENSIONS`.

Design (hybrid): interpretable load metrics ship today — TRIMP, session-RPE
load, acute:chronic workload ratio (ACWR), monotony/strain, and a Banister
fitness-fatigue model. A per-muscle-group distribution maps each session onto
muscle groups. The `MuscleForceEstimator` interface (`ml_interface.py`) lets the
heuristic muscle layer be swapped for the real ML/OpenSim/CEINMS pipeline
without touching report or GUI code.

### 5.5 Movement detection (`bioscout.movement_detector`)

```python
from bioscout.movement_detector import (
    detect_segments, fill_pose_gaps, MotionSegment, DetectorConfig,
)
```

Segments running, walking, jumping, squatting, side-step cut, shuffle,
deceleration, and backward locomotion from 2-D pose-landmark time-series.

### 5.6 Recording (`bioscout.record`)

`ScreenRecorder`, `MovementTracker` (webcam/IP camera with pose estimation),
plus `ARM26_BALL_CONFIG` / `FULL_BODY_CONFIG` presets. Imports degrade
gracefully to `None` when `opencv-python`/`mediapipe` are not installed.

### 5.7 GUI (`bioscout.gui`)

`MainWindow(ctk.CTk)` hosts tabbed widgets under `gui/widgets/`: C3D export &
GRF viewing, model scaling, EMG processing/normalisation, CEINMS calibration,
batch processing, recording & video analysis, results viewer, load tracking,
and training tracking. Launch via `main()` / `bioscout-gui`.

---

## 6. Typical workflows

**Full OpenSim pipeline (CLI):**
```bash
python -m bioscout --init /path/to/project
cd /path/to/project
python -m bioscout --add_player            # repeat per athlete
# copy C3D files into simulations/<player_id>/
python -m bioscout -b settings.py          # batch the pipeline
python -m bioscout --summary               # build reports
```

**Shot analysis (CV prototype):**
```bash
python -m bioscout --shots clip.mp4 --shooting-hand right --yolo-model best.pt
```

**Load & fatigue report (wearables):**
```bash
python -m bioscout --strava-pull --creds load_credentials.json \
    --load-report ./sessions --load-out load_report.pdf \
    --hr-max 190 --hr-rest 55 --age 30 --sex M
```

---

## 7. Requirements

Python 3.9–3.11 (OpenSim is not yet on 3.12+). OpenSim 4.6+ via
`pip install opensim` or conda. Core deps: numpy, pandas, scipy, scikit-learn,
matplotlib, plotly, customtkinter, c3d, pyyaml. Optional video extras:
opencv-python, mediapipe. Run `python -m bioscout --install` for a status table.

---

*This document describes the public structure of BioScout 1.3.0. Function
signatures live in the source under `bioscout/`; see `README.md` and
`CHANGELOG.md` for usage and release notes.*
