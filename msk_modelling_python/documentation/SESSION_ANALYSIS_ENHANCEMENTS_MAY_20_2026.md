# Session Analysis Tab Enhancements - May 20, 2026

## Overview
Enhanced the Session Analysis tab with template folder and model path management, allowing users to easily configure and update trial settings across all trials in a session.

---

## New Features

### 1. **Template Folder Selection**
- **Input**: Text entry with placeholder
- **Browse**: File browser button to select folder
- **Validation**: Real-time status indicator
  - ✅ **Green**: Folder found and valid
  - ❌ **Red**: Path entered but folder doesn't exist
  - ⚠️ **Yellow**: Not set

- **Use Case**: Select OpenSim setup/setup files location
- **Storage**: Relative path to session (if possible) or absolute path

### 2. **Model Path Selection**
- **Input**: Text entry with placeholder for `.osim` file
- **Browse**: File browser button with `.osim` filter
- **Validation**: Real-time status indicator (same as template)
- **Use Case**: Select the OpenSim model file to use
- **Storage**: Relative path to session (if possible) or absolute path

### 3. **Path Validation**
- **Real-time**: Updates as user types
- **Visual Feedback**: 
  - Green checkmark when path is valid
  - Red X when path doesn't exist
  - Yellow warning when field is empty
- **Trace Callbacks**: Validates on every character change
- **File Type Check**: Model path validates it's a file, template validates it's a directory

### 4. **Update Trial Settings Button**
- **Location**: Below path inputs
- **Function**: Updates `trial_settings.xml` for all trials
- **Relative Paths**: Converts absolute paths to relative (session-relative) when possible
- **Fallback**: Uses absolute paths if relative conversion fails
- **Scope**: Updates all trials in session, not just selected ones
- **Background Thread**: Runs in background to avoid UI freeze

### 5. **Trial Settings XML Structure**
Generated/Updated structure:
```xml
<?xml version='1.0' encoding='utf-8'?>
<trial_settings>
  <template_folder>setups</template_folder>
  <model>powerlifting_model.osim</model>
  <emg>emg_filtered_normalised.mot</emg>
  <!-- other settings -->
</trial_settings>
```

---

## Implementation Details

### UI Layout
```
Session-Level Analysis
Session: athlete1_session

┌─ TEMPLATE & MODEL PATHS ─────────────────────────────────┐
│                                                            │
│ Template Folder: [________________] [Browse] ✅ Found     │
│                                                            │
│ Model Path:     [________________] [Browse] ❌ Not found  │
│                                                            │
│              [Update Trial Settings]                       │
└────────────────────────────────────────────────────────────┘

[Rest of tab remains unchanged...]
```

### New Methods Added

#### `_browse_template_folder() -> None`
- Opens file dialog for folder selection
- Sets `template_path_var` on selection
- Triggers validation

#### `_browse_model_file() -> None`
- Opens file dialog with `.osim` filter
- Sets `model_path_var` on selection
- Triggers validation

#### `_validate_template_path() -> None`
- Checks if path exists and is a directory
- Updates `template_status` label with visual indicator
- Called on every character change via trace callback

#### `_validate_model_path() -> None`
- Checks if path exists and is a file
- Updates `model_status` label with visual indicator
- Called on every character change via trace callback

#### `_update_trial_settings() -> None`
- Main entry point for updating settings
- Validates input before proceeding
- Runs update in background thread
- Checks:
  - Session is loaded
  - At least one path is provided
  - Paths exist on filesystem

#### `_update_trial_settings_thread(template_path: str, model_path: str) -> None`
- Background thread worker
- Iterates through all trials in session
- For each trial:
  - Loads or creates `trial_settings.xml`
  - Converts absolute paths to relative (session-relative) when possible
  - Updates XML elements: `template_folder` and `model`
  - Writes updated XML back to file
- Provides detailed status updates
- Reports success/failure counts

---

## Relative Path Handling

### Algorithm
```python
try:
    rel_path = str(Path(absolute_path).relative_to(session_path))
except ValueError:
    # Path is not under session directory
    rel_path = absolute_path
```

### Examples
- Template at `C:\Git\powerlifing_model\setups` with session `C:\Git\msk_modeling_python\example_data\running\Athlete1\session1`
  - **Result**: `..\..\..\..\powerlifing_model\setups` (if possible)
  - **Fallback**: `C:\Git\powerlifing_model\setups` (absolute)

- Model at `C:\Git\powerlifing_model\code\models\powerlifting_model.osim` with same session
  - **Result**: `..\..\..\..\powerlifting_model\code\models\powerlifting_model.osim`
  - **Fallback**: Absolute path

