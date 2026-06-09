# OpenSim C3D Loading - API Fixes

## Issues Found & Fixed

### Issue 1: Time Column Access ❌ → ✅

**Error:** `'tuple' object has no attribute 'size'`

**Problem:** 
```python
# OLD - incorrect
time = forces_table.getIndependentColumn()
time_array = np.array([time.get(i) for i in range(time.size())])
```

The `getIndependentColumn()` returns a proper iterable object that can be directly converted to a numpy array.

**Fix:**
```python
# NEW - correct
time_column = forces_table.getIndependentColumn()
time_array = np.array(list(time_column))
```

---

### Issue 2: Data Matrix Access ❌ → ✅

**Error:** `'TimeSeriesTableVec3' object has no attribute 'get'`

**Problem:**
The flattened table doesn't support `.get(i, j)` directly on the original table object.

**Fix:**
```python
# Extract data row-by-row using proper OpenSim API
grf_array = []
for i in range(forces_table_flat.getNumRows()):
    row = []
    for j in range(forces_table_flat.getNumColumns()):
        row.append(forces_table_flat.get(i, j))
    grf_array.append(row)

grf_array = np.array(grf_array)
```

---

### Issue 3: Data Rotation ❌ → ✅

**Error:** `'TimeSeriesTableVec3' object has no attribute 'get'` (in rotation function)

**Problem:**
Trying to modify the table in-place with `.set()` method doesn't work as expected. Better to apply rotation to extracted numpy array.

**Solution:**
Moved rotation to work on numpy arrays instead of OpenSim table objects:

```python
def _rotate_data_array(self, data_array, axis='x', degrees=180):
    """Rotate force/moment data using numpy."""
    # Create rotation matrix
    # Apply to data in groups of 3 (Fx, Fy, Fz for each force plate)
    rotated_array = data_array.copy()
    for col_start in range(0, data_array.shape[1], 3):
        if col_start + 3 <= data_array.shape[1]:
            vec_data = data_array[:, col_start:col_start+3]
            rotated_vec = vec_data @ rotation_matrix.T
            rotated_array[:, col_start:col_start+3] = rotated_vec
    return rotated_array
```

---

## Data Flow (Corrected)

```
C3D File
    ↓
OpenSim C3DFileAdapter.read()
    ↓
Get Forces Table (TimeSeriesTableVec3)
    ↓
Convert time: list(getIndependentColumn()) → numpy array
    ↓
Flatten to get x, y, z components
    ↓
Extract all data rows: loop getNumRows/getNumColumns
    ↓
Convert to numpy array
    ↓
Apply rotation on numpy array
    ↓
Transform labels (f1x → ground_force_1_vx)
    ↓
Create Pandas DataFrame
    ↓
Extract GRF channels and populate UI
```

---

## Key OpenSim API Insights

### Correct Patterns

**Get time column:**
```python
time = forces_table.getIndependentColumn()
time_array = np.array(list(time))  # Directly convert to numpy
```

**Get table dimensions:**
```python
num_rows = forces_table.getNumRows()
num_cols = forces_table.getNumColumns()
```

**Access single element:**
```python
value = forces_table.get(row, col)  # Returns float
```

**Get all labels:**
```python
labels = list(forces_table.getColumnLabels())
```

**Iterate over data:**
```python
for i in range(forces_table.getNumRows()):
    for j in range(forces_table.getNumColumns()):
        value = forces_table.get(i, j)
```

### What DOESN'T Work

❌ `forces_table.get(i, j)` on original (non-flattened) table  
❌ `time.get(i)` and `time.size()` - time is iterable, not a container object  
❌ Direct modification with `.set()` - doesn't persist as expected  
❌ Rotation via table modification - better done on numpy arrays

---

## Updated Code Quality

All three files now compile successfully:
```
✓ c3d_grf_viewer.py       (427 lines) - Fixed OpenSim API usage
✓ c3d_export.py           (515 lines) - Working as before
✓ results_viewer.py       (187 lines) - No changes needed
```

---

## Testing Recommendations

1. **Load C3D file again** - should now properly extract GRF channels
2. **Check console output:**
   - `[INFO] Loading C3D file with OpenSim: filename.c3d`
   - `[OK] Loaded GRF data: X channels, Y frames`
3. **Verify channels appear** in the GRF Channels list
4. **Check data accuracy** by comparing rotation against original C3D viewer

---

## Summary

The OpenSim implementation now correctly uses the C3DFileAdapter API:
- Time column extracted as numpy array
- Data accessed via proper iteration methods
- Rotation applied post-extraction on numpy arrays
- Clean DataFrame creation with transformed labels

Application is ready for testing.

---

*Fixed: 2026-05-13*  
*Status: ✅ All API calls corrected*
