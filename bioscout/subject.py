"""Backward-compatibility shim.

The Subject / Session model moved to :mod:`bioscout.utils.analysis` so all the
analysis-side objects live together under ``utils`` (next to ``Analyse``).
Import from there, or just use the package-level names::

    from bioscout import Subject, build_model_config

This module re-exports the same objects so existing imports keep working.
"""
from .utils.analysis import (   # noqa: F401
    Subject, Session,
    build_model_config, discover_subjects,
    _is_ceinms, _pick_models, _sim_dir, _trial_class,
)

__all__ = ["Subject", "Session", "build_model_config", "discover_subjects"]
