<p align="center">
  <img src="https://raw.githubusercontent.com/basgoncalves/bioscout/main/bioscout/utils/logo.png" width="140" alt="BioScout Logo"/>
</p>

<h1 align="center">BioScout</h1>

<p align="center">v2.0.0 &nbsp;·&nbsp; <em>beta — the API may still move</em></p>

<p align="center"><strong>A Python toolbox for musculoskeletal modelling.</strong></p>

<p align="center">
Runs a full OpenSim + CEINMS pipeline from motion capture to muscle and joint contact forces,
validates the results against the literature, and organises everything by subject / session / trial.<br>
Successor to <a href="https://pypi.org/project/msk-modelling-python/">msk_modelling_python</a>.<br>
see <a href="LICENSE">License</a>
</p>

---

## Why BioScout

Getting from a motion-capture session to a defensible muscle-force number takes a
dozen tools that do not agree on where files live. A typical study ends up with
one folder per attempt, paths hard-coded into scripts, and no way to answer the
question the study is actually about: **does this modelling choice change the
answer?**

BioScout is built around that question. A **session** owns its raw captures once.
On top of it you define as many model **iterations** as you want to compare —
a generically scaled model, an MRI-personalised one, one with tuned moment arms —
and every iteration runs the same trials through the same pipeline. Because the
inputs are shared and the outputs are separated, the difference between two
iterations *is* the effect of the modelling choice, not of a path or a re-export.

Everything a run needs is declared in one `session.yaml`. There are no arguments
to remember and no state hidden in a notebook: the same file drives the Python
API, the command line and the GUI, so a session someone else hands you runs the
same way yours does.

```python
from bioscout import Session

s  = Session.open("simulations/Athlete_03/25_03_31")  # reads session.yaml
it = s.iteration("gpk_mri")                            # one runnable model variant

it.scale_model(muscle_opt=False)                       # generic -> scaled (+ MVIC for SO)
it.run(trials=["Squat_BW_01", "Walking_02"],
       do_exbiomec=True, do_so=True, do_ceinms=True, calibrate=True)

s.run(do_so=True, do_ceinms=True)   # every iteration in the session
s.summarise()                        # cross-model comparison figures
```

