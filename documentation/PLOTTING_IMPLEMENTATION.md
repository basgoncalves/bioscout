# IK and ID Plotting Implementation

## Overview

Added automatic plotting of IK (Inverse Kinematics) and ID (Inverse Dynamics) results in the batch pipeline. After each trial is processed, results are automatically visualized and saved as PNG files.

## What Gets Plotted

### After IK (STEP 3)
- **File**: `joint_angles.mot`
- **Title**: "Inverse Kinematics - Joint Angles"
- **Y-axis**: Angle (degrees)
- **Output**: `joint_angles.png` in trial results folder

Each subplot shows one joint angle over time:
- Pelvis angles (tilt, list, rotation)
- Hip angles (flexion, adduction, rotation)
- Knee angles (flexion, adduction)
- Ankle angles (flexion)
- All degrees of freedom in the model

### After ID (STEP 4)
- **File**: `inverse_dynamics.sto`
- **Title**: "Inverse Dynamics - Joint Moments"
- **Y-axis**: Moment (N·m)
- **Output**: `inverse_dynamics.png` in trial results folder

Each subplot shows joint moments over time:
- Joint moment at each degree of freedom
- Calculated from motion (kinematics) and forces (ground reaction forces)

## File Organization

Results are saved in the trial results folder:

```
{results_folder}/{trial_name}/
├── joint_angles.mot          ← IK output
├── joint_angles.png          ← IK plot (NEW)
├── inverse_dynamics.sto      ← ID output
└── inverse_dynamics.png      ← ID plot (NEW)
```

## Plotting Function

New function in `__main__.py`:

```python
def plot_motion_results(trial_name, data_file, title, ylabel, results_dir, logger):
    """
    Plot motion analysis results (IK joint angles or ID joint moments).
    
    Features:
    - Automatically adjusts number of subplots based on data columns
    - Creates 3 columns × N rows of subplots
    - Includes gridlines and legends
    - Saves at 150 DPI for publication quality
    - Uses matplotlib for consistent styling
    """
```

## Technical Details

### Plot Layout
- **Columns**: 3 columns per row (configurable)
- **Grid**: 3-column × N-row layout automatically calculated
- **Resolution**: 150 DPI (good for presentations and reports)
- **Size**: 15 inches wide × 4 inches per row

### Plot Features
- Each subplot has:
  - Title (joint/DOF name)
  - X-axis: Time (seconds)
  - Y-axis: Angle (degrees) or Moment (N·m)
  - Grid lines (alpha=0.3 for subtle visualization)
  - Legend with trial name
  - Bold, 11pt font for readability

### Error Handling
- If data file doesn't exist: logs warning and skips plotting
- If no data columns found: logs warning
- If plotting fails: logs warning but continues pipeline
- Pipeline execution is **not blocked** by plotting failures

## Integration with Pipeline

Plotting is **automatically triggered** after each trial:

```
IK Run → [Check Success] → Plot IK Results → Continue
ID Run → [Check Success] → Plot ID Results → Continue
```

Both steps happen automatically—no configuration needed.

## Logging

All plotting results are logged:

```
[OK] Plot saved: /path/to/joint_angles.png
[OK] Plot saved: /path/to/inverse_dynamics.png
```

Errors are logged as warnings and don't stop the pipeline:

```
[WARNING] Could not plot results for trial_name: error details
```

## Customization

To modify plotting behavior, edit `plot_motion_results()` in `__main__.py`:

```python
# Modify number of columns per row
n_cols = 3  # Change to 2, 4, etc.

# Modify figure size
fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4*n_rows))

# Modify DPI (higher = larger file size, better quality)
plt.savefig(plot_file, dpi=150, bbox_inches='tight')

# Modify grid style
ax.grid(True, alpha=0.3)  # Change alpha for more/less visible grid
```

## Example Output

For a trial with 15 degrees of freedom:
- IK plot: 5 rows × 3 columns = 15 subplots (one per DOF)
- All 15 joint angles displayed on single figure

For a trial with 12 degrees of freedom:
- ID plot: 4 rows × 3 columns = 12 subplots
- All 12 joint moments displayed on single figure

## Advantages

✓ **Automatic**: No manual plotting required
✓ **Quick QA**: Visual verification of results
✓ **Publication-ready**: High DPI, professional styling
✓ **Non-blocking**: Plotting failures don't stop pipeline
✓ **Flexible**: Easy to customize for your needs
✓ **Integrated**: Seamless integration with batch pipeline

## Troubleshooting

### Plots not being saved
- Check that matplotlib is installed: `pip install matplotlib`
- Verify write permissions in trial results folder
- Check log file for error messages

### Plots look wrong
- Verify data file contains valid time column
- Check that data columns exist (exclude 'time')
- Ensure Y-axis label is correct for your data type

### Memory issues with large trials
- Reduce figure size: `figsize=(12, 3*n_rows)`
- Reduce DPI: `dpi=100`
- Plot fewer DOFs at a time

## Related Code

- `Analyse.plot_ik()` - Class-based IK plotting (for GUI)
- `Analyse.plot_id()` - Class-based ID plotting (for GUI)
- `Analyse.plot_create_subplot()` - Subplot creation utility
- `plot_motion_results()` - Batch pipeline plotting (NEW)
