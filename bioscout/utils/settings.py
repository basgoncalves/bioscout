"""
DEPRECATED - This file is kept only for backwards compatibility.

All settings have been moved to the parent settings.py.

This module re-exports from the unified settings for any legacy code that imports from here.
"""

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Editor-only (no runtime effect): expose the schema names — Inputs,
    # BatchSettings, CEINMSSettings, model_config, SUBJECTS, … — so Pylance
    # resolves `settings.X` / `utils.settings.X` (the names below are injected
    # at runtime via globals().update, which a type checker cannot see).
    from bioscout.settings import *  # noqa: F401,F403

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
