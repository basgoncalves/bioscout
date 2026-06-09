# Urgent Issues and Answers - May 20, 2026

## ✅ COMPLETED UI Improvements

### Batch C3D Export Tab
- ✅ **Removed Source Folder** from visible UI (auto-populated from session)
- ✅ **Filters Side-by-Side** with text labels above each (Low, High, Notch)
- ✅ **EMG Channels Taller** (expanded height minsize=150px)

---

## 📋 REMAINING ISSUES

### 1. **Analog.csv Not Copied to Destination Folder**

**Problem**: 
- `analog.csv` is being created successfully in the source folder
- But error says: "Could not copy analog.csv: [WinError 2] The system cannot find the file specified"
- This means code is trying to COPY it but the path is wrong

**Root Cause**: 
The export utility creates `analog.csv` in one location, but the copy attempt looks for it in the wrong directory path.

**Solution Locations to Check**:
1. `C:\Git\powerlifing_model_clean\code\tests\app\utils\exportC3D.py` - Check how/where analog.csv is created
2. `C:\Git\powerlifing_model_clean\code\tests\app\gui\widgets\c3d_export.py` - Check line where it copies analog.csv
3. `C:\Git\powerlifing_model_clean\code\tests\app\gui\widgets\batch_c3d_export.py` - Check if batch export has custom copy logic

**What to look for**:
- Search for `shutil.copy` with `analog.csv`
- Check if path is absolute vs relative
- Verify the source path exists before trying to copy

---

### 2. **EMG Label Pattern Definition**

**Question**: "Where do I define template EMG label pattern?"

**Answer**: 
It's already defined in TWO places:

1. **Default Value** (`C:\Git\powerlifing_model_clean\code\tests\app\settings.py` line 80):
   ```python
   BATCH_C3D_EMG_LABEL_DEFAULT = "emg"
   ```
   This is the default pattern shown in the Batch C3D Export UI text field.

2. **User Input Field** (Batch C3D Export > EMG Settings > Label):
   Users can change "emg" to any pattern they want, e.g.:
   - `emg` (default, matches any channel with "emg" in the name)
   - `Voltage` (matches channels with "Voltage")
   - `EMG_` (matches channels with "EMG_" prefix)
   - `Subject01_.` (matches subject-specific patterns)

The pattern is used with `in` operator: `if pattern in channel_name:`

To change the default, modify `BATCH_C3D_EMG_LABEL_DEFAULT` in `settings.py`.

---

### 3. **Force Plates Checkbox Position (Picture 3 vs 4)**

**Issue**: Position of force plate checkboxes in C3D File Export tab

**To Fix**: 
The checkboxes appear to be in the wrong grid position. Need to check:
- `C:\Git\powerlifing_model_clean\code\tests\app\gui\widgets\c3d_export.py`
- Look for where force plate checkboxes are grid()'d
- Compare with picture 4 (reference position)
- Adjust row/column positioning

---

## 🔧 SETTINGS FILE CONSOLIDATION

### Current Situation:
```
C:\Git\powerlifing_model_clean\code\tests\app\settings.py
    └─ 100+ lines of UI constants (fonts, colors, spacing, dimensions)

C:\Git\powerlifing_model_clean\code\tests\app\utils\settings.py
    └─ 500+ lines of project-specific config (EMG mappings, DOFs, models, trials)
       ├─ Class definitions (Inputs class)
       ├─ Project configurations
       └─ Analysis group definitions
```

### Consolidation Strategy:

**Option A: Keep Two Separate (Current)**
- `/app/settings.py` = UI settings only
- `/utils/settings.py` = Project/analysis settings
- **Pro**: Clean separation, each module imports what it needs
- **Con**: Two different systems

**Option B: Merge into One Unified File**
- `/app/settings.py` = Everything (500+ lines)
- `/utils/settings.py` = Imports from `/app/settings.py`
- **Pro**: Single source of truth
- **Con**: Larger file, mixed concerns

**Option C: Structured Multi-Module (Recommended)**
```
/app/settings/
    ├── __init__.py          (re-exports all)
    ├── ui_settings.py       (fonts, colors, spacing)
    ├── batch_settings.py    (batch processing defaults)
    ├── project_settings.py  (EMG, DOFs, models)
    └── analysis_settings.py (analysis config)
```
Then all modules import: `from settings import VARIABLE`

### Current Usage in Modules:
- `gui/widgets/batch_c3d_export.py` imports: `BATCH_C3D_*` defaults
- `utils/exportC3D.py` likely uses local settings
- Various analysis scripts use `utils/settings.py`

### To Implement Consolidation:

1. **Decide on structure** (A, B, or C above)
2. **Create unified settings.py** with all constants
3. **Update all imports**:
   ```python
   # Before
   from utils.settings import EMG_muscle_mapping
   
   # After  
   from settings import EMG_muscle_mapping
   ```
4. **Test that everything still works**

---

## 🎯 Priority Order to Fix:

1. ⚠️ **URGENT**: Fix `analog.csv` copy error (blocks batch exports)
2. **HIGH**: Consolidate settings files (prevents configuration conflicts)
3. **MEDIUM**: Fix force plates checkbox positions (UI polish)
4. **LOW**: Document EMG label pattern usage (already working)

---

## Commands to Find Problematic Code:

```bash
# Find where analog.csv is copied
grep -r "shutil.copy.*analog" --include="*.py"
grep -r "analog\.csv" --include="*.py"

# Find all imports of utils.settings
grep -r "from utils.settings import" --include="*.py"
grep -r "from utils import.*settings" --include="*.py"

# Find force plate checkbox definitions  
grep -r "force.*plate.*checkbox" --include="*.py" -i
grep -r "Force Plate.*[Ff]orce" gui/widgets/c3d_export.py
```

---

## Files That Need Updates:

When doing settings consolidation:
- [ ] `C:\Git\powerlifing_model_clean\code\tests\app\settings.py` (consolidate TO here)
- [ ] `C:\Git\powerlifing_model_clean\code\tests\app\utils\settings.py` (consolidate FROM here)
- [ ] `All files that import from utils.settings` (update imports)
- [ ] `All files that import from settings` (verify they still work)

---

**Date**: May 20, 2026
**Status**: UI Improvements ✅ | Critical Issues Identified 🚨 | Ready for Implementation 🔧
