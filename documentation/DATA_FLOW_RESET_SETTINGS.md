# Data Flow: Reset Settings Feature (FIXED)

## Complete Flow Diagram

```
USER INTERFACE
  ↓
  [User checks "RESET_SETTINGS" checkbox]
  ├─ step_vars["RESET_SETTINGS"].set(True)
  ↓
[User clicks "Run Pipeline"]
  ↓
analysis_control_session.py :: _run_analysis()
  ├─ Line 395: Get selected steps including "RESET_SETTINGS"
  ├─ Line 396: reset_settings = "RESET_SETTINGS" in selected_step_names
  ├─ Line 397: Filter out "RESET_SETTINGS" from analysis_step_names
  ├─ Line 399: Convert analysis_step_names to AnalysisStep enums
  ├─ Line 411: args=(selected, enabled_steps, reset_settings) ✅ KEY FIX
  └─ Line 413: Start background thread with these args
  ↓
analysis_control_session.py :: _run_analysis_thread()
  ├─ Line 417: Accepts (selected_trials, enabled_steps, reset_settings)
  ├─ Line 429-431: Convert enums to step value strings
  ├─ Line 464: if analysis_steps or reset_settings: ✅ Allows running with just reset
  └─ Line 465-471: Create AnalysisConfig with reset_settings=reset_settings ✅ KEY FIX
  ↓
AnalysisConfig.__init__()
  ├─ Accepts reset_settings as a kwarg
  └─ Stores in self._config dict: {'reset_settings': True, 'steps': [], ...}
  ↓
analysis_runner.py :: run_analysis()
  ├─ Line 99: reset_settings = config.get('reset_settings', False) ✅ KEY FIX
  ├─ Line 100-107: if reset_settings: Call _reset_settings_xml()
  │   └─ Outputs to console:
  │      - logger.info(f"Resetting settings XML for: ...")
  │      - logger.info("Settings XML reset successfully")
  ├─ Line 110: steps = config.get('steps', [])  ← Empty list
  ├─ Line 113-115: if not steps and reset_settings: return True, "" ✅ KEY FIX
  └─ Return success tuple (True, "")
  ↓
analysis_control_session.py :: _run_analysis_thread() (continued)
  ├─ Line 473: Receives success=True, error=""
  ├─ Line 474: Checks if not success → FALSE, so continues
  ├─ Line 479: successful += 1
  ├─ Line 480: self.status_callback(f"[OK] {trial_name} completed", "success")
  └─ Loop ends
  ↓
Final Status Callback
  ├─ Line 490-492: Display final success/warning message
  └─ UI shows: "[OK] Session complete - All N trials analyzed"
```

## Key Changes (3 Critical Fixes)

### Fix 1: Pass reset_settings to thread (Line 411)
```python
# BEFORE (broken):
args=(selected, enabled_steps)

# AFTER (fixed):
args=(selected, enabled_steps, reset_settings)
```
**Why:** The flag needs to reach the thread function so it can be included in AnalysisConfig.

### Fix 2: Include reset_settings in AnalysisConfig (Line 470)
```python
# BEFORE (broken):
config = AnalysisConfig(
    trial_path=str(trial_path),
    steps=analysis_steps,
    parameters={},
    replace_existing=True
)

# AFTER (fixed):
config = AnalysisConfig(
    trial_path=str(trial_path),
    steps=analysis_steps,
    parameters={},
    replace_existing=True,
    reset_settings=reset_settings  # ← Added
)
```
**Why:** The flag must be in the config so AnalysisRunner can access it.

### Fix 3: Check config for reset_settings (Line 99)
```python
# BEFORE (broken):
if "RESET_SETTINGS" in steps:  # ← Never true, already filtered out

# AFTER (fixed):
reset_settings = config.get('reset_settings', False)
if reset_settings:
    self.analysis_obj._reset_settings_xml()
```
**Why:** The runner must check the config flag, not the steps list.

### Fix 4: Allow success with only reset_settings (Lines 113-115)
```python
# BEFORE (broken):
if not steps:
    return False, "No analysis steps selected"  # ← Even if reset_settings=True!

# AFTER (fixed):
if not steps:
    if reset_settings:
        return True, ""  # ← Success if reset_settings was the only thing
    else:
        return False, "No analysis steps selected"
```
**Why:** Running with only reset_settings should succeed, not fail.

## Testing the Fix

### Test Case 1: Reset Settings Only
1. Load a trial with trial_settings.xml
2. Check ONLY "Reset Settings" checkbox
3. Click "Run Pipeline"
4. **Expected:**
   - Console shows reset messages
   - Status shows "[OK] trial completed"
   - Old XML deleted, new XML created without model_name
   - **Result: ✅ FIXED**

### Test Case 2: Reset Settings + Analysis Steps
1. Check both "Reset Settings" and "Inverse Kinematics"
2. Click "Run Pipeline"
3. **Expected:**
   - Settings reset first (console output)
   - Then inverse kinematics runs
   - Both complete successfully
   - **Result: ✅ WORKS**

### Test Case 3: Analysis Steps Only
1. Uncheck "Reset Settings"
2. Check "Inverse Kinematics" only
3. Click "Run Pipeline"
4. **Expected:**
   - No reset messages
   - Just runs inverse kinematics
   - **Result: ✅ UNCHANGED (still works)**
