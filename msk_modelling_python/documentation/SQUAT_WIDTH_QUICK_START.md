# Squat Width Project - Quick Start Guide

## 🚀 One-Command Processing

Run the complete batch pipeline for your Squat Width sessions with a single command!

### Usage

```bash
cd C:\Git\app

# Process default session (P012) with default static trial (static_01)
python run_squat_width_pipeline.py

# Process specific session
python run_squat_width_pipeline.py P012

# Process session with custom static trial
python run_squat_width_pipeline.py P012 static_02

# Process different subject
python run_squat_width_pipeline.py P013 static_01
```

---

## 📋 What Gets Processed

The pipeline automatically:

1. **Discovers all C3D files** in the session folder
2. **Runs analysis on each file**:
   - ✓ C3D Export
   - ✓ Inverse Kinematics (IK)
   - ✓ Inverse Dynamics (ID)
   - ✓ Static Optimization (SO)
3. **Scales the model** using your static trial
4. **Organizes results** in Results folder
5. **Generates detailed logs**

---

## 🔧 Configuration

### Built-in Project Settings

The system uses `squat_width_config.py` with your project paths:

```python
PROJECT_ROOT = C:\Users\Basilio\ucloud\Squat_Width
SIMULATIONS_FOLDER = C:\Users\Basilio\ucloud\Squat_Width\Simulations
SETUP_FILES_FOLDER = C:\Users\Basilio\ucloud\Squat_Width\setup_files
MARKERSET = C:\Users\Basilio\ucloud\Squat_Width\setup_files\markers.xml
GENERIC_MODEL = C:\Users\Basilio\ucloud\Squat_Width\Models\Catelli-V4.0_pyCGM_pelvis.osim
```

### Custom Configuration

If you want to use custom settings, edit `squat_width_session_config.json`:

```json
{
  "session_folder": "C:\\Users\\Basilio\\ucloud\\Squat_Width\\Simulations\\P012",
  "setup_files_folder": "C:\\Users\\Basilio\\ucloud\\Squat_Width\\setup_files",
  "generic_model": "C:\\Users\\Basilio\\ucloud\\Squat_Width\\Models\\Catelli-V4.0_pyCGM_pelvis.osim",
  "markerset": "C:\\Users\\Basilio\\ucloud\\Squat_Width\\setup_files\\markers.xml",
  "static_trial_name": "static_01"
}
```

Then run:
```bash
python run_session_pipeline.py squat_width_session_config.json
```

---

## 📁 Session Folder Structure

Your session folder should contain C3D files:

```
Simulations/
└── P012/
    ├── static_01.c3d
    ├── squat_01.c3d
    ├── squat_02.c3d
    ├── walk_01.c3d
    └── walk_02.c3d
```

The pipeline will auto-generate:

```
Simulations/
└── P012/
    ├── static_01.c3d
    ├── squat_01.c3d
    ├── ...
    ├── Results/                          ← Generated
    │   ├── Scaled_static_01.osim         ← Scaled model
    │   ├── static_01/
    │   │   ├── joint_angles.mot
    │   │   ├── inverse_dynamics.sto
    │   │   └── SO_StaticOptimization_force.sto
    │   ├── squat_01/
    │   │   └── ...
    │   └── ...
    └── batch_logs/                       ← Generated
        └── batch_processing.log
```

---

## ✨ Markerset Location

The markerset is now **in the setup_files folder**:

```
setup_files/
├── markers.xml              ← Your markerset (NEW location!)
├── setup_IK.xml
├── setup_ID.xml
├── setup_SO.xml
└── setup_MA.xml
```

---

## 🎯 Quick Examples

### Example 1: Process P012 Session
```bash
python run_squat_width_pipeline.py P012
```
- Uses `C:\Users\Basilio\ucloud\Squat_Width\Simulations\P012`
- Uses `static_01` for model scaling
- Results saved to `P012/Results/`

### Example 2: Process P012 with Different Static Trial
```bash
python run_squat_width_pipeline.py P012 static_02
```
- Uses `static_02.c3d` for model scaling instead

### Example 3: Process Multiple Sessions
```bash
python run_squat_width_pipeline.py P012
python run_squat_width_pipeline.py P013
python run_squat_width_pipeline.py P014
```

---

## 📊 Output Files

After processing, you'll have:

### In `Results/<trial_name>/`:
- `joint_angles.mot` - IK results (joint angles over time)
- `inverse_dynamics.sto` - ID results (joint forces/moments)
- `SO_StaticOptimization_force.sto` - Muscle forces from optimization
- `SO_StaticOptimization_activation.sto` - Muscle activations

### In `Results/`:
- `Scaled_<static_trial>.osim` - Your subject-specific scaled model

### In `batch_logs/`:
- `batch_processing.log` - Detailed processing log

---

## 🔍 Monitoring Progress

Check the log file while processing:

```bash
# Windows
type C:\Users\Basilio\ucloud\Squat_Width\Simulations\P012\batch_logs\batch_processing.log

# Or open in your favorite text editor
notepad C:\Users\Basilio\ucloud\Squat_Width\Simulations\P012\batch_logs\batch_processing.log
```

---

## ⚙️ Required Files

Ensure these exist before running:

✓ **C3D files** in session folder with marker data
✓ **Markerset** at `setup_files/markers.xml`
✓ **Setup files** (IK, ID, SO) in `setup_files/` folder
✓ **Generic model** OSIM file

---

## 🆘 Troubleshooting

### "C3D files not found"
- Check files end with `.c3d` (lowercase)
- Verify session folder path is correct

### "Static trial not found"
- Check file name matches `static_trial_name` argument
- Example: file `static_02.c3d` → use `python run_squat_width_pipeline.py P012 static_02`

### "Setup files not found"
- Verify all 4 XML files exist: `setup_IK.xml`, `setup_ID.xml`, `setup_SO.xml`, `setup_MA.xml`
- Check folder is `setup_files/` (with underscore, not hyphen)

### "Markerset not found"
- Verify `markers.xml` exists in `setup_files/` folder
- Check file spelling and location

---

## ✅ Verification Checklist

Before running the pipeline:

- [ ] Session folder exists: `C:\Users\Basilio\ucloud\Squat_Width\Simulations\P012\`
- [ ] C3D files present in session folder
- [ ] Setup files folder exists: `setup_files/`
- [ ] Markerset exists: `setup_files/markers.xml`
- [ ] Generic model exists: `Models/Catelli-V4.0_pyCGM_pelvis.osim`
- [ ] All 4 setup XMLs present (IK, ID, SO, MA)

---

## 🎉 You're Ready!

```bash
cd C:\Git\app
python run_squat_width_pipeline.py P012
```

That's it! The pipeline handles everything else. ✨
