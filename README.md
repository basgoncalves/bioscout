# BioScout 🔬

**Biomechanical analysis and movement scouting for coaches and athletes.**

BioScout is an open-source Python toolbox for musculoskeletal modelling, motion capture analysis, and real-time movement assessment. It is the successor to [msk_modelling_python](https://pypi.org/project/msk-modelling-python/).

---

## What it does

- **Full OpenSim pipeline** — C3D → scaling → IK → ID → static optimisation → CEINMS muscle forces
- **Computer vision kinematics** — pose detection from phone or laptop camera
- **Player profiles** — organise athlete data across sessions, assign groups, track over time
- **Project-level analysis** — group comparisons, population stats, individual player comparisons
- **Batch processing** — run entire pipelines overnight with a single settings file

---

## Installation

```bash
pip install bioscout
```

Or clone and install in development mode:
```bash
git clone https://github.com/basgoncalves/bioscout
cd bioscout
pip install -e .
```

---

## Usage

**Launch GUI:**
```bash
python -m bioscout
```

**Run batch pipeline:**
```bash
python -m bioscout -b settings.py
```

**Custom dataset:**
```bash
python -m bioscout -b bioscout/settings_teaching.py
```

---

## Settings

All project paths derive from a single root — the only line you change per project:

```python
# settings.py
PROJECT_ROOT = Path(r'C:\your\project\folder')
PROJECT_NAME = 'my_project'

PLAYERS = {
    'P01': PlayerConfig(group='control'),
    'P02': PlayerConfig(group='fais'),
}
```

---

## Project-level analysis

```python
from bioscout.core.project_analysis import compare_groups, compare_players

# Compare groups
results = compare_groups(['fais', 'control'], result_type='ik', dof='hip_flexion_r')

# Compare individual players
results = compare_players(['P01', 'P02', 'P03'], result_type='so_forces', dof='recfem_r')
```

---

## Migration from msk_modelling_python

BioScout is a direct rename of `msk_modelling_python`. To migrate:

```bash
pip uninstall msk-modelling-python
pip install bioscout
```

Replace any imports:
```python
# Old
import msk_modelling_python

# New
import bioscout
```

---

## Requirements

- Python ≥ 3.8
- OpenSim 4.x (for musculoskeletal pipeline)
- OpenCV + MediaPipe (for computer vision, optional)

---

## License

MIT — see [LICENSE.md](LICENSE.md)
