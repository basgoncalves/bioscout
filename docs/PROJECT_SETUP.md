# BioScout — Project Setup

BioScout separates **model creation** (scaling / personalisation) from
**analysis**. A *session* owns its personalised OpenSim model and its motion
data; the analysis pipeline just *consumes* whatever model is in the session.
Making that model is a **standalone** step you run once per session.

This means the analysis run never scales, never needs a "generic model", and
never cares how the `.osim` was produced — it just uses it.

---

## 1. Folder convention

A project is a folder with a `settings.py`, a `simulations/` tree, and two
shared resource folders:

```
<project>/
  settings.py
  generic models/          # unscaled templates + geometry (INPUT to `scale`)
    Rajagopal2015.osim
    <TemplateFamily>/...
  setupFiles/              # OpenSim setup XMLs + marker sets (shared)
    markers_powerlifter.xml
    setup_IK.xml ...
  simulations/
    <subject>/
      <session>/                     # a SESSION owns the data + its model(s)
        session.xml                  # session config + per-trial windows/events
        c3dfiles/                    # raw motion data (shared by ALL models)
          Walking_02.c3d ...
        models/                      # one or MORE model iterations to compare
          scaled_opt_N10_mvicx3.00.osim
          gpk_scaled_mvicx3.00.osim
          ...
        <trial>/                     # per-trial outputs (created by pipeline),
          <model>/ ...               #   namespaced per model
    <subject>/                       # session-LESS datasets: subject folder = session
      session.xml
      c3dfiles/ ...
      models/ ...
```

Rules:

* A **session** owns its raw data (`c3dfiles/`) and **one or more models**
  (`models/*.osim`). The models are *iterations of the same session* (e.g.
  Cateli / Lernagopal / GPK / MRI / Rajagopal) — NOT different subjects. Every
  model is analysed over the same trials and compared.
* **`session.xml`** is the single config file for the session (see §2). It
  replaces the old per-trial `trial_settings.xml`: each trial just refers to the
  session and its own `<trial>` entry inside `session.xml`.
* `generic models/` and `setupFiles/` are shared project resources: templates for
  the `scale` step, and OpenSim setup/marker XMLs for analysis.
* **Some datasets have sessions, some don't.** If a subject folder has no session
  sub-folders, the subject folder *is* the session (`session = ""`). Discovery
  handles both.
* Raw `.c3d` files are distributed into `c3dfiles/` with `--ingest-c3d`.


## 2. session.xml — one config per session

Holds everything shared across the session's trials, plus a compact per-trial
block. Trials do not carry their own `.xml` any more.

```xml
<session subject="Athlete_03" session="25_03_31">
  <body_mass>89.9</body_mass>
  <setup_folder>setupFiles</setup_folder>
  <markerset>setupFiles/markers_powerlifter.xml</markerset>

  <!-- model iterations analysed + compared for this session -->
  <models>
    <model name="Cateli"    file="models/scaled_opt_N10_mvicx3.00.osim"
           ceinms="models/scaled_opt_N10.osim" color="green" group="generic"/>
    <model name="GPK"       file="models/gpk_scaled_mvicx3.00.osim"
           ceinms="models/gpk_scaled_opt_N10.osim" color="red" group="generic"/>
    <model name="MRI (GPK)" file="models/gpk_mri_scaled_mvicx3.00.osim" group="MRI"/>
  </models>

  <emg_muscle_mapping> ... </emg_muscle_mapping>   <!-- session-wide -->
  <ceinms alpha="10" beta="1" gamma="1000"/>

  <!-- trial-level: only what differs per trial -->
  <trials>
    <trial name="Walking_02" time_range="0.067 1.161" events="0.173 0.714"/>
    <trial name="Squat_BW_01" time_range="0.20 2.10"/>
  </trials>
</session>
```

The pipeline reads `session.xml` once, then for each `<model>` runs every
`<trial>` over the shared `c3dfiles/`, writing results under
`<trial>/<model>/`.

