# CEINMS Batch Pipeline Implementation

## Overview

CEINMS (Calibrated EMG-Informed Neuromusculoskeletal) calibration and execution have been integrated into the batch processing pipeline as **STEP 7** and **STEP 8**.

## Setup

### 1. Enable CEINMS in settings.py

Edit `settings.py` and set:

```python
class BatchSettings:
    # Enable the CEINMS pipeline
    enable_ceinms_calibration = True
    enable_ceinms_execution = True
    
    # Set which trials to use for calibration
    calibration_trial_names = ['sprint', 'cmj_02']
    
    # Calibration parameters (optional - defaults provided)
    ceinms_calibration_type = 'hybrid'      # 'ceinms' or 'hybrid'
    ceinms_learning_rate = 0.02
    ceinms_max_iterations = 1000
    ceinms_num_synergies = 4
    ceinms_tendon_type = 'elastic'          # 'elastic' or 'rigid'
```

### 2. Ensure EMG Data is Available

Make sure EMG files are available for each trial:
- `{trial_folder}/emg.mot` (or similar EMG file)

The `EMG_muscle_mapping` in settings.py maps EMG channels to muscles:

```python
EMG_muscle_mapping = {
    'EMG_Channels_EMG01_vast_lat_l': ['vaslat_l', 'vasmed_l'],
    'EMG_Channels_EMG02_vast_lat_r': ['vaslat_r', 'vasmed_r'],
    # ... etc for all muscles
}
```

### 3. Run the Batch Pipeline

```bash
python __main__.py -batch settings.py
```

## Pipeline Steps

### STEP 7: CEINMS Calibration

**Sub-steps:**

1. **Create CEINMS Model** (7.1)
   - Converts scaled OpenSim model to CEINMS neuromuscular format
   - Output: `{participant_id}_uncalibrated.xml`

2. **Create Excitation Generator** (7.2)
   - Maps EMG channels to muscles from `settings.EMG_muscle_mapping`
   - Output: `excitationGenerator.xml`

3. **Create Input Data XMLs** (7.3)
   - Generates trial-specific input files using Inverse Dynamics output
   - Creates input data for each calibration trial
   - Output: `inputData.xml` in each trial folder

4. **Create Calibration Configuration** (7.4)
   - Generates CEINMS calibration parameters XML
   - Output: `calibrationCfg_{calibration_type}.xml`

5. **Create Calibration Setup** (7.5)
   - Creates main calibration control file
   - Output: `calibrationSetup_{calibration_type}.xml`

6. **Run Calibration** (7.6)
   - Executes CEINMS calibration on selected trials
   - Optimizes muscle parameters to match experimental joint moments
   - Output: `{participant_id}_calibrated_{calibration_type}.xml`

### STEP 8: CEINMS Execution

Runs muscle force estimation on all trials using the calibrated model:
- Input: Inverse Dynamics output + calibrated CEINMS model
- Output: Muscle forces in `Execution_a{alpha}_b{beta}_g{gamma}/MuscleForces.sto`

## File Organization

After completion, the results directory contains:

```
P012/
├── {trial_1}/
│   ├── joint_angles.mot
│   ├── inverse_dynamics.sto
│   ├── inputData.xml               ← Created in STEP 7.3
│   └── emg.mot
├── {trial_2}/
│   └── ... (same structure)
├── P012_uncalibrated.xml           ← Created in STEP 7.1
├── P012_calibrated_hybrid.xml      ← Created in STEP 7.6
├── excitationGenerator.xml         ← Created in STEP 7.2
├── calibrationCfg_hybrid.xml       ← Created in STEP 7.4
├── calibrationSetup_hybrid.xml     ← Created in STEP 7.5
├── calibration_hybrid/
│   └── ... (calibration outputs)
└── Execution_a10_b1_g1000/
    ├── MuscleForces.sto            ← Created in STEP 8
    └── ... (execution outputs)
```

## Calibration Trials

Specify which trials to use for calibration in settings:

```python
calibration_trial_names = ['sprint', 'cmj_02']
```

These trials must:
1. Have Inverse Dynamics output (`inverse_dynamics.sto`)
2. Optionally have EMG data (`emg.mot`)
3. Exist in the session results folder

## Calibration Parameters

All calibration parameters can be customized in `BatchSettings`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ceinms_learning_rate` | 0.02 | Optimization learning rate |
| `ceinms_max_iterations` | 1000 | Maximum optimization iterations |
| `ceinms_early_stopping_patience` | 20 | Iterations without improvement before stopping |
| `ceinms_early_stopping_min_improvement` | 0.1 | Minimum improvement threshold (%) |
| `ceinms_num_synergies` | 4 | Number of motor synergies (for hybrid calibration) |
| `ceinms_tendon_type` | 'elastic' | Tendon model: 'elastic' or 'rigid' |

## Workflow Integration

The complete biomechanical analysis pipeline now runs:

```
1. Model Scaling (STEP 2)
2. Muscle Scaling (STEP 2b)
3. Inverse Kinematics (STEP 3)
4. Inverse Dynamics (STEP 4)
5. Static Optimization (STEP 5)
6. Muscle Analysis (STEP 6)
7. CEINMS Calibration (STEP 7) ← NEW
8. CEINMS Execution (STEP 8)   ← NEW
```

Each step can be independently enabled/disabled in batch settings.

## Troubleshooting

### Missing EMG Data
- If EMG files are missing, the excitation generator will still be created but may be incomplete
- Ensure all trials have `emg.mot` files for proper CEINMS execution

### Calibration Convergence Issues
- Increase `ceinms_max_iterations` (e.g., 1500, 2000)
- Adjust `ceinms_learning_rate` (try 0.01, 0.05)
- Check Inverse Dynamics output for quality and range

### Memory Issues
- Reduce the number of calibration trials
- Use shorter time windows in calibration trials

## Example Usage

```python
# settings.py
class BatchSettings:
    session_folder = r'C:\Users\Basilio\ucloud\Squat_Width\Simulations\P012'
    
    # OpenSim Pipeline
    enable_scale_model = True
    enable_inverse_kinematics = True
    enable_inverse_dynamics = True
    enable_static_optimization = False
    enable_muscle_analysis = False
    
    # CEINMS Pipeline
    enable_ceinms_calibration = True
    enable_ceinms_execution = True
    calibration_trial_names = ['sprint', 'cmj_02']
    ceinms_calibration_type = 'hybrid'
    ceinms_learning_rate = 0.02
    ceinms_max_iterations = 1000
```

Run:
```bash
python __main__.py -batch settings.py
```

## References

- CEINMS: Calibrated EMG-Informed Neuromusculoskeletal Modeling
- Uses EMG data to calibrate neuromuscular model parameters
- Produces subject-specific estimates of muscle forces
