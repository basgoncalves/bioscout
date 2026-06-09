# Powerlifting Model Analysis App - Fixes Summary

This document summarizes all fixes applied to resolve IK/ID analysis failures and path/EMG display issues.

## Issue 1: IK Failure Due to NaN Values in Marker Data

### Problem
IK was failing with "Missing output file for inverse_kinematics: joint_angles.mot" because the marker data contained NaN values at the beginning and end of recordings, causing the OpenSim solver to fail.

### Solution: Complete NaN Cropping Workflow

#### 1. Updated `exportC3D.crop_nans()` function
- **File**: `utils/exportC3D.py`
- **Changes**:
  - Modified return value from tuple `(start_idx, end_idx)` to dictionary with complete timing information
  - Return dict keys: `start_idx`, `end_idx`, `start_time`, `end_time`, `rows_removed_start`, `rows_removed_end`
  - Extracts actual time values from data at crop boundaries
  - Prints detailed cropping information including new time range

#### 2. Enhanced `_clean_motion_data()` method
- **File**: `utils/__init__.py`
- **Changes**:
  - Captures crop_info dictionary from `crop_nans()` return value
  - Calls new `_update_time_range_and_events()` method when rows are removed
  - Reloads settings after XML update to synchronize `self.time_range`
  - Logs detailed information about cleaning process

#### 3. Created new `_update_time_range_and_events()` method
- **File**: `utils/__init__.py`
- **Purpose**: Synchronizes all time-dependent files after NaN cropping
- **Actions**:
  1. Updates `trial_settings.xml` time_range element with new start/end times
  2. Updates `events.csv` to reflect new valid time range
  3. Preserves and updates start/end events
  4. Filters other events to only include those within valid range
  5. Creates start/end events if they don't exist

### How It Works
1. Before IK runs: `_clean_motion_data()` is called
2. `crop_nans()` removes rows where >10% of columns contain NaN values
3. If rows were removed:
   - Cropped data is saved back to files (marker_experimental.trc, grf.mot)
   - `trial_settings.xml` time_range is updated to match new data boundaries
   - `events.csv` is updated with new time values
   - Settings are reloaded to update `self.time_range`
4. IK now runs with:
   - Clean marker data (no NaN values)
   - Consistent time range across all files
   - Valid events that align with cropped data

---

## Issue 2: Path Auto-population Not Working in Session Analysis Tab

### Problem
Session Analysis tab showed empty path fields even though `trial_settings.xml` contained `setup_dir` and `model_dir` values.

### Solution: Fix XML Element Name Mismatch

#### Updated `_auto_populate_paths_from_first_trial()` method
- **File**: `gui/widgets/analysis_control_session.py`
- **Changes**:
  - Primary check: Look for `setup_dir` and `model_dir` elements (current format)
  - Fallback check: Look for `template_folder` and `model` elements (legacy format)
  - Added logging when paths are successfully auto-populated
  - Maintains relative-to-absolute path conversion

### Why This Works
- Current code writes `setup_dir` and `model_dir` to XML
- Old code was looking for `template_folder` and `model`
- Now supports both formats for smooth migration

---

## Issue 3: EMG Label Pattern Consistency

### Status: Verified Working
- EMG label pattern comes from `settings.py` via `BATCH_C3D_EMG_LABEL_DEFAULT`
- Default value: "Voltage"
- When exporting, pattern is extracted from selected channels for accuracy
- This ensures the detected EMG channels match the user's hardware naming convention

---

## Testing the Fixes

### For NaN Cropping:
```bash
1. Load a trial with marker data containing NaN values at start/end
2. Run Inverse Kinematics
3. Check logs for:
   - "Cropped marker_experimental.trc:"
   - "New time range: X.XXXX - Y.YYYY seconds"
   - "Updated time_range in trial_settings.xml"
   - "Updated events.csv with new time range"
4. Verify joint_angles.mot is created successfully
```

### For Path Auto-population:
```bash
1. Load a session with trials that have model_dir and setup_dir in XML
2. Verify path fields auto-populate
3. Check logs for "Auto-populated setup_dir from XML" and "Auto-populated model_dir from XML"
```

---

## Files Modified

1. `code/tests/app/utils/exportC3D.py`
   - Modified: `crop_nans()` function (lines 29-150)

2. `code/tests/app/utils/__init__.py`
   - Modified: `_clean_motion_data()` method (lines 843-879)
   - Added: `_update_time_range_and_events()` method (lines 880-950)

3. `code/tests/app/gui/widgets/analysis_control_session.py`
   - Modified: `_auto_populate_paths_from_first_trial()` method (lines 311-336)

---

## Expected Outcomes

1. ✅ IK should successfully complete and produce joint_angles.mot
2. ✅ ID should complete successfully and produce inverse_dynamics.sto
3. ✅ Path fields in Session Analysis should auto-populate from XML
4. ✅ Time range across all files (settings, events, data) is synchronized
5. ✅ Events.csv reflects only valid events within cropped time range

---

## Logging Output

After these fixes, the logs should show:
- Detailed NaN cropping information
- Confirmation of time_range and events.csv updates
- Path auto-population confirmations
- Successful IK and ID completion (if solver doesn't encounter other issues)

Check logs in: `app/logs/` directory for timestamped log files.
