# Settings System - Quick Reference

## What Changed

✅ **Template File Created**
- Location: `config/trial_settings_template.xml`
- Contains all default Analyse class attributes
- Auto-used when generating new trial settings

✅ **Settings Loading Implemented**
- GUI now reads `trial_settings.xml` when selecting trial
- Checkboxes auto-populate from loaded settings
- Analysis level (trial vs session) is preserved

✅ **Settings Auto-Generation**
- If trial has no `trial_settings.xml`, one is created from template
- Subject and session auto-extracted from folder structure
- File is ready to use immediately

✅ **Settings Persistence**
- Settings saved when you click "Save Settings"
- All existing attributes preserved (only analysis steps/level updated)
- Pretty XML formatting (matches your utils.py style)

✅ **File Structure Integration**
- Uses `<TrialSettings>` root (matching Analyse class)
- Reads/writes with proper indentation
- Compatible with your existing code

---

## The Workflow

```
1. USER SELECTS TRIAL
   ↓
2. GUI LOADS DIRECTORY
   ↓
3. APP CHECKS FOR trial_settings.xml
   ├─ EXISTS: Load it
   └─ MISSING: Generate from template
   ↓
4. GUI DISPLAYS LOADED SETTINGS
   (checkboxes auto-populated)
   ↓
5. USER SELECTS ANALYSIS STEPS
   ↓
6. USER CLICKS "SAVE SETTINGS"
   ↓
7. XML FILE UPDATED
   (all other attributes preserved)
   ↓
8. NEXT TIME: Settings auto-load
```

---

## Files Involved

| File | Purpose | Created/Updated |
|------|---------|-----------------|
| `config/trial_settings_template.xml` | Default template | **CREATED** |
| `gui/widgets/analysis_control_v2.py` | Loading/saving logic | **UPDATED** |
| `trial_directory/trial_settings.xml` | Trial settings | Auto-generated on first load |

---

## What Gets Saved

Only these are updated by GUI:
```xml
<analysis_level>trial</analysis_level>
<analysis_steps>
   <step>inverse_kinematics</step>
   <step>inverse_dynamics</step>
   <step>static_optimization</step>
</analysis_steps>
```

Everything else (paths, filenames, CEINMS params, etc.) is **preserved** from template/existing file.

---

## What Gets Loaded

When GUI loads a trial:
- ✅ `<analysis_level>` → Sets radio button
- ✅ `<analysis_steps>` → Checks matching checkboxes
- ✓ All other attributes → Preserved internally

---

## Testing

```bash
# 1. Launch app
python run.py

# 2. Select a trial (with no trial_settings.xml)
# → Should generate default settings

# 3. Check some analysis steps
# → IK, ID, SO for example

# 4. Click "Save Settings" (green button)
# → XML file should be created/updated

# 5. Check the generated file
cat "trial_directory/trial_settings.xml"
# → Should show your selected steps

# 6. Reload app, select same trial
# → Checkboxes should auto-populate!
```

---

## Key Improvements

| Before | After |
|--------|-------|
| Minimal XML created | Full Analyse-compatible XML |
| Settings not loaded | Settings auto-load |
| Checkboxes always empty | Checkboxes auto-populate |
| No persistence | Settings persist across sessions |
| One-way save only | Proper round-trip (load + save) |

---

## If Something Goes Wrong

**Settings file won't load:**
- Check `trial_settings.xml` exists in trial folder
- Verify XML is valid (use online validator if needed)
- Check write permissions in trial folder

**Wrong subject/session:**
- Folder structure must be: `subject_folder/session_folder/trial_folder/`
- Auto-extract uses path parts [-3] and [-2]
- Manually edit XML if needed

**Template not found:**
- Ensure `config/trial_settings_template.xml` exists
- Check file is in correct location

**Checkboxes not auto-populating:**
- Check that settings were actually saved (green button clicked)
- Verify trial_settings.xml has `<analysis_steps>` section
- Try reloading the app

---

## File Locations

```
App Files:
  config/trial_settings_template.xml    ← The template
  gui/widgets/analysis_control_v2.py    ← The code

Trial Files (auto-generated):
  simulations/Athlete_03/25_03_31/Squat_bw_01/
  └── trial_settings.xml                ← Loaded & saved here
```

---

## Summary

The GUI now:

1. ✅ **Generates** default settings from template (first time)
2. ✅ **Loads** settings when you select a trial
3. ✅ **Displays** them in checkboxes
4. ✅ **Saves** updates with all attributes preserved
5. ✅ **Persists** settings across app sessions

**Your settings workflow is now complete!** 🎯
