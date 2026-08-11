"""bioscout.utils.ceinms — the CEINMS toolbox: Python helpers AND the binaries.

    from bioscout.utils import ceinms
    ceinms.create_ceinms_cfg(...)          # configs.py
    ceinms.executable(...)                 # commands.py
    ceinms.ExecutionMode(trial).run(fn)    # modes.py
    ceinms.plot_ceinms_muscle_forces(...)  # plot.py

WHY THIS IS A PACKAGE NOW
    It used to be a 331 MB directory of .exe/.dll files with a single
    `__init__.py` whose only job was to work around a name collision: a
    *package* shadows a same-named *module*, so `import ceinms` reached the
    binaries and missed the helpers in the sibling `utils/ceinms.py`. That shim
    loaded the .py by file path inside `try/except Exception` and fell back to
    "binary package only" on any failure — so a missing OpenSim DLL silently
    removed every helper instead of raising.

    There is now one `ceinms`, and it is this package. The helpers are real
    submodules; the binaries live under `bin/`. Nothing is loaded by file path
    and nothing is swallowed.

LAYOUT
    shared.py    header, the live `settings` proxy, small shared helpers
    configs.py   every CEINMS XML builder (model, generator, cfgs, setups)
    commands.py  running the executables (terminal, calibrate, execute, loop,
                 optimise)
    modes.py     execution MODES — how many solves, and what the result IS
                 (single / bounds / full_loop / lcurve / optimise)
    plot.py      figures from CEINMS output
    bin/         CEINMS.exe, CEINMSoptimise.exe, ceinms-nn-calibrate.exe, DLLs

    `modes.py` deliberately imports only the standard library. Mode SELECTION
    must not depend on OpenSim importing: if it did, a missing DLL would turn a
    three-arm `bounds` run into a one-arm run with no error — a config option
    silently ignored, which is worse than one that fails.

        from bioscout.utils.ceinms.modes import ExecutionMode   # no OpenSim
"""
import os as _os

# --- the binaries ----------------------------------------------------------
# Kept beside the code but in their own directory, so `package_data` globs for
# *.exe / *.dll never sweep up source files.
BIN_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "bin")
if not _os.path.isdir(BIN_DIR):          # pre-move layout: binaries at the root
    BIN_DIR = _os.path.dirname(_os.path.abspath(__file__))

CEINMS_EXE = _os.path.join(BIN_DIR, "CEINMS.exe")
CEINMS_OPTIMISE_EXE = _os.path.join(BIN_DIR, "CEINMSoptimise.exe")
CEINMS_CALIBRATION_EXE = _os.path.join(BIN_DIR, "ceinms-nn-calibrate.exe")

# --- modes first: no heavy dependencies, so it is importable even when the
#     OpenSim-dependent halves below are not.
from .modes import (                                          # noqa: E402,F401
    ExecutionMode, ModeError, MODES as EXECUTION_MODES,
    aggregate_band, lcurve_knee, resolve as resolve_mode)

from .shared import *      # noqa: E402,F401,F403
from .configs import *         # noqa: E402,F401,F403
from .commands import *    # noqa: E402,F401,F403
from .plot import *        # noqa: E402,F401,F403

from . import shared, commands, plot, modes                   # noqa: E402,F401
from . import configs                                       # noqa: E402,F401