---

## Status Feedback

### Validation Status
| Status | Meaning | Icon | Color |
|--------|---------|------|-------|
| Found | Path exists and valid | ✅ | Green (#28a745) |
| Not found | Path entered but doesn't exist | ❌ | Red (#dc3545) |
| Not set | Field is empty | ⚠️ | Yellow (#ffc107) |

### Operation Status
```
"Updated athlete1_trial_1"                           [success]
"Updated athlete1_trial_2"                           [success]
"Failed to update athlete1_trial_3: Permission denied" [error]
"✅ Updated all 3 trials successfully"               [success]
"⚠️ Updated 2/3 trials (1 failed)"                   [warning]
```

---

## XML File Handling

### If File Doesn't Exist
- Creates new `trial_settings.xml` with root `<trial_settings>`
- Adds template_folder and model elements

### If File Exists
- Parses existing XML
- Updates/creates template_folder element
- Updates/creates model element
- Preserves all other elements (emg, etc.)

### Write Behavior
- UTF-8 encoding
- XML declaration included
- Overwrites existing file

---

## Thread Safety

- **Background Threading**: Update operation runs in daemon thread
- **UI Updates**: Status messages sent via `status_callback()`
- **No Blocking**: UI remains responsive during batch updates
- **Per-Trial Updates**: Users see progress as each trial is updated

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| No session loaded | Error: "No session loaded" |
| Empty paths | Warning: "Please set at least template folder or model path" |
| Template not found | Error: "Template folder not found" |
| Model not found | Error: "Model file not found" |
| XML parse error | Per-trial error message, continues with others |
| Permission denied | Per-trial error, continues with others |
| Path convert fails | Falls back to absolute path |

---

## Usage Workflow

### Scenario 1: New Session with Standard Paths
```
1. Load session (automatic)
2. Enter template folder: "C:\...\powerlifting_model\setups"
3. Enter model path: "C:\...\powerlifting_model.osim"
   → Both show ✅ Found
4. Click "Update Trial Settings"
   → Updates all trial_settings.xml with relative paths
   → Shows "✅ Updated all N trials successfully"
```

### Scenario 2: Different Model Per Trial
```
1. Load session
2. Use external tool to update individual trial_settings.xml
3. Trial settings now point to custom models
4. Session Analysis reads from each trial's settings when running
```

### Scenario 3: Browse and Verify
```
1. Click "Browse" for template folder
2. Navigate to C:\my_templates\
3. Entry auto-fills, validation shows ✅ Found
4. Click "Browse" for model
5. Navigate to C:\models\athlete_specific.osim
6. Entry auto-fills, validation shows ✅ Found
7. Click "Update Trial Settings"
```

---

## Integration Points

### Reads From
- Trial folder structure via `SessionManager`
- File system for validation
- Existing `trial_settings.xml` files

### Writes To
- `trial_settings.xml` in each trial folder

### Used By
- Analysis runner when executing OpenSim steps
- C3D export when creating trial setups
- Any component reading from `trial_settings.xml`

---

## Future Enhancements

Potential additions:
- Load/save path configurations (templates)
- Different models for different trial types
- Batch file picker for template selection
- Path history dropdown
- Validation of model compatibility with setup
- Automatic path detection from session structure

---

## Files Modified

```
analysis_control_session.py
  ├── Added: template_path_var, template_path_entry, template_status
  ├── Added: model_path_var, model_path_entry, model_status
  ├── Added: Update Trial Settings button
  ├── New Methods:
  │   ├── _browse_template_folder()
  │   ├── _browse_model_file()
  │   ├── _validate_template_path()
  │   ├── _validate_model_path()
  │   ├── _update_trial_settings()
  │   └── _update_trial_settings_thread()
  └── Updated: _create_widgets() row indexing
```

---

## Testing Checklist

- [ ] Template folder browse opens file dialog
- [ ] Model file browse opens file dialog with .osim filter
- [ ] Path validation shows ✅ for valid paths
- [ ] Path validation shows ❌ for invalid paths
- [ ] Path validation shows ⚠️ for empty fields
- [ ] Validation updates in real-time as user types
- [ ] Update button disabled if no session loaded
- [ ] Update button requires at least one path set
- [ ] Update runs in background (UI responsive)
- [ ] trial_settings.xml created if not exists
- [ ] Existing XML elements preserved
- [ ] Relative paths used when possible
- [ ] Fallback to absolute paths when needed
- [ ] Success count reported correctly
- [ ] Error messages show failed trial names
- [ ] Multiple trials updated in sequence

---

**Date**: May 20, 2026  
**Status**: ✅ Complete and Ready for Testing
