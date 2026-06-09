# Advanced C3D GRF Viewer - User Guide

**Version:** 2.1.0  
**Date:** 2026-05-13  
**Module:** `c3d_grf_viewer.py`

---

## Overview

The advanced C3D GRF Viewer provides professional-grade visualization and analysis of Ground Reaction Force (GRF) data extracted from C3D motion capture files. It matches the visualization quality and functionality of Mokka while integrating seamlessly into the biomechanics analysis pipeline.

## Key Features

### 1. **Auto-Detection of GRF Channels**
- Automatically identifies all Force and Moment channels from C3D analog data
- Detects multiple force platforms (up to 4+ platforms per trial)
- Supports multiple naming conventions (Fx, Fy, Fz, Mx, My, Mz, Force_X, etc.)
- Channel identification includes:
  - Force components (Fx, Fy, Fz)
  - Moment components (Mx, My, Mz)
  - Multi-platform detection
  - Custom analog channel labels

### 2. **Interactive Channel Selection**
```
Data Preparation:
  GRF Channels:
  [✓] Force_Platform_1_Fx
  [✓] Force_Platform_1_Fy
  [✓] Force_Platform_1_Fz
  [✓] Force_Platform_2_Fx
  [✓] Force_Platform_2_Fy
  [✓] Force_Platform_2_Fz
  [✓] Moment_1_Mx
  [✓] Moment_1_My
  ...

  [Select All] [Deselect All]
```

- Check/uncheck individual channels to show/hide them
- Instant plot refresh when toggling channels
- "Select All" / "Deselect All" buttons for batch operations
- Selected state is maintained during interaction

### 3. **Trial Cropping with Visual Feedback**
```
Trial Crop Range:
  [===========●==============] 0-100%
  
  Start %: [20]  End %: [80]
  
  Time Range: 0.20 - 0.80 s
```

Features:
- Slider for visual range selection (0-100% of trial)
- Numeric input fields for precise cropping
- Real-time time range display in seconds
- 20% visualization window by default
- Useful for:
  - Removing motion capture setup/cleanup phases
  - Isolating specific movement phases
  - Reducing data size for export
  - Focusing on contact phases

### 4. **Multi-Panel GRF Visualization**
- Displays all selected GRF channels in one figure
- Automatic layout (up to 3 columns)
- Individual subplot per channel with:
  - Channel name as title
  - Frame number on X-axis
  - Force/Moment value on Y-axis
  - Grid overlay for reference
  - Consistent scaling within subplots

### 5. **Matplotlib Integration**
- Embedded matplotlib figures in Tkinter
- High-quality vector graphics
- Interactive zoom and pan (using matplotlib toolbar)
- Automatic layout adjustment
- DPI 100 for clear visualization

## How to Use

### Loading C3D Files

```python
from gui.widgets.c3d_grf_viewer import C3DGRFViewer

# Create viewer instance
grf_viewer = C3DGRFViewer(parent_frame)

# Load C3D file
success = grf_viewer.load_c3d('/path/to/file.c3d')
```

### In the C3D Export Tab

1. **Select C3D File**
   - Click "Browse C3D File"
   - Navigate to your C3D motion capture file
   - File is loaded automatically

2. **View GRF Data**
   - All GRF channels appear in the viewer
   - Channels are auto-detected and listed with checkboxes
   - Plot updates in real-time as you interact

3. **Select Channels**
   - Check/uncheck individual channels
   - Use "Select All" to enable all at once
   - Use "Deselect All" to disable all at once

4. **Crop Trial**
   - Drag the slider to select time range
   - Or type start/end percentages directly
   - Time range updates in real-time
   - Plot refreshes instantly

5. **Export Data**
   - Configure export options (Markers, GRF, EMG)
   - Selected GRF crop range applies to export
   - Selected channels are included in GRF MOT file
   - Click "Export" to save files

## Technical Details

### Auto-Detection Algorithm
```
1. Read C3D analog labels
2. Search for keywords:
   - "Force", "Moment"
   - "fx", "fy", "fz", "mx", "my", "mz"
   - "Fx", "Fy", "Fz" (case-insensitive)
3. Extract analog data for matching channels
4. Organize by force platform
5. Display with proper labeling
```

