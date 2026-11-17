"""Model integrity: does every ``.osim`` still find its bones?

OpenSim resolves a mesh filename relative to the folder holding the ``.osim``.
Move a model — or move the geometry out from under it, which is what tidying a
``models/`` folder does, and what writing a personalised model into a new
subfolder does — and OpenSim loads it with every muscle, marker and joint
intact and **no bones at all**, with no exception and nothing in the log.

This package is the check for that, plus the two quieter variants of it:
handling only one of the OpenSim 3 / OpenSim 4 mesh tags, and filename case
differences that resolve on Windows and fail everywhere else.

    from bioscout.model import verify_model, verify_tree, format_text

    print(verify_model("subject021.osim").headline)
    report = verify_tree(["models", "generic models"])
    print(format_text(report))
    raise SystemExit(report.exit_code())

Command line::

    python -m bioscout.model --verify
    bioscout --model --verify --strict

Pure stdlib — no OpenSim, no numpy — so it runs during preflight and in a bare
environment.
"""
from .geometry import (GEOMETRY_TAGS, PASSING_TIERS, TIER_ORDER, GeometryRef,
                       bundled_geometry_dir, geometry_refs, resolve_ref,
                       search_roots_for)
from .verify import (ModelReport, TreeReport, find_models, format_text,
                     verify_model, verify_tree)

__all__ = [
    "GEOMETRY_TAGS", "TIER_ORDER", "PASSING_TIERS",
    "GeometryRef", "geometry_refs", "resolve_ref", "search_roots_for",
    "bundled_geometry_dir",
    "ModelReport", "TreeReport", "verify_model", "verify_tree", "find_models",
    "format_text",
]



# ---------------------------------------------------------------------------
# bs.model("x.osim") -- the package itself opens a model for editing
# (bioscout/model/osim_model.py; plain XML, no OpenSim). One name for everything
# model-related: bs.model(path) to edit, bs.model.<function> for the rest.
import sys as _sys
import types as _types


class _ModelPackage(_types.ModuleType):
    def __call__(self, path):
        """Open an .osim to edit: ``m = bs.model("gpkv4_scaled.osim")``.
        See bioscout/model/osim_model.py for what ``m`` can do."""
        from .osim_model import Model
        return Model(path)


_sys.modules[__name__].__class__ = _ModelPackage
