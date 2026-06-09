# Results Viewer Tab - User Guide

## Overview
The Results Viewer tab provides a comprehensive interface for viewing and analyzing exported analysis data. It features a tree-based file structure showing all trials and their data files, with options for flexible visualization and export.

## Key Features

### Tree-Based File Structure
- **Session-aware**: Automatically scans selected session for all trials
- **Expandable trials**: Click trial folders to see all available data files
- **Supported file types**:
  - MOT files (OpenSim motion files)
  - STO files (OpenSim storage files)
  - CSV files (comma-separated data)
  - TRC files (marker trajectory files)

### Plot Visualization
- **Single-plot mode**: All columns plotted on one graph (with legend)
- **Subplot mode**: Each column gets its own subplot for detailed analysis
- **Interactive plots**: Zoom, pan, and interact with matplotlib figures
- **Auto-scaling**: Layout automatically adjusts based on number of columns

### Save & Export
- **Save Figure**: Export plots as PNG, PDF, or SVG
- **High resolution**: Saves at 300 DPI for publication quality
- **Multiple formats**: Choose the best format for your needs

## How to Use

### 1. Select a Session (Top of App)
```
Session: [your_session_path] [Browse] [Load]
```
- Click "Browse" to select your session folder
- Click "Load" to apply the session to Results tab
- The tree will auto-populate with all trials and their files

### 2. Navigate to Results Viewer
Click "Results" in the sidebar

### 3. Browse Trials and Files
- The left panel shows a tree structure:
  - 📁 Session Name
    - 📊 Trial 1
      - 📄 marker_experimental.trc
      - 📄 grf.mot
      - 📄 emg.mot
      - 📄 events.csv
    - 📊 Trial 2
      - Files...

### 4. Select a Data File
Click on any file in the tree to select it. The selection is highlighted.

### 5. Choose Plot Options
- **Separate Subplots**: Toggle to show each column in its own subplot
  - Unchecked: All columns on one graph (recommended for comparing signals)
  - Checked: Each column has its own subplot (recommended for detailed analysis)

### 6. Load & Plot
Click "Load & Plot" button to:
- Load the selected file
- Parse the data
- Generate the visualization
- Display in the right panel

### 7. Save Figure (Optional)
Click "Save Figure" to:
- Choose save location
- Select file format (PNG, PDF, SVG)
- Export at 300 DPI resolution

### 8. Clear Plot
Click "Clear" to:
- Remove current plot
- Reset the viewer
- Ready for next file

## Plot Modes

### Single-Plot Mode (Default)
```
Separate Subplots: [X]  ← unchecked
```
- All data columns plotted on one graph
- Good for comparing multiple signals
- Includes legend showing all columns
- Better for signals with similar scales

Example: Plotting EMG data from multiple muscles
- All muscle activations on one plot
- Easy to see temporal relationships
- Can identify muscle synergies

### Subplot Mode
```
Separate Subplots: [✓]  ← checked
```
- Each column gets its own subplot
- Grid layout: 3 columns per row
- Good for detailed individual analysis
- Better for signals with different scales

Example: Plotting joint angles and moments
- Separate plots for hip angle, knee angle, ankle angle, etc.
- Each with its own Y-axis scale
- Easier to spot anomalies in individual channels

## Supported File Formats

### MOT Files (OpenSim Motion)
- Format: Text-based with header and data sections
- Contents: Can be marker positions, forces, EMG, etc.
- Example channels: FX, FY, FZ (force components), time-series data

### STO Files (OpenSim Storage)
- Format: Similar to MOT but typically for analysis results
- Contents: Can be muscle forces, joint moments, activations, etc.
- Example channels: soleus_force, tibialis_force, etc.

### CSV Files
- Format: Comma or tab-separated values
- Contents: Any numeric data (flexible)
- Example: phase timing, event detection, custom analysis

### TRC Files (Marker Trajectories)
- Format: OpenSim marker position format
- Contents: 3D marker positions (X, Y, Z per marker)
- Example: LASI (left anterior superior iliac spine), RASI, etc.

## File Information

When browsing the tree, file icons indicate:
- 📄 **Data file** - Ready to load and plot

## Workflow Example

