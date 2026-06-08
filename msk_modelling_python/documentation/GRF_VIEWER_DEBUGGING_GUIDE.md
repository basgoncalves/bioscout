# GRF Viewer Debugging and Testing Guide

**Status:** Enhanced C3D GRF Viewer with Improved Error Handling and Debugging

**Date:** 2026-05-13

---

## Changes Made

### 1. **Improved Analog Label Extraction** (c3d_grf_viewer.py)

#### Problem Identified
The original code tried to access `reader.analog_labels` directly, but this attribute might not exist or be structured differently depending on the c3d library version.

#### Fix Applied
Added multiple fallback methods to extract analog labels:

```python
# Method 1: Try reader.analog_labels
if hasattr(reader, 'analog_labels'):
    self._analog_labels = list(reader.analog_labels)

# Method 2: Try reader.header.analog_labels
if not self._analog_labels and hasattr(reader, 'header'):
    header = reader.header
    if hasattr(header, 'analog_labels'):
        self._analog_labels = list(header.analog_labels)
    elif hasattr(header, 'analog_channel_labels'):
        self._analog_labels = list(header.analog_channel_labels)
```

**Expected Result:** GRF channels should now be detected even if labels are stored in different locations.

---

### 2. **Enhanced Channel Detection Logic** (c3d_grf_viewer.py)

#### Improvements
- **Data Structure Validation:** Verify C3D data has 3 elements (header, points, analog)
- **Padding for Missing Labels:** If there are more analog channels than labels, pad with generic names
- **Extended Pattern Matching:** Added more GRF patterns: `'Foot', 'Plate', 'GRF', 'Force_', 'Vx', 'Vy', 'Vz'`
- **Better Error Handling:** Try-except blocks for individual channel extraction
- **Comprehensive Logging:** Debug messages for each step of channel detection

#### Channel Detection Flow
```
1. Check data structure: len(self.c3d_data) >= 3
   └─> If invalid, log warning and return

2. Extract analog data: self.c3d_data[2]
   └─> Get shape: (num_channels, num_frames)

3. Get labels: Try 3 different methods
   └─> Pad with generic names if needed

4. Pattern matching: Check each channel name against GRF patterns
   └─> Build grf_channels dict with detected channels

5. Log results: Total GRF channels found
   └─> Show each detected channel
```

---

### 3. **Better User Feedback** (c3d_grf_viewer.py)

#### Changes
- Show "No GRF channels detected" message when checkboxes are empty
- Count selected channels before plotting
- Early return if no channels are selected
- Debug logging at each step

---

### 4. **Improved C3D Loading Feedback** (c3d_export.py)

#### Enhancements
- Multiple fallback methods for getting analog labels
- Detailed debug logging for each step
- Better error messages with full traceback
- Status feedback showing number of markers and EMG channels found

---

## How to Test the Fixes

### Test Case 1: Load a C3D File with GRF Data

**Steps:**
1. Open the C3D Export tab in the GUI
2. Click "Browse C3D File"
3. Select any C3D file from your project (e.g., `/models/tps/motion_lab/Static_01/c3dfile.c3d`)
4. Observe the GRF viewer panel

**Expected Behavior:**
- Status bar shows: `[OK] Loaded: X markers, Y EMG channels`
- GRF viewer shows: Checkboxes for all detected GRF channels (Force, Moment, etc.)
- Plot shows: Multi-panel visualization of selected GRF channels
- Slider and input fields work: Can crop trial range

**What to Look For in Logs:**
```
DEBUG: Analog data shape: (N, M)
DEBUG: Number of analog labels: K
DEBUG: Found GRF channel [i]: Channel_Name
INFO: Total GRF channels found: X
DEBUG: Populated X channel checkboxes
```

---

### Test Case 2: Verify GRF Channel Detection

**Steps:**
1. Load a C3D file
2. Check the debug output for channel detection messages
3. Verify checkbox list shows GRF channels

