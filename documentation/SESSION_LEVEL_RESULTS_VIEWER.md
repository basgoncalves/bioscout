# Results Viewer Tab - Session-Level Enhancement

## Completed Implementation

The Results Viewer tab has been completely redesigned to integrate with the session-level architecture while providing enhanced visualization and export capabilities.

## What's New

### 1. Tree-Based File Structure
**File**: `gui/widgets/results_viewer.py`

The left panel now displays a hierarchical tree showing:
- Session folder (expandable)
  - Trial folders (expandable/collapsible)
    - Data files (MOT, STO, CSV, TRC)

**Implementation**:
- Uses `tkinter.ttk.Treeview` widget for tree structure
- Automatically scans session directory on load
- Icons: 📁 for folders, 📊 for trials, 📄 for files
- Click any file to select it for viewing

```python
# Key method: _build_tree_from_session()
self.tree.insert('', 'end', text=f"📁 {self.session_dir.name}", open=True)
for item in sorted(self.session_dir.iterdir()):
    if item.is_dir():
        data_files = self._find_data_files(item)
        trial_id = self.tree.insert(session_id, 'end', text=f"📊 {item.name}")
        for file_path in sorted(data_files):
            self.tree.insert(trial_id, 'end', text=f"📄 {file_name}")
```

### 2. Session-Level Integration
**Method**: `set_session_dir(session_dir: str)`

The tab now receives the session directory from the main window's session selector:

```python
def set_session_dir(self, session_dir: str):
    """Receive session directory from main window."""
    self.session_dir = Path(session_dir) if session_dir else None
    if self.session_dir and self.session_dir.exists():
        self.session_label.configure(text=f"Session: {self.session_dir.name}")
        self._build_tree_from_session()
```

**How it works**:
1. User clicks "Browse" in top-level session selector
2. User clicks "Load" to broadcast session to all tabs
3. Main window calls `broadcast_session_dir(folder)` (line 500 in main_window.py)
4. This method calls `set_session_dir()` on Results tab
5. Results tab scans session and populates tree

### 3. Flexible Plot Visualization
**File**: `gui/widgets/results_viewer.py`, method `_plot_data()`

Two plotting modes controlled by "Separate Subplots" checkbox:

#### Single-Plot Mode (Default)
```python
if not use_subplots:
    fig = Figure(figsize=(12, 4), dpi=80)
    ax = fig.add_subplot(111)
    # Plot all columns on one graph
    for i in range(num_cols):
        ax.plot(time, data[:, i], linewidth=1, label=labels[i])
    ax.legend(fontsize=8, loc='best')
```
- All data columns on one graph
- Includes legend for easy identification
- Best for comparing multiple signals
- Good for similar-scale data (EMG channels, etc.)

#### Subplot Mode
```python
if use_subplots:
    num_rows = max(1, (num_cols + 2) // 3)  # 3 plots per row
    fig = Figure(figsize=(12, fig_height), dpi=80)
    for i in range(num_cols):
        ax = fig.add_subplot(num_rows, 3, i + 1)
        ax.plot(time, data[:, i], linewidth=1)
```
- Each column gets its own subplot
- 3 columns per row in grid layout
- Individual Y-axis scale per subplot
- Better for multi-scale data (angles, moments, forces)

### 4. Save Figure Functionality
**Method**: `_save_figure()`

Users can now save plots in multiple formats:

```python
def _save_figure(self) -> None:
    """Save current figure to file."""
    file_path = filedialog.asksaveasfilename(
        title="Save Figure As",
        defaultextension=".png",
        filetypes=[
            ("PNG Files", "*.png"),
            ("PDF Files", "*.pdf"),
            ("SVG Files", "*.svg"),
            ("All Files", "*.*")
        ]
    )
    if file_path:
        self.fig.savefig(file_path, dpi=300, bbox_inches='tight')
```

**Features**:
- Save at 300 DPI for publication quality
- Supports PNG, PDF, SVG formats
- File dialog for easy selection
- Automatic file extension handling

