# Batch Processing - Quick Reference

## Usage

```bash
python __main__.py -batch batch_settings.py
```

That's it! The system will:
1. Discover all C3D files in your session folder
2. Run IK → ID → SO analysis on each trial
3. Scale the model using your static trial
4. Save results to `Results/` folder

## Configuration

Edit `batch_settings.py` to set:

```python
class BatchSettings:
    session_folder = r"C:\path\to\session"           # Contains C3D files
    setup_files_folder = r"C:\path\to\setup_files"   # Contains setup XML files
    generic_model = r"C:\path\to\model.osim"         # Template model
    markerset = r"C:\path\to\markers.xml"            # Markerset file
    static_trial_name = "static_01"                  # For model scaling
```

## Output

Results are organized by trial:

```
session_folder/
├── Results/
│   ├── Scaled_static_01.osim       ← Your scaled model
│   ├── static_01/
│   │   ├── joint_angles.mot        ← IK results
│   │   ├── inverse_dynamics.sto    ← ID results
│   │   └── SO_StaticOptimization_*.sto
│   ├── squat_01/
│   │   └── [same files]
│   └── ...
└── batch_logs/
    └── batch_processing.log
```

## Presets

Use included presets in `batch_settings.py`:

```python
# P012 with static_01
from batch_settings import SquatWidthP012

# P013 with static_01
from batch_settings import SquatWidthP013

# P012 with static_02
from batch_settings import SquatWidthP012Alt
```

## Requirements

Before running, ensure you have:
- ✅ Session folder with C3D files
- ✅ Setup files folder (IK, ID, SO, MA XML files)
- ✅ Generic/template OSIM model
- ✅ Markerset XML file
- ✅ batch_settings.py configured

## Examples

### Example 1: P012 Default
```bash
python __main__.py -batch batch_settings.py
```

### Example 2: Create Custom Config
```python
# Create custom_settings.py
class BatchSettings:
    session_folder = r"C:\Custom\Path\P012"
    setup_files_folder = r"C:\Custom\Path\setup"
    generic_model = r"C:\Custom\Path\model.osim"
    markerset = r"C:\Custom\Path\markers.xml"
    static_trial_name = "static_01"
```

Then run:
```bash
python __main__.py -batch custom_settings.py
```

## Troubleshooting

**"Session folder not found"**
- Check paths in batch_settings.py are correct
- Use full absolute paths

**"No C3D files found"**
- Verify C3D files exist in session_folder
- Check filenames end with `.c3d`

**"Static trial not found"**
- Verify static_trial_name matches a C3D filename
- Example: `static_01.c3d` → use `"static_01"`

**"Setup file not found"**
- Ensure all 4 setup XMLs exist: IK, ID, SO, MA
- Check setup_files_folder path is correct

## Documentation

For detailed information, see:
- `SESSION_PIPELINE_GUIDE.md` - Complete documentation
- `batch_settings.py` - Settings file with examples

---

**Ready to run!** 🚀
