# Batch Processing Guide

## Overview

The Powerlifting Model Analysis App supports batch processing mode, which allows you to run the full analysis pipeline without opening the GUI. This is useful for:

- Automated analysis of multiple trials
- Headless server operation
- Integration with other scripts and workflows
- CI/CD pipelines
- Parameter sweeps and sensitivity analyses

## Quick Start

### Basic Usage

```bash
# Run with default GUI
python __main__.py

# Run batch analysis with settings file
python __main__.py --batch batch_settings.xml
python __main__.py -b batch_settings.xml

# Show help
python __main__.py --help
```

### Example

```bash
cd C:\Git\powerlifing_model_clean\code\tests\app
python __main__.py --batch batch_settings_example.xml
```

## Settings File Format

Settings are provided in XML format. Two template files are included:

- **batch_settings_template.xml** - Complete reference with all available options
- **batch_settings_example.xml** - Working example with the sample dataset

### Creating Your Own Settings File

1. Copy `batch_settings_example.xml` to a new file (e.g., `my_analysis.xml`)
2. Update the paths and parameters for your analysis:

```xml
<Session>
    <settingsXML>C:\path\to\trial\trial_settings.xml</settingsXML>
</Session>

<Analysis>
    <trials>trial_name</trials>
    <left_foot_markers>LHEE,LMT1,LMT2,LMT5</left_foot_markers>
    <right_foot_markers>RHEE,RMT1,RMT2,RMT5</right_foot_markers>
    <methods>SO,CEINMS</methods>
</Analysis>
```

3. Run the analysis:

```bash
python __main__.py --batch my_analysis.xml
```

## Configuration Options

### Session Configuration

```xml
<Session>
    <!-- Method 1: Use existing trial settings -->
    <settingsXML>C:\path\to\trial_settings.xml</settingsXML>

    <!-- Method 2: Specify paths directly -->
    <setup_dir>C:\path\to\setup</setup_dir>
    <model_dir>C:\path\to\model.osim</model_dir>
</Session>
```

The trial_settings.xml file is created when you do a C3D export. It contains:
- Path to OpenSim model
- Path to biomechanics setup
- Time range for analysis
- Trial marker and GRF data paths

### Analysis Configuration

#### Markers
```xml
<left_foot_markers>LHEE,LMT1,LMT2,LMT5</left_foot_markers>
<right_foot_markers>RHEE,RMT1,RMT2,RMT5</right_foot_markers>
```

List of markers assigned to each foot for ground reaction force calculation. These should match your marker set.

#### Methods
```xml
<methods>SO,CEINMS</methods>
```

Specify which analysis methods to run:
- `SO` - Static Optimization (muscle force from IK)
- `CEINMS` - EMG-Informed Neuromusculoskeletal model
- `SO,CEINMS` - Run both and compare

#### Inverse Kinematics
```xml
<InverseKinematics>
    <run>true</run>
    <accuracy>1e-5</accuracy>
    <max_iterations>1000</max_iterations>
</InverseKinematics>
```

- `run`: Whether to execute IK solver
- `accuracy`: Convergence tolerance (smaller = more accurate, slower)
- `max_iterations`: Maximum solver iterations

#### Inverse Dynamics
```xml
<InverseDynamics>
    <run>true</run>
    <lowpass_filter>6.0</lowpass_filter>
</InverseDynamics>
```

- `lowpass_filter`: Low-pass filter cutoff frequency in Hz

#### Static Optimization
```xml
<StaticOptimization>
    <run>true</run>
    <convergence_criterion>0.001</convergence_criterion>
    <max_iterations>100</max_iterations>
</StaticOptimization>
```

Parameters for the SO optimization solver.

#### CEINMS
```xml
<CEINMS>
    <run>true</run>
    <calibration>false</calibration>
    <emg_low_cutoff>20</emg_low_cutoff>
    <emg_high_cutoff>500</emg_high_cutoff>
</CEINMS>
```

- `calibration`: Run parameter calibration before analysis
- EMG filter cutoffs in Hz

