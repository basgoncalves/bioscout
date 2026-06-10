# msk_modelling_python v0.4.2

A Python package for musculoskeletal modelling.

This package includes a combination of other packages and custom functions to manipulate and analyze biomechanical data. Originally inspired by the MATLAB version of BOPS (Batch OpenSim Processing Scripts) - [BOPS](https://simtk.org/projects/bops/)

**Author:** Basilio Goncalves, PhD, University of Vienna, 2024
https://ufind.univie.ac.at/de/person.html?id=1004543
https://github.com/basgoncalves

---

## Pre-requisites for Installation

1. **Download a Code Interpreter**  
    I recommend [Visual Studio Code](https://code.visualstudio.com/download), but use your preferred one.

2. **Download and Install Python (>= 3.8)**  
    Make sure it is the correct bit version: [Python 3.8](https://www.python.org/downloads/release/python-380/)

3. **Download and Install OpenSim (suggest >=4.3)**  
    [OpenSim Downloads](https://simtk.org/frs/?group_id=91)

4. **Install Rapid Env Editor (optional)**  
    [Rapid Env Editor](https://www.rapidee.com/en/about)

5. **MOKKA (optional / only Windows users)**
    [Open-source and cross-platform software to easily analyze biomechanical data](https://biomechanical-toolkit.github.io/mokka/)

---


### Pip installation (works for python 3.8)
(for later versions try [OpenSim using Conda](https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53085346/Scripting+in+Python))
https://pypi.org/project/msk-modelling-python/0.4.0/ 

#### Activate your Virtual Environment**
you can use [Python](https://docs.python.org/3/library/venv.html) or [Conda](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html) 
```sh
cd <your project folder>
python -m venv msk
```

conda
```sh
conda create -n msk python=3.11
conda activate msk
```
or if using miniconda
```
C:\ProgramData\miniconda3\Scripts\activate.bat msk
```

Note: replace 'msk' if you want a different name

```
.\msk\Scripts\activate
```
#### Install uv package manager
```
pip install uv
```

#### Install msk-modelling-python
```
uv pip install msk-modelling-python
```

#### Test usage

This launches the GUI. 
```cmd
python -m msk_modelling_python
```

To run in batch mode:
```cmd
python -m msk_modelling_python -b msk_modelling_python/settings.py
```


---
## Work with the code in edditing mode

1. **Activate your virtual enviroment (assume name 'msk')** 
   ```
   .\msk\Scripts\activate
   ```
---

2. **Clone this Module "msk_modelling_python" to your virtual environment**
   ```
   cd .\msk\Lib\site-packages
   ```
     ```
     git clone https://github.com/basgoncalves/msk_modelling_python.git
     ```
     *Note: Ensure the name of the package is exactly "msk_modelling_python"*
---

3. **Run OpenSim Setup from Installation Folder**  
    See [OpenSim Scripting in Python](https://simtk-confluence.stanford.edu:8443/display/OpenSim/Scripting+in+Python)

     ```sh
     cd 'C:\OpenSim 4.5\sdk\Python'
     ```
     ```sh
     python setup_win_python38.py
     ```
     ```sh
     python -m pip install .
     ```
     Note: run commands from shell or terminal    
---

4. **Add the Path to the OpenSim Libraries to Your Environment Variables**  
    Add the following paths to your `PATH` variable:
     ```
     C:\OpenSim 4.5\bin
     C:\OpenSim 4.5\lib
     ```
     Note: see for help https://answers.microsoft.com/en-us/windows/forum/all/change-system-variables-on-windows-11/f172c29e-fd9e-4f0b-949d-c4696bd656b8
---
5. **Verify the OpenSim Installation.**
     ```cmd
     python 
     ```
     ```cmd
     import opensim as osim
     model = osim.Model()
     ```
---
6. **Install requirements (in the terminal)**
     ```powershell
     cd .\msk\Lib\site-packages\msk_modelling_python
     pip install -r requirements.txt
     ```
---
7. **Launch msk_modelling_python**
     ```cmd
     python -m msk_modelling_python
     ```
     Note: to configure batch processing, edit `msk_modelling_python\settings.py` (see `BatchSettings` and `CEINMSSettings` classes)
---
8. **Basic Usage**

     **GUI mode (default):**
     ```cmd
     python -m msk_modelling_python
     ```

     **Batch mode** — configure `msk_modelling_python\settings.py` first, then:
     ```cmd
     python -m msk_modelling_python -b msk_modelling_python/settings.py
     ```

     Key settings to configure in `settings.py`:
     
---
9. **Use Example Scripts**
     Use example scripts in the "ExampleScripts" directory to get started with common tasks and workflows.

---


## Tools to be Included:
- **BTK**  
  [BTK Documentation](https://biomechanical-toolkit.github.io/docs/Wrapping/Python/_getting_started.html)
- **c3dServer**  
  [c3dServer](https://www.c3dserver.com/)
- **OpenSim**  
  [OpenSim Scripting in Python](https://simtk-confluence.stanford.edu:8443/display/OpenSim/Scripting+in+Python)
- **3D Slicer**  
  [3D Slicer](https://www.slicer.org/)
- **FEbioStudio**  
  [FEbioStudio](https://febio.org/)
- **MeshLab 2023.12**  
  [MeshLab](https://www.meshlab.net/)
- **Genesis**  
  [Genesis](https://genesis-embodied-ai.github.io/)
  

---

## Code Structure

1. **msk_modelling_python** — main package entry point; run with `python -m msk_modelling_python`

2. **settings.py** — central configuration file; edit `BatchSettings`, `CEINMSSettings`, `UISettings`, and `RecordingSettings` classes to control all pipeline behaviour

3. **gui/** — PyQt-based graphical interface (launched by default); widgets for batch processing, C3D export, EMG, CEINMS calibration, and results viewing

4. **utils/** — core processing functions: OpenSim (IK, ID, SO, MA), CEINMS, EMG normalisation, model scaling, C3D export, and XML helpers

5. **core/** — session and analysis runner logic used by both GUI and batch modes

6. **config/** — config manager for loading/saving settings

7. **record/** — video recording, camera utilities, and pose-estimation pipeline (`video_analyzer.py`) for motion capture sessions

8. **models/** — bundled OpenSim model files (`.osim`) and geometry meshes

9. **movement_detector/** — rule-based classifier that segments pose landmark time-series into labelled movement types (walking, running, jumping, etc.) with landmark gap-filling

---

## Examples

Launch the GUI for interactive use:
```cmd
python -m msk_modelling_python
```

For scripted/batch pipelines, configure `msk_modelling_python\settings.py` and run:
```cmd
python -m msk_modelling_python -b msk_modelling_python/settings.py
```
The pipeline supports: C3D export → model scaling → IK → ID → SO → muscle analysis → CEINMS calibration → CEINMS execution.

For video-only batch processing, pass a JSON file with a `"videos"` key:
```cmd
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

## Contact

For any questions or inquiries, please contact:

- **Name:** Basilio Goncalves
- **Email:** basilio.goncalves@univie.ac.at
- **ResearchGate:** [Basilio Goncalves](https://www.researchgate.net/profile/Basilio-Goncalves)

---

## References

Thelen, D. G. -2003- J. Biomech. Eng. 125, 70–77

Lloyd, D. G. et al. -2003- J. Biomech. 36, 765–776

Delp, S. L. et al. -2007- IEEE Trans. Biomed. Eng. 54, 1940–1950

Pizzolato, C. et al. -2015- J. Biomech. 48, 3929–3936

Hicks, J. L. et al. -2015- J. Biomech. Eng. 137,

Rajagopal, A. et al. -2016- IEEE Trans. Biomed. Eng. 63, 2068–2079

Goncalves, B. A. M. et al. -2023- Gait Posture 106, S68

Goncalves, B. A. M. et al. -2024- Med. Sci. Sport. Exerc. 56, 402–410

---

## Changelog

### v0.4.2 (2026-06-10)
- Fix `utils/__init__.py` truncated `emg_normalise` import block (IndentationError on startup)
- Fix `utils/openSim.py` truncated `_Tee` class in `__main__` block (SyntaxError)
- Fix `utils/dev.py` truncated parallel worker error handler
- Fix `utils/__init__.py` ceinms import collision: use `importlib.util` to load `ceinms.py` explicitly, bypassing `ceinms/` binary package
- Fix `settings.DOFs` → `settings.BatchSettings.dof_list` in `utils/__init__.py` and `utils/dev.py`
- Fix IK NaN crash: interpolate missing marker values in TRC files before running `InverseKinematicsTool`
- Add **Video Analysis GUI tab**: process pre-recorded videos to generate OpenSim MOT/TRC files using MediaPipe pose estimation
- Add **video batch mode** (`-b video_batch.json`): run `video_analyzer.py` over a list of videos from a JSON config file — auto-detected by the presence of a `"videos"` key
- Add **`movement_detector` module**: rule-based pose landmark classifier that segments video into labelled motion types (walking, running, jumping, squatting, side-cut, shuffle, deceleration, backward walking/running) with gap-filling for occluded landmarks
- Move OpenSim model files (`*.osim`) from `record/` into a dedicated `models/` package for cleaner imports
- Add `RecordingSettings.DEFAULT_VIDEO_ANALYSIS_MODEL` and `OUTPUT_DIR_TEMPLATE` to `settings.py`

### v0.4.1 (2026-06-09)
- Fix GUI crash on startup: `model_scaling` widget now correctly imports `marker_weights` from `BatchSettings` class instead of the deprecated module-level variable
- Fix `batch_c3d_export` widget to read EMG defaults from `BatchSettings` attributes instead of removed module-level constants

### v0.4.0
- Improved app and batch processing with new settings and GUI entry point
- Cleaned up stale files and moved CEINMS settings
- Added n8n-inspired workflow