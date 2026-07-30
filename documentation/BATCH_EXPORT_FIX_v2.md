# Batch C3D Export Fixes - Complete Solution (v2)

## Critical Bugs Fixed

### 1. **EMG Export Function Error** ✅ FIXED
**Error**: `cannot access local variable 'emg_mot_path' where it is not associated with a value`

**Root Cause**: In `exportC3D.py`, when no EMG channels were found, the code tried to filter the `emg.mot` file using an undefined variable.

**Solution in exportC3D.py** (lines 152-177):
- Moved `emg_mot_path` definition outside the if statement
- Only call `filter_emg()` if EMG channels were actually found
- Added debug logging showing:
  - Search patterns: `[DEBUG] Looking for EMG patterns: ...`
  - Available labels: `[DEBUG] Available analog labels: ...`

### 2. **EMG Pattern Matching Issue** ✅ FIXED
**Problem**: Batch was passing full channel names like "Voltage.EMG01_r_gastro" as patterns, but `export_emg()` couldn't match them.

**Root Cause**: The `export_emg()` function expects substring patterns (like "emg"), not full channel names.

**Solution in batch_c3d_export.py** (lines 897-910):
- Changed from using full channel names as patterns
- Now uses simple "emg" pattern matching (same as C3D Export tab)
- This ensures all EMG channels in the C3D file are found and exported

### 3. **Reader Iteration Error** ✅ FIXED
**Error**: `'Reader' object is not iterable`

**Root Cause**: Direct iteration over `c3d.Reader()` object instead of using `read_frames()` method.

**Solution**:
- **Line 961** (analog.csv fallback): Changed `for frame_num, point_data, analog_data in reader:` to `reader.read_frames()`
- **Line 1025** (events.csv): Changed same iteration to use `read_frames()`

### 4. **Analog CSV Missing After Export** ✅ FIXED
**Problem**: `analog.csv` was created by `export_emg()` in source directory but batch code was looking in output directory.

**Solution**:
- **Lines 911-920**: Now correctly copies `analog.csv` from `c3d_file.parent` (source) to `output_folder`
- Added file size logging for verification
- Shows message: `[OK] Copied analog.csv from export_emg (XXX.XX KB)`

## Summary of Code Changes

### File: `exportC3D.py`
```python
# Lines 152-177: Fixed EMG export to handle missing channels
- Moved emg_mot_path outside if block
- Only filter EMG if channels were found
- Added debug logging for pattern matching
```

### File: `batch_c3d_export.py`

#### Change 1: EMG Pattern Simplification (Lines 897-910)
```python
# Now uses simple "emg" pattern instead of full channel names
emg_patterns = ["emg"]
exportC3D.export_emg(str(c3d_file), emg_strings_list=emg_patterns)
```

#### Change 2: Analog CSV Copying (Lines 911-920)
```python
# Correctly copies from source directory
if analog_file.exists():
    shutil.copy(str(analog_file), str(output_folder / "analog.csv"))
```

#### Change 3: Reader Iteration Fix (Lines 961, 1025)
```python
# Use read_frames() instead of direct iteration
for frame_num, point_data, analog_data in reader.read_frames():
```

## Testing Checklist

### ✓ Test 1: EMG Export Success
1. Run batch export with EMG channels selected
2. Check terminal for:
   - `[DEBUG] Looking for EMG patterns: ['emg']`
   - `[DEBUG] Available analog labels: [...]`
   - Multiple `Found EMG channel: '...' at index X` messages
   - `[OK] EMG exported (...KB)`

### ✓ Test 2: Analog CSV Has Data
1. Check exported `analog.csv` file size - should be > 100 KB (not empty)
2. Terminal should show:
   - `[OK] Using analog.csv from export_emg (XXX.XX KB)` OR
   - `[OK] Generated fallback analog.csv (XXXX frames)`

### ✓ Test 3: Events CSV Created
1. Check for `events.csv` in output folder
2. Should contain Start and End timing lines
3. Terminal: `[OK] Created events.csv (0.000 - X.XXX seconds)`

