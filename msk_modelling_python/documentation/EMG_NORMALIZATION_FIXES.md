# EMG Normalization Tab - Fixes & Updates

## Issues Fixed

### 1. ✅ Removed Duplicate Console Output
**Problem**: EMG Normalization tab had its own console textbox separate from the unified console at the bottom
**Solution**: Removed the local console (lines 173-189) and now uses status_callback to send all messages to the unified console

### 2. ✅ Split Trial Selection into Two Sections
**Before**:
- Single "Select Trials" section with all trials mixed together

**After**:
- **"Trials for Max Calculation"** - trials used to determine the normalization factor (max value)
- **"Trials to Normalize"** - trials to which the calculated max is applied

**UI Changes**:
- Each section has its own scrollable frame
- Each section has All/None buttons
- Independent checkbox variables: `ref_trial_vars` and `norm_trial_vars`

### 3. ✅ Updated Normalization Algorithm
**New Two-Step Process**:

**Step 1: Calculate Max from Reference Trials**
```python
for trial in reference_trials:
    load EMG data
    if method == "Max":
        calculate max of absolute values
    elif method == "WindowAverage":
        calculate max of window average envelope
    keep overall maximum across all reference trials
```

**Step 2: Apply Max to Normalization Trials**
```python
for trial in normalization_trials:
    load EMG data
    normalized_data = emg_data / calculated_max
    save to emg_filtered_normalised.mot
```

### 4. ✅ Fixed File Saving Error
**Problem**: 
```
ERROR: Error saving MOT file: [Errno 2] No such file or directory
```

**Root Cause**: `_save_mot_file()` was trying to read the output file (which doesn't exist yet) to copy its header

**Solution**:
- Changed method signature: `_save_mot_file(input_file, output_file, data)`
- Now reads header from the original input file
- Writes normalized data to the new output file
- Ensures output directory exists with `mkdir(parents=True, exist_ok=True)`
- Uses `str()` to convert Path objects for file operations

### 5. ✅ Moved Apply Normalization Button
**Before**: Button at row 2 (too high, overlapped with window time input)
**After**: Button at row 3 with more padding (20px top, 15px bottom) - appears lower and more spacious

### 6. ✅ Unified Console Output
- Removed local `console_text` textbox
- All messages now go through `status_callback()` to the unified console at bottom
- Cleaner, consistent logging across all tabs
- Uses color-coded message types (info, success, warning, error)

## Code Changes

### Method Updates
```python
def _normalize_in_thread(ref_trials, norm_trials, norm_method, window_ms=None):
    # Step 1: Calculate max from reference trials
    # Step 2: Apply to normalization trials
    # Uses consistent status_callback for all output
```

```python
def _save_mot_file(input_file, output_file, data):
    # Now accepts both input and output file paths
    # Creates output directory if needed
    # Properly handles Path objects
```

### New Helper Method
```python
def _get_window_average_envelope(data, window_ms):
    # Calculates moving average envelope for a dataset
    # Used for both max calculation and normalization
```

## User Experience Improvements

1. **Clearer Intent**: Explicitly choose which trials define the max vs which get normalized
2. **Better Logging**: All output goes to unified console
3. **More Robust**: Handles file paths correctly, creates directories as needed
4. **Better Status**: Clear step-by-step feedback (STEP 1, STEP 2)
5. **Flexible Normalization**: Can use different trials for reference and application

## Testing

To verify the fixes:
1. Load a session with EMG data
2. Select different trials for max calculation vs normalization
3. Choose Max method and apply - should complete without file errors
4. Check that `emg_filtered_normalised.mot` is created in each trial folder
5. Verify all output appears in the unified console at bottom
6. Check that trial_settings.xml is updated with `<emg>emg_filtered_normalised.mot</emg>`

## Files Modified
- `gui/widgets/emg_normalization.py` - Complete restructuring for two-section layout, two-step algorithm, and unified console output