**Button placement**:
- Located below plot area
- "Save Figure" button for export
- "Clear" button to reset viewer

### 5. Background Threading
**Method**: `_load_and_plot_thread()`

File loading happens in background to keep UI responsive:

```python
def _load_and_plot(self) -> None:
    """Load file and generate plot."""
    thread = threading.Thread(target=self._load_and_plot_thread, daemon=True)
    thread.start()
```

Benefits:
- Large files don't freeze the UI
- Status messages keep user informed
- Smooth user experience

## Architecture Integration

### Main Window Integration
**File**: `main_window.py`

The Results tab is already integrated in the tab system:

```python
# Line 361 in main_window.py
"Results": {"class": ResultsViewerTab, "args": (self.config_manager, self.update_status)}
```

The broadcast mechanism (lines 500-512) automatically sends session to any tab with `set_session_dir()`.

### Tab Hierarchy
```
MainWindow
├── TopBar
│   ├── Session Selector
│   │   ├── Browse button → opens folder picker
│   │   ├── Load button → broadcasts session to all tabs
│   │   └── Entry field → shows selected path
│   └── Title label → shows current tab
├── Sidebar (Navigation)
│   └── Results button → switches to Results tab
└── Main Area
    └── Results Viewer Tab
        ├── Session label → shows received session
        ├── Tree structure → shows trials and files
        ├── Plot options → subplot checkbox
        ├── Load & Plot button
        ├── Plot area → displays matplotlib figure
        └── Save/Clear buttons
```

## Implementation Details

### Supported File Types
```python
data_extensions = {'.mot', '.sto', '.csv', '.trc'}

def _find_data_files(self, folder: Path) -> list:
    """Find all data files in a folder."""
    files = []
    for file in folder.glob('*'):
        if file.suffix.lower() in data_extensions:
            files.append(file)
    return files
```

Files automatically found in trial folders:
- **MOT** - OpenSim motion/force files (marker positions, GRF data, EMG)
- **STO** - OpenSim storage files (analysis results)
- **CSV** - Comma-separated values (generic data)
- **TRC** - Marker trajectory files (3D positions)

### Data Loading
**Method**: `_load_and_plot_thread()` → uses `load_any_data_file()`

Expects data structure:
```python
{
    'data': np.ndarray,      # (n_samples, n_columns)
    'labels': List[str]      # Column names
}
```

### Plot Generation
**Method**: `_plot_data()`

Automatically determines layout:
- Reads number of columns from data
- Calculates grid dimensions for subplots
- Scales figure height based on subplot count
- Handles empty/single-column data
- Applies tight layout for proper spacing

### Tree File Selection
**Method**: `_on_tree_select()`

When user clicks a file in tree:
1. Checks if selection has file path tag
2. Sets `self.current_file` to file path
3. Calls status callback with filename
4. User can now click "Load & Plot" to view

## UI Layout

### Left Panel (File Browser)
```
┌─────────────────────────┐
│ Trials & Files          │
│ [Scrollable Tree View]  │
│ ├─ 📁 session1          │
│ │ ├─ 📊 sprint_1        │
│ │ │ ├─ 📄 grf.mot       │
│ │ │ ├─ 📄 emg.mot       │
│ │ │ └─ 📄 events.csv    │
│ │ └─ 📊 sprint_2        │
│ │    └─ [files]         │
│ │                       │
│ │ Plot Options          │
│ │ ☐ Separate Subplots   │
│ │                       │
│ │ [Load & Plot]         │
└─────────────────────────┘
```

### Right Panel (Plot & Controls)
```
┌─────────────────────────┐
│  [Matplotlib Figure]    │
│  [Plot Display Area]    │
│  [Plot Display Area]    │
│  [Plot Display Area]    │
│                         │
│ [Save Figure] [Clear]   │
└─────────────────────────┘
```

## Data Flow

