# Settings Loading & Saving - Implementation Guide

## Overview

The GUI app now properly integrates with your `utils.Analyse` class XML format. It:

1. **Loads** settings from existing `trial_settings.xml` files
2. **Auto-generates** default settings from a template if file doesn't exist
3. **Populates** GUI checkboxes based on loaded settings
4. **Saves** settings preserving all existing attributes

---

## File Locations

### Template File (New)
```
C:\Git\powerlifing_model_clean\code\tests\app\config\trial_settings_template.xml
```

This template contains all default attributes from the `Analyse` class:
- Paths and directories
- File names (c3d, markers, EMG, GRF, etc.)
- CEINMS parameters (alpha, beta, gamma)
- Analysis settings
- Output file names

### Trial Settings File
```
C:\Git\powerlifing_model_clean\simulations\Athlete_03\25_03_31\Squat_bw_01\trial_settings.xml
```

This file is:
- **Auto-generated** on first load (from template)
- **Loaded** when you select a trial directory
- **Updated** when you click "Save Settings"

---

## How It Works

### 1. User Selects a Trial Directory

```
1. Click "Browse" or paste a path
2. GUI loads the directory
3. _load_path() is called
```

### 2. Settings Are Loaded

```python
def _load_path(self, path: str) -> None:
    """Load and process a trial/session path."""
    self.current_path = Path(path)
    self.path_var.set(str(self.current_path))
    self._reload_input_files()
    self._load_trial_settings()  # NEW: Load settings from XML
    self._log_message(f"✓ Loaded: {path}")
```

### 3. Load Trial Settings

If `trial_settings.xml` **exists**:
- Parse the XML file
- Extract `<analysis_level>` (trial or session)
- Extract `<analysis_steps>` list
- Update GUI checkboxes to match
- Load all other settings for display

If `trial_settings.xml` **doesn't exist**:
- Generate from template
- Extract subject/session from folder structure
- Save as default settings
- GUI loads from newly generated file

### 4. User Makes Changes

- Checks/unchecks analysis step checkboxes
- Toggles between "Single Trial" and "Entire Session"

### 5. User Clicks "Save Settings"

```python
def _save_settings_file(self) -> None:
    """Save current settings to trial_settings.xml file, preserving all existing attributes."""
```

Process:
1. Read existing `trial_settings.xml` to preserve ALL attributes
2. Update only `<analysis_level>` and `<analysis_steps>`
3. Keep everything else unchanged
4. Save with pretty XML formatting

---

## Template File Structure

Location: `config/trial_settings_template.xml`

```xml
<?xml version="1.0" ?>
<TrialSettings>
   <!-- Metadata -->
   <replace>False</replace>
   <path>.</path>
   <settingsXML>trial_settings.xml</settingsXML>
   <subject>Unknown</subject>
   <session>Unknown</session>
   <trial>Unknown</trial>
   
   <!-- Model -->
   <model_name>model.osim</model_name>
   <model_dir>.</model_dir>
   <body_mass>0.0</body_mass>
   
   <!-- Input Files -->
   <c3d>data.c3d</c3d>
   <markers>markers.trc</markers>
   <emg>emg.mot</emg>
   <grf_mot>grf.mot</grf_mot>
   <events>events.csv</events>
   
   <!-- Setup Files -->
   <setup_ik>setup_IK.xml</setup_ik>
   <setup_id>setup_ID.xml</setup_id>
   <setup_so>setup_SO.xml</setup_so>
   <!-- ... and many more ... -->
   
   <!-- Analysis Configuration (Updated by GUI) -->
   <analysis_steps>
      <step>inverse_kinematics</step>
   </analysis_steps>
   <analysis_level>trial</analysis_level>
</TrialSettings>
```

---

## Generated Settings File Example

When you select a trial at `Athlete_03/25_03_31/Squat_bw_01/`:

Generated `trial_settings.xml`:
```xml
<?xml version="1.0" ?>
<TrialSettings>
   <replace>False</replace>
   <path>.</path>
   <settingsXML>trial_settings.xml</settingsXML>
   <subject>Athlete_03</subject>
   <session>25_03_31</session>
   <trial>Squat_bw_01</trial>
   <!-- ... template defaults ... -->
   <analysis_steps>
      <step>inverse_kinematics</step>
   </analysis_steps>
   <analysis_level>trial</analysis_level>
</TrialSettings>
```

Subject and session are **auto-extracted** from folder structure!

---

## What Happens When You Save Settings

Before:
```xml
<analysis_steps>
   <step>inverse_kinematics</step>
</analysis_steps>
<analysis_level>trial</analysis_level>
```

