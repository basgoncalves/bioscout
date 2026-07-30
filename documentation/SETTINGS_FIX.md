# Settings XML Format Fix

## Problem
The GUI was saving settings to `trial_settings.xml` in an incorrect format, creating a minimal file:

```xml
<trial_settings>
  <trial_name>Squat_bw_01</trial_name>
  <subject>Unknown</subject>
  <session>Unknown</session>
  <analysis_level>trial</analysis_level>
  <analysis_steps />
</trial_settings>
```

This didn't match your existing `utils.py` code which saves ALL analysis settings using the `Analyse` class's `_to_xml()` method.

## Solution
Updated `gui/widgets/analysis_control_v2.py` to:

### Strategy 1: Use Existing Analyse Class (Preferred)
1. **Load the Analyse object** from your existing `utils.py`
2. **Update it** with the selected analysis steps from the GUI
3. **Call its native `_to_xml()` method** to save in the proper format
4. This preserves ALL settings that Analyse normally saves

Result: Proper, complete XML matching your existing code format.

### Strategy 2: Fallback Format
If loading Analyse fails, use a simplified approach that still:
1. **Preserves existing settings** (reads existing XML if present)
2. **Uses proper XML formatting** (indentation, no blank lines)
3. **Adds analysis steps** that were selected
4. **Matches structure** of Analyse output (TrialSettings root element)

## What You Get Now

### When You Save Settings:

**Before (Wrong):**
```xml
<trial_settings>
  <trial_name>Squat_bw_01</trial_name>
  ...
  <analysis_steps />
</trial_settings>
```

**After (Correct - uses your Analyse class):**
```xml
<?xml version="1.0" ?>
<TrialSettings>
   <path>C:\...\Squat_bw_01</path>
   <c3d_file>...\data.c3d</c3d_file>
   <marker_file>...\markers.trc</marker_file>
   <trial_name>Squat_bw_01</trial_name>
   <subject>Subject01</subject>
   <session>Trial01</session>
   <analysis_level>trial</analysis_level>
   <analysis_steps>
      <step>inverse_kinematics</step>
      <step>inverse_dynamics</step>
      <step>static_optimization</step>
   </analysis_steps>
   ... (all other Analyse attributes)
</TrialSettings>
```

## How It Works

When you click "Save Settings":

1. **Try Primary Method:**
   - Load `utils.py` and create Analyse object
   - Set `analyse_obj.analysis_steps = [selected steps]`
   - Call `analyse_obj._to_xml()` (your existing code)
   - ✅ Creates proper, complete XML with all settings

2. **If That Fails:**
   - Read existing `trial_settings.xml` (if it exists)
   - Create new XML maintaining structure
   - Add selected analysis steps
   - Use same pretty-printing as your code (`_save_pretty_xml()`)
   - ✅ Still creates proper format

## Key Changes to Code

Added to `analysis_control_v2.py`:

```python
# New imports
import xml.dom.minidom
import os

# Updated _save_settings_file() to:
1. Try loading Analyse object from utils.py
2. Update it with selected steps
3. Call analyse_obj._to_xml()
4. Fall back to pretty XML formatting if needed

# New method _save_pretty_xml() that:
- Uses proper indentation (3 spaces)
- Removes blank lines
- Matches utils.py formatting exactly
```

## Testing the Fix

1. Open the app: `python run.py`
2. Select a trial directory
3. Select some analysis steps (IK, ID, SO)
4. Click "Save Settings"
5. Check the XML file:

```bash
# View the saved settings
cat "C:\Git\powerlifing_model_clean\simulations\Athlete_03\25_03_31\Squat_bw_01\trial_settings.xml"
```

You should now see:
- ✅ Proper `<TrialSettings>` root element (not `<trial_settings>`)
- ✅ Pretty-printed with indentation
- ✅ All Analyse attributes saved (when using primary method)
- ✅ Selected steps properly listed in `<analysis_steps>`
- ✅ Relative paths where appropriate

## Compatibility

This fix:
- ✅ Works with your existing `utils.py` code
- ✅ Preserves the `Analyse` class's XML format
- ✅ Maintains backward compatibility
- ✅ Loads and updates existing settings files
- ✅ Uses the same pretty-printing as your code

## What to Do Now

1. **Update the app:**
   - The fix is already in `gui/widgets/analysis_control_v2.py`

2. **Test it:**
   - Run: `python run.py`
   - Select a trial
   - Select analysis steps
   - Click "Save Settings"
   - Verify the XML file is now correct

3. **Existing Settings:**
   - Old settings files will still work
   - New saves will use the proper format
   - You can delete old settings files if you want fresh ones

## Troubleshooting

### "Could not load Analyse object" message
- This is OK! It just means fallback method is used
- Settings still save in proper XML format
- Just check that `utils.py` path is correct if it's important

### XML format still looks wrong
- Verify you're looking at the right file
- Close any open editors (they might cache the view)
- Try saving again

### Settings not appearing in XML
- Make sure you checked the checkboxes for steps
- Make sure you clicked "Save Settings" (green button)
- Check the log messages for errors

## Summary

Your settings files should now be properly formatted using the same `Analyse` class structure as your existing code. The GUI integrates seamlessly with your biomechanics framework!