### Processing Options

```xml
<Processing>
    <clean_markers>true</clean_markers>
    <clean_grf>true</clean_grf>
    <num_workers>1</num_workers>
    <continue_on_error>false</continue_on_error>
</Processing>
```

- `clean_markers`: Remove NaN rows from marker data (recommended: true)
- `clean_grf`: Remove NaN rows from GRF data (recommended: true)
- `num_workers`: Parallel workers (1 = sequential)
- `continue_on_error`: Continue with other trials if one fails

### Output Configuration

```xml
<Output>
    <generate_plots>true</generate_plots>
    <generate_report>true</generate_report>
    <report_format>pdf</report_format>
    <log_level>info</log_level>
</Output>
```

- `log_level`: `debug`, `info`, `warning`, or `error`

### Comparison Configuration

```xml
<Comparison>
    <enabled>true</enabled>
    <metrics>
        <metric>moment_residuals</metric>
        <metric>emg_activation_correlation</metric>
        <metric>ik_marker_error</metric>
        <metric>muscle_activations</metric>
        <metric>muscle_forces</metric>
    </metrics>
    <generate_comparison_plots>true</generate_comparison_plots>
    <statistical_test>t-test</statistical_test>
</Comparison>
```

## Command Line Options

### --batch / -b
```bash
python __main__.py --batch settings.xml
python __main__.py -b settings.xml
```
Run in batch mode with specified settings file.

### --verbose / -v
```bash
python __main__.py --batch settings.xml --verbose
```
Enable debug logging for troubleshooting.

### --quiet / -q
```bash
python __main__.py --batch settings.xml --quiet
```
Suppress non-error output.

### --help / -h
```bash
python __main__.py --help
```
Show help message.

## Logging and Output

### Log Files

All output is saved to `code/tests/app/logs/batch_YYYYMMDD_HHMMSS.log`

Example:
```
2026-05-22 18:00:00 - INFO - ========================================================================
2026-05-22 18:00:00 - INFO - Batch Processing Started
2026-05-22 18:00:00 - INFO - ========================================================================
2026-05-22 18:00:00 - INFO - Settings file: C:\...\batch_settings.xml
2026-05-22 18:00:00 - INFO - ✓ Batch settings loaded from: C:\...\batch_settings.xml
2026-05-22 18:00:01 - INFO - Mode: analysis
2026-05-22 18:00:01 - INFO - Trials: run_baseline1
2026-05-22 18:00:01 - INFO - Methods: SO,CEINMS
2026-05-22 18:00:02 - INFO - Loading trial from: C:\...
2026-05-22 18:00:15 - INFO - ✓ Trial analysis completed
2026-05-22 18:00:15 - INFO - ========================================================================
2026-05-22 18:00:15 - INFO - Batch Mode Completed
```

### Output Files

Results are saved in the trial directory:

```
<trial_directory>/
├── joint_angles.mot          # IK results (joint angles)
├── id_results.sto            # ID results (joint moments)
├── SO_muscle_forces.sto      # Static Optimization results
├── SO_activations.sto        # SO muscle activations
├── CEINMS_muscle_forces.sto  # CEINMS results
├── CEINMS_activations.sto    # CEINMS muscle activations
├── plots/                    # Generated figures
│   ├── joint_angles.pdf
│   ├── moments.pdf
│   ├── muscle_forces.pdf
│   └── comparison.pdf
└── report.pdf                # Analysis report
```

## Examples

### Example 1: Run Single Trial

**File: my_trial.xml**
```xml
<?xml version="1.0" encoding="utf-8"?>
<BatchSettings>
    <mode>analysis</mode>
    <Session>
        <settingsXML>C:\data\trial1\trial_settings.xml</settingsXML>
    </Session>
    <Analysis>
        <trials>trial1</trials>
        <left_foot_markers>LHEE,LMT1,LMT2,LMT5</left_foot_markers>
        <right_foot_markers>RHEE,RMT1,RMT2,RMT5</right_foot_markers>
        <methods>SO,CEINMS</methods>
    </Analysis>
    <Processing>
        <clean_markers>true</clean_markers>
        <clean_grf>true</clean_grf>
    </Processing>
</BatchSettings>
```