### Example 1: Compare Multiple Trials
1. Select session with sprinting trials: sprint_1, sprint_2, sprint_3
2. Load marker_experimental.trc from sprint_1
3. Observe hip, knee, ankle angles
4. Switch to sprint_2's marker file (just click in tree)
5. Click "Load & Plot" to view for comparison
6. Note differences between trials

### Example 2: Detailed EMG Analysis
1. Select session with EMG data
2. Click emg.mot from sprint_1 trial
3. Enable "Separate Subplots"
4. Click "Load & Plot"
5. View each muscle activation separately
6. Identify activation patterns and timing
7. Save figure for report: "Save Figure" → PNG format

### Example 3: Export Results for Paper
1. Load analysis results (usually STO files)
2. Plot without subplots (single plot mode)
3. Customize plot (if needed, using "Save Figure")
4. Save as PDF for: "Save Figure" → PDF format
5. Insert into manuscript

## Data File Organization in Session

Expected structure after C3D Export and Batch processing:

```
/session1/
├── sprint_1.c3d              ← Source (not viewed in Results)
├── sprint_1/                 ← Trial folder
│   ├── marker_experimental.trc   ← Viewable
│   ├── grf.mot                   ← Viewable
│   ├── emg.mot                   ← Viewable
│   ├── emg_filtered.mot          ← Viewable
│   ├── events.csv                ← Viewable
│   ├── trial_settings.xml        ← Viewable
│   └── analog.csv                ← Viewable
├── sprint_2/
│   └── [same files]
└── walking_1/
    └── [same files]
```

All files in trial folders are available in the Results Viewer tree.

## Best Practices

1. **Always load session first**
   - Use Browse/Load buttons at top
   - This ensures tree shows all trials

2. **Use single-plot for overview**
   - Good for first inspection
   - Shows overall data structure
   - Can see relationships between signals

3. **Switch to subplots for detail**
   - When single plot is too crowded
   - When analyzing individual columns
   - When comparing channels of different scales

4. **Save high-quality figures**
   - Use "Save Figure" → PDF for publications
   - Use PNG for presentations
   - All saved at 300 DPI

5. **Keep data organized**
   - Use descriptive trial folder names
   - Keep all files for a trial in one folder
   - Run full export pipeline to generate all files

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Tree is empty | Load session first using Browse/Load buttons |
| File won't load | Check file format is MOT, STO, CSV, or TRC |
| Plot looks wrong | Try different subplot setting |
| Can't save figure | Load a file and plot it first |
| Too many subplots | Switch to single-plot mode for overview |
| Can't find file | Ensure trial folder has data files (run export) |

## Technical Details

### Supported Data Shapes
- Matrix: Time samples × Columns (e.g., 1000 samples × 3 coordinates)
- Single column: Time samples × 1 (e.g., EMG single channel)
- Multiple columns: Flexible number of channels

### Plot Layout Algorithm
```
If Separate Subplots:
    rows = ceil(num_cols / 3)
    grid = rows × 3
    figure_height = max(4, rows × 2) inches
Else:
    Single plot with all columns
    figure_height = 4 inches
```

### File Detection
Results Viewer automatically finds files with these extensions:
- `.mot` - OpenSim motion/force files
- `.sto` - OpenSim storage/results files
- `.csv` - Comma-separated values
- `.trc` - Marker trajectory files

## Session Integration

The Results Viewer fully integrates with the session-level architecture:

```
┌─────────────────────────────────┐
│ Session: [folder] [Browse] [Load]  │  ← Global session selector
├─────────────────────────────────┤
│ Results Viewer Tab              │
├─────────────────────────────────┤
│ Received session from top bar ✓ │
│ Auto-scanned trials: 3          │
│ Ready to browse files           │
└─────────────────────────────────┘
```

When you click "Load" in the topbar:
1. Session directory is broadcast to all tabs
2. Results Viewer receives the path
3. Tree automatically populates with trials and files
4. Ready to browse and plot

## Summary

The Results Viewer provides:
- ✅ **Tree-based browsing** - Easy navigation of trials and files
- ✅ **Session-aware** - Auto-populates from session directory
- ✅ **Flexible plotting** - Single plot or subplots per file
- ✅ **High-quality export** - Save figures as PNG/PDF/SVG
- ✅ **Interactive** - Click files to select, load and plot
- ✅ **Integrated** - Works seamlessly with batch export workflow
