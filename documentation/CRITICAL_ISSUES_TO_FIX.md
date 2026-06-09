# Critical Issues Found - May 20, 2026

## Issue Summary

From user screenshots and error logs, the following issues need to be addressed:

---

## 🔴 CRITICAL (Blocking)

### 1. DPI Scaling Error - Launch/Resize
**Status**: 🔴 CRITICAL
**Symptom**: `_tkinter.TclError: wrong # coordinates: expected 0 or 2, got 3`
**When**: During window DPI scaling (resize, move, or initialization)
**Location**: CustomTkinter canvas coordinate setting
**Impact**: Prevents smooth window operations, crashes on certain resize events
**Root Cause**: CustomTkinter trying to set 3 coordinates when 0 or 2 expected
**Files to Check**:
- `gui/widgets/emg_normalization.py` (recently modified)
- `gui/main_window.py` (main window structure)
- Any custom widget with canvas-based rendering

**Possible Solutions**:
- Check for widgets with invalid width/height (0 or negative)
- Verify scrollable frame configuration
- Check grid/pack geometry manager usage

---

### 2. Results Visualization - Geometry Manager Error
**Status**: 🔴 CRITICAL
**Symptom**: `Error rendering plot: cannot use geometry manager grid inside .tckframe`
**When**: Trying to plot results
**Location**: Results Viewer tab
**Impact**: Results cannot be visualized
**Root Cause**: Mixing grid() and pack() geometry managers, or using grid inside CTkFrame parent

**Files to Check**:
- `gui/widgets/results_viewer.py`
- Any plot widget using grid()

**Possible Solutions**:
- Use pack() for widgets inside CTkFrames
- Use grid() only at same level
- Check parent widget type

---

## 🟠 HIGH (Important)

### 3. EMG File Headings
**Status**: 🟠 HIGH (JUST FIXED ✓)
**Symptom**: `emg_filtered_normalised.mot` missing column headers
**File**: `emg_filtered_normalised.mot` (normalized output)
**Issue**: Header has "time" only, missing EMG channel names
**Impact**: Files cannot be properly read by downstream analysis

**Fix Applied**: Updated `_load_mot_file()` to properly read headers after endheader line
**Status**: ✅ FIXED in emg_normalization.py

---

### 4. Session Analysis - Error on Load
**Status**: 🟠 HIGH
**Symptom**: Multiple errors in console when loading Session Analysis tab
**Error Types**: 
- ValueError in conversion/casting
- File not found errors
**When**: Loading session data
**Files**: `gui/widgets/session_analysis.py`

---

### 5. Results Viewer - Inverse Kinematics Error
**Status**: 🟠 HIGH
**Symptom**: "inverse_kinematics: Error"
**When**: Running analysis pipeline
**Related Error**: IK fails with ValueError about string/float conversion
**Location**: Inverse Kinematics step

---

## 🟡 MEDIUM (Important but not blocking)

### 6. Menu Structure Reorganization
**Status**: 🟡 MEDIUM
**Requested**: 
- Move "Session Analysis" to between "CEINMS Calibration" and "EMG Normalization"
- Remove "Configuration" tab (duplicate of Settings)
- Order should be: C3D Export, Batch C3D, EMG Normalization, Session Analysis, CEINMS Calibration, Batch, Results, Configuration, Logs

**Files**: `gui/main_window.py`

---

### 7. Outputs Directory Cleanup
**Status**: 🟡 MEDIUM
**Issue**: `C:\Git\powerlifing_model_clean\code\tests\app\outputs\` has many temporary files
**Action**: Organize into tests/ or documentation/
**Files to Move/Delete**:
- Temporary analysis outputs
- Debug documentation
- Session reports

---

## Issues by Priority

| Priority | Issue | Status |
|----------|-------|--------|
| 🔴 CRITICAL | DPI Scaling Error | Needs investigation |
| 🔴 CRITICAL | Results Geometry Error | Needs fix |
| 🟠 HIGH | EMG Headings | ✅ FIXED |
| 🟠 HIGH | Session Analysis Errors | Needs investigation |
| 🟠 HIGH | IK Error | Needs investigation |
| 🟡 MEDIUM | Menu Reorganization | Needs implementation |
| 🟡 MEDIUM | Outputs Cleanup | Needs implementation |

---

## Investigation Steps

### For DPI Scaling Error:
1. Check EMG Normalization widget dimensions
2. Verify all CTkScrollableFrame sizes are positive
3. Test window resize/move operations
4. Check for any widgets with width=0 or height=0

### For Geometry Error:
1. Find which widget is using grid() inside CTkFrame
2. Change to pack() or restructure parent
3. Verify no mixed geometry managers in same parent

### For Session Analysis:
1. Check file path construction
2. Verify data type conversions
3. Check for missing files in session directory

### For IK Error:
1. Check input data types (string vs float)
2. Verify IK model file exists
3. Check OpenSim configuration

---

## Fix Order (Recommended)

1. **FIRST**: Fix DPI Scaling Error (blocks UI operations)
2. **SECOND**: Fix Results Geometry Error (blocks visualization)
3. **THIRD**: Fix Session Analysis Errors (blocks workflow)
4. **FOURTH**: Fix IK Error (blocks analysis pipeline)
5. **FIFTH**: Reorganize Menu Structure
6. **SIXTH**: Clean up Outputs Directory

---

## Verification

After each fix:
- [ ] Test app launch
- [ ] Test window resize
- [ ] Test tab switching
- [ ] Run analysis pipeline
- [ ] Check console for errors
- [ ] Verify file outputs

---

**Generated**: May 20, 2026
**Status**: Issue tracking document created - ready for fixes

