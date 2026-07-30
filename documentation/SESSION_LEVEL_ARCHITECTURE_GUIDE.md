# Session-Level Analysis Architecture Guide

**Version:** 2.1.0  
**Last Updated:** 2026-05-13

## Overview

The Powerlifting Model Analysis Application has been refactored to support **session-level analysis**, enabling efficient processing of multiple trials within a single session. This guide explains the new architecture and how to use it.

---

## Architecture Overview

### What Changed

The application transitioned from **trial-level analysis** to **session-level analysis**:

| Aspect | Trial-Level (Old) | Session-Level (New) |
|--------|------------------|-------------------|
| **Scope** | Single trial at a time | Multiple trials in parallel |
| **Trial Discovery** | Manual selection | Auto-discovery from C3D/TRC files |
| **Selection** | Pre-selected single trial | Multi-select with status indicators |
| **Validation** | Per-trial checks | Per-trial + session-wide validation |
| **Batch Processing** | Via Batch tab | Native in Analysis/CEINMS tabs |

### Core Components

#### 1. **Session Manager** (`core/session_manager.py`)
Orchestrates multi-trial operations:

- **`TrialValidator`**: Validates individual trials based on file requirements
  - `BASIC_REQUIREMENTS`: For core analysis (C3D, markers, GRF)
  - `CEINMS_REQUIREMENTS`: For CEINMS calibration (includes scaled model, GRF.xml)
  - `EMG_REQUIREMENTS`: For EMG processing (filtered EMG signals)

- **`SessionManager`**: Manages session-level operations
  - Auto-discovers trials (folders containing C3D or TRC files)
  - Returns trial list with status information
  - Validates trials for different analysis types
  - Provides session summary with trial counts and readiness

#### 2. **Analysis Control Session Tab** (`gui/widgets/analysis_control_session.py`)
Session-level analysis with trial auto-discovery:

**Features:**
- Load session directory (browse or paste path)
- Auto-discover valid trials (C3D/TRC detection)
- Display trial list with status indicators
  - ✓ Green: Trial has required files, ready for analysis
  - ✗ Red: Trial missing required files
- Multi-select trials for batch analysis
- Select analysis steps (Core, Extended, Advanced Dynamics)
- Run analysis on all selected trials in background
- Real-time progress tracking with status updates

**Analysis Steps Available:**
```
Core (OpenSim):
  - Inverse Kinematics (IK)
  - Inverse Dynamics (ID)
  - Static Optimization (SO)

Extended:
  - Muscle Analysis
  - Joint Reaction Analysis

Advanced Dynamics:
  - Residual Reduction Algorithm (RRA)
  - Computed Muscle Control (CMC)
  - Energetics (Metabolic Cost)
  - Body Kinematics
```

#### 3. **CEINMS Calibration Session Tab** (`gui/widgets/ceinms_calibration_session.py`)
Session-level CEINMS calibration with trial selection:

**Features:**
- Load session directory (browse or paste path)
- Auto-discover valid trials for CEINMS
- Display trial list with CEINMS-specific status
  - ✓ Green: Trial has all CEINMS requirements (model, GRF.xml, etc.)
  - ✗ Red: Trial missing CEINMS files (disabled for selection)
- "Select All Ready Trials" button
- Right-click to view missing files for incomplete trials
- Run CEINMS calibration on selected trials

**CEINMS Requirements:**
- C3D file
- Marker file (TRC)
- GRF file (MOT)
- GRF XML configuration
- Scaled OpenSim model

#### 4. **Version System** (`version.py`)
Centralized version tracking:

```python
APP_VERSION = "2.1.0"

MODULE_VERSIONS = {
    "config": "1.2.0",      # Configuration system
    "core": "2.0.0",        # Analysis runner & orchestration
    "gui": "2.1.0",         # GUI framework
    "utils": "2.0.0",       # Utilities & data handling
    "openSim": "2.1.0",     # OpenSim wrapper with new steps
    "ceinms": "1.1.0",      # CEINMS integration
    "emg_normalise": "1.0.0", # EMG processing
    "exportC3D": "1.0.0",   # C3D export
    "logger": "1.0.0",      # Logging system
}

COMPONENT_VERSIONS = {
    "analysis_runner": "2.0.0",
    "analysis_step_enum": "2.0.0",
    "session_manager": "1.0.0",
    "trial_discovery": "1.0.0",
    "ceinms_calibration": "1.1.0",
    "emg_processing": "2.0.0",
}
```

