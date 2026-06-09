# Reset Settings Fix - Complete Solution

## Problem
When clicking "Run Pipeline" with only the "RESET_SETTINGS" checkbox selected, nothing happens - no console output, no XML reset, no error message.

## Root Cause
The `reset_settings` flag was being extracted in the control classes but **never passed to the AnalysisRunner**. 

### The Issue Flow:
1. **analysis_control_session.py** extracted the flag:
   ```python
   reset_settings = "RESET_SETTINGS" in selected_step_names
   analysis_step_names = [name for name in selected_step_names if name != "RESET_SETTINGS"]
   ```

2. But only passed `enabled_steps` to the thread:
   ```python
   args=(selected, enabled_steps)  # ❌ reset_settings missing!
   ```

3. In **analysis_runner.py**, the code checked for the flag in the steps list:
   ```python
   if "RESET_SETTINGS" in steps:  # ❌ Never true - was already filtered out!
       self.analysis_obj._reset_settings_xml()
   ```

The flag was lost between the control class and the runner, so `_reset_settings_xml()` was never called.

## Solution

### Changes Made:

#### 1. **analysis_control_session.py**
```python
# Pass reset_settings to the thread
args=(selected, enabled_steps, reset_settings)  # ✅ Added reset_settings

# Accept it in the thread method
def _run_analysis_thread(self, selected_trials: list, enabled_steps: list, reset_settings: bool = False):
    # Pass it in the config
    config = AnalysisConfig(
        trial_path=str(trial_path),
        steps=analysis_steps,
        parameters={},
        replace_existing=True,
        reset_settings=reset_settings  # ✅ Added to config
    )
```

#### 2. **analysis_control_simplified.py**
```python
# Pass reset_settings in the config
config = AnalysisConfig(
    trial_path=str(self.current_path),
    steps=enabled_steps,
    parameters={},
    replace_existing=True,
    reset_settings=reset_settings  # ✅ Added to config
)
```

#### 3. **analysis_control_v2.py**
```python
# Pass reset_settings through the pipeline
args=(enabled_steps, reset_settings)  # ✅ Added to thread args

def _run_analysis_thread(self, enabled_steps: dict, reset_settings: bool = False):
    # And in both analysis methods
    config = AnalysisConfig(
        trial_path=str(trial_dir),
        steps=enabled_steps,
        parameters=self.config_manager.get_section("analysis"),
        reset_settings=reset_settings  # ✅ Added to config
    )
```

#### 4. **analysis_runner.py**
```python
def run_analysis(self, config: AnalysisConfig) -> tuple[bool, str]:
    # Check config instead of steps list
    reset_settings = config.get('reset_settings', False)  # ✅ From config
    if reset_settings:
        logger.info(f"Resetting settings XML for: {config.trial_path}")
        self.analysis_obj._reset_settings_xml()
        logger.info("Settings XML reset successfully")
    
    # Allow success with only reset_settings and no steps
    if not steps:
        if reset_settings:
            return True, ""  # ✅ Success if reset_settings is True
        else:
            return False, "No analysis steps selected"
```

## How It Works Now

1. User checks "RESET_SETTINGS" checkbox and clicks "Run Pipeline"
2. Control class extracts `reset_settings = True`
3. Control class passes `reset_settings` to background thread
4. Thread creates `AnalysisConfig(..., reset_settings=True)`
5. `run_analysis()` receives config and checks `config.get('reset_settings')`
6. **✅ `_reset_settings_xml()` is called and prints to console**
7. Settings XML is deleted and regenerated without model_name
8. Returns `True, ""`
9. User sees success message and console output

## Testing
To test:
1. Load a trial with an existing trial_settings.xml
2. Select only "Reset Settings" checkbox (no other steps)
3. Click "Run Pipeline"
4. **Expected result:**
   - Console shows: `"Resetting settings XML for: /path/to/trial"`
   - Console shows: `"Settings XML reset successfully"`
   - Old trial_settings.xml is deleted
   - New trial_settings.xml is created without model_name attribute
   - Status shows: "[OK] trial_name completed"
