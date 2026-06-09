# Powerlifting Model Analysis App - Startup Guide

## Prerequisites

- Python 3.8+
- Conda with `msk311` environment (contains OpenSim, customtkinter, etc.)

## Starting the App

### GUI Mode
```bash
conda activate msk311
cd C:\Git\app
python .
```

This launches the full graphical interface for interactive analysis.

### Batch Mode (No GUI)
```bash
conda activate msk311
cd C:\Git\app
python . --batch batch_settings_example.xml
python . -b batch_settings_example.xml  # short form
```

Batch mode processes multiple trials without opening the GUI.

### Direct Batch Runner
```bash
conda activate msk311
cd C:\Git\app
python batch_runner.py batch_settings_example.xml
```

## Batch Settings Files

- **batch_settings_example.xml** — Core OpenSim analysis (IK, ID, SO, MA, etc.)
- **batch_settings_ceinms_calibration.xml** — CEINMS workflow (calibration + execution)
- **batch_settings_c3d_export.xml** — Export data to C3D format

## Environment Setup

If you haven't created the msk311 environment yet:

```bash
conda env create -f environment.yml
# or install manually:
conda activate msk311
conda install -c conda-forge opensim
pip install customtkinter pyyaml
```

## Troubleshooting

**ModuleNotFoundError: No module named 'opensim'**
- Make sure you've activated the msk311 environment: `conda activate msk311`
- Verify OpenSim is installed: `python -c "import opensim; print(opensim.__version__)"`

**ModuleNotFoundError: No module named 'tkinter'**
- This is normal in headless/server environments
- Use batch mode instead of GUI mode
- On desktop: ensure Python was installed with tkinter support

## Batch Processing Examples

### Process IK for two trials
```xml
<analysis_steps>
    <step name="inverse_kinematics" enabled="true"/>
</analysis_steps>
<replace_existing>false</replace_existing>
```

### Full CEINMS workflow
```bash
python . -b batch_settings_ceinms_calibration.xml
```

### Export results to C3D
```bash
python . -b batch_settings_c3d_export.xml
```

## Session/Working Directory

Add to your batch settings to specify where session files are stored:
```xml
<session_dir>C:\path\to\session\folder</session_dir>
```

## Logging

All batch output is logged to: `C:\Git\app\logs\app_*.log`

Custom log location:
```xml
<log_file>C:\path\to\custom\batch_log.txt</log_file>
```
