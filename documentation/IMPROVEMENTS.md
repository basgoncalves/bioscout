# Improvements to Powerlifting Model Analysis App v2

## What's New

### 🎯 Simplified Single-Click Analysis
The redesigned Analysis tab now makes it super easy to run analyses:

1. **Select your directory** (trial or entire session)
2. **Pick analysis steps** using quick presets or checkboxes
3. **Click "Run Analysis"** - Done!

### 📁 Dual-Level Analysis Support

#### **Trial-Level Analysis** (Single Trial)
- Analyze one trial at a time
- Perfect for quick validation or specific trials
- Results saved to that trial's directory

#### **Session-Level Analysis** (Entire Session)
- Analyze ALL trials in a session at once
- Ideal for CEINMS calibration (needs multiple trials)
- Progress tracking for all trials
- Summary report at the end

**How to use:**
1. Browse to a session directory
2. Select "Entire Session" radio button
3. Choose your steps
4. Click "Run Analysis"
5. App automatically processes all trials in order

### 📋 Input File Management

#### **Auto-Detection**
App automatically finds:
- C3D files (motion capture)
- Marker files (TRC format)
- EMG files (MOT format)
- GRF files (ground reaction forces)
- Event files (CSV)

#### **Quick Selectors**
If multiple files are found, dropdown menus let you switch between them instantly without browsing.

#### **"Reload Files" Button**
Updates the file list - useful if you added new files to the directory.

### ⚙️ Settings File Integration

#### **trial_settings.xml Support**
- App can read/write settings from `trial_settings.xml`
- Persistent configuration per trial

#### **Edit Settings Button**
- Click to open settings file in your default editor
- Auto-creates default settings if file doesn't exist
- Changes take effect immediately

### 🎨 Cleaner UI Design

**Before:**
- Complex checkbox grid
- Hard to distinguish steps
- Single-trial only
- No file management

**Now:**
- Grouped step categories (Core, Extended, EMG, CEINMS)
- Large "Run Analysis" button (hard to miss!)
- Input file browser on the left
- Session-level toggle for easy switching
- Status updates in real-time

### ⚡ Key Features

| Feature | Benefit |
|---------|---------|
| **Session Analysis** | Process all trials at once (no manual loop) |
| **Auto File Detection** | Finds input files automatically |
| **File Dropdowns** | Quickly switch between files without browsing |
| **Settings Integration** | Load/save per-trial configuration |
| **Progress Tracking** | See which trial is running and overall progress |
| **Large Run Button** | Can't miss when you're ready to go |
| **Simplified Presets** | "IK Only" for validation, "Full" for complete analysis |

## Usage Examples

### Example 1: Quick IK Validation
```
1. Browse to trial directory
2. Click "IK Only" preset
3. Click "Run Analysis"
4. Wait 2-3 minutes
5. Done!
```

### Example 2: Full CEINMS Analysis (Single Trial)
```
1. Browse to trial directory
2. Select individual steps OR use custom preset
3. Click "Run Analysis"
4. Monitor progress in output log
```

### Example 3: CEINMS Calibration (Entire Session)
```
1. Browse to session directory
2. Select "Entire Session" radio button
3. Choose analysis steps
4. Click "Run Analysis"
5. App processes all trials in session
6. View summary when done
```

### Example 4: Change Input Files
```
1. Browse to trial
2. App auto-detects C3D, markers, EMG files
3. If multiple files found, use dropdowns to switch
4. Click "Reload Files" if you added new files
5. Run analysis
```

## Technical Details

### Session Analysis
When you select "Entire Session":
- App looks for all subdirectories in the session folder
- Each subdirectory is treated as a trial
- Runs analysis on each trial sequentially
- Tracks success/failure for each
- Provides summary at end

### Input File Detection
Searches for common file patterns:
- `*.c3d` → C3D motion capture
- `*marker*.trc` → Marker files
- `*emg*.mot` → EMG data
- `*grf*.mot` → Ground reaction forces
- `*.csv` → Event files

### Settings File
- Located at: `trial_directory/trial_settings.xml`
- Auto-created if doesn't exist
- Can be edited directly or via app's "Edit Settings" button
- Contains trial metadata and configuration

## File Structure

```
trial/
  ├── data.c3d
  ├── markers.trc
  ├── emg.mot
  ├── grf.mot
  ├── trial_settings.xml      ← App reads/writes this
  ├── results/
  │   ├── ik_results/
  │   ├── id_results/
  │   └── so_results/
  ...
```

## Migration from Old Version

If you have the old Analysis tab still, no changes needed! The new version does everything the old one did plus more.

The new features are:
- **Non-breaking**: Old trial-level analysis still works
- **Additive**: Session-level analysis is new capability
- **Compatible**: All existing analysis scripts work unchanged

## Performance Tips

1. **Session analysis**: Use for same analysis type on many trials
2. **Parallel**: Could be extended for true parallelization (future)
3. **Validation**: Use "IK Only" first to check data before full analysis

## Next Steps (Possible Enhancements)

- [ ] Parallel processing for session analysis (run multiple trials simultaneously)
- [ ] Drag-drop support for directories
- [ ] Analysis history/logging
- [ ] Comparison plots across session
- [ ] Configuration templates (save/load)
- [ ] Batch queue (multiple sessions)

## Known Limitations

- Session analysis runs sequentially (one trial at a time)
- Settings UI only available via external editor (for now)
- No real-time filtering of which trials to process

## Troubleshooting

**"No input files found"**
→ Check files are in the trial directory and named according to patterns

**"Failed to prepare analysis"**
→ Check trial directory contains required input files

**Settings file won't open**
→ Try creating it first with "Edit Settings" button

**Session analysis is slow**
→ Normal - each trial takes 10-30 minutes depending on parameters

---

## Summary

The improved app now makes it **trivial to run single-trial analysis** and adds the powerful capability to **analyze entire sessions at once** - perfect for CEINMS calibration and other workflows that need multiple trials processed together.

Enjoy! 🚀
