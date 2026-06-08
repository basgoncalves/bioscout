# Quick Fix Instructions

## Issues Found

1. **utils.py path error** - FIXED ✅
   - Changed path from 3 levels up to 4 levels up
   - Now correctly finds: C:\Git\powerlifing_model_clean\code\utils.py

2. **Settings loading** - PARTIALLY FIXED
   - _load_trial_settings() loads analysis steps ✅
   - Still needs to load file selections from XML

3. **Settings saving** - INCOMPLETE
   - Only saves analysis steps
   - Should also save file selections (c3d, emg, grf, markers, events, model_path)

4. **Missing EMG input** - NOT YET IMPLEMENTED
   - GUI doesn't show EMG file selector
   - Need to add EMG file browse/select

5. **Missing model path input** - NOT YET IMPLEMENTED
   - No way to specify or change model directory
   - Need to add model path browse field

## What's Working Now
✅ App launches
✅ Trial directory selection
✅ File auto-detection
✅ Analysis step selection
✅ Settings file creation
✅ Analysis runner path (fixed)
✅ Settings save button

## Next Steps (Manual for Now)

1. Test with current setup
2. Edit trial_settings.xml manually to add:
   ```xml
   <emg>your_emg_file.mot</emg>
   <model_dir>path/to/model</model_dir>
   ```

3. Or implement GUI updates for:
   - EMG file selector
   - Model path selector
   - File selection persistence in XML
   - File selection loading from XML

## To Implement

Would require updating:
- analysis_control_v2.py:
  - Add EMG file display section
  - Add model path browse section
  - Update _load_trial_settings() to load file paths
  - Update _save_settings_file() to save file paths
  - Store selected files in instance variables

Let me know if you want me to implement these!
