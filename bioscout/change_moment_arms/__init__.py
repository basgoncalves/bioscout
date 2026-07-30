"""
bioscout.change_moment_arms
===========================

Adjust a muscle's moment arm on an OpenSim model, and derive the amount from
measured muscle volume rather than a guessed factor.

Why wrap radii rather than moving attachment points: in OpenSim the wrap
surface *is* the geometric stand-in for muscle bulk — the path is held off the
bone by the cylinder, so its radius sets how far the line of action sits from
the joint axis. Growing it is the mechanism by which a bigger muscle produces a
bigger moment arm, it preserves the curve's shape because the path still wraps,
and the change in where the path engages the surface moves the peak along the
coordinate on its own. Translating path points (``paths``) models a different
anatomical change — the attachment moving — and is the fallback for muscles
with no wrap on their path.

    bioscout --change-moment-arms          # guided
    python -m bioscout.change_moment_arms

    from bioscout.change_moment_arms import apply_offset, measure_volumes
    apply_offset(model, out, "glmax1_r", "hip_adduction_r", offset_mm=5)

Layout — only ``core`` needs OpenSim, so everything else is testable without it:

    wraps.py    read/edit wrap radii            (pure XML)
    paths.py    translate/rotate path points    (pure XML)
    volumes.py  MRI mask -> radius factor       (needs nibabel)
    solve.py    bracket + bisect on a callable  (pure numpy)
    core.py     the OpenSim sweeps              (needs opensim)
    inspection.py  before/after check of an edit (needs opensim)
    cli.py      the guided prompt
"""
from __future__ import annotations

__version__ = "0.2.0"

from .paths import read_path_points, rotate_path_points, translate_path_points  # noqa: F401
from .solve import solve_radius_for_offset  # noqa: F401
from .volumes import (DEFAULT_MASK_MAP, measure_volume,  # noqa: F401
                      measure_volumes, radius_factor_from_volumes)
from .wraps import read_wraps, scale_wrap_radii, set_wrap_radii  # noqa: F401

__all__ = [
    "__version__",
    "read_wraps", "scale_wrap_radii", "set_wrap_radii",
    "read_path_points", "translate_path_points", "rotate_path_points",
    "measure_volume", "measure_volumes", "radius_factor_from_volumes",
    "DEFAULT_MASK_MAP", "solve_radius_for_offset",
]


def __getattr__(name):           # keep `opensim` out of import time
    if name in ("apply_offset", "apply_to_muscle", "apply_batch",
                "list_targets", "sweep_moment_arm", "check_model", "Target"):
        from . import core
        return getattr(core, name)
    if name in ("inspect_change", "compare_sweeps", "plot_comparison"):
        from . import inspection
        return getattr(inspection, name)
    raise AttributeError(name)
