"""muscle_inspect.core -- compatibility aggregator.

The muscle-length/strength side of this package (ported from the standalone
MuscleLengthsChecker) imports its shared helpers from ``muscle_inspect.core``.
bioscout keeps those helpers split across small modules
(``geometry``/``discontinuity``/``logutil``); this module simply re-exports them
under the ``core`` name so the ported files (``strength``,
``muscle_length_validation``) work unchanged, and adds the one helper bioscout
did not already have: :func:`load_function_matrix`.
"""
from __future__ import annotations

import csv as _csv
import os as _os

# logging helpers
from .logutil import LOG, setup_logging, timed, fmt_hms, add_file_handler
# pure-math geometry helpers
from .geometry import (
    euler_xyz_to_rotation_matrix,
    project_point_outside_cylinder,
    radial_distance,
)
# discontinuity detection
from .discontinuity import detect_discontinuities, mad

__all__ = [
    "LOG", "setup_logging", "timed", "fmt_hms", "add_file_handler",
    "euler_xyz_to_rotation_matrix", "project_point_outside_cylinder",
    "radial_distance", "detect_discontinuities", "mad",
    "load_function_matrix",
]


def load_function_matrix(path):
    """Parse the muscle-centric ``muscle_functions.csv`` incidence matrix.

    Columns: model_muscle, literature_muscle, then one JOINT ACTION per column (0/1).
    Returns ``(lit_map, action_map)``:
      lit_map    : {literature_muscle: [model_muscle, ...]}  (aggregation for moment-arm/fibre validation)
      action_map : {joint_action:      [model_muscle, ...]}  (agonist groups for strength validation)
    Model muscle names are WITHOUT side. Returns ({}, {}) if the file is absent or
    is not a matrix (first column != 'model_muscle')."""
    lit_map, action_map = {}, {}
    if not _os.path.isfile(path):
        return lit_map, action_map
    with open(path) as f:
        rows = [r for r in _csv.reader(f) if r and not r[0].strip().startswith("#")]
    if not rows or rows[0][0].strip() != "model_muscle":
        return lit_map, action_map
    header = [h.strip() for h in rows[0]]
    lit_i = header.index("literature_muscle") if "literature_muscle" in header else None
    action_idx = [(i, h) for i, h in enumerate(header) if i != 0 and h != "literature_muscle"]
    truthy = {"1", "1.0", "x", "X", "true", "True", "yes", "YES"}
    for r in rows[1:]:
        if not r or not r[0].strip() or r[0].strip() == "model_muscle":
            continue
        mm = r[0].strip()
        if lit_i is not None and len(r) > lit_i and r[lit_i].strip():
            lit_map.setdefault(r[lit_i].strip(), []).append(mm)
        for i, act in action_idx:
            if len(r) > i and r[i].strip() in truthy:
                action_map.setdefault(act, []).append(mm)
    return lit_map, action_map
