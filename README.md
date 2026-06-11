# msk_modelling_python

A Python package for musculoskeletal modelling and biomechanical data analysis.  
Inspired by [BOPS](https://simtk.org/projects/bops/) (Batch OpenSim Processing Scripts).

**Author:** Basilio Goncalves, PhD — University of Vienna  
[ufind.univie.ac.at](https://ufind.univie.ac.at/de/person.html?id=1004543) · [github.com/basgoncalves](https://github.com/basgoncalves)

---

## Requirements

- Python ≥ 3.8 (3.11 recommended)
- [OpenSim ≥ 4.3](https://simtk.org/frs/?group_id=91)
- Windows (primary target; Linux/macOS untested)

Optional: [Visual Studio Code](https://code.visualstudio.com/download), [MOKKA](https://biomechanical-toolkit.github.io/mokka/)

---

## Quick Start — pip install

**1. Create and activate a virtual environment**

```sh
# Python venv
python -m venv msk
.\msk\Scripts\activate          # Windows
source msk/bin/activate         # Linux / macOS

# Or Conda / Miniconda
conda create -n msk python=3.11
conda activate msk
```

**2. Install**

```sh
pip install uv
uv pip install msk-modelling-python
```

**3. Launch**

GUI interface (default):

```sh
python -m msk_modelling_python
```

Batch mode:

```sh
python -m msk_modelling_python -b msk_modelling_python/settings.py
```

Video batch mode:

```sh
python -m msk_modelling_python -b video_batch.json
```

> Note: do not paste the descriptive text after these commands. On Windows
> `cmd.exe`, `#` is not a comment character, so a trailing `# ...` is passed to
> the program as arguments and causes `unrecognized arguments`.

---

## Development Setup — work from source

**1. Clone into your virtual environment's site-packages**

```sh
.\msk\Scripts\activate
cd .\msk\Lib\site-packages
git clone https://github.com/basgoncalves/msk_modelling_python.git
```

**2. Install dependencies**

```sh
cd msk_modelling_python
pip install -r requirements.txt
```

**3. Set up OpenSim Python bindings**

```sh
cd "C:\OpenSim 4.5\sdk\Python"
python setup_win_python38.py
python -m pip install .
```

Add to your `PATH` environment variable:
```
C:\OpenSim 4.5\bin
C:\OpenSim 4.5\lib
```

Verify:
```python
import opensim as osim
osim.Model()   # should not raise
```

**4. Launch**

```sh
python -m msk_modelling_python
```

---

## Usage

### GUI (default)
```sh
python -m msk_modelling_python
```

Opens the full interface with tabs for batch processing, video analysis, EMG, model scaling, and results viewing.

### Batch mode
Edit `msk_modelling_python/settings.py` (see `BatchSettings`, `CEINMSSettings`) then run:
```sh
python -m msk_modelling_python -b msk_modelling_python/settings.py
```
Pipeline: C3D export → model scaling → IK → ID → static optimisation → muscle analysis → CEINMS.

### Video batch mode
```sh
python -m msk_modelling_python -b video_batch.json
```
```json
{
    "videos": ["path/to/video1.mp4", "path/to/video2.mp4"],
    "model": "full_body",
    "detect_interval": 1,
    "output_dir": "path/to/output"
}
```

---

## Code Structure

| Package | Description |
|---|---|
| `gui/` | GUI widgets — batch processing, C3D export, EMG, CEINMS, video analysis |
| `utils/` | Core processing — OpenSim (IK, ID, SO, MA), CEINMS, EMG, model scaling, C3D |
| `core/` | Session and analysis runner (shared by GUI and batch modes) |
| `config/` | Settings load/save |
| `record/` | Screen/video recording, camera utilities, pose-estimation pipeline |
| `models/` | Bundled OpenSim model files (`.osim`) and geometry meshes |
| `movement_detector/` | Rule-based classifier: segments pose landmarks into labelled movement types |
| `settings.py` | Central config — edit `BatchSettings`, `CEINMSSettings`, `UISettings`, `RecordingSettings` |

---

## Contact

**Basilio Goncalves** — basilio.goncalves@univie.ac.at  
[ResearchGate](https://www.researchgate.net/profile/Basilio-Goncalves)

---

## References

Thelen, D. G. (2003) J. Biomech. Eng. 125, 70–77  
Lloyd, D. G. et al. (2003) J. Biomech. 36, 765–776  
Delp, S. L. et al. (2007) IEEE Trans. Biomed. Eng. 54, 1940–1950  
Pizzolato, C. et al. (2015) J. Biomech. 48, 3929–3936  
Hicks, J. L. et al. (2015) J. Biomech. Eng. 137  
Rajagopal, A. et al. (2016) IEEE Trans. Biomed. Eng. 63, 2068–2079  
Goncalves, B. A. M. et al. (2023) Gait Posture 106, S68  
Goncalves, B. A. M. et al. (2024) Med. Sci. Sport. Exerc. 56, 402–410  

---

## Changelog

### v0.4.2 (2026-06-11)

**Video Analysis tab**
- Fix crash on scroll/zoom: invalid 8-digit colour `#00000088` (Tkinter accepts only 6-digit hex) broke the canvas redraw
- Fix video frame jumping to the top-left corner while scrubbing the timeline (now uses the shared centred redraw)
- Compact the under-video controls and add a draggable horizontal sash to resize the video pane
- Move pose detection settings (interval, smoothing) **above** the action buttons
- Reduce tracked ROI box jitter between frames (exponential smoothing + dead-zone)
- Fix **Export Outputs**: now runs `record/video_analyzer.py` to generate the OpenSim `.mot` (path resolution was wrong), passing the GUI's poses/anchors to skip re-detection
- Wire **`movement_detector`** into Export: writes `<video>_motion_segments.json` (standing / walking / running / squatting / jumping / …)

**Player profiles**
- Add `utils/player_profile.py`: per-player anthropometry, limb proportions, saved calibration, OpenSim/CEINMS model paths and detection settings, stored one folder per player
- Add a **Player** dropdown (New/Edit) to the Video Analysis tab; selecting a player applies their calibration, models and detection settings, and Export writes a player snapshot

**Batch / settings**
- Add **multi-session batch**: process many sessions in one run via a single `SESSIONS = {session_folder: static_trial_name}` dict in `settings.py`
- Tolerant static-trial matching (`static01` / `static_01` / `Static_01` all match; `None` auto-detects)
- Remove `SESSION_DIR` / `session_folder` / `static_trial_name` from `BatchSettings` — `SESSIONS` is the single source of truth
- Lenient `-b` settings-path handling so batch runs from any working directory

**Logging**
- One log file per run (`app_*.log` for GUI, `batch_*.log` for batch) — no more empty second log

**Carried over from earlier 0.4.2 work**
- Fix `utils/__init__.py` truncated `emg_normalise` import block (IndentationError on startup)
- Fix `utils/openSim.py` truncated `_Tee` class in `__main__` block (SyntaxError)
- Fix `utils/dev.py` truncated parallel worker error handler
- Fix `utils/__init__.py` CEINMS import collision: use `importlib.util` to load `ceinms.py` explicitly
- Fix `settings.DOFs` → `settings.BatchSettings.dof_list` in `utils/__init__.py` and `utils/dev.py`
- Fix IK NaN crash: interpolate missing marker values in TRC files before running `InverseKinematicsTool`
- Add **Video Analysis GUI tab**: process pre-recorded videos → OpenSim MOT/TRC via MediaPipe pose estimation
- Add **video batch mode** (`-b video_batch.json`)
- Add **`movement_detector` module**: rule-based pose landmark classifier with gap-filling
- Move OpenSim model files into dedicated `models/` package
- Add `RecordingSettings.DEFAULT_VIDEO_ANALYSIS_MODEL` and `OUTPUT_DIR_TEMPLATE`

### v0.4.1 (2026-06-09)
- Fix GUI crash on startup: `model_scaling` widget imports `marker_weights` from `BatchSettings`
- Fix `batch_c3d_export` widget to read EMG defaults from `BatchSettings` attributes

### v0.4.0
- New settings and GUI entry point; cleaned up stale files
- n8n-inspired workflow pipeline with full OpenSim batch processing example
- Batch pipeline fixes, GUI stability improvements, OpenSim late-load

### v0.3.6
- Updated utils; added CEINMS support with troubleshooting and calibration executables

### v0.0.20
- CEINMS2 integration via pip packaging

### v0.0.17
- Version bump with new images and path adjustments
