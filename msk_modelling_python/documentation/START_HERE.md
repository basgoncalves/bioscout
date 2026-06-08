# 🚀 START HERE

## Welcome to the Powerlifting Model Analysis App!

This document will get you up and running in **2 minutes**.

---

## What You Have

A complete, production-ready **GUI application** that combines all your biomechanical analysis modules into one easy-to-use interface.

✅ Single-trial analysis
✅ Session-level batch processing  
✅ Auto-detects input files
✅ Real-time progress tracking
✅ EMG processing tools
✅ Settings persistence

---

## Quick Start (2 Minutes)

### Step 1: Open Command Prompt/Terminal

Navigate to the app directory:
```bash
cd C:\Git\powerlifing_model_clean\code\tests\app
```

### Step 2: Launch the App

```bash
python run.py
```

That's it! The app will:
- Check for required packages (customtkinter, opensim, etc.)
- Automatically install missing dependencies
- Launch the GUI

### Step 3: Use the App

1. **Click "Browse"** → Select a trial or session directory
2. **Check analysis steps** you want to run (e.g., Inverse Kinematics)
3. **Click "▶ Run Pipeline"**
4. Watch the progress bar and output log

---

## Documentation (Pick What You Need)

| Document | Read This If... |
|----------|-----------------|
| **QUICK_REFERENCE.txt** | You want a quick cheat sheet (workflows, shortcuts) |
| **README_LATEST.md** | You want the complete user guide |
| **IMPROVEMENTS.md** | You want to understand the new features |
| **VERIFICATION.md** | You want technical details and architecture |

**Recommended order:**
1. QUICK_REFERENCE.txt (2 min) ← Start here for quick workflows
2. README_LATEST.md (10 min) ← Full details
3. IMPROVEMENTS.md (5 min) ← New features explained

---

## First Workflow: Quick Test (IK Only)

Perfect for validating your setup:

```
1. Click "Browse" → Select a trial directory
2. Check only: "Inverse Kinematics"
3. Click "▶ Run Pipeline"
4. Wait ~5-10 minutes
5. Review results in trial directory
```

---

## Features at a Glance

### 6 Tabs in the GUI

| Tab | What It Does |
|-----|--------------|
| **EMG Processing** | Filter and normalize EMG signals |
| **Analysis** | Run single-trial or session analyses ⭐ MAIN TAB |
| **Batch** | Batch processing queue (coming soon) |
| **Results** | View and compare results |
| **Configuration** | Adjust project settings |
| **Logs** | View application logs |

### Key Buttons

- **Browse** - Select a directory
- **Reload Files** - Refresh detected input files
- **Save Settings** - Save analysis configuration
- **Edit Settings** - Open settings in text editor
- **▶ Run Pipeline** - Execute analysis
- **⏹ Stop** - Stop running analysis

### Auto-Detected Files

The app automatically finds:
- Motion capture (*.c3d)
- Marker files (*marker*.trc)
- EMG data (*emg*.mot)
- Ground forces (*grf*.mot)
- Events (*.csv)
- OpenSim model (*.osim)

---

## Typical Workflows

### Workflow 1: Validate Marker Data
```
Time: ~5 min
1. Browse to trial
2. Select "Inverse Kinematics"
3. Run Pipeline
4. Check marker error plots
```

### Workflow 2: Full Single-Trial Analysis
```
Time: ~20-30 min
1. Browse to trial
2. Select: IK, ID, SO, Muscle Analysis
3. Save Settings (optional)
4. Run Pipeline
5. View results
```

### Workflow 3: Analyze Entire Session
```
Time: Varies (1-4 hours depending on trials)
1. Browse to SESSION directory (parent of trials)
2. Select "Entire Session"
3. Select your analysis steps
4. Run Pipeline (processes all subdirectories)
```

