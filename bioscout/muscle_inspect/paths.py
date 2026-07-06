"""Locations of the literature data bundled with this package.

Keeping these here (rather than hard-coding ``"validation/..."`` relative to the
current working directory, as the standalone scripts do) lets the module be
imported and used from anywhere inside bioscout while still finding its data.
"""
from __future__ import annotations

import os

PKG_DIR = os.path.dirname(os.path.abspath(__file__))

#: digitized literature moment-arm bands (cm vs deg), used by ``validation.py``
LITERATURE_MOMENT_ARMS_CSV = os.path.join(PKG_DIR, "validation", "literature_moment_arms.csv")

#: tidy long-form literature curves (joint-contact & muscle forces vs % gait cycle)
LITERATURE_CURVES_CSV = os.path.join(PKG_DIR, "validation", "literature_curves.csv")

#: provenance / citations for the curves above
LITERATURE_MANIFEST_JSON = os.path.join(PKG_DIR, "validation", "literature_manifest.json")

#: digitized joint isometric / isokinetic strength bands (Nm vs deg or deg/s)
LITERATURE_STRENGTH_CSV = os.path.join(PKG_DIR, "validation", "literature_strength.csv")

#: joint-action -> muscle-group map used by the strength validators
MUSCLE_FUNCTIONS_CSV = os.path.join(PKG_DIR, "validation", "muscle_functions.csv")


def resolve_literature_csv(path=None):
    """Return an existing moment-arm CSV path.

    Prefers an explicit ``path`` (absolute, or relative to cwd) when it exists;
    otherwise falls back to the CSV bundled with the package.
    """
    if path:
        cand = path if os.path.isabs(path) else os.path.join(os.getcwd(), path)
        if os.path.isfile(cand):
            return cand
    return LITERATURE_MOMENT_ARMS_CSV
