# Settings Configuration Guide

## Two Configuration Approaches

### Approach 1: Python Settings (Current - settings.py)
Unified configuration for all trials in a session.

**Pros:**
- Single configuration file
- Quick setup for batch processing
- Easy to automate

**Cons:**
- Same settings applied to all trials
- Less flexibility per trial

### Approach 2: XML Trial Settings (Recommended - trial_settings.xml)
Separate XML file per trial with specific parameters.

**Structure:**
```xml
<ITrialSettings>
  <setup_dir>./setup_files/</setup_dir>
  <model_dir>../Models/P02_scaled.osim</model_dir>
  <start_time>0.0000</start_time>
  <end_time>5.3150</end_time>
  <c3d>cmj_01.c3d</c3d>
  <emg>emg_filtered_normalised.mot</emg>
  <grf_mot>grf.mot</grf_mot>
  <markers>marker_experimental.trc</markers>
  <events>events.csv</events>
  <setup_ik>setup_IK.xml</setup_ik>
  <setup_id>setup_ID.xml</setup_id>
  <!-- ... more configuration -->
</ITrialSettings>
```

**File Location:**
```
session_folder/
├── static_01.c3d
├── static_01/
│   ├── marker_experimental.trc
│   └── trial_settings.xml    ← Trial-specific settings
├── dynamic_01.c3d
├── dynamic_01/
│   ├── marker_experimental.trc
│   └── trial_settings.xml
```

## Using settings.py with BatchSettings

The current Python configuration in `settings.py` provides default values that work for standard workflows:

```python
class BatchSettings:
    # Session configuration
    session_folder = 'C:\Users\Basilio\ucloud\Squat_Width\Simulations\P012'
    setup_files_folder = 'C:\Users\Basilio\ucloud\Squat_Width\setup_files'
    generic_model = 'C:\Users\Basilio\ucloud\Squat_Width\Models\Catelli-V4.0_pyCGM_pelvis.osim'
    markerset = 'markers.xml'
    
    # Output configuration
    results_dir_name = 'Results'
    static_trial_name = 'static_01'
    
    # Pipeline configuration
    enable_c3d_export = True
    enable_inverse_kinematics = True
    enable_inverse_dynamics = True
    enable_static_optimization = True
```

## Migration Path

To switch to XML trial settings:
1. Create `trial_settings.xml` in each trial subdirectory
2. Update batch mode to load XML settings per trial
3. Use trial-specific time ranges, model files, etc.

This allows maximum flexibility while maintaining a unified batch processing workflow.
