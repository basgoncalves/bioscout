# Squat_Width Project Batch Processing Guide

## Quick Start

Run batch processing for the Squat_Width project:

```bash
cd C:\Git\app
python . -batch batch_settings_squat_width.xml
```

## Configuration

The batch settings are defined in `batch_settings_squat_width.xml`:

### Project Paths
- **Models**: `C:\Users\Basilio\ucloud\Squat_Width\Models\`
- **Setup Files**: `C:\Users\Basilio\ucloud\Squat_Width\setup_files\`
- **Data**: `C:\Users\Basilio\ucloud\Squat_Width\Simulations\`
- **Results**: `C:\Users\Basilio\ucloud\Squat_Width\Results\`

### Enabled Analysis Steps
1. **Inverse Kinematics (IK)** - Calculates joint angles from marker positions
2. **Inverse Dynamics (ID)** - Calculates joint forces and moments
3. **Static Optimization (SO)** - Estimates muscle forces
4. **C3D Export** - Exports processed data to C3D format

### EMG Normalization
EMG normalization is disabled by default. To enable it:
1. Modify `batch_settings_squat_width.xml`
2. Change `<emg_normalization enabled="false"/>` to `enabled="true"`

Note: EMG normalization should be done as a pre-processing step before running IK/ID analysis.

## Adding Multiple Sessions

To process multiple sessions, edit `batch_settings_squat_width.xml` and uncomment/add trial paths:

```xml
<trials>
    <trial path="C:\Users\Basilio\ucloud\Squat_Width\Simulations\P02\19-03-2026"/>
    <trial path="C:\Users\Basilio\ucloud\Squat_Width\Simulations\P02\20-03-2026"/>
    <trial path="C:\Users\Basilio\ucloud\Squat_Width\Simulations\P03\19-03-2026"/>
    <trial path="C:\Users\Basilio\ucloud\Squat_Width\Simulations\P03\20-03-2026"/>
</trials>
```

## Required Trial Structure

Each trial directory must contain:
- `trial_settings.xml` - Trial-specific configuration
- `marker_experimental.trc` - Experimental marker data
- `grf.mot` - Ground reaction force data (if using GRF)
- `emg.mot` - EMG data (if applicable)
- Setup files (IK, ID, SO) - As specified in trial_settings.xml

## Output

Results are saved to:
- **Log File**: `C:\Users\Basilio\ucloud\Squat_Width\batch_logs\squat_width_batch.log`
- **Results**: `C:\Users\Basilio\ucloud\Squat_Width\Results\`
- **Session**: `C:\Users\Basilio\ucloud\Squat_Width\batch_session\`

## Troubleshooting

### Issue: "Trial path is invalid"
- Ensure `trial_settings.xml` exists in the trial directory
- Check that all paths are absolute and correctly formatted

### Issue: "OpenSim analysis failed"
- Check the batch log file for detailed error messages
- Verify that all setup files (setup_IK.xml, setup_ID.xml, etc.) are present
- Confirm model files exist at the specified paths

### Issue: "Permission denied"
- Ensure the Results and batch_logs directories exist and are writable
- Check Windows file permissions

## Next Steps

After batch processing completes:
1. Check `batch_logs/squat_width_batch.log` for any warnings or errors
2. Verify results in `Results/` directory
3. Review exported C3D files
4. Perform post-analysis as needed (plotting, statistics, etc.)
