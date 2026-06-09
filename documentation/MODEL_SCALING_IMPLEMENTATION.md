# Model Scaling Tab Implementation

## Summary
Added a new "Model Scaling" tab to the GUI that appears between "EMG Normalization" and "Session Analysis". This tab provides an interface for OpenSim Model Scaling with adjustable marker weights.

## Files Modified

### 1. **settings.py**
**Path:** `C:\Git\powerlifing_model_clean\code\tests\app\settings.py`

**Changes:**
- Added project-specific configuration variables for `powerlifing_model`:
  - `marker_weights`: Dictionary of marker names with default weights
  - `DOFs`: List of degrees of freedom
  - `DOFs_moments`: Mapping of DOF to moment columns
  - `Muscle_Groups`: Muscle groupings for analysis
  - `JCF_Groups`: Joint contact force groupings
  - `EMG_muscle_mapping`: EMG channel to muscle mapping
  - `model_config`: Model configuration dictionary

These variables are now imported from settings.py and used by the Model Scaling widget.

### 2. **gui/widgets/model_scaling.py** (NEW FILE)
**Path:** `C:\Git\powerlifing_model_clean\code\tests\app\gui\widgets\model_scaling.py`

**Features:**
- **Input Paths Section:**
  - Template Model (.osim) - Required
  - Markerset File (.xml) - Optional (uses model's default if not specified)
  - TRC File for Scaling - Required
  - Destination Folder - Required
  - "Load Markers from TRC" button

- **Marker Weights Panel:**
  - Displays all markers found in TRC file
  - Shows default weights from `marker_weights` in settings
  - Allows editing of individual marker weights
  - "Reset to Default" button to revert changes
  - Scrollable panel for many markers

- **Action Buttons:**
  - [RUN] Scale Model - Starts the scaling process
  - [STOP] Cancel - Stops scaling (shown during operation)
  - Status indicator showing current state

**Key Methods:**
- `_load_trc_markers()`: Loads marker names from TRC file
- `_parse_trc_file()`: Parses TRC file header to extract marker names
- `_populate_markers_panel()`: Creates UI elements for each marker with weight input
- `_reset_weights()`: Resets all weights to default values
- `_run_scaling()`: Validates inputs and starts scaling thread
- `_run_scaling_thread()`: Placeholder for actual scaling implementation

### 3. **gui/main_window.py**
**Path:** `C:\Git\powerlifing_model_clean\code\tests\app\gui\main_window.py`

**Changes:**
- Added import: `from gui.widgets.model_scaling import ModelScalingTab`
- Added tab definition in `tab_definitions` dictionary:
  ```python
  "Model Scaling": {"class": ModelScalingTab, "args": (self.config_manager, self.update_status)},
  ```
- Tab appears between "EMG Normalization" and "Session Analysis"

## User Workflow

1. **Navigate to Model Scaling Tab** in the main application
2. **Select Template Model** (.osim file) using Browse button
3. **Optionally Select Markerset** (.xml file) - if not selected, model's default will be used
4. **Select TRC File** for scaling using Browse button
5. **Select Destination Folder** where scaled model will be saved
6. **Click "Load Markers from TRC"** to populate the markers panel
7. **Adjust Marker Weights** as needed:
   - Default weights are loaded from `settings.py`
   - Can be customized per marker
   - Click "Reset to Default" to revert
8. **Click "[RUN] Scale Model"** to start scaling
9. Scaling status is shown in the status indicator

## What Still Needs Implementation

### 1. OpenSim Integration
The `_run_scaling_thread()` method currently only logs the process. You need to integrate with OpenSim's Scale Tool:

**Required:**
```python
import opensim as osim

# Create Scale Tool
scale = osim.ScaleTool(template_model_path)
scale.setGenericModelMass(...)
scale.setMarkerFile(trc_file_path)
scale.run()
```

**Resources:**
- OpenSim Python API documentation
- Scale Tool XML setup files

### 2. Configuration File Generation
Generate OpenSim Scale Tool configuration XML with:
- Marker pairs and weights
- Segment scaling options
- Coordinate transformations

### 3. Output Validation
- Check if scaled model was created successfully
- Validate model can be loaded in OpenSim
- Provide feedback on scaling success/failure

### 4. Error Handling
- Validate model file format
- Check marker names against model anatomy
- Handle missing markers in TRC

### 5. Advanced Features (Optional)
- Preview marker placement before scaling
- Show scaling statistics (percent changes per segment)
- Save scaling configuration for later use
- Batch scaling of multiple models

## Technical Details

### Marker Weight Panel
The panel dynamically creates entries for each marker found in the TRC file:
- Sorted alphabetically for easier navigation
- Each marker has a corresponding DoubleVar for weight storage
- Weights can be from 0 to any positive value
- Default weights from `settings.marker_weights` are used

### TRC File Parsing
Simplistic parsing that extracts marker names from TRC header:
- Looks for "Frame#" line (typically line 3)
- Extracts marker names from following line
- Ignores X, Y, Z coordinate suffixes
- Returns dict of marker_name -> count

### Thread Safety
- Scaling runs in daemon thread to prevent UI blocking
- Progress updates sent via status_callback()
- Buttons disabled during operation

## File Paths for Testing

**Example paths you can use:**
- Template Model: `C:\Git\powerlifing_model_clean\code\tests\app\utils\setupFiles\Purzel\*\*.osim`
- TRC File: Your trial marker file (marker_experimental.trc)
- Markerset: Optional, usually in setupFiles folder
- Destination: Any accessible folder

## Integration Notes

The tab automatically inherits:
- The application's theme and styling
- Status callback system for user feedback
- Logger integration for debugging
- Config manager for persistence (if needed)

All marker weights are sourced from `settings.py` at import time, so changing marker_weights there will automatically update the default values in the scaling widget.