After selecting IK, ID, SO and clicking "Save Settings":
```xml
<analysis_steps>
   <step>inverse_kinematics</step>
   <step>inverse_dynamics</step>
   <step>static_optimization</step>
</analysis_steps>
<analysis_level>trial</analysis_level>
```

**All other attributes remain unchanged** (paths, filenames, etc.)

---

## Key Methods Added

### `_load_trial_settings()`
- Called when directory is loaded
- Reads existing XML or generates default
- Populates GUI checkboxes

### `_generate_default_settings(settings_file)`
- Creates default `trial_settings.xml` from template
- Extracts subject/session from folder path
- Saves to trial directory

### `_save_settings_file()`
- Reads existing settings (preserves all attributes)
- Updates only analysis_level and analysis_steps
- Saves with pretty XML formatting

### `_save_pretty_xml(tree, path)`
- Formats XML with proper indentation
- Removes blank lines
- Matches your utils.py style

---

## Data Flow

```
User selects directory
    ↓
_load_path()
    ↓
_reload_input_files()
_load_trial_settings()  ← NEW
    ↓
Check if trial_settings.xml exists
    ├─ YES: Parse and load
    └─ NO: Generate from template
    ↓
Populate GUI with loaded settings
(checkboxes, analysis level, etc.)
    ↓
User makes changes
    ↓
Click "Save Settings"
    ↓
_save_settings_file()
    ├─ Read existing XML
    ├─ Update analysis_steps and level
    └─ Save with pretty formatting
    ↓
Settings preserved for next session
```

---

## Settings Persistence

Once you set analysis steps for a trial:

1. Settings are saved to `trial_settings.xml`
2. Next time you open the app and select that trial
3. GUI automatically loads and checks those steps
4. You can modify and save again

Example workflow:
```
Session 1:
- Select trial
- Check: IK, ID, SO
- Click "Save Settings"
- Close app

Session 2:
- Open app
- Select same trial
- GUI shows: IK ✓, ID ✓, SO ✓ (automatically!)
- Modify: uncheck ID
- Save again
```

---

## Template Customization

To customize defaults for your biomechanics workflow:

1. Edit `config/trial_settings_template.xml`
2. Update file paths, parameters, etc.
3. When new trials are loaded, they'll use your custom template
4. Existing trials keep their saved settings

---

## Comparison: Before & After

### Before
- GUI saved minimal XML with only metadata
- Didn't load settings back
- Checkboxes always unchecked on reload
- No integration with Analyse class

### After
- GUI loads comprehensive XML from template
- Settings auto-populate checkboxes
- Subject/session auto-extracted from path
- Full integration with Analyse class format
- Settings persist across sessions
- Preserves all Analyse attributes

---

## Troubleshooting

### "No input files found" but files exist
→ Check if XML loads correctly
→ Try "Reload Files" button

### Settings don't persist
→ Check that "Save Settings" button was clicked
→ Verify trial_settings.xml was created
→ Check for write permissions in trial folder

### Wrong subject/session
→ Folder structure must be: `subject/session/trial/`
→ Auto-extract looks for path parts [-3] and [-2]
→ Manually edit settings file if needed

### Template not found
→ Ensure `config/trial_settings_template.xml` exists
→ Check file path: `config/` folder in app directory

---

## File Locations Summary

```
C:\Git\powerlifing_model_clean\code\tests\app\
├── config/
│   └── trial_settings_template.xml    ← Template (EDIT THIS for defaults)
└── gui/
    └── widgets/
        └── analysis_control_v2.py     ← Loading/saving logic (UPDATED)

C:\Git\powerlifing_model_clean\simulations\
└── Athlete_03\25_03_31\Squat_bw_01\
    └── trial_settings.xml             ← Per-trial settings (AUTO-GENERATED + SAVED)
```

---

## Next Steps

1. **Test it:**
   ```bash
   python run.py
   ```

2. **Select a trial** without existing settings
   → Settings file should auto-generate
   → Check `trial_settings.xml` was created

3. **Select steps and click "Save Settings"**
   → File should update with your selections

4. **Reload the app and select same trial**
   → Checkboxes should automatically load your saved steps

5. **Modify and save again**
   → Settings should persist for future sessions

---

## Summary

Your settings workflow is now:

1. **Auto-generate** defaults from template (first time)
2. **Load** from XML when selecting trials
3. **Display** loaded settings in GUI
4. **Save** updates while preserving all attributes
5. **Persist** settings across sessions

The app fully integrates with your `Analyse` class XML format! 🎯
