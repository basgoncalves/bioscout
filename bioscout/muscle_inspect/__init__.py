"""muscle_inspect

A small, headless Python toolkit (ported from the MATLAB MuscleLengthsChecker
pipeline) to check an OpenSim model's muscle geometry and properties against the
literature, mirroring how the joint-contact-force overlay validates JRA results:

  1. detect muscle path points that sit *inside* wrap cylinders and project them
     back out -- the geometry error that produces non-physiological / discontinuous
     moment arms in scaled or warped OpenSim models,
  2. sweep each joint coordinate over its range of motion and plot moment arms and
     muscle lengths *before vs after* the correction, so the fix can be inspected
     visually,
  3. validate the model's MOMENT ARMS and MUSCLE ARCHITECTURE (fascicle length /
     pennation) against digitized literature bands  (``muscle_length_validation``), and
  4. validate joint STRENGTH -- isometric and isokinetic peak moments -- against
     literature MVC bands  (``strength``).

Requires the official OpenSim Python package (`import opensim`) at run time.
The pure-math helpers in `geometry` and `discontinuity` do not need OpenSim and
are unit-testable on their own.
"""

from .geometry import (
    euler_xyz_to_rotation_matrix,
    project_point_outside_cylinder,
    radial_distance,
)
from .discontinuity import detect_discontinuities, mad
from .core import load_function_matrix
from .paths import (
    LITERATURE_MOMENT_ARMS_CSV,
    LITERATURE_CURVES_CSV,
    LITERATURE_MANIFEST_JSON,
    resolve_literature_csv,
)
from . import literature_jcf
from . import moment_arm_motion
from .moment_arm_motion import inspect_moment_arms_over_motion
from . import model_ma_check
from .model_ma_check import check_ma_discontinuities

__all__ = [
    "moment_arm_motion",
    "inspect_moment_arms_over_motion",
    "model_ma_check",
    "check_ma_discontinuities",
    "euler_xyz_to_rotation_matrix",
    "project_point_outside_cylinder",
    "radial_distance",
    "detect_discontinuities",
    "mad",
    "load_function_matrix",
    "wrap_fixer",
    "moment_arms",
    "plotting",
    "validation",
    "muscle_length_validation",
    "strength",
    "literature_jcf",
    "LITERATURE_MOMENT_ARMS_CSV",
    "LITERATURE_CURVES_CSV",
    "LITERATURE_MANIFEST_JSON",
    "resolve_literature_csv",
]

__version__ = "0.2.0"

# Quiet OpenSim's [info]/[warning] spam (missing display geometry, etc.) for every
# muscle_inspect entry point, honoring settings.BatchSettings.opensim_log_level.
try:
    from bioscout.utils.shared import quiet_opensim as _quiet_opensim
    _quiet_opensim()
except Exception:
    pass
