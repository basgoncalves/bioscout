# Session Batch Pipeline Guide

## Overview

The Session Batch Pipeline automates the complete workflow for processing motion capture data:

1. **Auto-discovers C3D files** in your session folder
2. **Runs batch analysis**: IK → ID → SO → C3D Export
3. **Auto-scales model** using a static trial
4. **Generates results** in organized directories

## Quick Start

### Step 1: Configure Your Session

Edit `squat_width_session_config.json`:

```json
{
  "session_folder": "C:\\Users\\Basilio\\ucloud\\Squat_Width\\Simulations\\P012",
  "setup_files_folder": "C:\\Users\\Basilio\\ucloud\\Squat_Width\\setup_files",
  "generic_model": "C:\\Users\\Basilio\\ucloud\\Squat_Width\\Models\\Catelli-V4.0_pyCGM_pelvis.osim",
  "markerset": "C:\\Users\\Basilio\\ucloud\\Squat_Width\\setup_files\\markers.xml",
  "static_trial_name": "static_01"
}
```

### Step 2: Run the Pipeline

```bash
cd C:\Git\app
python run_session_pipeline.py squat_width_session_config.json
```

That's it! The system will:
- Discover all C3D files in the session
- Run IK, ID, and SO for each trial
- Export C3D files
- Scale the model using the static trial
- Generate results and logs

## Configuration Details

### Required Fields

| Field | Description | Example |
|-------|-------------|---------|
| `session_folder` | Path to session folder containing C3D files | `C:\Squat_Width\Simulations\P012` |
| `setup_files_folder` | Folder with OpenSim setup files | `C:\Squat_Width\setup_files` |
| `generic_model` | Template OSIM model | `C:\Models\Catelli-V4.0_pyCGM_pelvis.osim` |
| `markerset` | Markerset XML file | `C:\Squat_Width\setup_files\markers.xml` |
| `static_trial_name` | Name of static trial for scaling | `static_01` |

### Setup Files Folder

Must contain these files:
- `setup_IK.xml` - Inverse kinematics configuration
- `setup_ID.xml` - Inverse dynamics configuration
- `setup_SO.xml` - Static optimization configuration
- `setup_MA.xml` - Muscle analysis configuration (optional)

Example structure:
```
setup_files/
├── setup_IK.xml
├── setup_ID.xml
├── setup_SO.xml
└── setup_MA.xml
```

## Workflow Details

### Phase 1: Batch Processing

For **each C3D file** discovered in the session:

1. **C3D Export** - Extracts and validates motion capture data
2. **Inverse Kinematics (IK)** - Calculates joint angles from marker positions
3. **Inverse Dynamics (ID)** - Calculates joint moments and forces
4. **Static Optimization (SO)** - Estimates muscle forces

Output files per trial:
- `joint_angles.mot` - IK results
- `inverse_dynamics.sto` - ID results
- `SO_StaticOptimization_force.sto` - Muscle forces
- `SO_StaticOptimization_activation.sto` - Muscle activations

### Phase 2: Model Scaling

Uses the **static trial** to scale the generic model:

1. Extract body segment lengths from static trial IK results
2. Scale generic model to match subject proportions
3. Save scaled model as `Scaled_<static_trial_name>.osim`

The scaled model can then be used for:
- More accurate muscle-tendon length calculations
- Subject-specific muscle physics
- Refined force predictions

## Session Folder Structure

Your session should look like:

```
P012/
├── 19-03-2026_squat.c3d
├── 19-03-2026_walk.c3d
├── static_01.c3d
├── Results/                    (auto-created)
│   ├── Scaled_static_01.osim
│   ├── 19-03-2026_squat/
│   │   ├── joint_angles.mot
│   │   ├── inverse_dynamics.sto
│   │   └── SO_StaticOptimization_force.sto
│   └── 19-03-2026_walk/
│       ├── joint_angles.mot
│       └── ...
└── batch_logs/                 (auto-created)
    └── batch_processing.log
```

## Input Requirements

### C3D Files
- Valid C3D format with motion capture data
- Marker labels matching markerset

### Markerset
- XML file defining marker names and positions
- Must match marker labels in C3D files
- Example: `lfwt` (left foot), `rfwt` (right foot), etc.

### Generic Model
- OpenSim OSIM file (XML format)
- Should have default body segment properties
- Markerset references in model

## Output Files

### Logs
- `batch_logs/batch_processing.log` - Full processing log with timestamps
- Includes errors, warnings, and processing times

### Results
- `Results/<trial_name>/` - One folder per trial
- `Results/Scaled_<static_trial>.osim` - Scaled subject model
- All analysis output files (IK, ID, SO, muscles)

### C3D Exports
- Processed C3D files with computed data
- Ready for further analysis or visualization

## Troubleshooting

### "No C3D files found"
- Check that session folder path is correct
- Ensure C3D files have `.c3d` extension (lowercase)
- Verify files aren't corrupted

### "Static trial not found"
- Check `static_trial_name` matches a C3D filename
- Example: if file is `static_01.c3d`, use `static_01`
- Names are case-sensitive

### "Setup file not found"
- Verify all 4 setup files exist in setup folder
- Check file names: `setup_IK.xml`, `setup_ID.xml`, `setup_SO.xml`, `setup_MA.xml`

### "IK analysis failed"
- Check marker labels in C3D match markerset
- Verify marker data quality (gaps, noise)
- Review `batch_processing.log` for details

### "Model scaling failed"
- Ensure static trial completes IK successfully
- Check `Results/<static_trial>/joint_angles.mot` exists
- Verify generic model and markerset are compatible

## Advanced Usage

### Multiple Sessions

Create separate config files for each session:

```bash
# Session 1
python run_session_pipeline.py p012_config.json

# Session 2
python run_session_pipeline.py p013_config.json

# Batch multiple (requires external script)
for config in *.json; do
    python run_session_pipeline.py "$config"
done
```

### Reprocessing with Different Settings

Edit configuration and rerun:
- Change `generic_model` for different template
- Change `static_trial_name` to scale with different trial
- Modify `setup_files_folder` for different OpenSim settings

## Next Steps

After the pipeline completes:

1. **Review logs** - Check `batch_logs/batch_processing.log`
2. **Inspect results** - Open IK/ID/SO files in OpenSim
3. **Validate model** - Check scaled model proportions
4. **Further analysis** - Use results for EMG correlation, statistics, etc.

## Example Command

```bash
# Navigate to app directory
cd C:\Git\app

# Run pipeline with default Squat_Width configuration
python run_session_pipeline.py squat_width_session_config.json

# Monitor batch log
# Windows:
type C:\Users\Basilio\ucloud\Squat_Width\Simulations\P012\batch_logs\batch_processing.log

# View results
# C:\Users\Basilio\ucloud\Squat_Width\Simulations\P012\Results\
```

## Support

For issues:
1. Check the batch processing log
2. Verify all input files exist and are readable
3. Review this guide for configuration requirements
4. Check OpenSim documentation for analysis setup details
