# Quick Start Guide - OpenSim GRF Viewer
**For:** Powerlifting Model Analysis App  
**Version:** May 13, 2026  
**Status:** Ready to Launch

---

## Installation (One-Time Setup)

### 1. Install OpenSim
**Option A: Using Conda (Recommended)**
```bash
conda install -c conda-forge opensim-core>=4.4
```

**Option B: Using pip**
```bash
pip install opensim
```

### 2. Install GUI Dependencies
```bash
cd code/tests/app
pip install -r requirements.txt
```

Or manually:
```bash
pip install customtkinter>=5.0.0 numpy pandas matplotlib PyYAML
```

### 3. Verify Installation
```bash
python3 -c "import opensim; import customtkinter; print('✓ Ready')"
```

---

## Running the Application

### Launch from Command Line
```bash
cd code/tests/app
python3 run.py
```

The GUI window should open in a few seconds.

---

## Testing the GRF Viewer

### Quick Test (5 minutes)

1. **Navigate to C3D Export tab**
   - Look for the "C3D Export" tab at the top

2. **Load a C3D File**
   - Click "Browse C3D File"
   - Navigate to: `models/tps/motion_lab/Static_01/c3dfile.c3d`
   - Click "Open"

3. **View GRF Channels**
   - On the left side, you should see a list of GRF channels:
     - ground_force_1_vx
     - ground_force_1_vy
     - ground_force_1_vz
     - ground_moment_1_mx
     - etc.

4. **Test Channel Selection**
   - Click "All" to select all channels
   - Plot on the right should update with all channels
   - Click "None" to deselect all
   - Plot should show "No channels selected"

5. **Test Plotting**
   - Select a few channels (e.g., ground_force_1_vx, ground_force_1_vy, ground_force_1_vz)
   - Plot should show time-series graphs for each selected channel
   - X-axis should show time in seconds
   - Y-axis should show force/moment values

6. **Test Cropping**
   - Adjust the "Start" and "End" sliders
   - Plot should automatically update to show only the selected time range
   - Time range label should update (e.g., "0.25 - 1.75 s")

7. **Test Manual Time Entry**
   - In the "Start (s)" and "End (s)" fields, enter specific time values
   - Press Enter
   - Plot should update to show that time range

### Full Workflow Test (15 minutes)

1. **Load Multiple C3D Files**
   - Test with different C3D files from `simulations/` directory
   - Verify channels load correctly for each

2. **Export Data**
   - After viewing GRF data, you can export it
   - Click "Export" button
   - Verify files are generated in output folder:
     - `marker_experimental.trc`
     - `grf.mot`
     - `emg.mot`
     - `emg_filtered.mot`
     - `analog.csv`
     - `trial_settings.xml`

3. **Check Console Output**
   - Open a terminal window (keep it open while app runs)
   - Watch for console messages like:
     ```
     [INFO] Loading C3D file with OpenSim: c3dfile.c3d
     [OK] Loaded GRF data: 18 channels, 1500 frames
     [OK] Found 18 GRF channels
     ```

---

## Expected Behavior

### GRF Channels Should Display As:
```
ground_force_1_vx    (Force X on plate 1)
ground_force_1_vy    (Force Y on plate 1)
ground_force_1_vz    (Force Z on plate 1)
ground_moment_1_mx   (Moment X on plate 1)
ground_moment_1_my   (Moment Y on plate 1)
ground_moment_1_mz   (Moment Z on plate 1)
```

