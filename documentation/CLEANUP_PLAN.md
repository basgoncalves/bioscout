# Project Cleanup & Organization Plan

## Files to Move

### 1. Documentation Files (.md)
Moving from various locations to `/documentation/`:

**From `/gui/` to `/documentation/`:**
- UI_IMPROVEMENTS_SUMMARY.md
- PERFORMANCE_AND_MARKERS_IMPROVEMENTS.md

**From `/app/` root to `/documentation/`:**
- BATCH_EXPORT_FIXES.md
- BATCH_EXPORT_FIX_v2.md
- SESSION_LEVEL_RESTRUCTURE.md
- EMG_NORMALIZATION_GUIDE.md

**From `/outputs/` to `/documentation/` (keep as reference):**
- RESULTS_VIEWER_IMPLEMENTATION_SUMMARY.md
- SESSION_CLEANUP_AND_EMG_UPDATES.md
- CHANGES_APPLIED_MAY_20_2026.md
- EMG_NORMALIZATION_TRIAL_SETTINGS_UPDATE.md
- CONSOLE_OUTPUT_FIX.md
- EMG_NORMALIZATION_FIXES.md

### 2. Backup/Temporary Files
These should be archived or deleted from main codebase:

**In `/gui/widgets/`:**
- c3d_grf_viewer_backup_may14.py → Move to `/tests/backups/`
- c3d_grf_viewer_backup_basic.py → Move to `/tests/backups/`
- c3d_grf_viewer_fixed.py → Move to `/tests/backups/` (fixed version merged into main)
- c3d_grf_viewer_improved.py → Check if used, move to `/tests/backups/` if not

### 3. Test Files Organization
Current state (looks good):
- `/tests/test_gui_launch.py` ✅ Correct location
- `/tests/utils/test_import.py` ✅ Correct location

### 4. Verification Files
Check if these are needed:
- `/app/verify_batch_export.py` → Move to `/tests/` if verification script
- `/app/tests/launch_checks.py` → Already in tests, verify it's not duplicated

## Directory Structure After Cleanup

```
code/tests/app/
├── __main__.py
├── settings.py
├── version.py
│
├── config/
│   ├── __init__.py
│   └── config_manager.py
│
├── core/
│   ├── __init__.py
│   ├── session_manager.py
│   └── analysis_runner.py
│
├── gui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── styles.py
│   └── widgets/
│       ├── __init__.py
│       ├── *.py (all active widget files)
│
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   ├── dependency_installer.py
│   ├── emg_normalise.py
│   ├── settings.py
│   ├── openSim.py
│   ├── ceinms.py
│   └── exportC3D.py
│
├── tests/
│   ├── __init__.py
│   ├── test_gui_launch.py
│   ├── launch_checks.py
│   ├── backups/
│   │   ├── c3d_grf_viewer_*.py (archived versions)
│   │   └── *.py (other backups)
│   └── utils/
│       ├── __init__.py
│       └── test_import.py
│
└── documentation/
    ├── README.md (main entry point)
    ├── START_HERE.md
    ├── QUICKSTART.md
    ├── INSTALLATION_GUIDE.md
    ├── IMPLEMENTATION_SUMMARY.md
    ├── SESSION_LEVEL_ARCHITECTURE_GUIDE.md
    ├── TECHNICAL_SPECIFICATION_GRF_VIEWER.md
    ├── (all other .md files organized here)
    └── backups/
        └── (old/archived documentation versions)
```

## Cleanup Action Items

- [ ] Create `/tests/backups/` directory
- [ ] Move backup/old widget files to `/tests/backups/`
- [ ] Move .md files from `/gui/` to `/documentation/`
- [ ] Move .md files from app root to `/documentation/`
- [ ] Move or archive old documentation versions to `/documentation/backups/`
- [ ] Verify `/tests/` contains only active test files
- [ ] Update README with new organization
- [ ] Remove verify_batch_export.py if merged into main app
- [ ] Clean up any .pyc, __pycache__ files

## Benefits After Cleanup

✅ Clean source code directory (only active files)
✅ All documentation in one place (easy to find, maintain)
✅ Backup files preserved but not cluttering active code
✅ Clear test directory with organized test utilities
✅ Professional project structure
✅ Easier to find what's active vs archived
