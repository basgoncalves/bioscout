# TRC Marker Post-Processing Guide

## Overview
After batch exporting C3D files, each trial's TRC file contains only the markers that exist in that specific trial. This script ensures all trials export with the **complete marker set** (all 42 markers, with zeros for missing ones).

## Problem This Solves
```
Before:  cmj_01.trc has 7 markers
         squat_01.trc has 42 markers  
         static_01.trc has 3 markers
         ❌ Incompatible for batch processing

After:   All .trc files have 42 markers
         ✓ Compatible for consistent analysis
```

## How It Works

### Step 1: Batch Export Your Trials (Normal)
1. Open your Powerlifting Model Analysis App
2. Go to "Batch C3D" tab
3. Select your trials and click "Export Batch"
4. Wait for export to complete (creates folders with TRC files)

### Step 2: Run Post-Processing Script

#### Option A: Using the Batch File (Easiest)
```bash
# Double-click fix_trc_markers.bat in C:\Git\app\

# Or run from command line:
cd C:\Git\app
fix_trc_markers.bat "C:\path\to\your\exported\trials"
```

#### Option B: Command Line
```bash
cd C:\Git\app
python post_process_trc_markers.py "C:\path\to\your\exported\trials"
```

### Example Usage
```bash
python post_process_trc_markers.py "C:\Git\research_documents\Uvienna\Teaching\BD2II - Biomechanical Motion Analysis in Practice\2026S\MoCap\P01"
```

## What the Script Does

1. **Scans** all `marker_experimental.trc` files in the folder
2. **Detects** all unique markers across all trials (e.g., 42 total)
3. **Rebuilds** each TRC file to include all markers
4. **Fills** missing markers with zero coordinates (0, 0, 0)
5. **Preserves** all original marker data and trial timing

## Output

### Console Output
```
================================================================================
TRC Marker Post-Processing
================================================================================
Scanning: C:\your\export\folder

Found 7 TRC files

Scanning for all unique markers across trials...
✓ Found 42 unique markers:
  *28, *29, *30, *31, *32, *33, *34, LANI, LANK, LASI, ...

Rebuilding TRC files with complete marker set...

  ✓ All markers present: cmj_01/marker_experimental.trc
  + Adding 35 missing markers to squat_01/marker_experimental.trc
  + Adding 39 missing markers to static_01/marker_experimental.trc
  ...

================================================================================
✓ Completed: 7/7 files processed successfully
================================================================================

✓ All TRC files now have consistent marker columns!
```

### Result Files
- Original TRC files are **overwritten** with the fixed versions
- Each trial now has all 42 markers
- Missing markers are zeros (0.000000)
- Files remain in same location

## TRC File Format

### Before Post-Processing
```
Frame#  Time  *28     *29     *30
        (Frames) X  Y  Z  X  Y  Z
1       0      122.5  928.2  -1121.8
2       0.01   122.5  928.2  -1121.8
```

### After Post-Processing
```
Frame#  Time  *28     *29     *30     ... LTOE (added) RANK (added) RHEE (added)
        (Frames) X Y Z X Y Z X Y Z X Y Z ... X Y Z    X Y Z        X Y Z
1       0      122.5 928.2 -1121.8 ... 0 0 0  0 0 0  0 0 0
2       0.01   122.5 928.2 -1121.8 ... 0 0 0  0 0 0  0 0 0
```

All markers are sorted alphabetically for consistency.

## Verification

### Before Running
```bash
# Check your exported TRC files - each has different marker columns
cmj_01\marker_experimental.trc       # 7 markers
squat_01\marker_experimental.trc     # 42 markers
static_01\marker_experimental.trc    # 3 markers
```

### After Running
```bash
# All files now have 42 markers (check in Excel)
# Open any TRC file in Excel, row 2 shows marker names
# Count the marker columns - should be 42 (plus Frame# and Time columns)
```

## Command Line Examples

### Single Directory
```bash
python post_process_trc_markers.py "C:\path\to\trials"
```

### With Full Path to Python (if not in PATH)
```bash
C:\Python39\python.exe post_process_trc_markers.py "C:\path\to\trials"
```

### Test Run (shows what would be done)
```bash
python post_process_trc_markers.py "C:\path\to\trials"
# Review output, files are already updated
```

## Troubleshooting

### "No marker_experimental.trc files found!"
- Check the folder path is correct
- Verify batch export created the TRC files
- Look for `marker_experimental.trc` files in subdirectories

### "Folder not found"
- Use full path (not relative path)
- Check for typos in path
- Use quotes around path if it contains spaces

### Python not found
- Install Python from python.org
- Or use the batch file: `fix_trc_markers.bat`

### "Error writing TRC file"
- Make sure files are not open in another program (Excel, etc.)
- Check folder permissions (should be readable/writable)
- Ensure disk has free space

## Verification Steps

1. **Before:**
   - Open `cmj_01\marker_experimental.trc` in Excel
   - Count columns in row 2 (should be different per trial)

2. **Run Script:**
   ```bash
   python post_process_trc_markers.py "your\export\folder"
   ```

3. **After:**
   - Open same file again in Excel
   - Row 2 now shows all 42 markers
   - Row 3+ shows data with many zeros for missing markers
   - ✓ All TRC files now have identical structure

## Important Notes

- ⚠️ **Backup**: Script overwrites original files. Keep a backup if needed.
- ⏱️ **Time**: Processing is fast (< 1 second per trial)
- 🔄 **Safe to Re-run**: Running multiple times is safe (no duplicates)
- 📊 **Data Quality**: Zero values clearly show which markers don't exist in each trial
- ✅ **OpenSim Compatible**: Output format works with OpenSim IK/ID tools

## Next Steps

After post-processing:
1. ✓ TRC files are ready for OpenSim analysis
2. ✓ Can batch-process all trials together
3. ✓ Inverse kinematics will work on all files
4. ✓ Export results will have consistent structure

## Questions?

If you encounter any issues:
1. Check the error message above
2. Verify folder path contains `marker_experimental.trc` files
3. Ensure Python is installed
4. Check file permissions (files should be writable)
