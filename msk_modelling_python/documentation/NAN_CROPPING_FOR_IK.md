# NaN Cropping Feature for IK Stability (May 22, 2026)

## Problem

Motion capture data files (TRC, MOT, STO) often contain NaN (Not-a-Number) values at the beginning and end of recordings. These occur when:
- Motion capture system is warming up
- Markers are being set up
- Motion capture system is shutting down
- Markers go out of view temporarily

These invalid values cause the Inverse Kinematics (IK) solver to fail with errors like:
```
InverseKinematicsTool Failed: AssemblySolver::assemble() Failed
Error: calcGoal() method returned a negative or non-finite value -nan(ind)
```

## Solution

Added a `crop_nans()` function to `utils/exportC3D.py` that automatically removes rows with excessive NaN values from the beginning and end of data files.

### How It Works

```python
def crop_nans(filepath, nan_threshold=0.1):
    """
    Crop NaN values from TRC/MOT/STO files.
    
    - Loads the data file
    - Calculates NaN fraction for each row
    - Finds first/last rows with ≤10% NaN values
    - Removes earlier and later rows
    - Saves cleaned data back to file
    """
```

**Parameters:**
- `filepath`: Path to TRC, MOT, or STO file
- `nan_threshold`: Maximum allowed NaN fraction (default 0.1 = 10%)
  - Only rows where >10% of columns are NaN are removed
  - Rows with valid data in ≥90% of columns are kept

### File Format Support

- ✅ **TRC files** (.trc) - Marker trajectory data
- ✅ **MOT files** (.mot) - General motion data (forces, joint angles, etc.)
- ✅ **STO files** (.sto) - Storage files (similar to MOT)

### Example Output

```
Cropped /path/to/marker_experimental.trc:
  Removed 45 rows from beginning
  Removed 12 rows from end
  Kept 1174 rows (original: 1231)
  Saved cropped data to /path/to/marker_experimental.trc
```

---

## Usage

### Manual Cropping

```python
from utils.exportC3D import crop_nans

# Crop a TRC file
crop_nans('/path/to/markers.trc')

# Crop with custom threshold (allow up to 20% NaN)
crop_nans('/path/to/markers.trc', nan_threshold=0.2)

# Crop MOT file (GRF data)
crop_nans('/path/to/grf.mot')
```

### Integration with Analysis Pipeline

Add to your analysis setup code to automatically clean data before IK:

```python
from utils.exportC3D import crop_nans

# Clean marker data
crop_nans('markers.trc')

# Clean GRF data
crop_nans('grf.mot')

# Now run IK with clean data
```

### From Export Process

When exporting C3D files to OpenSim format:

```python
# After creating TRC and MOT files
create_trc_and_grf_from_c3d('data.c3d', 'markers.trc', 'grf.mot')

# Automatically crop NaN values
crop_nans('markers.trc')
crop_nans('grf.mot')
```

---

## Technical Details

### NaN Detection Logic

For each row in the data:
1. Count columns with NaN values (excluding time column)
2. Calculate fraction: `nan_count / total_data_columns`
3. Keep row if fraction ≤ `nan_threshold`

**Example:**
- Row has 61 data columns (markers × 3 coordinates)
- Row has 5 columns with NaN values
- NaN fraction = 5/61 = 0.082 (8.2%)
- With threshold 0.1 (10%), this row is KEPT ✅

**Example:**
- Row has 61 data columns
- Row has 12 columns with NaN values
- NaN fraction = 12/61 = 0.197 (19.7%)
- With threshold 0.1 (10%), this row is CROPPED ❌

### Threshold Guidance

| Threshold | Use Case |
|-----------|----------|
| 0.05 (5%) | Very strict - only perfect data rows |
| 0.10 (10%) | **Recommended** - removes most invalid data |
| 0.20 (20%) | Lenient - keeps some marker dropouts |
| 0.30 (30%) | Very lenient - keeps almost everything |

**Recommended: 0.1 (10%)**

---

## Why This Fixes IK Errors

The IK solver uses marker positions to determine joint angles. When markers are NaN (invalid):

1. **Solver can't match markers** - Missing data prevents proper convergence
2. **Negative/infinite values** - Mathematical operations on NaN produce -nan(ind)
3. **Assembly fails** - The optimization problem has no valid solution

By removing rows with too many NaN values:
- ✅ Solver has complete marker data to work with
- ✅ Assembly can properly converge
- ✅ Joint angles are calculated from valid data
- ✅ No more -nan(ind) errors

---

## Implementation in exportC3D.py

**New Functions Added:**

1. **`crop_nans(filepath, nan_threshold=0.1)`**
   - Main function that crops NaN rows
   - Handles all file formats (TRC, MOT, STO)
   - Returns (start_idx, end_idx) of kept rows

2. **`_write_trc_file(filepath, data)`**
   - Helper to write TRC files with proper header
   - Preserves original TRC format

3. **`_write_sto_file(filepath, data, labels)`**
   - Helper to write STO files
   - Uses OpenSim format with headers

---

## Example Workflow

```python
from utils.exportC3D import crop_nans
from utils import Analyse

# 1. Export C3D to OpenSim format
# (This would normally happen in your export process)

# 2. Clean up data files
print("Cleaning up motion capture data...")
crop_nans('trial/markers.trc')      # Remove NaN marker rows
crop_nans('trial/grf.mot')           # Remove NaN force rows

# 3. Run analysis with clean data
trial = Analyse('trial/')
trial.run_ik()                       # IK should now work!
trial.run_id()                       # ID should also work
```

---

## When This Helps

✅ **Solves IK errors caused by:**
- NaN values at recording start
- Missing markers at recording end
- Marker dropout periods with >10% invalid data

⚠️ **May not solve:**
- Missing markers during the middle of the trial
- Systematic tracking errors
- Incorrect marker labeling

---

## Notes

- The function preserves all non-NaN data
- Original files are **overwritten** with cropped versions
- If you need the original files, back them up first
- The threshold (10%) is conservative and shouldn't remove valid data
- Time column is always preserved (never considered for NaN cropping)

---

## Future Enhancements

Potential improvements:
- Option to create backup files before cropping
- Interpolation for small NaN gaps in the middle of data
- Separate thresholds for different file types
- Progress reporting for batch processing

---

*Last Updated: May 22, 2026*
*Status: IMPLEMENTED & READY*
