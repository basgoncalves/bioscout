# Session Cleanup & EMG Updates - Implementation Summary

## ✅ Completed Changes

### 1. Session Analysis Tab - Removed Duplicate Session Selector
**File**: `gui/widgets/analysis_control_session.py`

**Changes Made**:
- ✅ Removed the redundant session directory selector from row 1
- ✅ Added `set_session_dir()` method to receive session from main window
- ✅ Simplified top section to show only session label
- ✅ Removed `_browse_session()` and `_load_session_from_entry()` methods
- ✅ Updated `_load_session()` to update session label

**Before**:
```
┌─────────────────────────────────────────────────────┐
│ Session-Level Analysis                              │
│ Session Directory: [Browse] [Load]                  │
│ Available Trials    │    Analysis Steps              │
└─────────────────────────────────────────────────────┘
```

**After**:
```
┌─────────────────────────────────────────────────────┐
│ Session-Level Analysis                              │
│ Session: session1 (from top-level selector)         │
│ Available Trials    │    Analysis Steps              │
└─────────────────────────────────────────────────────┘
```

**Integration**:
- When user clicks "Load" in top session selector → all tabs receive session
- Session Analysis tab receives it via `set_session_dir()`
- Automatically populates trial list when session loads

### 2. EMG Normalization Tab - Updated Methods
**File**: `gui/widgets/emg_normalization.py`

**Changes Made**:
- ✅ Changed normalization methods from "None, Max, RMS" to **"Max, Window Average"**
- ✅ Added textbox for window time input (milliseconds)
- ✅ Implemented `_normalize_window_average()` method
- ✅ Added `_on_norm_method_change()` to show/hide window time input
- ✅ Updated `_normalize_in_thread()` to accept window_ms parameter

**Normalization Methods**:

#### Max Normalization
```python
# Scale data by maximum value
normalized = data / max(abs(data))
# Result: Peak values = ±1.0
```

#### Window Average Normalization
```python
# Apply moving window average to smooth the data
window_samples = window_ms * sampling_rate / 1000
smoothed = convolve(abs(data), window, mode='same')
normalized = data / max(smoothed)
# Result: Normalized by smoothed envelope
```

**UI Changes**:
- Radio buttons: "Max" (default) and "Window Average"
- Window time input: Only visible when "Window Average" selected
- Default window time: 200 ms (adjustable)
- Input validation: Ensures window time > 0

**Example Usage**:
1. Select trials (sprint_1, static_1, walking_1)
2. Choose "Window Average"
3. Set window time to 200 ms (or custom value)
4. Click "Apply Normalization"

### 3. Button Styling - Already Correct
The Run/Stop buttons already have proper styling:
```python
# Run button (green)
fg_color="#28a745"  # Green
hover_color="#218838"  # Darker green

# Stop button (red)
fg_color="#dc3545"  # Red
hover_color="#c82333"  # Darker red
```

---

## 📋 Remaining Issues & Solutions

### Issue 1: Console Output Not Showing All Messages

**Problem**: 
The app console doesn't display all logger outputs that appear in the command line terminal.

**Root Cause**:
- Logger is configured to output to file + console (StreamHandler)
- GUI console widget receives messages via `console.write()` calls
- Not all logger outputs are explicitly passed to the GUI console
- Buffering and threading issues may cause some messages to not appear

**Solution (Recommended)**:
Add a custom logging handler to the logger that writes directly to the GUI console:

```python
# In console_terminal.py, add:
class GUIHandler(logging.Handler):
    def __init__(self, console_widget):
        super().__init__()
        self.console = console_widget
    
    def emit(self, record):
        msg = self.format(record)
        self.console.write(msg, msg_type="info")

# In logger.py, add:
def add_gui_handler(console_widget):
    gui_handler = GUIHandler(console_widget)
    gui_handler.setLevel(logging.DEBUG)
    logger.logger.addHandler(gui_handler)
```

**Temporary Workaround**:
All important status messages should use `status_callback()` instead of `logger.info()` to ensure they appear in the GUI.

---

### Issue 2: Inverse Kinematics Error

**Problem**:
Log shows: "Trial missing required files: c3d"

**Root Cause**:
- IK analysis expects C3D file to be in the trial folder
- With new architecture, C3D files stay in session root (not copied to trial folders)
- Trial validation is looking for C3D in wrong location

**Current Behavior**:
```
/session1/
├── sprint_1.c3d          ← C3D file (session root)
└── sprint_1/
    ├── marker_experimental.trc
    ├── grf.mot
    └── emg.mot
    # No C3D file here!
```