### ✓ Test 4: All Output Files Present
Terminal should show:
```
[INFO] Files in output folder:
  - sprint_1.c3d (353.45 KB)
  - marker_experimental.trc (223.84 KB)
  - grf.mot (62.05 KB)
  - emg.mot (XX.XX KB)          ← Should exist now
  - emg_filtered.mot (XX.XX KB) ← Should exist now
  - analog.csv (125.XX KB)       ← Should exist now  
  - trial_settings.xml (0.31 KB)
  - events.csv (0.05 KB)         ← Should exist now
```

## Expected Console Output

```
[INFO] Batch Export Settings
  Left foot markers (3): ['LANK', 'LHEE', 'LTOE']
  Right foot markers (3): ['RANK', 'RHEE', 'RTOE']
  EMG channels (10): ['Voltage.EMG01_r_gastro', 'Voltage.EMG02_r_soleus', ...]

================================================================================
[START] Exporting sprint_1.c3d to sprint_1
================================================================================
[OK] Copied C3D file to sprint_1/
[INFO] Exporting markers...
[OK] Markers exported
[INFO] Exporting GRF data...
[OK] GRF exported

[INFO] Exporting EMG channels: ['Voltage.EMG01_r_gastro', ...]
[DEBUG] Calling export_emg with pattern: ['emg']
[DEBUG] Looking for EMG patterns: ['emg']
[DEBUG] Available analog labels: ['Voltage.EMG01_r_gastro', 'Voltage.EMG02_r_soleus', ...]
Found EMG channel: 'Voltage.EMG01_r_gastro' at index 10
Found EMG channel: 'Voltage.EMG02_r_soleus' at index 11
Found EMG channel: 'Voltage.EMG03_r_rect_fem' at index 12
... (more channels)
[OK] Copied analog.csv from export_emg (125.80 KB)
[OK] EMG exported (10 channels)
[OK] Generated emg_filtered.mot
[OK] Using analog.csv from export_emg

[INFO] Creating trial_settings.xml...
[OK] Created trial_settings.xml

[INFO] Creating events.csv...
[OK] Created events.csv (0.000 - 2.456 seconds)

[INFO] Files in output folder:
  - sprint_1.c3d (353.45 KB)
  - marker_experimental.trc (223.84 KB)
  - grf.mot (62.05 KB)
  - emg.mot (28.40 KB)
  - emg_filtered.mot (28.40 KB)
  - analog.csv (125.80 KB)
  - trial_settings.xml (0.31 KB)
  - events.csv (0.05 KB)

[SUCCESS] Export completed for sprint_1.c3d
================================================================================
```

## Troubleshooting

### Issue: Still no EMG exported
- Check: Are EMG channels being selected in the UI?
- Check: Terminal shows `Found EMG channel:` messages?
- If not found: Export is working but C3D file might not have EMG channels

### Issue: Analog.csv is empty or missing
- Check: `[OK] Copied analog.csv` message in terminal
- If missing: Check that `export_emg()` completed successfully
- Size should be > 100 KB, not 0 KB

### Issue: Events.csv not created
- Check: `[OK] Created events.csv` message in terminal
- Verify C3D file is readable and has frame data

## Files Modified

1. **C:\Git\powerlifing_model_clean\code\tests\app\utils\exportC3D.py**
   - Fixed EMG export bug
   - Added debug logging

2. **C:\Git\powerlifing_model_clean\code\tests\app\gui\widgets\batch_c3d_export.py**
   - Fixed Reader iteration
   - Fixed EMG pattern matching  
   - Fixed analog.csv copying
   - Fixed events.csv creation

## Key Insights

1. **Pattern vs Channel Names**: exportC3D expects search patterns (like "emg"), not full channel names
2. **File Locations**: exportC3D creates files in source directory, batch must copy to output
3. **Reader API**: Must use `read_frames()` for iteration, not direct iteration
4. **Error Handling**: Must define variables before using them in conditional blocks
