# Batch Runner Guide

Run biomechanical analysis on multiple trials without using the GUI.

## Quick Start

1. Create a batch settings XML file (see example below)
2. Run from command line:

```bash
cd C:\Git\app
python batch_runner.py batch_settings_example.xml
```

## Settings File Format

The batch settings XML file controls which trials to process and which analysis steps to run.

### Basic Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<batch>
    <trials>
        <trial path="path/to/trial1"/>
        <trial path="path/to/trial2"/>
    </trials>

    <analysis_steps>
        <step name="inverse_kinematics" enabled="true"/>
        <step name="inverse_dynamics" enabled="false"/>
        <step name="static_optimization" enabled="false"/>
        <step name="muscle_analysis" enabled="false"/>
    </analysis_steps>

    <replace_existing>true</replace_existing>
</batch>
```

### Elements

**`<trials>`** — List of trial directories to process
- Each `<trial>` element must have a `path` attribute pointing to a directory containing `trial_settings.xml`
- Each trial is processed sequentially

**`<analysis_steps>`** — Which analysis to run
- `inverse_kinematics` — Calculate joint angles from marker positions
- `inverse_dynamics` — Calculate joint forces and moments
- `static_optimization` — Estimate muscle forces
- `muscle_analysis` — Analyze muscle properties

Set `enabled="true"` to run a step, `enabled="false"` to skip it.

**`<replace_existing>`** — Whether to recompute results
- `true` — Re-run analysis and overwrite existing results
- `false` — Skip analysis if output files already exist (faster for re-runs)

**`<log_file>` (optional)** — Custom log file location
- If not specified, batch output is logged to the app's main log file: `C:\Git\app\logs\app_*.log`
- You can specify a custom path to save batch-specific logs separately
- All output appears on console AND in logs

**`<results_dir>` (optional)** — Custom output directory
- If not specified, results are saved to each trial's directory

## Usage Examples

### Example 1: Run only inverse kinematics

```xml
<?xml version="1.0" encoding="UTF-8"?>
<batch>
    <trials>
        <trial path="C:\data\trial_001"/>
        <trial path="C:\data\trial_002"/>
    </trials>

    <analysis_steps>
        <step name="inverse_kinematics" enabled="true"/>
        <step name="inverse_dynamics" enabled="false"/>
        <step name="static_optimization" enabled="false"/>
        <step name="muscle_analysis" enabled="false"/>
    </analysis_steps>

    <replace_existing>false</replace_existing>
</batch>
```

### Example 2: Run full pipeline (all steps)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<batch>
    <trials>
        <trial path="C:\data\trial_001"/>
    </trials>

    <analysis_steps>
        <step name="inverse_kinematics" enabled="true"/>
        <step name="inverse_dynamics" enabled="true"/>
        <step name="static_optimization" enabled="true"/>
        <step name="muscle_analysis" enabled="true"/>
    </analysis_steps>

    <replace_existing>true</replace_existing>
</batch>
```

### Example 3: Update results only if missing

```xml
<?xml version="1.0" encoding="UTF-8"?>
<batch>
    <trials>
        <trial path="C:\data\trial_001"/>
        <trial path="C:\data\trial_002"/>
        <trial path="C:\data\trial_003"/>
    </trials>

    <analysis_steps>
        <step name="inverse_kinematics" enabled="true"/>
        <step name="inverse_dynamics" enabled="true"/>
        <step name="static_optimization" enabled="false"/>
        <step name="muscle_analysis" enabled="false"/>
    </analysis_steps>

    <replace_existing>false</replace_existing>
</batch>
```

## Running the Batch

```bash
# From the app directory
cd C:\Git\app

# Run with settings file
python batch_runner.py my_settings.xml
```

## Output

The batch runner prints detailed progress:

```
================================================================================
 BATCH ANALYSIS RUNNER
================================================================================
Settings file: batch_settings.xml
Start time: 2026-05-28 12:00:00

► Parsing settings file...
  ► Found 3 trial(s)
  ► Replace existing: false
  ► Enabled analysis: inverse_kinematics, inverse_dynamics

► Validating trial paths...
  ► ✓ Valid: C:\data\trial_001
  ► ✓ Valid: C:\data\trial_002
  ► ✓ Valid: C:\data\trial_003

================================================================================
 RUNNING ANALYSIS
================================================================================

► Processing trial 1/3: trial_001
  ► Running inverse kinematics...
    ► ✓ inverse kinematics completed
  ► Running inverse dynamics...
    ► ✓ inverse dynamics completed
  ► Trial completed successfully

► Processing trial 2/3: trial_002
  ► Running inverse kinematics...
    ► ✓ inverse kinematics completed
  ► Running inverse dynamics...
    ► ✓ inverse dynamics completed
  ► Trial completed successfully

► Processing trial 3/3: trial_003
  ► Running inverse kinematics...
    ► ✓ inverse kinematics completed
  ► Running inverse dynamics...
    ► ✓ inverse dynamics completed
  ► Trial completed successfully

================================================================================
 BATCH SUMMARY
================================================================================
Total trials: 3
Successful: 3
Failed: 0
End time: 2026-05-28 12:15:30

✓ All trials processed successfully!
```

## Exit Codes

- `0` — All trials processed successfully
- `1` — One or more trials failed (check output for errors)

## Troubleshooting

**"Settings file not found"**
- Verify the path to the settings XML file is correct
- Use absolute paths or run from the app directory

**"Invalid: path/to/trial"**
- The trial directory must contain `trial_settings.xml`
- Check that all trial paths in the settings file are correct

**Analysis step failed**
- Check that all required input files exist in the trial directory
- Verify the trial_settings.xml is properly configured
- Check the app log files for detailed error messages

**"No analysis steps enabled"**
- Set at least one `<step>` element to `enabled="true"`

## Advantages Over GUI

1. **Automate processing** — Run multiple trials without manual clicking
2. **Reproducibility** — Settings stored in XML file (easy to track and repeat)
3. **Batch operations** — Process dozens of trials with one command
4. **Script integration** — Easily integrate with other analysis pipelines
5. **Server/cluster** — Run on remote machines via command line

## Integration with Scripts

You can call the batch runner from Python or shell scripts:

```bash
# Run batch processing
python batch_runner.py settings.xml

# Check exit code
if [ $? -eq 0 ]; then
    echo "Analysis completed successfully"
else
    echo "Analysis failed - check output above"
fi
```

## Next Steps

1. Copy `batch_settings_example.xml` to `batch_settings.xml`
2. Edit to add your trial paths
3. Set which analysis steps you want to run
4. Run `python batch_runner.py batch_settings.xml`