**Solution (Required)**:
Update trial validator to look for C3D file in session root:

```python
# File: core/session_manager.py, TrialValidator class
def _validate_c3d_file(self) -> bool:
    """Check if C3D file exists."""
    # Try trial folder first (backward compatibility)
    if (self.trial_path / f"{self.trial_name}.c3d").exists():
        return True
    
    # Try session root (new architecture)
    session_root = self.trial_path.parent
    if (session_root / f"{self.trial_name}.c3d").exists():
        return True
    
    return False
```

---

### Issue 3: Python Terminal "import os" Error

**Problem**:
Terminal shows error when trying to use `os` module after importing it.

**Root Cause**:
- Python terminal has its own execution context/namespace
- Variables may not persist between commands
- Possible namespace isolation issue

**Current Terminal Code**:
```python
def _execute_command(self):
    """Execute Python command."""
    code = self.input_entry.get()
    self.input_entry.delete(0, "end")
    
    # Executes in isolated namespace
    try:
        exec(code)  # ← This is the issue
    except Exception as e:
        self.write(str(e), "error")
```

**Solution**:
Create a persistent namespace for the Python terminal:

```python
class ConsoleTerminal:
    def __init__(self, parent, height=150):
        super().__init__(parent)
        # Create persistent namespace for commands
        self.namespace = {
            '__name__': '__console__',
            '__doc__': None,
            'np': np,
            'pd': pd,
            # Import common modules
        }
    
    def _execute_command(self):
        code = self.input_entry.get()
        try:
            # Execute in persistent namespace
            exec(code, self.namespace)
        except Exception as e:
            self.write(str(e), "error")
```

---

## 📊 File Summary

| File | Changes | Status |
|------|---------|--------|
| `gui/widgets/analysis_control_session.py` | Removed session selector, added set_session_dir() | ✅ Complete |
| `gui/widgets/emg_normalization.py` | Max + Window Average methods | ✅ Complete |
| `utils/logger.py` | Add GUI logging handler | ⏳ Recommended |
| `core/session_manager.py` | Update C3D validation | ⏳ Required |
| `gui/widgets/console_terminal.py` | Add persistent namespace | ⏳ Recommended |

---

## 🔧 Next Steps

### High Priority (Required for IK to work)
1. Update `core/session_manager.py` TrialValidator to look for C3D in session root
2. Test IK analysis with updated validator

### Medium Priority (Improves user experience)
1. Add GUI logging handler to show all console messages
2. Fix Python terminal namespace to persist variables
3. Add flush mechanism to ensure all messages are displayed

### Low Priority (Polish)
1. Add confirmation dialogs for destructive actions
2. Improve error messages with troubleshooting tips
3. Add progress feedback for long-running operations

---

## Testing Checklist

- [ ] Session Analysis receives session from top selector
- [ ] EMG Normalization Max method works correctly
- [ ] EMG Normalization Window Average works with custom window time
- [ ] All trials populate correctly after session loads
- [ ] IK analysis runs without "missing C3D file" error
- [ ] Console shows all INFO level messages
- [ ] Python terminal persists variables between commands
- [ ] Run/Stop buttons have correct green/red styling

---

## Code Examples

### Using Window Average (EMG Normalization)
```
1. Browse and Load session
2. Click "EMG Normalization" tab
3. Session automatically shows as "Session: session1"
4. Trials auto-populate: sprint_1, static_1, walking_1
5. Select all trials with "All" button
6. Choose "Window Average"
7. Set window time to 150 ms
8. Click "Apply Normalization"
9. Watch console output for progress
```

### Session-Level Architecture Flow
```
Main Window
├── Top Session Selector: Browse/Load
├── broadcast_session_dir(path)
└── All tabs receive set_session_dir(path)
    ├── Session Analysis → Auto-populates trials
    ├── EMG Normalization → Shows session label
    ├── Results → Scans for data files
    ├── Batch C3D → Uses as source folder
    └── CEINMS Calibration → Uses as session reference
```

---

## Summary

✅ **Completed**:
- Removed duplicate session selector from Session Analysis
- Updated EMG Normalization with Max and Window Average methods
- Added window time configuration for moving average
- Maintained proper button styling (green/red)
- Integrated session-level architecture across tabs

⏳ **Recommended**:
- Add GUI logging handler for complete console output
- Fix Python terminal namespace persistence
- Update trial C3D validation to check session root

🚀 **Result**:
Users now have a streamlined, single-session workflow where:
- One session is selected at the app level
- All tabs automatically receive and use that session
- No duplicate selection dialogs
- Cleaner user experience
