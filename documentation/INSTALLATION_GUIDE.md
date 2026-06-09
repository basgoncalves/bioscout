# Installation Guide - Powerlifting Model Analysis App

## Overview

The app now includes an **automatic dependency installer** that will:
1. Check if OpenSim is installed
2. If missing, show available versions from PyPI
3. Let you choose which version to install
4. Download and install it automatically
5. Handle all other dependencies

## Quick Start

### Windows (Easiest)

Just run the launcher - it handles everything:

```cmd
cd C:\Git\powerlifing_model_clean\code\tests\app
run.bat
```

Or navigate to the folder and double-click `run.bat`

The launcher will:
- Check Python installation
- Install basic dependencies if needed
- Launch the app
- App will then check for OpenSim and install if needed

### macOS/Linux

```bash
cd C:\Git\powerlifing_model_clean\code\tests\app
pip install customtkinter pyyaml packaging
python main.py
```

## What Happens When You Launch

### First Time Startup Flow

```
1. App checks if OpenSim is installed
   ├─ If YES → Skip to step 4
   └─ If NO → Continue to step 2

2. App offers to install OpenSim
   ├─ Downloads list of available versions from PyPI
   ├─ Shows top 10 versions
   └─ Asks you which one to install

3. You select a version (or auto-select latest)
   └─ App downloads and installs it (~5-10 minutes)

4. App checks other dependencies (numpy, matplotlib, etc.)
   └─ Installs any missing ones

5. App launches when all dependencies are ready
   └─ Ready to use!
```

## OpenSim Installation Details

### What is OpenSim?

[OpenSim](https://opensim.stanford.edu/) is a free, open-source software for modeling and simulating musculoskeletal structures and dynamics. It's required for your biomechanical analysis pipeline.

### Available Versions

The installer will show the **10 most recent stable versions** available on PyPI:

```
Available OpenSim versions (10 shown):

  1. 4.4.1
  2. 4.4.0
  3. 4.3.1
  4. 4.3
  5. 4.2
  ...
```

### Recommended Version

- **Latest (4.4.1+)** - Recommended for new installations
- **4.4.x** - Well-tested, stable
- **4.3.x** - Also good, slightly older

If unsure, just select option "Latest (auto-select)" and the app will install the newest version.

### Installation Time

OpenSim is large (~500MB) and may take 5-10 minutes to download and install depending on internet speed.

## Troubleshooting

### "ModuleNotFoundError: No module named 'opensim'"

This means OpenSim installation failed. Try again:

```bash
python main.py
```

The app will ask again if you want to install OpenSim.

### "Connection error when fetching versions"

Internet connectivity issue. Either:
1. Check your internet connection
2. Click "Skip interactive installation" (will install latest version)
3. Choose "Cancel" and install manually:

```bash
pip install opensim-core
```

### "Installation timeout"

Installation took too long. Try again with the latest version - it usually installs faster.

### Python says "module not found: customtkinter"

The basic dependencies weren't installed. Run:

```bash
pip install customtkinter pyyaml packaging
python main.py
```

### "ImportError: cannot import name 'osim'"

OpenSim is installed but Python can't find it. This can happen with conda environments. Try:

```bash
pip install --upgrade opensim-core
```

Or use the app's installer to reinstall a specific version.

## Manual Installation (Alternative)

If the automatic installer doesn't work for any reason, you can install all dependencies manually:

### Step 1: Basic Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: OpenSim (if not included in requirements.txt)

```bash
pip install opensim-core
```

Or specific version:

```bash
pip install opensim-core==4.4.1
```

### Step 3: Verify Installation

```bash
python -c "import opensim; print(opensim.__version__)"
```

Should print something like: `4.4.1`

## Advanced: System-Wide OpenSim

If you want to use the system-installed OpenSim (compiled from source) instead of the PyPI package:

1. **Install OpenSim from source** following [official instructions](https://opensim.stanford.edu/site/downloads/)

2. **Add to Python path**: Create a file in the app directory called `local_settings.py`:

```python
# local_settings.py
import sys
import os

# Add OpenSim to Python path
OPENSIM_PYTHON_DIR = "C:\\path\\to\\opensim\\lib\\python"
if os.path.exists(OPENSIM_PYTHON_DIR):
    sys.path.insert(0, OPENSIM_PYTHON_DIR)
```

3. **Run the app** - it will use your local OpenSim installation

## Automatic Dependency Checking

The app includes a smart dependency checker (`utils/dependency_installer.py`) that:

### Checks For:

**Critical (Required):**
- customtkinter - GUI framework
- PyYAML - Configuration files
- numpy - Numerical computing
- opensim - Biomechanical modeling

**Optional (Nice to have):**
- matplotlib - Plotting
- pandas - Data analysis
- scipy - Scientific computing

### Installation Strategy:

1. **First launch** - Interactive (asks user)
2. **Missing OpenSim** - Special handling with version selection
3. **Missing others** - Auto-installed or user prompt
4. **All installed** - App launches immediately

## Testing Your Installation

Once installed, verify everything works:

```bash
# Test in Python
python -c "import opensim; import customtkinter; import yaml; print('All dependencies OK!')"

# Run the app
python main.py
```

If you see "All dependencies OK!" your system is ready.

## Version Management

### Update OpenSim

To update to a newer version:

```bash
pip install --upgrade opensim-core
```

Or reinstall a specific version:

```bash
pip install opensim-core==4.4.1 --force-reinstall
```

### Downgrade OpenSim

If you need an older version:

```bash
pip install opensim-core==4.3.0
```

## Environment-Specific Notes

### Conda Users

If you're using Anaconda/Miniconda:

```bash
# Create new environment
conda create -n opensim-app python=3.10

# Activate
conda activate opensim-app

# Install dependencies
pip install -r requirements.txt
pip install opensim-core

# Run app
python main.py
```

### Virtual Environment Users

```bash
# Create venv
python -m venv opensim_env

# Activate (Windows)
opensim_env\Scripts\activate

# Activate (Mac/Linux)
source opensim_env/bin/activate

# Install
pip install -r requirements.txt

# Run
python main.py
```

## Getting Help

If you encounter installation issues:

1. **Check the console output** - Look for specific error messages
2. **Check application logs** - `~/.powerlifting_app/logs/`
3. **Verify internet connection** - For downloading packages
4. **Try manual installation** - See "Manual Installation" section above
5. **Check OpenSim documentation** - https://opensim.stanford.edu/

## Next Steps

Once installed successfully:

1. Read [QUICKSTART.md](QUICKSTART.md) for a 5-minute guide
2. Read [README.md](README.md) for full documentation
3. Open a trial directory and click "IK Only" to test

Enjoy! 🏋️‍♀️
