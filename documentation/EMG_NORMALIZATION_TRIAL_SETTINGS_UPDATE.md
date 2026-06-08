# EMG Normalization & Trial Settings Update

## ✅ Changes Implemented

### 1. EMG Normalized Output File
**Status**: ✅ COMPLETE
**File**: `gui/widgets/emg_normalization.py`

**Change**: Normalized EMG is now saved as **`emg_filtered_normalised.mot`** instead of overwriting `emg.mot`

**Before**:
```
/session1/sprint_1/
├── emg.mot              ← Original (overwritten with normalized data)
└── emg_filtered.mot     ← Filtered version
```

**After**:
```
/session1/sprint_1/
├── emg.mot                      ← Original (unchanged)
├── emg_filtered.mot             ← Filtered version
└── emg_filtered_normalised.mot  ← Normalized version (NEW)
```

**Benefits**:
- ✨ Original EMG data preserved
- ✨ Clear tracking of processing steps
- ✨ Can re-normalize with different settings without re-exporting

---

### 2. Trial Settings XML Update
**Status**: ✅ COMPLETE
**File**: `gui/widgets/emg_normalization.py`

**New Method**: `_update_trial_settings_emg()`

**What It Does**:
- After normalization, automatically updates the `<emg>` tag in `trial_settings.xml`
- Changes from `emg.mot` or `emg_filtered.mot` to `emg_filtered_normalised.mot`
- Ensures trial_settings.xml always points to the correct EMG file

**Example**:
```xml
<!-- Before normalization -->
<emg>emg_filtered.mot</emg>

<!-- After normalization -->
<emg>emg_filtered_normalised.mot</emg>
```

---

### 3. Trial Settings XML Format
**Status**: ✅ COMPLETE
**File**: `gui/widgets/batch_c3d_export.py`

**Changed**: trial_settings.xml creation now uses proper format matching the reference model

**Before** (minimal):
```xml
<?xml version='1.0' ?>
<trial_settings>
  <emg_settings>
    <label_pattern>EMG</label_pattern>
    <lowpass_hz>500</lowpass_hz>
  </emg_settings>
  <markers>
    <left_foot>LASI, LP, ...</left_foot>
    <right_foot>RASI, RP, ...</right_foot>
  </markers>
</trial_settings>
```

**After** (comprehensive):
```xml
<?xml version='1.0' ?>
<TrialSettings>
   <replace>False</replace>
   <path>.</path>
   <settingsXML>trial_settings.xml</settingsXML>
   <subject>Athlete1</subject>
   <session>session1</session>
   <trial>sprint_1</trial>
   <c3d>sprint_1.c3d</c3d>
   <emg>emg_filtered_normalised.mot</emg>
   <grf_mot>grf.mot</grf_mot>
   <markers>marker_experimental.trc</markers>
   <events>events.csv</events>
   <setup_ik>setup_IK.xml</setup_ik>
   <setup_grf>GRF.xml</setup_grf>
   <setup_id>setup_ID.xml</setup_id>
   <emg_lowpass_hz>500</emg_lowpass_hz>
   <emg_highpass_hz>20</emg_highpass_hz>
   <emg_notch_hz>50</emg_notch_hz>
   <emg_label_pattern>EMG</emg_label_pattern>
   <left_foot_markers>LASI, LP, ...</left_foot_markers>
   <right_foot_markers>RASI, RP, ...</right_foot_markers>
</TrialSettings>
```

**Key Tags**:
- `<subject>`: From session parent folder
- `<session>`: From session folder name
- `<trial>`: From trial folder name
- `<emg>`: Points to normalized file (updated during normalization)
- `<c3d>`: Points to C3D file in session root
- All other files point to trial folder contents

---

## 🔄 Workflow with New Changes

### Batch C3D Export
```
1. Browse/Load session
2. Select C3D files, markers, EMG channels
3. Run Batch Export
   ↓
4. For each trial:
   - Extract markers, GRF, EMG
   - Create emg_filtered.mot (filtered, not normalized)
   - Create proper trial_settings.xml
   - <emg> tag points to: emg_filtered.mot
```

### EMG Normalization
```
1. Load session (from top selector)
2. Select trials
3. Choose Max or Window Average
4. Run Normalization
   ↓
5. For each trial:
   - Create emg_filtered_normalised.mot
   - Update trial_settings.xml
   - <emg> tag changed to: emg_filtered_normalised.mot
```

### Analysis (IK, ID, etc.)
```
1. Load trial settings from trial_settings.xml
2. Read EMG file path from <emg> tag
3. Use correct EMG file for analysis
```

