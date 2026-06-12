<p align="center">
  <img src="https://raw.githubusercontent.com/basgoncalves/bioscout/main/bioscout/utils/logo.png" width="140" alt="BioScout Logo"/>
</p>

<h1 align="center">BioScout</h1>

<p align="center"><strong>Biomechanical analysis and movement scouting for coaches and athletes.</strong></p>

<p align="center">
BioScout is an open-source Python toolbox for musculoskeletal modelling, motion capture analysis, and real-time movement assessment.<br>
Successor to <a href="https://pypi.org/project/msk-modelling-python/">msk_modelling_python</a>.<br>
see <a href="LICENSE">License</a>
</p>


---

## App Preview

![BioScout Video Analysis — pose estimation on a sprinting athlete](https://raw.githubusercontent.com/basgoncalves/bioscout/main/bioscout/utils/app_window.png)

---

## What it does

- **Full OpenSim pipeline** — C3D → scaling → IK → ID → static optimisation → CEINMS muscle forces
- **Computer vision kinematics** — pose detection from phone or laptop camera
- **Player profiles** — organise athlete data across sessions, assign groups, track over time
- **Batch processing** — run entire pipelines overnight with a single settings file

---

## Requirements

| Dependency | Version | Install via |
|---|---|---|
| Python | 3.9 – 3.11 | conda |
| OpenSim | 4.6+ | `pip install opensim` (or `conda install -c opensim-org opensim`) |
| numpy, pandas, scipy, matplotlib | latest | pip (auto with bioscout) |
| opencv-python, mediapipe | latest | pip (optional, video features) |

---

## Installation

### Step 1 — Create a conda environment with Python 3.11

OpenSim requires Python 3.11 or earlier (it is not yet available for 3.12+).

```bash
conda create -n bioscout_env python=3.11 -y
conda activate bioscout_env
```

### Step 2 — Install OpenSim

OpenSim 4.6+ is available on PyPI (Python 3.11 required):

```bash
pip install opensim
```

If that fails (e.g. Python 3.12+), install via conda instead:

```bash
conda install -c opensim-org opensim -y
```

Verify it works:
```bash
python -c "import opensim; print(opensim.__version__)"
```

### Step 3 — Install BioScout

**From PyPI (stable release):**
```bash
pip install bioscout
```

**From source (development):**
```bash
git clone https://github.com/basgoncalves/bioscout
cd bioscout
pip install -e .
```

### Step 4 — Optional: video and pose estimation

Only needed for the recording / computer vision tabs:

```bash
pip install opencv-python mediapipe
```

### Step 5 — Verify

```bash
python -m bioscout --install
```

This prints a dependency status table and offers to install anything still missing.

---

## Quick start — new project from scratch

```bash
# 1. Initialise project folder (copies settings template, models, setup files)
python -m bioscout --init /path/to/my_project

# 2. Add participants (interactive prompts, saved to players.json)
cd /path/to/my_project
python -m bioscout --add_player   # repeat for each participant

# 3. Copy your C3D files into simulations/<player_id>/
#    e.g. simulations/012/HAB1.c3d, simulations/012/static1.c3d

# 4. Edit settings.py — set PROJECT_ROOT and PLAYERS
#    (players.json holds all participant data; settings.py only needs IDs)

# 5. Run the pipeline
python -m bioscout -b settings.py
```

---

## Usage reference

**Launch GUI:**
```bash
python -m bioscout
```

**Initialise a new project:**
```bash
python -m bioscout --init /path/to/my_project
```
Creates `simulations/`, `Models/`, `setup_files/`, and `logs/` and copies
the `settings.py` template, bundled OpenSim models, and setup XML files.

**Add a participant:**
```bash
cd /path/to/my_project
python -m bioscout --add_player
```
Prompts for ID, demographics (height, mass, age, sex), dominant leg, and injury
details. IDs are unique — duplicates are rejected. Data is saved to `players.json`.

**settings.py — PLAYERS field:**
```python
# Simple: IDs only — all data comes from players.json
PLAYERS = ['012', '078']

# With per-run overrides:
PLAYERS = {
    '012': {},
    '078': {'static_trial': 'static2'},
}
```

**Run batch pipeline:**
```bash
cd /path/to/my_project
python -m bioscout -b settings.py
```

**Check / install dependencies:**
```bash
python -m bioscout --install
```

---

## Project structure

After `--init` and adding two participants your project looks like:

```
my_project/
├── settings.py              ← edit PROJECT_ROOT and PLAYERS here
├── players.json             ← participant registry (auto-managed)
├── Models/
│   ├── GPK_generic.osim
│   └── Geometry/
├── setup_files/
│   ├── IK_task_set.xml
│   ├── markers_*.xml
│   └── ...
├── simulations/
│   ├── 012/
│   │   ├── static1.c3d
│   │   ├── HAB1.c3d
│   │   └── HAB1/           ← created by pipeline
│   │       ├── marker_experimental.trc
│   │       ├── grf.mot
│   │       ├── joint_angles.mot
│   │       └── ...
│   └── 078/
└── logs/
```

---

## Project-level analysis

```python
from bioscout.core.project_analysis import compare_groups, compare_players

results = compare_groups(['fais', 'control'], result_type='ik', dof='hip_flexion_r')
results = compare_players(['012', '078'], result_type='so_forces', dof='recfem_r')
```

---

## Migration from msk_modelling_python

```bash
pip uninstall msk-modelling-python
pip install bioscout
```

Replace imports:
```python
# Old
import msk_modelling_python as msk
# New
import bioscout as msk
```

---

