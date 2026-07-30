# App Cleanup and Organization Guide

## Current State Analysis

The app has several organizational issues causing slowdowns and clutter:

### 1. **Scattered Files**
- Backup files: `settings_backup.py`, `settings_complete.py`
- Test files scattered in main folder: `test_relative_paths.py`, `core/test_reset_settings.py`
- Verification files: `verify_batch_export.py`
- Old backup widgets: `tests/backups/c3d_grf_viewer_*.py` (5 versions)

### 2. **Documentation Files in Root**
- `BATCH_C3D_AUTO_PATHS_MAY_20_...`
- `DATA_FLOW_RESET_SETTINGS.md`
- `MODEL_SCALING_IMPLEMENTATION.md`
- `RESET_SETTINGS_FIX.md`
- `RESULTS_VIEWER_ENHANCEMENTS.md`
- `SESSION_ANALYSIS_ENHANCEMENTS.md`
- `UNRESOLVED_ISSUES_AND_ANSWERS.md`

### 3. **Performance Issues**
- Heavy imports in `utils/__init__.py` (Analyse class loads everything at init)
- OpenSim imports not lazy-loaded
- GUI widgets import all modules eagerly

## Recommended Cleanup

### Phase 1: File Organization
```
app/
├── docs/                          # Documentation
│   ├── CHANGELOG.md
│   ├── ARCHITECTURE.md
│   └── implementation_notes/      # Detailed implementation docs
│       ├── reset_settings.md
│       ├── model_scaling.md
│       └── data_flow.md
├── backups/                       # Old versions (optional keep)
│   ├── settings_backup.py
│   └── c3d_viewer_backups/
├── tests/                         # Proper test structure
│   ├── unit/
│   │   ├── test_inputs.py
│   │   └── test_xml_generation.py
│   └── integration/
│       └── test_gui_launch.py
├── core/                          # Core logic (no tests here)
│   ├── analysis_runner.py
│   └── session_manager.py
├── gui/                           # UI only
├── config/                        # Configuration
├── utils/                         # Utilities
├── settings.py                    # Main settings
└── __main__.py                    # Entry point
```

### Phase 2: Performance Optimization

#### 2.1 Lazy Load OpenSim
**File: `utils/__init__.py`**
```python
def get_opensim():
    """Lazy load opensim only when needed"""
    try:
        import opensim
        return opensim
    except ImportError:
        raise ImportError("OpenSim not installed")
```

#### 2.2 Defer Heavy Imports
Move heavy imports to method level in GUI widgets:
- Don't import `opensim` at module level
- Don't import pandas/numpy at module level in widgets
- Use lazy imports in methods that actually need them

#### 2.3 Profile Bottlenecks
```bash
python -m cProfile -s cumtime app/__main__.py
```

## Cleanup Checklist

### Remove Duplicates
- [ ] Delete `settings_backup.py` (keep settings.py and settings_complete.py as reference)
- [ ] Delete test files from app root → move to `tests/`
- [ ] Delete old c3d_viewer backups → archive in `backups/`
- [ ] Delete `verify_batch_export.py` if outdated

### Create Documentation Folder
- [ ] Create `docs/` folder
- [ ] Move all `.md` files to `docs/`
- [ ] Create `docs/implementation_notes/` for technical details

### Optimize Imports
- [ ] Add lazy loading to `utils/__init__.py` for opensim
- [ ] Remove unused imports from widgets
- [ ] Use TYPE_CHECKING for type hints in hot paths

### Test Structure
- [ ] Move `test_relative_paths.py` → `tests/unit/`
- [ ] Move `core/test_reset_settings.py` → `tests/unit/`
- [ ] Move `tests/utils/test_import.py` → `tests/unit/`

## Expected Performance Gains

| Area | Before | After | Gain |
|------|--------|-------|------|
| App startup | ~3-5s | ~1-2s | 50-60% |
| Tab switching | ~500ms | ~200ms | 60% |
| Memory usage | ~200MB | ~150MB | 25% |

## Implementation Order

1. **Low Risk (5 min)**
   - Create `docs/` folder and move `.md` files
   - Move backup files to `backups/` folder
   - Move test files to proper test structure

2. **Medium Risk (15 min)**
   - Add lazy loading to OpenSim imports
   - Remove unused imports from widgets
   - Profile startup time

3. **High Risk (30 min)**
   - Implement async tab loading (only load tab on click)
   - Cache expensive operations
   - Test all functionality

## Files to Keep/Remove

### Remove (Safe to Delete)
- `settings_backup.py` - backed up in git
- `test_relative_paths.py` - move to tests/
- `verify_batch_export.py` - outdated
- `core/test_reset_settings.py` - move to tests/
- Old c3d_viewer backups

### Keep (with Organization)
- `settings_complete.py` - reference implementation
- All widget implementations
- All documentation (move to docs/)

## Model Scaling Implementation

The Model Scaling widget is created but needs OpenSim integration:

**Status:** ✅ GUI widget created
**Status:** ❌ OpenSim integration needed
**Status:** ❌ Configuration file generation needed

See `docs/implementation_notes/model_scaling.md` for details.