---

## 📊 File Structure Example

```
C:\Git\msk_modelling_python\example_data\running\Athlete1\session1\

├── sprint_1.c3d              ← Source data (session root)
├── static_1.c3d
├── walking_1.c3d

├── sprint_1/                 ← Trial folder
│   ├── trial_settings.xml    ← UPDATED FORMAT
│   ├── marker_experimental.trc
│   ├── grf.mot
│   ├── events.csv
│   ├── emg.mot                      ← Original (from export)
│   ├── emg_filtered.mot             ← Filtered (from export)
│   └── emg_filtered_normalised.mot  ← Normalized (from EMG Norm tab)
│
├── static_1/
│   ├── trial_settings.xml    ← UPDATED FORMAT
│   ├── marker_experimental.trc
│   ├── grf.mot
│   ├── emg.mot
│   ├── emg_filtered.mot
│   └── emg_filtered_normalised.mot
│
└── walking_1/
    ├── trial_settings.xml    ← UPDATED FORMAT
    ├── marker_experimental.trc
    ├── grf.mot
    ├── emg.mot
    ├── emg_filtered.mot
    └── emg_filtered_normalised.mot
```

---

## 🧪 Testing Steps

### Test 1: Batch C3D Export
1. Browse/Load session
2. Run Batch C3D Export
3. Check each trial folder:
   - ✓ trial_settings.xml exists
   - ✓ Has all required tags (subject, session, trial, c3d, emg, etc.)
   - ✓ `<emg>` tag points to: `emg_filtered.mot`
   - ✓ `<c3d>` tag points to: `sprint_1.c3d` (trial name)

### Test 2: EMG Normalization
1. Load session
2. Select all trials
3. Choose "Max" method
4. Run "Apply Normalization"
5. Check results:
   - ✓ `emg_filtered_normalised.mot` created in each trial folder
   - ✓ `trial_settings.xml` updated
   - ✓ `<emg>` tag now points to: `emg_filtered_normalised.mot`
   - ✓ Original `emg.mot` and `emg_filtered.mot` unchanged

### Test 3: Trial Settings Content
1. Open `trial_settings.xml` in trial folder
2. Verify:
   - ✓ Root element is `<TrialSettings>` (capital T and S)
   - ✓ Contains subject, session, trial info
   - ✓ Contains file references
   - ✓ EMG settings match what was selected
   - ✓ Marker selections are stored

---

## 🎯 Key Improvements

1. **Data Preservation**: Original data never overwritten
2. **Clear Tracking**: Each processing step creates new file
3. **Proper Configuration**: trial_settings.xml matches reference format
4. **Automatic Updates**: trial_settings.xml automatically updated during normalization
5. **Analysis Readiness**: All analysis code can use trial_settings.xml to find correct files

---

## 💾 Implementation Details

### EMG Normalization
```python
# Save to new file
output_file = emg_file.parent / "emg_filtered_normalised.mot"
self._save_mot_file(output_file, normalized_data)

# Update trial settings
self._update_trial_settings_emg(emg_file.parent, "emg_filtered_normalised.mot")
```

### Trial Settings Update
```python
def _update_trial_settings_emg(self, trial_dir, emg_filename):
    """Update <emg> tag in trial_settings.xml"""
    tree = ET.parse(trial_dir / "trial_settings.xml")
    root = tree.getroot()
    emg_elem = root.find('emg')
    if emg_elem is None:
        emg_elem = ET.SubElement(root, 'emg')
    emg_elem.text = emg_filename
    tree.write(...)
```

### Trial Settings Creation
```python
# Create with proper structure
root = ET.Element("TrialSettings")
ET.SubElement(root, "subject").text = subject_name
ET.SubElement(root, "session").text = session_name
ET.SubElement(root, "trial").text = trial_name
ET.SubElement(root, "emg").text = "emg_filtered_normalised.mot"
# ... more tags ...
```

---

## 📝 Notes

- Trial settings automatically created during Batch C3D Export
- EMG tag automatically updated during EMG Normalization
- Both operations use XML for reliable configuration storage
- Format matches reference models for consistency
- All file paths are relative to trial folder (allows moving session)

---

## Summary

✅ EMG normalized files saved separately: `emg_filtered_normalised.mot`
✅ trial_settings.xml automatically updated after normalization
✅ trial_settings.xml format now comprehensive and matches reference models
✅ Analysis code can rely on trial_settings.xml for file locations
✅ Data preservation: no original files overwritten during normalization
