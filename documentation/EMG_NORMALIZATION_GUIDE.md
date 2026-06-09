# EMG Normalization Tab - User Guide

## Overview
The EMG Normalization tab has been completely simplified and now uses the session-level architecture. It provides a straightforward interface for normalizing EMG data across all trials in a session.

## Key Changes from EMG Processing

### Removed
- ❌ Session selector (uses top-level session selector)
- ❌ EMG file selector (auto-detects from trial folders)
- ❌ Visualization/plotting
- ❌ Complex processing settings
- ❌ Channel selection

### Kept
- ✅ Trial selection
- ✅ Normalization methods (None, Max, RMS)
- ✅ Simple, focused interface
- ✅ Console output for feedback

## How to Use

### 1. Select a Session (Top of App)
```
Session: [your_session_path] [Browse] [Load]
```
- Click "Browse" to select your session folder
- Click "Load" to apply the session to all tabs

### 2. Navigate to EMG Normalization
Click "EMG Normalization" in the sidebar

### 3. Select Trials
- The tab automatically scans for trials with EMG data
- Checkboxes appear for each trial found
- Use "All" and "None" buttons to select/deselect

### 4. Choose Normalization Method
Select one of three options:
- **None**: No normalization (pass-through)
- **Max**: Normalize by maximum value (range: -1 to +1)
- **RMS**: Normalize by RMS value (standardized scale)

### 5. Apply
Click "Apply Normalization" button

### 6. Monitor Progress
- Console output shows which trials are processing
- Status label updates when complete
- Each trial shows [OK], [FAIL], or [ERROR]

## Normalization Methods

### None
- No modification to EMG data
- Useful for just re-saving files in the correct format

### Max (Recommended for Peak-Based Tasks)
```
normalized = original / max(abs(original))
```
- Scales data so peak value = 1.0
- Good for tasks where peak contraction is meaningful
- Useful for movements with obvious peak effort

### RMS (Recommended for General Analysis)
```
normalized = original / sqrt(mean(original²))
```
- Standardizes signal energy
- Good for comparing across trials/subjects
- Better for averaging and statistical analysis
- Less sensitive to outliers

## Output

### Modified Files
- Each trial's `emg.mot` file is updated with normalized data
- Original header and format are preserved
- MOT format remains compatible with OpenSim

### Console Messages
```
[START] Normalizing 3 trials using Max method
[1/3] Processing sprint_1... [OK]
[2/3] Processing static_1... [OK]
[3/3] Processing walking_1... [OK]
[SUCCESS] Normalization completed for 3 trials
```

## File Structure Used

```
/session1/
├── sprint_1/
│   └── emg.mot          ← Normalized data
├── static_1/
│   └── emg.mot          ← Normalized data
└── walking_1/
    └── emg.mot          ← Normalized data
```

## Error Handling

### "No trials with EMG data found"
- Check that trials have been exported with batch C3D export
- Ensure each trial folder has an `emg.mot` file

### "Could not read EMG file"
- Verify the MOT file is not corrupted
- Check file permissions

### "Error during normalization"
- Check console output for specific error
- Verify EMG data contains valid numbers

## Session Integration

The EMG Normalization tab now fully integrates with the session-level architecture:

```
┌─────────────────────────────────────┐
│ Session: [folder] [Browse] [Load]   │  ← Global session selector
├─────────────────────────────────────┤
│ EMG Normalization Tab               │
├─────────────────────────────────────┤
│ Received session from top bar ✓     │
│ Auto-scanned trials: 3              │
│ Ready to normalize                  │
└─────────────────────────────────────┘
```

## Best Practices

1. **Use Max normalization for**:
   - Peak force events
   - Single, clear contractions
   - Specific movement phases

2. **Use RMS normalization for**:
   - Comparing muscle activations
   - Statistical analysis
   - Cross-subject comparisons
   - Research and publication

3. **Use None when**:
   - You just want to organize/re-save files
   - Data is already normalized
   - You need raw amplitudes

## Command-Line Alternative

To normalize EMG data programmatically:

```python
from pathlib import Path
import numpy as np

def normalize_emg(emg_file: Path, method: str = "Max"):
    """Normalize EMG data in MOT file."""
    # Read data
    data = np.loadtxt(emg_file, skiprows=4)  # Skip header
    
    # Apply normalization
    if method == "Max":
        data = data / np.max(np.abs(data), axis=0, keepdims=True)
    elif method == "RMS":
        rms = np.sqrt(np.mean(data**2, axis=0, keepdims=True))
        data = data / rms
    
    # Save back
    np.savetxt(emg_file, data)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No trials appear | Check Batch C3D export completed successfully |
| Normalization runs but no visible change | Check if using "None" method |
| Values look wrong | Try different normalization method |
| File won't save | Check write permissions on trial folders |
| Session not loading | Click "Load" button after selecting folder |

## Summary

The EMG Normalization tab is now:
- ✅ **Simple**: Just select trials and normalize
- ✅ **Session-aware**: Uses top-level session selector
- ✅ **Fast**: No visualization overhead
- ✅ **Reliable**: Console feedback for each step
- ✅ **Integrated**: Works seamlessly with batch export workflow