### Plot Should Show:
- **X-axis:** Time in seconds (e.g., 0.0, 0.5, 1.0, 1.5, 2.0)
- **Y-axis:** Force/Moment values
- **Grid:** Dashed lines for clarity
- **Line color:** Blue (#0099ff)
- **Multiple subplots:** One for each selected channel

---

## Troubleshooting

### Issue: "OpenSim module not available"
**Solution:** Install opensim
```bash
conda install -c conda-forge opensim-core>=4.4
```

### Issue: "No channels appear in list"
**Possible causes:**
1. C3D file doesn't have force plate data
2. OpenSim failed to load the file
3. **Check console output** for error messages

**Solution:**
- Try a different C3D file
- Check that file contains force plate data
- Look for error messages in console

### Issue: "Plot doesn't update when I select channels"
**Solution:**
1. Make sure you clicked the checkbox
2. Wait a moment for plot to render
3. Check console for error messages
4. Try clicking "All" to select all channels at once

### Issue: "Sliders don't affect the plot"
**Solution:**
1. Make sure at least one channel is selected
2. Wait for plot to update
3. Try entering time values manually in the fields
4. Press Enter after typing time values

### Issue: "Application won't start"
**Steps:**
1. Check Python version: `python3 --version` (should be 3.8+)
2. Verify all packages installed: `pip list | grep -E "customtkinter|opensim|numpy|pandas"`
3. Run with verbose output: `python3 -u run.py` (shows errors as they happen)
4. Check for error messages in console

---

## File Locations for Testing

### Test C3D Files (pick any):
```
models/tps/motion_lab/Static_01/c3dfile.c3d
models/tps/motion_lab/static/static_01/static_01.c3d
simulations/Athlete_03/25_03_31/Squat_BW_01/c3dfile.c3d
simulations/Athlete_03/25_03_31/Walking_02/c3dfile.c3d
```

### Output Folder:
```
code/tests/app/output/
```
(Files are saved here after export)

---

## Expected Console Output

### On Successful Load:
```
================================================================================
[START] Processing c3dfile.c3d
[INFO] Loading C3D file with OpenSim: c3dfile.c3d
[OK] Loaded GRF data: 18 channels, 1500 frames
[OK] Found 18 GRF channels
[INFO] Exporting markers...
[OK] Markers exported to marker_experimental.trc (6 selected)
[INFO] Exporting Ground Reaction Force (GRF) data...
[OK] GRF exported to grf.mot
[INFO] Exporting EMG channels...
[OK] EMG exported to emg.mot
[INFO] Generating emg_filtered.mot and analog.csv...
[OK] Generated emg_filtered.mot
[OK] Generated analog.csv
[INFO] Creating trial_settings.xml with EMG parameters...
[OK] Created trial_settings.xml at /path/to/output/trial_settings.xml
[SUCCESS] Export process completed!
================================================================================
```

---

## What to Check

### ✅ Layout
- [ ] Channels list on LEFT side
- [ ] Plot on RIGHT side
- [ ] Plot expands when window is resized
- [ ] All/None buttons visible at top of channel list
- [ ] Sliders and time entry fields visible below channels

### ✅ Functionality
- [ ] Channels load when C3D selected
- [ ] All/None buttons work
- [ ] Checkboxes update plot when clicked
- [ ] Sliders adjust time range
- [ ] Time entries accept values in seconds
- [ ] Plot shows proper axis labels

### ✅ Data Quality
- [ ] X-axis shows time in seconds
- [ ] Y-axis shows numeric values
- [ ] Grid lines are visible
- [ ] Multiple subplots for multiple channels
- [ ] Line color is consistent (blue)

### ✅ Export
- [ ] Export button creates output folder
- [ ] Folder contains all expected files
- [ ] Files are not empty
- [ ] trial_settings.xml has correct parameters

---

## Next Steps After Successful Testing

1. **Validate output files** - Check that exported .mot and .csv files are correct
2. **Test with different C3D files** - Try various motion capture files
3. **Check data accuracy** - Compare plots with original C3D viewer
4. **Run full pipeline** - Test integration with OpenSim analysis
5. **Performance testing** - Try large C3D files and monitor memory

---

## Support

If you encounter issues:
1. Check the console output (error messages appear here first)
2. Look at `VALIDATION_REPORT_GRF_VIEWER_2026_05_13.md` for technical details
3. Review `OPENSIM_API_FIXES.md` for API troubleshooting
4. Check log files in `code/tests/app/logs/` directory

---

**Status:** ✅ Application is ready to run  
**Last Updated:** 2026-05-13  
**All systems operational**
