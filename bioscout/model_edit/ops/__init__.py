"""Importing this package populates :data:`bioscout.model_edit.spec.REGISTRY`.

Every module here must be importable WITHOUT OpenSim — the ``import opensim``
lives inside each op function, never at module scope. That is what lets the CLI
list operations, validate a recipe and build a GUI form on a machine that cannot
run them, and it is why ``Op.needs_opensim`` is a declared fact rather than
something discovered by a failed import.
"""
from __future__ import annotations

from . import coordinates, inspect, markers, moment_arms, scale, strength  # noqa: F401

#: op name -> callable(params) -> params, applied before a suffix is formatted.
#: Lets an op expose a derived token (``{factor_tag}``) without leaking a
#: filename-escaping rule into :mod:`bioscout.model_edit.naming`.
SUFFIX_HOOKS = {}
for _mod in (coordinates, inspect, markers, moment_arms, scale, strength):
    SUFFIX_HOOKS.update(getattr(_mod, "SUFFIX_HOOKS", {}))
del _mod
