"""Backward-compatibility shim.

The Project bootstrap moved to :mod:`bioscout.utils.analysis` so all the
analysis-side objects live together under ``utils``. Import from there, or just
use the package-level names::

    import bioscout
    proj = bioscout.Project()
    utils, settings = bioscout.init_project()

This module re-exports the same objects so existing imports keep working.
"""
from .utils.analysis import (   # noqa: F401
    Project, init_project,
    check_settings_version, migrate_settings, ensure_editor_paths,
    _find_project_root, _force_load_helper,
)

__all__ = [
    "Project", "init_project",
    "check_settings_version", "migrate_settings", "ensure_editor_paths",
]
