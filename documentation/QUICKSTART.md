# Quick Start Guide - Powerlifting Model Analysis App

## 🚀 Get Started in 5 Minutes

### Step 1: Install Dependencies (One-time)

**Windows (Command Prompt)**:
```cmd
cd C:\Git\powerlifing_model_clean\code\tests\app
pip install -r requirements.txt
```

**macOS/Linux (Terminal)**:
```bash
cd C:\Git\powerlifing_model_clean\code\tests\app
pip install -r requirements.txt
```

### Step 2: Launch the App

**Windows** - Double-click:
```
run.bat
```

**Or Command Line (All platforms)**:
```bash
python main.py
```

### Step 3: Your First Analysis

1. **Go to "Analysis" Tab** (default tab when you open the app)

2. **Select a Trial**:
   - Click "Browse" button
   - Navigate to a trial directory (e.g., `simulations/subject1/session1/trial1`)
   - Click "Open"

3. **Choose Analysis Steps**:
   - Use a quick preset (easiest):
     - Click "IK Only" for a quick validation
     - Or "Full Pipeline" for complete analysis
   - Or manually check the boxes for specific steps

4. **Run Analysis**:
   - Click "Run Analysis" button
   - Watch the progress and output in the right panel
   - Analysis runs in background (GUI stays responsive)

5. **View Results**:
   - Check output console for messages
   - Look for results in your results directory
   - Use the "Results" tab (coming soon) to view plots

## 📋 Main Tabs Explained

### 1️⃣ **Analysis** (The Main Tab)
- **What**: Run analysis on individual trials
- **Use When**: You want to analyze a single trial with specific steps
- **Quick Actions**:
  - "IK Only" preset - Just run inverse kinematics for quick check
  - "Full Pipeline" preset - Run all major analysis steps
  - Manual step selection - Pick exactly what you want to run

### 2️⃣ **Batch** 
- **What**: Process multiple trials at once
- **Use When**: You have many subjects/sessions/trials to process
- **Quick Actions**:
  - Enable "Auto-Discovery" to find all trials automatically
  - Choose "Parallel" mode for faster processing (if you have multiple CPU cores)
  - Set "Max Workers" to number of CPUs you have

### 3️⃣ **Results**
- **What**: View analysis results and generate plots
- **Use When**: Your analysis is done and you want to visualize results
- **Quick Actions**:
  - Browse to your results directory
  - Select plot type (moment residuals, EMG vs activation, etc.)
  - Click "Generate Plot"

### 4️⃣ **Configuration**
- **What**: Adjust settings for your analyses
- **Use When**: You need to change parameters or file paths
- **Quick Actions**:
  - Adjust analysis settings (enable/disable steps by default)
  - Change CEINMS parameters (alpha, beta, gamma)
  - Set processing mode (sequential or parallel)
  - Click "Save Configuration" when done

### 5️⃣ **Logs**
- **What**: View application logs for debugging
- **Use When**: Something doesn't work and you need to troubleshoot
- **Quick Actions**:
  - Read the output to find error messages
  - Click "Open Log Folder" to save logs elsewhere
  - Click "Clear" to clear the display

## 🎯 Common Workflows

### Workflow A: Quick Validation
Perfect for checking if a trial is valid before running full analysis:

```
1. Open app
2. Go to "Analysis" tab
3. Browse and select trial
4. Click "IK Only" preset
5. Click "Run Analysis"
6. Wait 2-5 minutes
7. Check output for success/errors
```

### Workflow B: Full Analysis
For complete biomechanical analysis:

```
1. Open app
2. Go to "Analysis" tab
3. Browse and select trial
4. Click "Full Pipeline" preset
5. (Optional) Go to "Configuration" to adjust parameters
6. Go back to "Analysis" tab
7. Click "Run Analysis"
8. Wait 10-30 minutes (depending on parameters)
9. View results in "Results" tab
```

### Workflow C: Batch Processing
For processing multiple trials:

```
1. Open app
2. Go to "Batch" tab
3. Enable "Auto-Discovery"
4. Select "Parallel" mode
5. Set "Max Workers" (e.g., 4)
6. Click "Start Batch Processing"
7. Monitor progress
8. View all results when complete
```

## ⚙️ Configuration Quick Tips

### Change Default Analysis Steps
1. Go to "Configuration" tab
2. In "Analysis Pipeline" section, check/uncheck steps
3. Click "Save Configuration"
4. These will be the defaults next time you open the app

### Change Processing Mode
1. Go to "Configuration" tab
2. In "Processing Options" section
3. Choose "Sequential" (one at a time) or "Parallel" (multiple at once)
4. If Parallel, set number of workers
5. Click "Save Configuration"

### Change CEINMS Parameters
1. Go to "Configuration" tab
2. In "CEINMS Parameters" section
3. Adjust Alpha, Beta, Gamma values
4. Click "Save Configuration"

## 🐛 Troubleshooting

### Problem: "Browse button doesn't work"
**Solution**: Make sure your trial directory exists and has the required files (c3d, markers, etc.)

### Problem: "Analysis starts but shows no progress"
**Solution**: This is normal - long analyses don't show detailed progress. Check the logs tab after it's done.

### Problem: "Get ImportError for opensim"
**Solution**: 
```bash
# Make sure OpenSim is installed
# Try: python -c "import opensim; print(opensim.__version__)"
# If not installed, see OpenSim installation instructions
```

### Problem: "Application is frozen"
**Solution**: The app runs analysis in background. Wait a few seconds and it will respond. Use the "Stop" button to cancel if needed.

## 💡 Pro Tips

1. **Use IK Only preset** first to validate trial setup
2. **Enable parallel processing** in Configuration for faster batch runs
3. **Check logs** if analysis fails - scroll down in Logs tab to see errors
4. **Save configurations** for different experiment types
5. **Use auto-discovery** for batch processing - it finds all trials automatically

## 📁 Where Are My Results?

Results are saved in the same directory as your trial:
```
simulations/
  subject1/
    session1/
      trial1/
        results/
          ik_results/          ← Inverse kinematics outputs
          id_results/          ← Inverse dynamics outputs
          so_results/          ← Static optimization outputs
          etc...
```

Or check the path in Configuration tab under "Results Directory"

## 🎓 Next Steps

- Read full documentation in **README.md**
- Understand all options in **IMPLEMENTATION_SUMMARY.md**
- Check default configuration in **config/default_config.yaml**
- View application logs at: `~/.powerlifting_app/logs/`

## ✅ Ready?

**You're all set!** 

1. Make sure you have your trial directories ready
2. Install requirements if you haven't: `pip install -r requirements.txt`
3. Double-click `run.bat` (Windows) or `python main.py`
4. Select your first trial and click "Run Analysis"

Good luck! 🏋️‍♀️