**Run:**
```bash
python __main__.py --batch my_trial.xml
```

### Example 2: Multiple Trials (future feature)

```xml
<Analysis>
    <trials>trial1,trial2,trial3</trials>
    <methods>SO,CEINMS</methods>
</Analysis>

<Processing>
    <num_workers>4</num_workers>
    <continue_on_error>true</continue_on_error>
</Processing>
```

### Example 3: Debug Mode

```bash
python __main__.py --batch settings.xml --verbose
```

This enables detailed logging to help diagnose issues.

## Troubleshooting

### "Settings file not found"
Check that the XML file path is correct and the file exists.

### "Trial settings file not found"
The settingsXML path inside the batch settings file is incorrect. Verify the path to trial_settings.xml from a completed C3D export.

### Analysis fails silently
Check the log file:
```bash
cat code\tests\app\logs\batch_*.log
```

Enable verbose mode:
```bash
python __main__.py --batch settings.xml --verbose
```

### "Trial_settings.xml not found"
You need to run a C3D export first to generate this file. The C3D export can be done through the GUI.

### Output files not generated
Check:
1. Log file for errors
2. Trial directory has proper permissions
3. Output configuration in settings file:
   ```xml
   <Output>
       <generate_plots>true</generate_plots>
       <generate_report>true</generate_report>
   </Output>
   ```

## Batch Processing Pipeline

The batch processor executes this pipeline:

```
1. Load Settings XML
   ↓
2. Validate Settings
   ↓
3. Load Trial Configuration
   ↓
4. Export C3D → TRC/GRF files (if needed)
   ↓
5. Clean NaN rows from marker/GRF data
   ↓
6. Run Inverse Kinematics → joint_angles.mot
   ↓
7. Run Inverse Dynamics → joint moments
   ↓
8. Run Static Optimization → muscle forces/activations
   ↓
9. Run CEINMS → EMG-informed muscle forces/activations
   ↓
10. Compare SO vs CEINMS → metrics and plots
    ↓
11. Generate Report
    ↓
12. Save All Results
    ↓
13. Exit with status (0=success, 1=failure)
```

## Integration with Scripts

### Python Script
```python
import subprocess
import sys

settings_file = "my_analysis.xml"
result = subprocess.run(
    [sys.executable, "__main__.py", "--batch", settings_file],
    cwd="C:\\Git\\powerlifing_model_clean\\code\\tests\\app"
)

if result.returncode == 0:
    print("Analysis completed successfully!")
else:
    print("Analysis failed!")
```

### Batch Script (.bat)
```batch
cd C:\Git\powerlifing_model_clean\code\tests\app
python __main__.py --batch batch_settings.xml
if %ERRORLEVEL% EQU 0 (
    echo Analysis completed successfully!
) else (
    echo Analysis failed!
    exit /b 1
)
```

### Bash Script (.sh)
```bash
#!/bin/bash
cd /path/to/powerlifing_model_clean/code/tests/app
python __main__.py --batch batch_settings.xml

if [ $? -eq 0 ]; then
    echo "Analysis completed successfully!"
else
    echo "Analysis failed!"
    exit 1
fi
```

## Performance Tips

1. **Clean Data First**: Enable `clean_markers` and `clean_grf` to remove NaN rows
2. **Appropriate Thresholds**: Set IK accuracy and SO convergence to match your needs
3. **Filter Settings**: Adjust EMG filter cutoffs for your data quality
4. **Parallel Processing**: Use `num_workers > 1` for multiple trials (future)

## Support

For issues or questions:
1. Check the log file (code/tests/app/logs/batch_*.log)
2. Run with `--verbose` flag for debug output
3. Review the FIXES_SUMMARY.md for known issues
4. Check documentation in code/tests/app/documentation/