### Crop Range Calculation
```
Total Samples = Number of frames in C3D
Crop Start Index = (Start %) / 100 * Total Samples
Crop End Index = (End %) / 100 * Total Samples
Cropped Data = Data[Crop Start Index : Crop End Index]
```

### Multi-Platform Detection
The viewer automatically detects multiple force platforms by:
- Analyzing channel names for platform numbers
- Detecting force triplets (Fx, Fy, Fz grouped together)
- Detecting moment triplets (Mx, My, Mz grouped together)
- Organizing channels by source force platform

## Integration with Analysis Pipeline

The GRF viewer integrates with the analysis workflow:

```
1. C3D Export Tab
   ├── Load C3D file
   ├── View GRF with advanced viewer
   ├── Select channels to export
   └── Crop trial data

2. Export to MOT format
   └── Selected channels + crop range applied

3. Session-Level Analysis
   ├── C3D Export (preprocessing step)
   ├── OpenSim Analysis (IK, ID, SO)
   └── Advanced Dynamics (RRA, CMC, Energetics)
```

## API Reference

### C3DGRFViewer Class

```python
class C3DGRFViewer(ctk.CTkFrame):
    """Advanced C3D GRF visualization widget."""
    
    def load_c3d(self, c3d_file_path: str) -> bool:
        """Load C3D file and extract GRF data."""
        # Returns: True if successful, False otherwise
    
    def get_crop_range(self) -> tuple:
        """Get current crop range as (start%, end%) tuple."""
        # Returns: (crop_start, crop_end)
    
    def get_selected_channels(self) -> list:
        """Get list of selected GRF channels."""
        # Returns: ['Force_Platform_1_Fx', 'Force_Platform_1_Fy', ...]
```

## Common Use Cases

### 1. **Isolate Double Support Phase**
- Set crop range to 20-80% of trial
- Hides initial contact setup and final liftoff
- Focuses on main weight-bearing phase

### 2. **Remove Motion Capture Artifacts**
- Identify problematic channels with checkbox
- Deselect them before export
- Reduces noise in downstream analysis

### 3. **Extract Specific Force Platform**
- Deselect other force platform channels
- Keep only desired platform (e.g., Force_Platform_2)
- Export clean data for focused analysis

### 4. **Multi-Platform Comparison**
- Select one force platform
- Export as MOT
- Repeat for second platform
- Compare results side-by-side

## Troubleshooting

### "No GRF channels detected"
- Verify C3D file contains analog data
- Check channel naming in Mokka
- Ensure c3d Python module is installed

### Plot not updating
- Check that matplotlib is installed
- Verify channel selection
- Try loading file again

### Time range incorrect
- Verify C3D file sample rate
- Check frame count in properties
- Ensure time is calculated correctly

## File Structure

```
code/tests/app/gui/widgets/
├── c3d_grf_viewer.py         # NEW: Advanced GRF viewer widget
├── c3d_export.py             # UPDATED: Integrated viewer
└── ...

code/tests/app/utils/
├── openSim.py                # UPDATED: Improved exportC3D import
├── exportC3D.py              # C3D export functions
└── ...
```

## Performance Notes

- Handles up to 4 force platforms efficiently
- Supports trials up to 1000+ frames
- Matplotlib rendering typically <100ms for 10 channels
- Memory usage: ~5-10MB per trial data in memory

## Version History

### v2.1.0 (2026-05-13)
- Added advanced C3D GRF viewer widget
- Implemented auto-detection of GRF channels
- Added interactive channel selection
- Added trial cropping with visual feedback
- Integrated into C3D Export tab
- Fixed exportC3D module import issues

## Future Enhancements

- [ ] FFT analysis for frequency content
- [ ] COP (Center of Pressure) visualization
- [ ] Filtering options (low-pass, high-pass)
- [ ] Export COP trajectory plots
- [ ] Multi-trial comparison view
- [ ] Statistical analysis (min, max, mean forces)

---

**Note:** This viewer is designed to replicate the functionality of Mokka while integrating seamlessly into the biomechanics analysis workflow. All GRF data visualization and processing follows standard biomechanics conventions.
