# Biomechanical Analysis Application

A ready-to-use musculoskeletal modeling package for motion capture analysis based on OpenSim and CEINMS, compatible with any device.

## Overview

This application provides a complete pipeline for biomechanical analysis:
- **Model Scaling**: Scale generic OpenSim models to subject-specific anatomy
- **Inverse Kinematics**: Compute joint angles from marker data
- **Inverse Dynamics**: Calculate joint forces and moments
- **Static Optimization**: Estimate individual muscle forces
- **Muscle Analysis**: Compute muscle kinematics and energetics
- **CEINMS Integration**: Advanced muscle force estimation

## Quick Start

### GUI Mode (Interactive)
```bash
python __main__.py
```

### Batch Mode (Automated)
1. Edit `settings.py` - Configure your session:
   ```python
   session_folder = r'C:\path\to\your\motion_capture_data'
   setup_files_folder = r'C:\path\to\opensim_setup_files'
   generic_model = r'C:\path\to\generic.osim'
   markerset = r'C:\path\to\markers.xml'
   static_trial_name = 'static_01'
   ```

2. Run batch processing:
   ```bash
   python __main__.py -batch settings.py
   ```

3. Check logs:
   ```
   C:\Git\app\logs\batch_20260529_121021.log
   ```

## Configuration

### BatchSettings (settings.py)

**Session Configuration**
- `session_folder`: Directory containing C3D files
- `setup_files_folder`: Directory with OpenSim setup XML files
- `generic_model`: Generic OSIM model for scaling
- `markerset`: Marker set definition XML file
- `static_trial_name`: Static calibration trial name

**Analysis Pipeline** (enable/disable steps in order)
- `enable_scale_model`: Scale generic model to subject anatomy
- `enable_inverse_kinematics`: Compute joint angles from marker data
- `enable_inverse_dynamics`: Calculate joint forces and moments from IK + GRF data
- `enable_static_optimization`: Estimate individual muscle forces from ID results
- `enable_muscle_analysis`: Compute muscle kinematics and energetics (not yet implemented)
- `enable_c3d_export`: Extract EMG and marker data

**C3D Export Settings**
- `emg_lowpass_default`: EMG lowpass filter (Hz)
- `emg_highpass_default`: EMG highpass filter (Hz)
- `emg_notch_default`: EMG notch filter (Hz)
- `emg_string_list`: List of EMG channel identifiers

## Data Structure

Expected input folder structure:
```
session_folder/
├── static_01.c3d           # Static calibration trial
├── dynamic_01.c3d          # Dynamic motion trial
├── dynamic_02.c3d
├── static_01/              # Trial subfolders (auto-discovered)
│   └── marker_experimental.trc
├── dynamic_01/
│   └── marker_experimental.trc
└── Results/                # Output directory (auto-created)
```

Output structure:
```
session_folder/
├── Results/
│   ├── [trial outputs]
│   └── inverse_dynamics.sto
└── trial_name/
    ├── scale_set.xml
    └── static_output.trc

C:\Git\app/
├── logs/
│   └── batch_20260529_121021.log
└── Models/
    └── Scaled_static_01.osim
```

## Project Configuration

The application supports multiple biomechanics projects:

### squatting_fais
- Squat analysis with different loads
- Subjects: Athlete_03, Athlete_03_Lernagopal, Athlete_03_GPK
- Trials: Walking, Squat (bodyweight and loaded)

### powerlifting_model
- Powerlifting movement analysis
- Customizable subject and trial lists

## Architecture

### Module Structure
```
__main__.py              Entry point (GUI or batch)
├── BatchSettings        Configuration (settings.py)
├── BatchLogger          Logging with file output
├── scale_model()        OpenSim integration
├── Analyse class        Trial processing
└── UISettings           GUI configuration
```

### Legacy Configuration
The application maintains backward compatibility with legacy code:
- `PROJECT_NAME`: Project identifier (squatting_fais, powerlifting_model)
- `marker_weights`, `DOFs`, `Muscle_Groups`: Biomechanical model parameters
- `EMG_muscle_mapping`: EMG channel to muscle mapping
- `Inputs` class: Trial-level file path definitions