See [Project structure](#project-structure) for the folder layout and what
`session.yaml` controls.

---

## What it does

- **Full OpenSim pipeline** — C3D → IK → ID → Muscle Analysis → Static Optimisation → muscle moments → Joint Reaction Analysis, per trial.
- **EMG-informed muscle forces** — CEINMS calibration (once per session) and execution (per trial), compared against static optimisation and measured EMG.
- **Joint contact forces** — SO vs CEINMS joint reaction forces, normalised to body weight, with **literature validation bands** overlaid (hip, knee) and gait-event marks.
- **Model validation** — an independent `muscle_inspect` module sweeps moment arms, flags wrap discontinuities, and validates moment arms, fibre length/pennation, and joint strength against the literature (writes `muscle_inspect_<model>/`).
- **Batch processing** — run one session or a whole project from `settings.py` or `Session.batch_sessions()`; idempotent (resumes) unless you force a rebuild.

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
pip install bioscout
```

> **2.x is a beta line.** It is a normal release — no `--pre` needed — but it is
> marked *Development Status :: 4 - Beta* on PyPI because the session/iteration
> API is still settling. Pin it (`bioscout==2.0.0`) if you need a run to stay
> reproducible. Coming from 1.x, see
> [Migration from msk_modelling_python](#migration-from-msk_modelling_python);
> note 2.x requires Python 3.9–3.11 and OpenSim.

For development, install editable so your edits take effect immediately:

```bash
git clone https://github.com/basgoncalves/bioscout
cd bioscout
pip install -e .
```

**4 — Verify:**

```bash
bioscout utils install     # prints a dependency status table
```

---

## Command line

Ten verbs. Every one takes `--help` of its own, and `bioscout help <verb>` is the
same thing.

```
bioscout                 launch the GUI
bioscout help [VERB]     the verb list, or one verb's detail
bioscout init            create a project: folders, models, settings template
bioscout gui             launch the GUI
bioscout run             the pipeline: IK -> ID -> MA -> SO -> CEINMS -> JRA
bioscout session         new / export / classify / ingest / reset
bioscout model           check / edit / compare / ma / validate / joint-centres
bioscout tps             build an MRI-personalised model
bioscout plot            figures, summaries, Collings ranking, JCF direction
bioscout utils           env / install / md2pdf / pylance
bioscout lab             EXPERIMENTAL 3.0: video and wearable tracking
```

`bioscout -h` needs nothing but the standard library — no conda check, no
OpenSim import — so it still answers on a machine where the environment is
half-built, which is when you need it most.

```bash
bioscout run 021 --session pre,post --replace
bioscout session new simulations/022/pre        # opens a dialog
bioscout model check models --strict
bioscout plot --list
bioscout help run
```

### Coming from the flags

Every old flag still works. It is hidden from `--help` and prints one line
naming its replacement, so existing scripts keep running while you migrate.
They will be removed one release after that.

| old | new |
|---|---|
| `--run_subject X --REPLACE` | `run X --replace` |
| `-b settings.py` | `run --batch settings.py` |
| `--new-session P --from-session Q --body-mass M` | `session new P` (a dialog asks) |
| `--c3d-export P` | `session export P` |
| `--classifier P` | `session classify P` |
| `--ingest-c3d F --subject S --session N` | `session ingest F --subject S --session N` |
| `--reset --reset-dry-run --reset-raw` | `session reset --dry-run --raw` |
| `--model-edit`, `--edit` | `model edit` |
| `--compare-models`, `--scale-setups` | `model compare --scale-setups` |
| `--change-moment-arms`, `--ma` | `model ma` |
| `--joint-centres`, `--jc` | `model joint-centres` |
| `--summary -overall -s -t -p` | `plot summary --overall --subject --trial --project` |
| `--collings --skip --metric --side --top` | `plot collings --skip --metric --side --top` |
| `--env`, `--env-create` | `utils env`, `utils env --create` |
| `--install` | `utils install` |
| `--md2pdf --toc --bib --outdir` | `utils md2pdf --toc --bib --outdir` |
| `--pylance-fix` | `utils pylance` |
| `--shots`, `--load-report`, `--add_subject` | `lab shots`, `lab load-report`, `lab add-subject` |

The point was not shorter names. The flat parser had grown to 66 options, and
**25 of them existed only to modify another flag** — their help began
*"With `--X`:"*. `--top` and `--side` mean nothing without `--collings`; `--toc`
and `--bib` mean nothing without `--md2pdf`. Under a verb they are simply that
verb's options, and the root help is ten lines.

### `bioscout plot jcf` — the contact force vector, on the model's bones

For anyone who has run an OpenSim JointReaction analysis. One polar panel per
joint: the bearing is the force's direction in the receiving bone's own frame
(SUP up, ANT right), the radius is |JCF| in body weights, and the loop is the
contact-force vector traced over the trial, drawn over the bone's silhouette
read straight out of the `.osim`. No OpenSim install needed — the model and
its `.vtp` meshes are read as plain XML.

```bash
bioscout plot jcf --model scaled.osim \
    --jra Analyse_JRA_ReactionLoads_SO.sto Analyse_JRA_ReactionLoads_CEINMS.sto \
    --labels SO CEINMS --mass 95 --ik joint_angles.mot -o jcf_direction.png
```

`--ik` (the trial's IK `.mot`) buys two things: the hip is converted exactly
from the femur frame OpenSim wrote to the pelvis frame (Newton's third law +
the hip's own SpatialTransform rotation), and each panel gains the
neighbouring segment dotted at its two extremes with a range-of-motion arc.
`--bw` (newtons) replaces `--mass`; `--plane frontal` gives the MED/LAT view;
`--geometry DIR ...` adds mesh search folders. Details: `docs/JCF_DIRECTION.md`.

### `bioscout model check` — the one to run after moving anything

OpenSim resolves a mesh path **relative to the folder holding the `.osim`**. Move
a model, rename a `Geometry/` folder, or write a personalised model into a new
subfolder, and OpenSim opens it with every muscle, marker and joint intact and
**no bones at all** — no exception, nothing in the log.

```bash
bioscout model check                      # the project's model folders
bioscout model check models --strict      # fail on anything not portable
bioscout model check models --json geometry.json
```

It reads XML only — no OpenSim needed — and reports *which tier* resolved each
mesh, because "found it" is not the useful answer:

| tier | meaning |
|---|---|
| `local` | the model's own folder or its `Geometry/`. **Portable — the only pass.** |
| `parent` | `../Geometry`. Fine in a project tree, breaks if the model alone is copied. |
| `bundled` | only bioscout's own `Geometry/`. Renders only because bioscout is installed. |
| `search` | only via `--search` or `$OPENSIM_HOME`. Machine-local. |
| `absolute` | an absolute path. Points somewhere *else* on another computer. |
| `case` | only by ignoring filename case. Works on Windows, fails on Linux. |
| `empty` / `missing` | zero-byte mesh / not found. **No bone will be drawn.** |

Anything but `local` warns; `--strict` makes it a failure. The same check runs at
warn level every time a model is loaded during a run.

---

## Project structure

A project is a folder holding a `settings.py` and a `simulations/` tree organised
**subject → session → iteration → trial**.

```
my_project/
├── settings.py                    ← project config AND the runner (see below)
├── generic models/                ← unscaled .osim models shared by every subject
└── simulations/
    └── <Subject>/<Session>/
        ├── session.yaml           ← the source of truth for this session
        ├── 1_c3dfiles/            ← raw captures, flat: <Trial>.c3d
        ├── 2_experimental/        ← model-INDEPENDENT exports, written once
        │   └── <Trial>/  marker_experimental.trc  grf.mot  GRF.xml
        │                 emg.mot  emg_filtered.mot  emg_filtered_normalised.mot
        │                 grf_events.png  emg_processing.png
        ├── 3_iterations/          ← model-DEPENDENT outputs, one folder per variant
        │   ├── cateli/
        │   ├── gpk/
        │   └── gpk_mri/
        │       ├── scaled_opt_N10.osim  scaled_opt_N10_mvicx3.00.osim
        │       ├── ceinms_calibration/  ← calibrated subject, per ITERATION
        │       ├── validation/          ← muscle_inspect reports for this model
        │       └── <Trial>/
        │           ├── external_biomechanics/  IK + ID (.sto), kinematics_moments.png
        │           ├── muscle_analysis/        muscle lengths / moment arms
        │           ├── static_optimisation/    SO forces + activations + figures
        │           ├── ceinms/                 CEINMS execution outputs
        │           └── joint_contact_forces/   JRA (SO & CEINMS) + literature bands
        ├── logs/
        └── results/               ← cross-iteration comparison figures
```

### The three levels, and why they are separate

**Session** — one visit to the lab. It owns the raw `.c3d` captures and the
model-independent exports derived from them (markers, ground reaction forces,
EMG). These depend only on what the participant did, so they are computed **once**
and every iteration reads the same files. Re-exporting per model is the single
most common way to make two models look different for the wrong reason.

**Iteration** — one model variant. Everything downstream of a scaled `.osim`
lives here: the model itself, its CEINMS calibration, its validation reports and
its per-trial results. Two iterations of the same session differ *only* in the
model, which is what makes them comparable.

**Trial** — one movement, with one folder per pipeline stage. Stages are
idempotent: a stage whose output already exists is skipped unless you pass
`replace=True`, so an interrupted run resumes rather than restarting.

`ceinms_calibration/` sits **inside** the iteration, not at the session root. The
calibrated subject is a property of one model variant — `cateli`, `gpk` and
`gpk_mri` each have their own — so a session-level folder would claim one
calibration covers all of them.

### `session.yaml` is the source of truth

One file per session defines the iterations and their labels, colours and groups;
the static trial and body mass; per-trial time windows and events; the EMG
channel-to-muscle map; and the CEINMS α/β/γ weights.

**It outranks `settings.py` at run time.** Where the two disagree, `settings.py`
is the one silently doing nothing — that is the first thing to check when a
setting appears to have no effect.

It is parsed strictly: duplicate keys and iteration names differing only in case
are errors, not last-wins. `Session.open` requires exactly `session.yaml` (not
`.yml`), and `Session.iterations` only reports an iteration whose folder exists
on disk.

Create one from the captures rather than by hand — the trial list comes from the
c3d filenames, so a trial cannot go missing:

```bash
bioscout --new-session "simulations/<Subject>/<Session>" --body-mass 82.5
bioscout --c3d-export  "simulations/<Subject>/<Session>"
bioscout --classifier  "simulations/<Subject>/<Session>" --write-session-yaml
```

The full walkthrough, including what `session new` deliberately does *not*
guess, is in [docs/SESSION_LAYOUT.md](docs/SESSION_LAYOUT.md).

### Resolving folder names — never join them by hand

Two layouts are supported. The numbered one above is current; the older flat one
(`c3dfiles/`, `experimental/`, iterations directly under the session) still works,
and existing sessions are never renamed behind your back. The resolvers in
`bioscout.utils.session_layout` answer from **what is on disk**, preferring the
numbered names only when creating something new:

| call | returns |
|---|---|
| `c3d_root(session)` | `1_c3dfiles/` |
| `experimental_root(session)` | `2_experimental/` |
| `iterations_root(session)` | `3_iterations/` |
| `iteration_path(session, name)` | `3_iterations/<name>/` |
| `is_numbered_layout(session)` | `True` once the session is numbered |

Because they read the disk, a resolver must be called **after** the folders exist.
Caching one in a module-level constant returns the wrong answer on a session that
is half-migrated — the mistake to watch for.

### Trial layout & attribute names

As of 2.0 there is no `Inputs` class — the canonical folder layout is owned by
`Analyse` itself (`bioscout.utils.analysis._default_layout_paths`). A project only
needs its own `Inputs` class in `settings.py` if it wants to *override* the
default paths (`Analyse` picks it up automatically when present). On an
`Analyse`/trial object the terse layout fields have readable aliases (read/write
proxies onto the same value):

| alias | field | | alias | field |
|---|---|---|---|---|
| `model_path` | `model_dir` | | `grf` | `grf_mot` |
| `joint_angles` | `ik` | | `joint_reaction_so` | `jra` |
| `inverse_dynamics` | `id` | | `joint_reaction_ceinms` | `jra_ceinms` |
| `static_optimisation_forces` | `so_forces` | | `static_optimisation_activations` | `so_activations` |

The short names remain the canonical keys serialised into `trial_settings.xml`.

### Resetting

`s.reset()` and `Session.reset_project()` strip a session back to inputs-only,
keeping a timestamped backup. Pass `dry_run=True` to see what would go first — a
dry run that reports nothing removed is correct behaviour, not a failure.

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

Raw captures go in `simulations/<Subject>/<Session>/1_c3dfiles/` as flat
`<Trial>.c3d`; `bioscout --c3d-export` turns them into the shared
`2_experimental/` inputs. See [Project structure](#project-structure).

---

### `settings.py` is also the runner

The project's `settings.py` doubles as the runner: edit the CONFIG block at the
bottom (which iterations, trials, and stages to run) and launch it directly. It
opens the session and drives `Iteration.run` / `Session.summarise` for you:

```bash
conda activate bioscout_env
python settings.py
```

Toggle `DO_SCALE` / `DO_EXBIOMEC` / `DO_SO` / `DO_CEINMS` / `DO_SUMMARY` and
`REPLACE` there; per-trial config (time windows, sides, CEINMS α/β/γ, model names)
lives in each session's `session.yaml`.

---

## Adding a new subject

A subject needs three things: **(1)** an entry in `settings.py`, **(2)** a scaled
`.osim` model, and **(3)** the trial `.c3d` files placed in the simulations tree.

Say your raw captures live as one folder per session with each file named after
the trial, e.g.:

```
C:/…/Powerlifiting/c3dfiles/25_03_31/Walking_02.c3d
                                     Squat_BW_01.c3d
                                     Squat_35kg_01.c3d
```

1. **Declare the subject** in `settings.py` → `BatchSettings.subjects` (plain data):
   ```python
   dict(name="Athlete_04", label="Athlete 04", session="25_03_31",
        model_so="scaled.osim", model_ceinms="scaled.osim",
        generic_model="Rajagopal2015.osim", color="orange", group="generic"),
   ```

2. **Ingest the C3D files** — distributes each `<trial>.c3d` into
   `simulations/<subject>/<session>/<trial>/inputs/c3dfile.c3d` and creates the
   `models/<subject>/<session>/` folder:
   ```bash
   bioscout session ingest "C:/…/Powerlifiting/c3dfiles/25_03_31" \
     --subject Athlete_04 --session 25_03_31
   ```

3. **Drop the scaled model** at `models/Athlete_04/25_03_31/scaled.osim` (matching
   the `model_so`/`model_ceinms` names from step 1).

4. **Run** — `--export` regenerates markers/GRF/EMG + `trial_settings.xml` from each c3d:
   ```bash
   bioscout run Athlete_04 --session 25_03_31 --export --replace
   ```

(`session ingest` is also available on the Python API as `session.ingest_c3d(source=…)`.)

---

## Running the pipeline

> The commands below are the **stable OpenSim / CEINMS pipeline** (the focus of
> 2.x). `bioscout lab` holds the markerless-video / wearables features
> (`lab shots`, `lab load-report`, `lab add-subject`) — **targeted for bioscout
> 3.0 and not stable yet**. Ignore them for pipeline work; they're documented in
> [Future add-ons](#future-add-ons).

**Command line** — run the full pipeline (SO + CEINMS) for one subject:

```bash
cd /path/to/my_project
bioscout run Athlete_03_Cateli
```

Restrict scope, force a rebuild, or re-export inputs from C3D:

```bash
bioscout run Athlete_03_Cateli --session 25_03_31 --trial Walking_02
bioscout run Athlete_03_Cateli --replace      # overwrite existing outputs
bioscout run Athlete_03_Cateli --export       # regenerate inputs/ from c3d first
```

`--session` and `--trial` accept comma-separated lists; `bioscout run` with no
subject runs every subject in `settings.py`. Runs are **idempotent** — a stage is
skipped when its output already exists unless `--replace` is given.

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

### CEINMS execution modes

CEINMS execution minimises a weighted objective (Sartori et al. 2014, Eq. 1):

```
F_obj = α · E_trackMOM  +  β · E_sumEXC  +  γ · E_trackEMG
```

| term | weight | what it penalises |
|:--|:--|:--|
| `E_trackMOM` | **α** | difference between CEINMS and inverse-dynamics joint moments |
| `E_sumEXC` | **β** | sum of squared excitations — an **effort** penalty, not an EMG term |
| `E_trackEMG` | **γ** | difference between adjusted and measured excitations — the **EMG-tracking** weight |

Only the **ratios** `β/α` and `γ/α` are identifiable: scaling an objective
cannot move its minimum, so `(α, β, γ)` and `(1, β/α, γ/α)` are the same
problem. That is why α is conventionally fixed at 1, and why
`α10 β1 γ1000` and `α1 β0.1 γ100` are the same run.

Choosing γ is not settled, and it is not cosmetic — on a powerlifting dataset
γ moved hip contact force by several body weights. So bioscout does not assume
one way of running CEINMS. Pick a **mode**, and the mode decides both how many
solves happen and *what the result is*.

```yaml
# simulations/<subject>/<session>/session.yaml
ceinms:
  mode: bounds          # single | bounds | full_loop | lcurve | optimise
  alpha: 1
  beta: 1
  gamma: 30             # the PRODUCTION weighting
  gamma_bounds: [10, 100]
```

Default is `single`, so a project that never sets `mode` behaves exactly as
before.

| mode | solves | the result is | use it when |
|:--|:--|:--|:--|
| **`single`** | 1 | one curve | the weighting is already justified; you want the cheapest correct run |
| **`bounds`** | 3 | production estimate **+ a sensitivity band** | you must show how much the weighting moved the answer, without paying for a grid |
| **`full_loop`** | ∏ ranges | a **range with a median** | you want the distribution over a grid, not a bracket |
| **`lcurve`** | β × γ grid, +1 | production taken from the **knee** | you want the published tuning procedure — read the caveat below |
| **`optimise`** | — | CEINMSoptimise picks the weights | you would rather search than choose; far the slowest |

#### `single`

```yaml
ceinms: {mode: single, alpha: 1, beta: 1, gamma: 30}
```

One solve into `ceinms/Execution_a1_b1_g30/`. Identical to pre-mode behaviour.

#### `bounds`

```yaml
ceinms:
  mode: bounds
  alpha: 1
  beta: 1
  gamma: 30
  gamma_bounds: [10, 100]     # must bracket gamma
```

Three solves — lower, upper, then **production last**. Report γ = 30 as the
estimate and γ = 10–100 as a band around it. The band is *not* a confidence
interval and its middle is *not* a median: the brackets are chosen to expose a
sensitivity, so averaging them would invent a central tendency. bioscout
refuses bounds that do not bracket γ, because a band that excludes the estimate
cannot be read as a sensitivity around it.

#### `full_loop`

```yaml
ceinms:
  mode: full_loop
  alpha_range: [1]
  beta_range:  [0.2, 1, 3]
  gamma_range: [1, 3, 10, 30, 100, 300]
```

Every combination, production last. Here the median *is* descriptive, because
the grid is dense enough for it to mean something. Cost is the product of the
range lengths — 18 solves per trial above.

#### `lcurve`

```yaml
ceinms:
  mode: lcurve
  lcurve_betas:  [0, 0.2, 1, 3, 10, 30, 100, 300]
  lcurve_gammas: [0, 1, 3, 10, 30, 100, 300, 1000, 3000]
```

Sweeps the grid, normalises each objective term to its own maximum, builds the
best curve (at each γ the lowest `Ê_trackMOM`, breaking ties toward the lowest
`Ê_sumEXC` as Sartori do — without that tie-break β = 0 wins every point by
construction), locates the knee by the L-method, and then re-solves at the knee
so production is the knee.

> **Check the knee before you trust it.** The L-method finds the corner of a
> *normalised* picture. When the curve is nearly flat past the elbow, both axes
> are normalised to their own extremes and the knee tracks the **range you
> swept** rather than the data. On this project's squat trials the knee came
> out at exactly one tenth of the top of the γ range, in five nested ranges out
> of five.
>
> The manifest reports two diagnostics:
> - `elbow_ratio` — two-segment fit RMSE ÷ single-line RMSE. Below about 2 there
>   is no real elbow and the "knee" is just the best place to break a line.
> - `knee_gamma_over_range_top` — run two different γ ranges. If this is
>   unchanged, the knee is a property of your grid. Use `bounds` or
>   `full_loop` and report a band instead.

#### `optimise`

CEINMSoptimise searches the weight space itself. Nothing to configure, but it
is far the slowest, and it builds its **own** cfg — check that the dofSet it
tracks matches your execution cfg, since a silently dropped coordinate (knee
adduction, typically) changes predicted hip contact force substantially.

#### What lands on disk

Every mode writes one folder per solve,
`ceinms/Execution_a<α>_b<β>_g<γ>/`, plus a manifest:

```
ceinms/ceinms_modes_manifest.json
  {"mode": "bounds",
   "arms": [{"alpha":1,"beta":1,"gamma":10,"tag":"a1_b1_g10","production":false,
             "output_dir":"...","ok":true}, ...],
   "production": {...},
   "knee": null}
```

**The production arm is always solved last**, and its outputs keep the plain
untagged filenames — so downstream code that knows nothing about modes reads
the production result by default, and a run that dies half way leaves a tree
that is incomplete rather than one quietly describing the wrong weighting.

#### The API

```python
from bioscout.utils import ceinms
m = ceinms.ExecutionMode(trial)      # reads session.yaml via the trial
print(m.mode, m.n_solves, m.arms)    # inspect before committing the compute
manifest = m.run(trial.run_ceinms_exe_single)

ceinms.ExecutionMode.describe()      # {mode: one-line definition}
```

The implementation lives in `bioscout/utils/ceinms/modes.py` and is re-exported
above, so there is one name to remember. It is a separate module on purpose:
`ceinms.py` imports OpenSim, scipy, matplotlib and pandas at its top and is
loaded inside a `try/except` that degrades to "binary package only" when any of
those is missing. If mode *selection* lived there, a missing OpenSim DLL would
turn a three-arm `bounds` run into a one-arm run **with no error** — the config
option would be silently ignored. `ceinms.modes` imports only the standard
library, so `mode` is parsed and validated identically whether or not the
solver can start:

```python
from bioscout.utils.ceinms.modes import ExecutionMode   # no OpenSim needed
```

To turn per-arm results into a band:

```python
band = ceinms.ExecutionMode.aggregate({"a1_b1_g10": jcf_low,
                                       "production": jcf_prod,
                                       "a1_b1_g100": jcf_high})
# -> {"production", "low", "high", "median", "n"}
```

Quote `production`. Plot `low`–`high` as the band.


### Several EMG maps in one session

Which model muscles an electrode is taken to drive is a modelling assumption,
and a consequential one — widening the gastrocnemius channel to the whole
triceps surae changes what CEINMS is fitting. So `emg_map` can hold **named**
maps, and each iteration names the one it runs with:

```yaml
# simulations/<subject>/<session>/session.yaml
emg_map:
  narrow:
    EMG_Channels_EMG09_gast_med_l: [gasmed_l, gaslat_l]
    # ... the session's other channels
  triceps:
    EMG_Channels_EMG09_gast_med_l: [gasmed_l, gaslat_l, soleus_l]
  wide:
    EMG_Channels_EMG09_gast_med_l: [gasmed_l, gaslat_l, soleus_l, perlong_l]

default_emg_map: narrow          # optional: what a silent iteration gets

iterations:
  cateli_narrow:  {generic: Catelli.osim, emg_map: narrow,  ...}
  cateli_triceps: {generic: Catelli.osim, emg_map: triceps, ...}
  gpk_wide:       {generic: GPK_v3.osim,  emg_map: wide,    ...}
```

The alternative was one COPIED session per grouping — same subject, same
trials, same windows, same exported inputs, differing in one dict, and three
places to keep a time range in step. As iterations they share all of that and
compare in the same tables and figures.

A single flat `emg_map` (the original form) still works exactly as before: the
two are told apart by value type — a channel maps to a **list** of muscles, a
named map to a **mapping** of channels.

Ambiguity is an error rather than a default. With more than one map and no way
to choose — no iteration selector, no `default_emg_map`, no map called
`default` — the session refuses to load, as does a selector naming a map that
does not exist. The failure being avoided is a run that completes normally
several hours later having used the wrong electrode set, with nothing in the
output to show it.

```python
from bioscout.utils.session import emg_maps, resolve_emg_map
emg_maps(cfg)                        # {'narrow': {...}, 'triceps': {...}, ...}
resolve_emg_map(cfg, "cateli_wide")  # the flat {channel: [muscles]} it runs with
```


### Several calibration configs in one session

CEINMS's calibration bounds were one global value in `settings.py`, so sweeping
one meant copied sessions and a runtime monkeypatch. `calibration` is a
session.yaml block with the same shape as `emg_map`:

```yaml
calibration:
  wide:  {optimalFiberLength: "0.5 3",        tendonSlackLength: "0.5 3"}
  tight: {optimal_fiber_length: [0.75, 1.25], tendon_slack_length: "0.75 1.25"}

default_calibration: wide

iterations:
  cateli__wide:  {generic: Catelli.osim, calibration: wide,  ...}
  cateli__tight: {generic: Catelli.osim, calibration: tight, ...}
```

Same rules throughout: one flat block or several named ones, told apart by
value type; ambiguity refuses to load. An override is **partial** — a config
naming only `optimalFiberLength` leaves every other bound to `settings.py`.

**Both spellings of every parameter now work.** `settings.py` has always
declared `optimal_fiber_length`, `tendon_slack_length`, `shape_factor` and
`strength_coefficient`, while the XML writer read the camelCase names — so four
of the six ranges were unreachable and editing them in `settings.py` silently
did nothing. Only `c1` and `c2` were ever live. Both spellings are canonicalised
now, in `settings.py` and in `calibration:` alike.

```python
from bioscout.utils.session import calibration_configs, resolve_calibration
resolve_calibration(cfg, "cateli__tight")   # {'optimalFiberLength': '0.75 1.25', ...}
```


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

`session reset` strips generated outputs (IK/ID/MA/SO/JRA results, `setup_*.xml`,
`MuscleAnalysis/`, `Execution*/`, filtered EMG, plots, CEINMS calibration, …)
back to the raw inputs, so a trial re-runs clean. It **keeps** each trial's
`inputs/` folder (the C3D lives inside it) and `trial_settings.xml`, and makes a
**timestamped backup** (`simulations_backup_<ts>/`) before deleting anything.

`session reset` follows the same scoping as everything else — pass `--trial` to reset
one trial, `--session` for a whole session, or no scope to reset the entire
`simulations/` folder:

```bash
# reset only, no run
bioscout session reset --trial Walking_02            # one trial (keeps whole inputs/)
bioscout session reset --session 25_03_31            # a whole session
bioscout session reset                               # the entire simulations/ folder
bioscout session reset --trial Walking_02 --dry-run  # preview, touch nothing
bioscout session reset --trial Walking_02 --raw      # prune inputs/ to just the c3d + trial_settings.xml

# reset-then-run: `run --reset` resets exactly the trials it is about to run
bioscout run Athlete_03_Cateli --session 25_03_31 --trial Walking_02 --reset --replace

# add --export to also regenerate inputs/ (markers/GRF/EMG) from the C3D
bioscout run Athlete_03_Cateli --session 25_03_31 --trial Walking_02 --reset --export --replace
```

When scoped to a trial, sibling trials and session-level files are left
untouched. Because `inputs/` is preserved, a plain `session reset` already gives a
clean recompute; add `--export` only when you also want inputs rebuilt from the
C3D.

**Python API** — the session-centric hierarchy (`Session` → `Iteration` → trial):

```python
from bioscout import Session

s  = Session.open("simulations/Athlete_03/25_03_31")
it = s.iteration("gpk_mri")

# whole iteration (all its trials); do_scale builds the scaled model first
it.run(trials=["Walking_02", "Squat_BW_01"], do_scale=False,
       do_so=True, do_ceinms=True, calibrate=True, replace=True)

# one trial, step by step (a trial is an Analyse object)
t = it.trial("Walking_02")
t.run_ik(); t.run_id(); t.run_ma(); t.run_so()
t.calculate_muscle_moments(forces_type="so"); t.run_jra()

# every model iteration in the session, then cross-model comparison figures
s.run(do_so=True, do_ceinms=True); s.summarise()

# whole project — batch across every simulations/<subject>/<session>/session.yaml
Session.batch_sessions(".", subjects="Athlete_03", do_so=True, do_ceinms=True)
```

The per-trial stages are, in order:

```
IK → ID → Muscle Analysis → Static Optimisation → muscle moments → JRA        (SO branch)
EMG normalise → CEINMS calibrate (session) → CEINMS execute → muscle moments → JRA   (CEINMS branch)
```

To clean a session back to inputs-only (with a timestamped backup):

```python
s.reset(dry_run=True)                                          # this session (dry_run first!)
Session.reset_project(".", sessions="25_03_31", dry_run=True)  # whole project, scoped
```

---

## Muscle ranking across models — `bioscout plot collings`

Which muscles a model leans on, ranked, with every model side by side and the
disagreement drawn on:

```bash
bioscout plot collings "simulations/Athlete_03/25_03_31"
bioscout plot collings "simulations/Athlete_03/25_03_31" --skip gpk_mri cateli_mri
bioscout plot collings . --trial Walking_03 --metric impulse --top 15 --side _l
```

One ranked panel per model iteration, ordered by **peak muscle force** of each
functional group (`--metric impulse` for the time-integral instead). Static
optimisation is the leftmost panel wherever it exists — it uses no EMG, so it is
the same whatever the EMG-informed columns do, which is what makes it the right
reference to anchor on.

**Read the colours, not the lines.** Each muscle is coloured by its rank in the
leftmost panel and keeps that colour all the way right, so the left panel is
always a clean dark→pale ramp and *any* colour disorder further right is a
re-ranking. Connectors then tell you the direction: blue = ranked higher by the
panel on its right, red = lower, dotted = dropped out of the top N.

| flag | meaning |
|---|---|
| `plot collings [SESSION]` | session folder (the one holding `session.yaml`); defaults to `.`. Pointing at a project or subject folder works too if exactly one session sits below it. |
| `--skip A B ...` | iterations to leave out, case-insensitive |
| `--trial NAME[,NAME]` | restrict to these trials (default: all) |
| `--metric peak\|impulse` | rank by peak force (default) or force impulse |
| `--side _r\|_l` | which limb (default right) |
| `--top N` | how many muscle groups (default 12) |
| `-o DIR` | output folder (default `<session>/4_outputs/collings`) |

After Collings et al. (2025), *Med Sci Sports Exerc*, who use this layout to
compare exercise rankings by peak muscle force against peak EMG. The layout and
the colour anchoring are theirs; the columns here are **models**, not two
measures of one model, so output from this flag is not a replication of their
result.

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
overlay data lives in `bioscout.muscle_inspect.literature_jcf` and can be plotted
on its own:

```python
from bioscout.muscle_inspect import literature_jcf as ljcf
ljcf.plot_jcf_validation("hip_ref.png", entity="hip")
```

**Model validation (`muscle_inspect`).** An independent module checks a model's
geometry and properties against the literature, writing everything into
`muscle_inspect_<model>/` next to the model. `all` runs the full battery — moment
arms + fibre length/pennation + isometric & isokinetic strength (bundled
literature auto-resolved, only `--model` required):

```bash
python -m bioscout.muscle_inspect all      --model scaled_mvicx3.00.osim   # full validation
python -m bioscout.muscle_inspect inspect  --model scaled.osim             # moment-arm sweep + wrap fix
python -m bioscout.muscle_inspect validate --model scaled.osim             # moment arms vs literature
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

These features exist in early/experimental form (some already have CLI flags in
the **"player tracking — EXPERIMENTAL"** group of `--help`) but are **not stable
and not part of the 2.x OpenSim pipeline — targeted for bioscout 3.0**:

- **Player / movement tracking (computer vision).** Markerless kinematics from a
  phone or laptop camera via pose estimation, feeding the same OpenSim pipeline.
  Experimental CLI: `--shots` (video shot analysis), `--poses`, `--hoop`,
  `--yolo-model`, and the player registry (`--add_subject` → `subjects.json`).
- **Training-load & wearables.** Fatigue/load reports from fitness-tracker
  exports and cloud pulls. Experimental CLI: `--load-report`, `--zepp-pull`,
  `--strava-pull`, `--hr-max`/`--hr-rest`/`--age`/`--sex`, `--creds`.
- **Real-time muscle forces.** A pre-trained ML model that maps camera-derived
  kinematics to muscle and joint contact forces in (semi-)real time, integrating
  the computer-vision and OpenSim/CEINMS pipelines.

> Pipeline subjects (for the OpenSim/CEINMS batch) are declared in your project's
> `settings.py` `subjects` list — **not** via `--add_subject`, which targets the
> separate player-tracking registry.