**Expected Logs:**
```
DEBUG: Loading C3D file: /path/to/file.c3d
DEBUG: Analog data shape: (24, 2000)
DEBUG: Number of analog labels: 24
DEBUG: Scanning 24 channels for GRF patterns
DEBUG: Found GRF channel [0]: Force_Platform_1_Fx
DEBUG: Found GRF channel [1]: Force_Platform_1_Fy
DEBUG: Found GRF channel [2]: Force_Platform_1_Fz
DEBUG: Found GRF channel [3]: Force_Platform_1_Mx
...
INFO: Total GRF channels found: 8
```

---

### Test Case 3: Channel Selection and Plotting

**Steps:**
1. Load a C3D file with GRF data
2. Check the "Select All" button
3. Observe the plot updates
4. Uncheck individual channels
5. Observe plot refreshes with fewer subplots

**Expected Behavior:**
- Plot shows multiple subplots (up to 3 columns)
- Each subplot shows: Channel name, X-axis (Frame), Y-axis (Value)
- Grid overlay present
- Plot updates instantly when toggling checkboxes

---

### Test Case 4: Trial Cropping

**Steps:**
1. Load a C3D file
2. Move the crop slider left/right
3. Check that time range updates
4. Enter specific percentages in Start/End fields
5. Press Enter to apply

**Expected Behavior:**
- Slider moves smoothly
- Time range updates (e.g., "0.20 - 0.80 s")
- Input fields update when slider moves
- Plot zooms to selected range
- Crop range persists through channel toggles

---

### Test Case 5: Error Handling

**Test 5a: C3D file with no GRF channels**
```
Expected: "No GRF channels detected" message in checkbox area
Logs: "INFO: Total GRF channels found: 0"
```

**Test 5b: Invalid C3D file**
```
Expected: Error message in status bar
Logs: "ERROR: Error loading C3D file: [error details]"
```

---

## What the Improved Code Does

### Analog Label Extraction Logic

```python
def load_c3d(self, c3d_file_path: str) -> bool:
    """
    1. Opens C3D file with c3d.Reader
    2. Reads data: (header, points, analog) = reader.read()
    3. Extracts analog_labels via 3-step fallback:
       - reader.analog_labels (direct)
       - reader.header.analog_labels (from header)
       - reader.header.analog_channel_labels (alternate name)
    4. Stores in self._analog_labels for use in _extract_grf_channels
    5. Calls _extract_grf_channels() to find GRF channels
    """
```

### GRF Channel Detection Logic

```python
def _extract_grf_channels(self) -> None:
    """
    1. Validates C3D data structure (must have 3 elements)
    2. Gets analog data from self.c3d_data[2] (numpy array)
    3. Gets labels from self._analog_labels
    4. Pads labels if count < analog channel count
    5. Scans each channel against GRF patterns:
       ['Force', 'Moment', 'Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz',
        'fx', 'fy', 'fz', 'mx', 'my', 'mz',
        'Foot', 'Plate', 'GRF', 'Force_', 'Vx', 'Vy', 'Vz']
    6. Stores matching channels in self.grf_channels dict:
       {
         'Channel_Name': {
           'index': 0,
           'data': numpy_array[i, :].copy()
         },
         ...
       }
    7. Logs each detected channel with debug level
    8. Logs final count with info level
    """
```

---

## Troubleshooting Guide

### Problem: "No GRF channels detected"

**Step 1: Check if C3D file has analog data**
- Open C3D file in Mokka
- Look for "Analog Data" or "Force Plates" section
- Verify analog channels exist

**Step 2: Check analog channel labels**
- In Mokka, right-click on analog data
- Check "Channel Names" or "Labels"
- Note the exact label format (e.g., "Force_Platform_1_Fx")

**Step 3: Add custom patterns if needed**
- If your C3D uses non-standard naming (e.g., "FX", "FY", "FZ"):
- Edit the grf_patterns list in `_extract_grf_channels()`
- Add your custom patterns to the list