### Logging

**Batch Mode Logging**
- Console output: All INFO and above messages
- File output: All DEBUG and above messages
- Location: `C:\Git\app\logs\batch_YYYYMMDD_HHMMSS.log`

**GUI Mode Logging**
- Configured through utils/logger.py
- Location: `C:\Git\app\logs\app_YYYYMMDD_HHMMSS.log`

## Command Line Options

```bash
# GUI mode (default)
python __main__.py

# Batch mode
python __main__.py -batch settings.py
python __main__.py -b settings.py

# Verbose output
python __main__.py -batch settings.py -verbose
python __main__.py -batch settings.py -v

# Suppress non-error output
python __main__.py -batch settings.py -quiet
python __main__.py -batch settings.py -q

# Help
python __main__.py -help
```

## Output Files

### Model Scaling
- **Scaled Model**: `C:\Git\app\Models\Scaled_<trial_name>.osim`
- **Scale Settings**: `<session>\<trial>\scale_set.xml`
- **Scaled Markers**: `<session>\<trial>\static_output.trc`

### Inverse Kinematics (IK)
- **Joint Angles**: `<session>\Results\<trial>\joint_angles.mot`
- **Model Marker Locations**: `<session>\Results\<trial>\<trial>_ik_model_marker_locations.sto`
- **IK Results**: All output files from OpenSim InverseKinematicsTool

### Inverse Dynamics (ID)
- **Joint Moments/Forces**: `<session>\Results\<trial>\inverse_dynamics.sto`
- **ID Setup**: `<session>\Results\<trial>\setup_ID.xml`
- **ID Results**: All output files from OpenSim InverseDynamicsTool

### Static Optimization (SO)
- **Muscle Forces**: `<session>\Results\<trial>\SO_StaticOptimization_force.sto`
- **Muscle Activations**: `<session>\Results\<trial>\SO_StaticOptimization_activation.sto`
- **SO Setup**: `<session>\Results\<trial>\setup_SO.xml`
- **SO Results**: All output files from OpenSim StaticOptimizationTool

### Static Optimization (SO)
- `<session>\Results\<trial>\SO_StaticOptimization_force.sto`
- `<session>\Results\<trial>\SO_StaticOptimization_activation.sto`

### Muscle Analysis (MA)
- `<session>\Results\<trial>\muscleAnalysis\`
  - Various kinematic and energetic outputs

## Troubleshooting

### "Session folder not found"
- Check that `session_folder` path in settings.py is correct
- Ensure path exists on your system
- Use absolute paths (C:\Users\..., not relative paths)

### "Generic model not found"
- Verify `generic_model` file exists
- Check file has .osim extension
- Use absolute paths

### "TRC file not found"
- Ensure trial subfolder exists: `<session_folder>\<trial_name>\`
- Check marker file is named: `marker_experimental.trc`
- File must be in the trial subfolder, not the session root

### "No C3D files found"
- Check C3D files exist in `session_folder`
- Verify file extension is `.c3d` (lowercase)

### Import Errors
- Ensure Python environment has required packages:
  - opensim
  - numpy, scipy
  - customtkinter (for GUI)

## Project Status

✅ **Ready for Production Use**

- Complete batch processing pipeline
- Model scaling with OpenSim
- Centralized logging to LOG_DIR
- Legacy and new architecture fully integrated
- Support for project-specific configurations

## Next Steps

1. **Configure settings.py** with your data paths
2. **Test with sample data** using batch mode
3. **Enable additional analysis steps** as needed
4. **Monitor logs** in C:\Git\app\logs\ for debugging

## Support

For detailed technical information, see:
- `PROJECT_STATUS.md`: Project history and architecture
- `settings.py`: Complete configuration reference
- Batch logs: `logs/batch_*.log` for execution details

---

**Version**: 1.0  
**Updated**: May 29, 2026  
**Status**: ✅ Production Ready
