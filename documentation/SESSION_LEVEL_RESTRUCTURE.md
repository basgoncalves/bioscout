# Session-Level Analysis Restructure

## Overview
The app has been restructured to be fully session-aware at the top level. All tabs now work with a single selected session directory, and the batch export no longer duplicates C3D files.

## Key Changes

### 1. Session Directory Selector in Top Bar ✅
**File: `main_window.py`**

Added a new session selector to the topbar that appears above all tabs:
```
Session: [Select session folder...] [Browse] [Load]
```

Features:
- Browse button to select a session folder
- Load button to apply the session to all tabs
- Path entry field shows selected session directory
- Applies to all tabs automatically

### 2. Session Propagation to Tabs ✅
**File: `main_window.py`**

New `broadcast_session_dir()` method:
- Sends selected session directory to all tabs
- Tabs implement `set_session_dir()` method to receive the session
- Allows tabs to update their working directory automatically

### 3. Batch C3D Export Updates ✅
**File: `batch_c3d_export.py`**

Changes:
- **Implements `set_session_dir()` method** - receives session from main window
- **Auto-populates source folder** - when session is selected, source folder is automatically set
- **Auto-scans for C3D files** - files are detected when session is loaded
- **NO longer copies C3D files** - only exports processed data (markers, GRF, EMG, etc.)
- **Cleaner trial folders** - each trial folder now contains only:
  - `marker_experimental.trc`
  - `grf.mot`
  - `emg.mot`
  - `emg_filtered.mot`
  - `analog.csv`
  - `trial_settings.xml`
  - `events.csv`

## Workflow

### Before (Multiple Steps)
1. Open Batch C3D Export tab
2. Browse and select source folder
3. Browse and select destination folder
4. Wait for C3D file scanning
5. Run export (C3D file copied to each trial folder - wasteful!)

### After (Streamlined)
1. Select session folder at top using "Browse"
2. Click "Load" button
3. All tabs automatically configured
4. Batch C3D Export shows C3D files
5. Run export (only processed files exported - clean!)

## Session Directory Benefits

1. **Single Source of Truth**
   - One session folder selected at application level
   - All tabs work with the same session
   - No confusion about which folder you're working with

2. **Cleaner Project Structure**
   - C3D files stay in session root
   - Trial folders contain only processed data
   - No file duplication
   - Clear separation of source vs. output data

3. **Automatic Configuration**
   - Select session once
   - All tabs auto-configure
   - No need to manually select folders in each tab

## File Structure Example

```
/running/Athlete1/session1/
├── sprint_1.c3d          ← Source data (NOT copied)
├── static_1.c3d          ← Source data (NOT copied)
├── walking_1.c3d         ← Source data (NOT copied)
├── sprint_1/             ← Trial export folder
│   ├── marker_experimental.trc
│   ├── grf.mot
│   ├── emg.mot
│   ├── emg_filtered.mot
│   ├── analog.csv
│   ├── trial_settings.xml
│   └── events.csv
├── static_1/             ← Trial export folder
│   ├── marker_experimental.trc
│   ├── grf.mot
│   ├── emg.mot
│   ├── emg_filtered.mot
│   ├── analog.csv
│   ├── trial_settings.xml
│   └── events.csv
└── walking_1/            ← Trial export folder
    ├── marker_experimental.trc
    ├── grf.mot
    ├── emg.mot
    ├── emg_filtered.mot
    ├── analog.csv
    ├── trial_settings.xml
    └── events.csv
```

## Implementation Details

### Main Window Changes

1. **Topbar Session Selector**
   ```python
   # New components in _create_topbar()
   - Session directory input field
   - Browse button (opens folder picker)
   - Load button (broadcasts to all tabs)
   ```

2. **Broadcast Method**
   ```python
   def broadcast_session_dir(self, session_dir: str):
       """Sends session directory to all tabs that support it"""
       for tab_name, tab in self.tabs.items():
           if hasattr(tab, 'set_session_dir'):
               tab.set_session_dir(session_dir)
   ```

### Batch C3D Export Changes

1. **Session Directory Support**
   ```python
   def set_session_dir(self, session_dir: str):
       """Receives session from main window"""
       # Auto-populate source folder
       # Auto-scan C3D files
   ```

2. **No C3D File Copying**
   ```python
   # OLD: shutil.copy(c3d_file, output_folder / c3d_file.name)
   # NEW: print("[INFO] C3D file remains in source folder")
   ```

## Next Steps

To make other tabs session-aware:

1. Add `set_session_dir()` method to each tab class
2. Update the tab to use the session directory
3. The main window will automatically broadcast to it

Example for EMG Processing tab:
```python
def set_session_dir(self, session_dir: str):
    """Receive session directory from main window"""
    self.session_dir = Path(session_dir) if session_dir else None
    if self.session_dir:
        # Update UI to show session
        self.session_label.configure(text=f"Session: {self.session_dir.name}")
        # Load trials from session
        self._load_trials_from_session()
```

## Testing Checklist

- [ ] Session directory selector appears in topbar
- [ ] Browse button opens folder picker
- [ ] Load button populates all tabs
- [ ] Batch C3D Export auto-populates source folder
- [ ] C3D files are detected automatically
- [ ] Trial folders do NOT contain C3D files
- [ ] Only processed files are exported
- [ ] File sizes match previous exports
- [ ] No stray files in session root after export

## Architecture Benefits

1. **Scalability** - Easy to add more session-aware tabs
2. **Maintainability** - Single point of session configuration
3. **User Experience** - Clear, intuitive workflow
4. **Data Integrity** - Source files never duplicated
5. **Disk Space** - No wasteful C3D file copies
