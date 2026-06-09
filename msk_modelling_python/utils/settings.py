"""
DEPRECATED - This file is kept only for backwards compatibility.

All settings have been moved to the parent settings.py.

This module re-exports from the unified settings for any legacy code that imports from here.
"""

import importlib.util
from pathlib import Path

# Load the parent settings.py by file path to avoid circular self-import
# (if we do 'from settings import *', Python finds THIS file first since
#  utils/ is on sys.path, causing a circular import of itself)
_real_path = Path(__file__).parent.parent / 'settings.py'
_spec = importlib.util.spec_from_file_location('_parent_settings', str(_real_path))
_real = importlib.util.module_from_spec(_spec)
if '_settings_loaded' not in globals():
    _spec.loader.exec_module(_real)
    globals().update({k: v for k, v in vars(_real).items() if not k.startswith('__')})
    _settings_loaded = True