---

## Updated Analysis Pipeline

### Removed Steps
- ~~EMG_NORMALISE~~ (moved to EMG Processing tab)
- ~~SCALE_EMG~~ (moved to EMG Processing tab)

### New Steps Added
1. **RRA (Residual Reduction Algorithm)**: Reduces dynamics inconsistencies
2. **CMC (Computed Muscle Control)**: Optimizes muscle excitations
3. **ENERGETICS (Metabolic Cost)**: Calculates energy expenditure
4. **BODY_KINEMATICS**: Computes body position/velocity/acceleration

### Step Organization

```
AnalysisStep Enum:
  Core (OpenSim):
    - INVERSE_KINEMATICS
    - INVERSE_DYNAMICS
    - STATIC_OPTIMIZATION
  
  Extended:
    - MUSCLE_ANALYSIS
    - JOINT_REACTION_ANALYSIS
  
  Advanced Dynamics:
    - RRA
    - CMC
    - ENERGETICS
    - BODY_KINEMATICS
```

---

## How to Use the New Architecture

### Scenario 1: Run Session-Level Analysis

1. **Open "Analysis" Tab** in the main window
2. **Load Session Directory**
   - Click "Browse" or paste session path
   - Click "Load" to auto-discover trials
3. **Review Trial Status**
   - Green (✓): Ready for analysis
   - Red (✗): Missing files (can still select if needed)
4. **Select Trials**
   - Check individual trials
   - Use "Select All" / "Deselect All" buttons
5. **Choose Analysis Steps**
   - Select steps from Core, Extended, Advanced Dynamics groups
6. **Run Analysis**
   - Click "▶ Run Pipeline"
   - Monitor progress in status bar
   - View results once complete

### Scenario 2: CEINMS Calibration

1. **Open "CEINMS Calibration" Tab** in the main window
2. **Load Session Directory**
   - Click "Browse" or paste session path
   - Click "Load" to auto-discover trials
3. **Review CEINMS Status**
   - Green (✓): Trial ready for CEINMS calibration
   - Red (✗): Trial missing CEINMS files (disabled)
4. **Select Trials for Calibration**
   - Check trials that are ready (green)
   - Use "Select All Ready Trials" to auto-select
   - Right-click on red trials to see missing files
5. **Run CEINMS Calibration**
   - Click "▶ Run CEINMS Calibration"
   - Monitor progress in status bar

### Scenario 3: EMG Processing

1. **Open "EMG Processing" Tab** in the main window
2. **Load Session Directory** (if session-level processing)
3. **Process EMG Data**
   - Select filters, normalization options
   - Preview signals with interactive plotting
   - Export to STO format if needed

---

## File Structure

```
code/tests/app/
├── version.py                              # Version tracking system
├── core/
│   ├── session_manager.py                  # NEW: Trial discovery & validation
│   ├── analysis_runner.py                  # UPDATED: Progress callback fix
│   └── __init__.py
├── gui/
│   ├── main_window.py                      # UPDATED: New tab imports
│   ├── widgets/
│   │   ├── analysis_control_session.py     # NEW: Session-level analysis
│   │   ├── ceinms_calibration_session.py   # NEW: Session-level CEINMS
│   │   ├── emg_processing_session.py       # EMG Processing tab
│   │   ├── analysis_control_simplified.py  # OLD: Single-trial (kept for reference)
│   │   └── ...
│   └── __init__.py
├── utils/
│   ├── __init__.py                         # FIXED: Truncation & null byte errors
│   ├── openSim.py                          # UPDATED: New analysis methods
│   └── ...
└── ...
```

---

## Key Improvements

### 1. **Auto-Discovery System**
- Automatically finds valid trials (C3D or TRC files)
- No manual folder navigation required
- Clear status indicators for each trial

