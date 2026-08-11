"""Locations of the literature data bundled with this package, and of the
per-model report folders written next to a model on disk.

Keeping these here (rather than hard-coding ``"validation/..."`` relative to the
current working directory, as the standalone scripts do) lets the module be
imported and used from anywhere inside bioscout while still finding its data.

Two different things are called "validation" in this file and they are NOT
related:

* ``PKG_DIR/validation/`` -- the literature CSVs shipped INSIDE the package.
* ``validation_dir(model)`` -- ``<model_dir>/validation/<model_stem>/``, the
  place every report ABOUT a model is written on the user's disk.
"""
from __future__ import annotations

import os

#: Name of the per-iteration folder that collects every report about a model.
VALIDATION_DIRNAME = "validation"

#: Folder-name prefixes that are reports, not models. Anything scanning an
#: iteration folder for .osim files must skip these (and ``VALIDATION_DIRNAME``)
#: or it will offer a report folder as a model. Kept for the pre-2.0.0b11 layout,
#: where reports sat directly in the iteration folder.
REPORT_DIR_PREFIXES = ("validation", "muscle_inspect", "moment_arm_change")

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


def validation_dir(model_path, kind=None, out=None, base=None):
    """Return the folder that reports about ``model_path`` should be written to.

    ``<model_dir>/validation/<model_stem>/[<kind>/]``

    So an iteration folder holds only models plus one ``validation/`` folder,
    and every report about a given model sits together under that model's name::

        cateli/
            scaled.osim
            scaled_opt_N10.osim
            scaled_opt_N10_mvicx3.00.osim
            validation/
                scaled_opt_N10/                    <- moment arms, fibre, strength
                scaled_opt_N10_mvicx3.00/
                    moment_arm_change/             <- kind="moment_arm_change"

    Before 2.0.0b11 these were ``muscle_inspect_<stem>/`` and
    ``moment_arm_change_<stem>/`` directly in the iteration folder. Old folders
    are not read by anything, so there is no fallback -- re-run the report.

    Parameters
    ----------
    model_path : str
        The model the report is about. Only its folder and stem are used; the
        file does not have to exist.
    kind : str, optional
        Sub-folder for a specific report type, e.g. ``"moment_arm_change"``.
        Omit for the standard ``muscle_inspect`` outputs.
    out : str, optional
        An explicit user-supplied output folder. When given it is returned
        as-is (made absolute against the cwd), so ``--out`` always wins.
    base : str, optional
        Override the model stem, for callers that already computed it.

    Returns
    -------
    str
        Absolute path. The folder is NOT created -- callers do that.
    """
    if out:
        return out if os.path.isabs(out) else os.path.join(os.getcwd(), out)
    model_path = os.path.abspath(model_path)
    model_dir = os.path.dirname(model_path)
    stem = base or os.path.splitext(os.path.basename(model_path))[0]
    parts = [model_dir, VALIDATION_DIRNAME, stem]
    if kind:
        parts.append(kind)
    return os.path.join(*parts)


def is_report_dir(name):
    """True if ``name`` is a report folder rather than anything to scan for models.

    Accepts a name or a path; matches the current ``validation/`` folder and the
    pre-2.0.0b11 ``muscle_inspect_*`` / ``moment_arm_change_*`` folders that may
    still be lying around in old sessions.
    """
    leaf = os.path.basename(str(name).rstrip("/\\"))
    return any(leaf.startswith(p) for p in REPORT_DIR_PREFIXES)


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
