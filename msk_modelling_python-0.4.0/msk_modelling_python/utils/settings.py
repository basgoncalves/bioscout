"""
DEPRECATED - This file is kept only for backwards compatibility.

All settings have been moved to the parent settings.py.

This module re-exports from the unified settings for any legacy code that imports from here.
"""

import importlib.util
from pathlib import Path

# Load the parent settings.py by file path to avoid circular self-import
# (if we do 'from settings import *', Python finds THIS file first since
#  utils/ is on sys.path, causing a circular import of