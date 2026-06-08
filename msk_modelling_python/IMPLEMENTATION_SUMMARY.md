# Musculoskeletal Modelling Pipeline - Y-Coordinate Force Plate Assignment Fix

## Summary of Changes

### 1. **Fixed Force Plate Assignment Logic** (Primary Issue)
- **File**: `utils/openSim.py`, function `create_grf_xml()` (lines 1971-2569)
- **Problem**: Force plates were being assigned incorrectly to left/right feet
- **Solution**: Implemented Y-coordinate distance-based assignment

**How it works:**
1. Reads force plate Center of Pressure (CoP) Y positions from GRF MOT file
2. Extracts foot marker Y positions from TRC marker file
3. Calculates Y-distance: `distance = |cop_y - foot_marker_y|`
4. Assigns force plate to the closer foot based on Y-distance only
5. Y-coordinate represents the walking direction axis (anterior-posterior)

**Key code section** (lines 2151-2244):
```python
# Second pass: assign plates based on CoP Y position
# Use Y coordinate (walking direction) to find closest foot
if cop_data_by_plate:
    # Calculate mean foot marker Y positions from TRC data if available
    r_foot_y = None
    l_foot_y = None
    
    # ... extract Y positions from TRC file ...
    
    # Assign plates to feet based on Y position distance
    for plate_num, cop in sorted(cop_data_by_plate.items()):
        cop_y = cop.get('y', 0)
        
        if r_foot_y is not None and l_foot_y is not None:
            # Calculate distance along Y axis
            r_dist = abs(cop_y - r_foot_y)
            l_dist = abs(cop_y - l_foot_y)
            
            if r_dist < l_dist:
                plate_to_body[plate_num] = right_foot_body
            else:
                plate_to_body[plate_num] = left_foot_body
```

### 2. **Added Missing Utility Functions** (utils/__init__.py)
- Added `load_trc()` - Loads TRC marker files with 4-line header support
- Added `load_sto()` - Loads OpenSim STO storage files
- Both support proper header parsing and data extraction

### 3. **Created Helpers Module** (utils/helpers.py - NEW FILE)
- `setup_logging()` - Configures logging for batch pipeline
- `plot_motion_results()` - Creates plots of IK/ID results from OpenSim output files

### 4. **Fixed File Synchronization Issues**
- Reconstructed `settings.py` (259 lines, was truncated to 68)
- Reconstructed `utils/__init__.py` (160 lines, was incomplete)
- Verified all files have valid Python syntax

## Batch Pipeline Architecture (8 Steps)

The pipeline now supports the complete musculoskeletal analysis workflow:

1. **C3D Export** - Extract markers, GRF, EMG from C3D files
2. **Model Scaling** - Scale generic model to subject anthropometrics
3. **Inverse Kinematics (IK)** - Compute joint angles from marker data
4. **Inverse Dynamics (ID)** - Compute joint moments using GRF data ✓ Y-coordinate assignment active here
5. **Static Optimization (SO)** - Estimate individual muscle forces
6. **Muscle Analysis (MA)** - Compute muscle-specific parameters
7. **CEINMS Calibration** - Calibrate EMG-informed model
8. **CEINMS Execution** - Run full neuromusculoskeletal analysis

## File Structure
```
C:\Git\app\
├── __main__.py              - Batch processing entry point
├── settings.py              - Configuration (BatchSettings, Inputs, UISettings)
├── IMPLEMENTATION_SUMMARY.md - This file
└── utils/
    ├── __init__.py          - Core utilities (load_trc, load_sto, load_any_data_file)
    ├── helpers.py           - Batch helpers (setup_logging, plot_motion_results)
    ├── openSim.py           - OpenSim analysis functions (create_grf_xml with Y-coord logic)
    ├── model_scaler.py      - Model scaling pipeline
    └── (other modules)
```

## Configuration

Edit `settings.py` BatchSettings class to enable/disable pipeline steps:
- `enable_inverse_dynamics = True` (currently enabled for testing)
- `right_foot_markers = ['RTOE', 'RHEE', 'RFMH', 'RSMH', 'RVMH']`
- `left_foot_markers = ['LTOE', 'LHEE', 'LFMH', 'LSMH', 'LVMH']`

## Testing the Y-Coordinate Implementation

The corrected force plate assignment will:
1. Generate a `grf_analysis.png` plot showing CoP vs foot marker positions
2. Log assignments: "Plate N: CoP Y=XXX.X mm -> Dist to R=XXX.X mm, L=XXX.F mm -> [R|L]"
3. Create properly formatted GRF.xml for OpenSim ID step

## Next Steps

1. Run batch pipeline from Windows command prompt:
   ```
   python __main__.py -b settings.py
   ```

2. Verify GRF.xml output in trial directories:
   - Check `Simulations/P012b/<Trial>/GRF.xml` has correct plate assignments
   - Check `Simulations/P012b/<Trial>/grf_analysis.png` shows correct foot assignments

3. Confirm ID step uses correct force plates for each foot in joint moment computation

## Technical Notes

- **Y-Coordinate Axis**: Anterior-posterior direction in walking (walking direction)
- **Force Plate Convention**: Plates 4-5 are standard dual-plate setup
- **TRC Parsing**: Custom 4-line header handling for marker position extraction
- **Fallback Logic**: If Y-positions unavailable, falls back to X-based median assignment