**Step 4: Enable debug logging**
- Set logger level to DEBUG
- Look for "Scanning X channels for GRF patterns"
- Verify all channel labels are being read

**Step 5: Check if labels are being extracted**
- Look for log: "Found X analog labels in reader"
- If 0 labels found, the fallback methods aren't working
- This suggests a different c3d library version

---

### Problem: Plot doesn't update when I toggle channels

**Possible Cause:** BooleanVar references not updated
- Solution: Ensure self.selected_grfs stores BooleanVar objects, not bool values

**Possible Cause:** No channels selected
- Solution: Check "Select All" button to select all channels

**Possible Cause:** Channel data not properly copied
- Solution: Ensure data is copied with `.copy()` when storing

---

### Problem: Crop slider not working

**Possible Cause:** Slider range not set correctly
- Check: `from_=0, to=100`
- Should allow full 0-100% range

**Possible Cause:** Crop indices calculated incorrectly
- Formula: `crop_start_idx = int(start_% / 100 * total_samples)`
- Verify: Indices are within valid range [0, total_samples]

---

## Logging Output Reference

### Successful Load (Debug Level)
```
DEBUG: Loading C3D file: /path/to/file.c3d
DEBUG: Got 24 labels from reader.analog_labels
DEBUG: Total analog labels extracted: 24
DEBUG: Analog data shape: (24, 2000)
DEBUG: Number of analog labels: 24
DEBUG: Scanning 24 channels for GRF patterns
DEBUG: Found GRF channel [0]: Force_Platform_1_Fx
DEBUG: Found GRF channel [1]: Force_Platform_1_Fy
...
INFO: Total GRF channels found: 12
DEBUG: Populated 12 channel checkboxes
```

### Issues to Look For
```
WARNING: Invalid C3D data structure: N elements
  └─> Means reader.read() didn't return tuple of 3 items

WARNING: Got 0 labels from reader.analog_labels
  └─> Analog label extraction failed, check fallback methods

WARNING: Padding N channels with generic names
  └─> More analog channels than labels

ERROR: Error extracting GRF channels: [error]
  └─> Exception during channel extraction, see traceback
```

---

## Next Steps for Testing

1. **Load the updated GUI application**
   - Run the main application
   - Navigate to C3D Export tab

2. **Test with your C3D files**
   - Start with `Static_01/c3dfile.c3d`
   - Try other trial C3D files
   - Test with different capture systems

3. **Monitor the logs**
   - Open the terminal/console view
   - Watch for debug messages during loading
   - Note any warnings or errors

4. **Test the workflow**
   - Load C3D → Select channels → Crop trial → Export
   - Verify exported files have correct format
   - Compare with Mokka reference if available

5. **Report Issues**
   - Include full debug log output
   - Specify which C3D file causes problems
   - Note the exact error message

---

## Files Modified

1. **c3d_grf_viewer.py**
   - Enhanced `load_c3d()` with 3-method fallback for labels
   - Improved `_extract_grf_channels()` with validation and padding
   - Added user feedback message when no channels detected
   - Added comprehensive debug logging

2. **c3d_export.py**
   - Enhanced `_load_c3d_data()` with fallback label extraction
   - Better error handling with full traceback
   - Status messages showing what was loaded

3. **analysis_control_session.py**
   - No changes to GRF viewer, pre-existing fixes applied

4. **openSim.py**
   - No changes to GRF viewer, pre-existing export functions

---

## Summary

The updated GRF viewer should now:

✓ Automatically detect analog labels from multiple locations
✓ Handle different c3d library versions gracefully
✓ Provide clear error messages when issues occur
✓ Log detailed debugging information for troubleshooting
✓ Display user-friendly messages when no channels are found
✓ Support extended GRF pattern matching for more channel types
✓ Properly handle trial cropping with percentage-based range
✓ Update plots instantly when channels are toggled

All critical files compile successfully and are ready for testing.