---

## 2. The two entry points

### a) Create the model  (standalone — run once per session)

Scaling → muscle-parameter optimisation → MVIC strength → personalisation writes
the session's `model.osim`. It is **not** part of the analysis run.

```bash
python -m bioscout scale --project . \
    --subject Athlete_03 --session 25_03_31 \
    --generic "generic models/Rajagopal2015.osim" \
    --static Static_01 \
    --opt-neval 10 --mvic 3.0 \
    --out model.osim
```

Produces `simulations/Athlete_03/25_03_31/model.osim`. Skip this step entirely
for data that already arrives with a model — just drop the `.osim` in.

### b) Analyse  (the pipeline)

```bash
python -m bioscout -b settings.py
```

Runs, per session, the linear stages:

```
export_c3d -> run_emg_normalise -> run_external_biomechanics (IK+ID)
           -> run_muscle_analysis -> run_static_optimisation (+JRA)
           -> run_ceinms_calibration -> run_ceinms (+JRA) -> run_summary
```

No scaling. The session's model is read from the folder.

---

## 3. settings.py (minimal)

The models, body mass, EMG mapping and per-trial windows all live in each
session's `session.xml`, so `settings.py` shrinks to *what to run* and
*analysis parameters* — no generics, no per-subject model names.

```python
from pathlib import Path
from bioscout.utils.analysis import discover_sessions

__version__  = "2.0.0"
RUN_PIPELINE = True
RUN_SUMMARY  = True
RUN_CEINMS   = True
LOG_TYPE     = "detailed"          # detailed | minimal | quiet

PROJECT_ROOT    = Path(__file__).resolve().parent
SIMULATIONS_DIR = PROJECT_ROOT / "simulations"
GENERIC_DIR     = PROJECT_ROOT / "generic models"
SETUP_DIR       = PROJECT_ROOT / "setupFiles"

class BatchSettings:
    PROJECT_ROOT    = PROJECT_ROOT
    SIMULATIONS_DIR = SIMULATIONS_DIR
    GENERIC_DIR     = GENERIC_DIR
    SETUP_DIR       = SETUP_DIR

    # Every session (folder with session.xml + c3dfiles + models) becomes a row;
    # its model iterations come from session.xml, not from here.
    SESSIONS = discover_sessions(SIMULATIONS_DIR, require_session_xml=True)

    RUN_SUBJECTS = 'all'      # 'all' | ["Athlete_03"] | [0,2]
    RUN_MODELS   = 'all'      # 'all' | ["Cateli","GPK"]  (subset of the session's models)
    trial_list   = []         # [] = every trial in each session
    # + EMG string list, DOFs, GRF axis map, etc. (pure analysis params)
```

`discover_sessions` returns **Session** objects (subject, session, path, models[])
built from each `session.xml`; `RUN_SUBJECTS`/`RUN_MODELS`/`trial_list` filter
what actually runs.

---

## 4. Heterogeneous datasets (e.g. Squat_Width — "some have sessions, some don't")

Point `SIMULATIONS_DIR` at the data root and let discovery walk it:

* `subject/session/` folders → session rows.
* `subject/` folders with data but no session sub-folders → one session-less row.
* Folders **without** a model are skipped when `require_model=True` (so you can
  first run the `scale` step for those, then analyse).

No per-subject configuration is needed; `settings.py` is the same file whether
the project has 1 or 500 subjects.

---

## 5. Migration from the old (in-pipeline scaling) layout

* Move `generic_model` / `model_so` / `model_ceinms` / `muscle_force_factor` /
  `muscle_opt_neval` out of the analysis roster; they are now **arguments to the
  `scale` step**.
* Run `bioscout scale ...` once per session to produce `model.osim`.
* The analysis `settings.py` keeps only run-flags, `session_model`, subject/trial
  selection, and analysis parameters.