### 2. **File Validation**
- Different requirement sets per analysis type:
  - Basic analysis: C3D, markers, GRF
  - CEINMS: Includes scaled model and GRF.xml
  - EMG: Filtered EMG signals
- Disabled selection for incomplete trials (CEINMS tab)
- Right-click to view missing files

### 3. **Batch Processing**
- Select multiple trials once
- Run analysis on all trials in background
- No need to repeat configuration per trial

### 4. **Progress Tracking**
- Real-time status updates
- Progress bar for multi-trial runs
- Success/failure summary at completion

### 5. **Version Tracking**
- Centralized version information
- Module-level versioning
- Easy to share and track capabilities

---

## Development Notes

### Progress Callback Pattern

The new architecture uses a dictionary-based progress callback:

```python
def _update_progress(self, step, status, progress):
    """Update progress with dictionary callback."""
    if self.progress_callback:
        self.progress_callback({
            'step': step,
            'status': status,
            'progress': progress  # 0-100
        })
```

GUI tabs receive updates via:

```python
def _on_progress(self, progress_info: dict) -> None:
    """Handle progress updates from runner."""
    step = progress_info.get('step', '')
    status = progress_info.get('status', '')
    progress = progress_info.get('progress', 0)
    
    if progress is not None:
        self.progress_bar.set(progress / 100)
    
    self.status_label.configure(text=f"{step}: {status}")
```

### Trial Validation Example

```python
from core.session_manager import SessionManager, TrialValidator

# Load session
manager = SessionManager('/path/to/session')
trials = manager.discover_trials()

# Check trial status
for trial_path in trials:
    status = TrialValidator.get_trial_status(trial_path)
    print(f"Trial: {status['name']}")
    print(f"  Basic ready: {status['basic_complete']}")
    print(f"  CEINMS ready: {status['ceinms_complete']}")
    print(f"  EMG ready: {status['emg_complete']}")
```

---

## Testing Recommendations

### 1. **Unit Tests**
- Test TrialValidator with sample trial folders
- Test SessionManager discovery with various folder structures
- Test progress callback with different analysis steps

### 2. **Integration Tests**
- Load session with multiple trials
- Run analysis on selected trials
- Verify progress callbacks fire correctly
- Check results are saved to correct locations

### 3. **User Acceptance Tests**
- Create sample data directory with 5-10 trials
- Run full analysis pipeline (IK → ID → SO)
- Run CEINMS calibration on ready trials
- Verify results in Results Viewer tab

---

## Known Limitations

1. **CEINMS Calibration**: Currently has placeholder implementation (marked TODO at line 322)
   - Needs actual CEINMS integration
   - Background thread structure is ready for implementation

2. **EMG Processing Tab**: Not yet integrated with session-level architecture
   - Works at trial level currently
   - Can be upgraded to session-level if needed

3. **Batch Processor Tab**: Partially redundant with new session-level tabs
   - Kept for backward compatibility
   - Could be deprecated in future versions

---

## Next Steps

1. **Complete CEINMS Calibration**: Implement actual calibration logic
2. **Add Test Trial Data**: Create sample session directories
3. **Integration Testing**: Run full pipeline with real data
4. **Documentation**: Create user manual with screenshots
5. **Performance Optimization**: Profile multi-trial runs
6. **Error Handling**: Add recovery mechanisms for failed trials

---

## Support & Issues

For issues or questions:
1. Check trial status indicators (green/red)
2. Right-click trials to see missing files
3. Check application logs in Logs tab
4. Review error messages in status bar
5. Check console output for detailed errors

---

## Version History

### v2.1.0 (2026-05-13)
- Added session-level analysis with auto-discovery
- Added RRA, CMC, Energetics, Body Kinematics steps
- Implemented centralized version tracking
- Fixed progress callback signature
- Created comprehensive session management system

### v2.0.0 (2026-05-12)
- Complete module import system fix
- AnalysisRunner restructured with proper callbacks
- GUI simplified with session-level focus
- EMG Processing tab enhancements

### v1.0.0 (2026-01-01)
- Initial release with basic OpenSim analysis pipeline