### Workflow 4: Preprocess EMG Data
```
Time: ~5 min
1. Go to "EMG Processing" tab
2. Select high-pass frequency (20 Hz recommended)
3. Choose normalization (MVC-based or RMS-based)
4. Check "Extract envelope" and "Apply smoothing"
5. Click "Process EMG"
```

---

## Troubleshooting

### App Won't Launch

```bash
# Check system
python test_gui_launch.py
```

Expected output: "All tests passed"

If you get errors, check:
- Python version (3.8+)
- CustomTkinter installed (`pip install customtkinter`)
- Logs in `logs/` folder

### No Input Files Found

- Ensure files are in the trial directory
- Check file names match patterns:
  - EMG file: must contain "emg" (e.g., `emg_data.mot` or `right_emg.mot`)
  - Marker file: must contain "marker" (e.g., `markers.trc`)
  - C3D file: `*.c3d`

- Try "Reload Files" button

### Analysis is Very Slow

- Normal! Each trial takes 10-30 minutes depending on:
  - Number of analysis steps selected
  - Trial duration
  - OpenSim version
- Session analysis multiplies this by number of trials

### Settings Won't Save

- Make sure trial directory is writable
- "Save Settings" button creates `trial_settings.xml`
- Try "Edit Settings" button to create file manually

---

## File Locations

```
C:\Git\powerlifing_model_clean\code\tests\app\
├── run.py              ← CLICK THIS TO START
├── QUICK_REFERENCE.txt ← QUICK CHEAT SHEET
├── README_LATEST.md    ← FULL USER GUIDE
├── VERIFICATION.md     ← TECHNICAL DETAILS
├── logs/               ← ERROR LOGS HERE
└── config/             ← SETTINGS HERE
```

---

## Settings Files

The app creates two types of settings:

1. **Global Config**: `config/default_config.yaml`
   - Project-wide settings
   - Analysis parameters
   - Batch processing options

2. **Per-Trial Config**: `trial_directory/trial_settings.xml`
   - Trial-specific settings
   - Selected analysis steps
   - Input file choices
   - Created automatically or via "Save Settings" button

---

## Next Steps

### Right Now
1. ✅ You've read this file
2. ⏭️ **Launch the app**: `python run.py`
3. ⏭️ **Test with a trial**: Browse and run IK
4. ⏭️ **Review logs**: Check logs/ folder if issues

### Later
- [ ] Read QUICK_REFERENCE.txt for more workflows
- [ ] Read README_LATEST.md for complete documentation
- [ ] Test session-level analysis
- [ ] Try EMG Processing tab
- [ ] Explore Configuration tab

---

## System Requirements

- **Python**: 3.8 or higher
- **OS**: Windows, Mac, or Linux
- **RAM**: 4GB minimum (8GB recommended)
- **Disk**: 2GB for dependencies
- **Disk Space**: Varies by analysis (100MB-5GB per trial)

---

## Installation

### Automatic (Recommended)

```bash
python run.py
```

Dependencies installed automatically.

### Manual

```bash
pip install -r requirements.txt
python __main__.py
```

---

## What's New This Version

✅ **EMG Processing Tab** - Filter, normalize, and export EMG signals
✅ **Improved Analysis Control** - Simpler, cleaner interface
✅ **Session-Level Analysis** - Process entire sessions automatically
✅ **Input File Auto-Detection** - Finds C3D, markers, EMG, etc.
✅ **Settings Persistence** - Save/load analysis configurations
✅ **Real-Time Progress** - Watch analysis execute live

---

## Getting Help

1. **Quick question?** → QUICK_REFERENCE.txt
2. **How do I...?** → README_LATEST.md
3. **Technical details?** → VERIFICATION.md
4. **What's new?** → IMPROVEMENTS.md
5. **Something broken?** → Check logs/ folder

---

## Ready?

```bash
python run.py
```

Enjoy! 🚀

---

**Questions or Feedback?**
- Check the documentation files
- Review logs in `logs/` folder
- Run `python test_gui_launch.py` for system check