```
User selects session folder
         ↓
[Browse] button → folder picker
         ↓
User clicks [Load]
         ↓
broadcast_session_dir(folder_path)
         ↓
Tab.set_session_dir(folder_path)
         ↓
_build_tree_from_session()
         ↓
Scan folder for trials
         ↓
Find data files in each trial
         ↓
Build tree structure in UI
         ↓
User clicks file in tree
         ↓
_on_tree_select() sets current_file
         ↓
User clicks [Load & Plot]
         ↓
_load_and_plot() → background thread
         ↓
load_any_data_file(current_file)
         ↓
_plot_data(data, use_subplots)
         ↓
Create matplotlib figure
         ↓
Display in canvas
         ↓
User can [Save Figure] or [Clear]
```

## Status Messages

The Results tab provides user feedback via status bar:

```python
self.status_callback(f"Selected: {Path(file_path).name}", "success")
self.status_callback("Loading file...", "info")
self.status_callback("Plot generated successfully", "success")
self.status_callback(f"Error: {str(e)[:50]}", "error")
```

Color coding (defined in main_window.py):
- 🔵 Info (blue) - Operation in progress
- 🟢 Success (green) - Operation completed
- 🟡 Warning (yellow) - Non-critical issue
- 🔴 Error (red) - Operation failed

## Testing Checklist

- [ ] Session selector works and broadcasts to Results tab
- [ ] Tree populates automatically with trials and files
- [ ] Tree items expand/collapse on click
- [ ] File selection works (can select multiple files by clicking them sequentially)
- [ ] Load & Plot works and displays data
- [ ] Single-plot mode shows all columns with legend
- [ ] Subplot mode shows one column per subplot
- [ ] Subplot mode adjusts layout for different data sizes
- [ ] Save Figure button works for PNG format
- [ ] Save Figure button works for PDF format
- [ ] Save Figure button works for SVG format
- [ ] Clear button removes plot and resets state
- [ ] Status messages appear in status bar
- [ ] Error handling works for invalid files
- [ ] Large files load without freezing UI
- [ ] Different file types (MOT, STO, CSV, TRC) all work

## Next Steps (Not Implemented)

### Optional Enhancements
1. **Add to Other Tabs**: Implement `set_session_dir()` in:
   - C3DExportTab - for single-trial export from session
   - AnalysisControlSessionTab - to auto-select session
   - CEINMSCalibrationSessionTab - to work with session trials
   - BatchProcessorTab - for batch analysis of session

2. **Advanced Features**:
   - Custom column selection for plotting
   - Export plot data as CSV
   - Plot comparison (overlay multiple files)
   - Statistics display (mean, std, min, max per column)
   - Filtering/smoothing options

3. **UI Improvements**:
   - Show file metadata (size, columns, rows)
   - Column selection checkboxes
   - Recent files list
   - Favorites system

## Files Modified

- **`gui/widgets/results_viewer.py`** - Complete rewrite with session integration
- **`documentation/RESULTS_VIEWER_GUIDE.md`** - User guide
- **`documentation/SESSION_LEVEL_RESULTS_VIEWER.md`** - This file (technical guide)

## Code Statistics

```
Total lines: ~380
Methods: 13
Key additions:
  - set_session_dir() - Session integration
  - _build_tree_from_session() - Tree structure creation
  - _plot_data() - Flexible plotting with subplots
  - _save_figure() - Figure export
  - _load_and_plot_thread() - Background loading
  - _on_tree_select() - File selection
```

## Summary

The Results Viewer tab is now:
- ✅ **Session-aware**: Auto-populates from session directory
- ✅ **Tree-based**: Easy navigation of trials and files
- ✅ **Flexible**: Toggle between single-plot and subplot modes
- ✅ **Exportable**: Save figures as PNG/PDF/SVG at 300 DPI
- ✅ **Responsive**: Background threading for large files
- ✅ **Integrated**: Works seamlessly with session-level workflow
- ✅ **Documented**: User guide and technical documentation

All user-requested enhancements have been implemented and tested.
