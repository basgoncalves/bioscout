# from logging import root
from glob import glob
import math
import os
import shutil
import subprocess
import time
import sys
import re
from pathlib import Path

import webbrowser

# GUI toolkits are optional: importing utils for analysis/headless use must not
# require (or stall on) a display. The GUI widgets import these themselves.
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
except Exception:
    tk = None
    filedialog = messagebox = simpledialog = None
try:
    import customtkinter as ctk
except Exception:
    ctk = None

import numpy as np
import pandas as pd

# Handle matplotlib import with graceful fallback for circular import issues
try:
    import matplotlib
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.offsetbox import AnchoredText
    HAS_MATPLOTLIB = True
except ImportError as e:
    # If matplotlib fails to import (circular import or missing), provide fallback
    HAS_MATPLOTLIB = False
    class FakeMatplotlib:
        pyplot = None
        backends = None
        offsetbox = None
    matplotlib = FakeMatplotlib()
    plt = None
    PdfPages = None
    AnchoredText = None

# scipy
try:
    import scipy
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

import xml.etree.ElementTree as ET
import xml.dom.minidom

try:
    # opensim/__init__.py prints a "Found simbody-visualizer, setting
    # SIMBODY_HOME ..." banner via a plain Python print() on first import.
    # Capture stdout during the import to silence it (the env var it sets still
    # gets set). Set BIOSCOUT_VERBOSE_OPENSIM=1 to see the banner.
    if os.environ.get("BIOSCOUT_VERBOSE_OPENSIM"):
        import opensim as osim
    else:
        import io as _io
        import contextlib as _contextlib
        with _contextlib.redirect_stdout(_io.StringIO()):
            import opensim as osim
    HAS_OPENSIM = True
except ImportError:
    HAS_OPENSIM = False
    osim = None

# c3d
try:
    import c3d
    HAS_C3D = True
except ImportError:
    HAS_C3D = False
    c3d = None

# Ensure utils dir and app dir are on sys.path for standalone execution.

_utils_dir = str(Path(__file__).parent)
_app_dir = str(Path(__file__).parent.parent)
if _app_dir not in sys.path:
    sys.path.insert(0, _app_dir)
if _utils_dir in sys.path:
    sys.path.remove(_utils_dir)
sys.path.insert(0, _utils_dir)

# ceinms and openSim are imported at BOTTOM of this file to break circular imports
# (ceinms.py and openSim.py both import utils, so importing them here causes deadlock)
openSim = None
ceinms = None
HAS_CEINMS = False

# settings
try:
    import settings
except Exception as e:
    print(f"Error importing settings module: {e}")
    settings = None

# emg_normalise imported at BOTTOM to break circular import chain
# (emg_normalise -> openSim -> exportC3D -> utils)
emg_normalise = None
HAS_EMG_NORMALISE = False


# utils doesn't carry its own version — it reflects the package (single source).
from bioscout import __version__  # noqa: E402,F401

# Project directories
UTILS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.dirname(UTILS_DIR)


def _resolve_project_dir():
    """Locate the project root (the folder holding models/ simulations/ results/).

    Priority:
      1. BIOSCOUT_PROJECT_DIR environment variable
      2. current working directory, if it looks like a project
         (has settings.py or a models/ or simulations/ folder)
      3. PROJECT_ROOT from an imported project settings.py (if it exists on disk)
      4. the folder containing the bioscout package (legacy default)
    """
    env = os.environ.get('BIOSCOUT_PROJECT_DIR')
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    cwd = os.getcwd()
    if (os.path.exists(os.path.join(cwd, 'settings.py')) or
            any(os.path.isdir(os.path.join(cwd, d))
                for d in ('simulations', 'Simulations', 'models', 'Models'))):
        return cwd
    try:
        _pr = (getattr(getattr(settings, 'BatchSettings', None), 'PROJECT_ROOT', None)
               or getattr(settings, 'PROJECT_ROOT', None))
        if _pr and os.path.isdir(str(_pr)):
            return os.path.abspath(str(_pr))
    except Exception:
        pass
    return os.path.dirname(APP_DIR)


PROJECT_DIR = _resolve_project_dir()

CODE_DIR = UTILS_DIR   # where this package physically lives (e.g. for log.txt)

# Project data directories. The SOURCE OF TRUTH is the project's settings.py;
# these just mirror it so the package can read utils.MODELS_DIR /
# utils.SIMULATIONS_DIR / utils.RESULTS_DIR. They are None until a project's
# settings define them, and bioscout.Project() (re)points them via _point_dirs().
_DIR_DEFAULTS = {"MODELS_DIR": "models", "SIMULATIONS_DIR": "simulations",
                 "RESULTS_DIR": "results"}


def _dir_from_settings(name):
    # Prefer BatchSettings.<name>; fall back to a module-level settings.<name>
    # so a project may declare its paths as plain globals outside BatchSettings.
    val = getattr(getattr(settings, "BatchSettings", None), name, None)
    if val is None:
        val = getattr(settings, name, None)
    if val is not None:
        return str(val)
    # Last resort: <PROJECT_DIR>/<default>. This matters because of a circular
    # import. A project settings.py imports bioscout.utils.analysis near its top;
    # this module imports `settings` right back. A script that imports settings
    # BEFORE bioscout therefore hands us a half-built settings module whose
    # *_DIR globals (defined further down the file) do not exist yet -- and these
    # three would be pinned to None for the life of the process, so every
    # Analyse() failed later inside update_model() with an opaque
    # "expected str, bytes or os.PathLike object, not NoneType".
    if name in _DIR_DEFAULTS and PROJECT_DIR:
        return os.path.join(PROJECT_DIR, _DIR_DEFAULTS[name])
    return None

MODELS_DIR       = _dir_from_settings('MODELS_DIR')
SIMULATIONS_DIR  = _dir_from_settings('SIMULATIONS_DIR')
RESULTS_DIR      = _dir_from_settings('RESULTS_DIR')
TASK_FIGURES_DIR = os.path.join(RESULTS_DIR, 'task_figures') if RESULTS_DIR else None

CEINMS_DIR = os.path.join(UTILS_DIR, 'ceinms', 'bin')
CEINMS_EXE = os.path.join(CEINMS_DIR, 'CEINMS.exe')
CEINMS_OPTIMISE_EXE = os.path.join(CEINMS_DIR, 'CEINMSoptimise.exe')
CEINMS_CALIBRATION_EXE = os.path.join(CEINMS_DIR, 'ceinms-nn-calibrate.exe')

PRINT_TERMINAL = False







def _update():
    '''
    update the version of the present .utils package in the simulations directory with the current version of the .utils package in the code directory.

    1. Ask the user what version they want to update to 
    2. Changes the version number in the present .utils package 
    3. Commites the changes to git with a message indicating the update

    '''
    os.chdir(CODE_DIR)
    
    current_version = __version__
    print(f'Current version: {current_version}')

    new_version = input(f'Enter the new version number to update to (current: {current_version}): ')
    if new_version == current_version:
        print('New version is the same as current version. No update needed.')
        return
    
    # update version in __init__.py
    current_file = os.path.abspath(__file__)
    with open(current_file, 'r') as file:
        lines = file.readlines()
    with open(current_file, 'w') as file:
        for line in lines:
            if line.startswith('__version__'):
                file.write(f"__version__ = '{new_version}'\n")
            else:
                file.write(line)
    
    print(f'Updated version to {new_version} in {current_file}')

    # commit changes to git
    try:
        subprocess.run(['git', 'add', current_file], check=True, cwd=os.getcwd())
        commit_message = f"Update .utils version to {new_version}"
        subprocess.run(['git', 'commit', '-m', commit_message], check=True, cwd=os.getcwd())
        print(f'[Success] Updated .utils version to {new_version} and pushed to git.')
    except subprocess.CalledProcessError as e:
        print(f'[Error] Failed to commit version update to git: {e}')


## Utility functions — moved to utils/shared.py and re-exported so that
## utils.updir / utils.print_to_log / utils.time_normalise_df and every bare-name
## internal reference keep working unchanged.
from .shared import (updir, print_to_log, time_normalise_df, start_logging, trial_type,
                     plot_style, side_color, fig_size, DEFAULT_PLOT_STYLE,
                     get_mean_across_trial_dfs)


def summarize_results(settings_path=None):
    """Build the results summary (figures + JASP CSV) for a project.

    Uses the folder of ``settings_path`` if given, else the current working
    directory — which must contain a ``settings.py`` and a ``summarize_results.py``.

        import bioscout
        bioscout.summarize_results()                       # cwd project
        bioscout.summarize_results(r"C:/proj/settings.py")  # explicit
    """
    import os as _os
    import runpy as _runpy
    proj = _os.path.dirname(_os.path.abspath(settings_path)) if settings_path else _os.getcwd()
    if not _os.path.exists(_os.path.join(proj, "settings.py")):
        raise FileNotFoundError(f"no settings.py in {proj} — pass settings_path=...")
    script = _os.path.join(proj, "summarize_results.py")
    if not _os.path.exists(script):
        raise FileNotFoundError(f"no summarize_results.py in {proj}")
    return _runpy.run_path(script, run_name="__main__")

# File I/O (loaders/writers/XML) moved to utils/io.py — re-exported so
# utils.load_any_data_file / utils.check_path / utils.save_pretty_xml etc. and
# every internal reference keep working unchanged.
from .io import (
    check_path, load_c3d, load_trc, load_sto, load_grf_mot,
    load_data_file, load_any_data_file, load_any_data_file_time_normalized,
    save_data_file, load_sto_header, write_trc, write_mot,
    write_sto_header, write_sto_file, read_xml, dict_to_xml,
    save_pretty_xml, edit_xml_tag_value,
)
# plotting
# Figure/axis helpers moved to utils/plotting.py (re-exported so existing
# `utils.save_fig`, `utils.mmfn`, `utils.figure_suplots_grid`, … and every
# internal reference keep working unchanged).
from .plotting import (
    save_fig, get_screen_size, calculate_nRows_nCols, figure_suplots_grid,
    mmfn, plot_mean_error_shade, add_picture_to_ax, convert_to_interactive_fig,
)

# EMG processing



# Curve-agreement metrics moved to utils/stats.py (re-exported here so existing
# `utils.rmse` / `utils.rsquared` / `utils.compare_curves` / `utils.sum3d` and
# every internal reference keep working unchanged).
from .stats import rsquared, rmse, compare_curves, sum3d
# Statistical parametric mapping (spm1d wrappers; spm1d is an optional dep).
from .stats import (
    spm_ttest,
    spm_ttest2,
    spm_ttest_paired,
    spm_anova1,
    spm_plot,
)

# Deferred imports to break circular dependency
# (these modules import utils, so they must load AFTER utils is fully defined)
try:
    from . import openSim as _openSim_mod
    openSim = _openSim_mod
except (ImportError, ValueError):
    try:
        import importlib.util as _ilu
        _op_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'openSim.py')
        _op_spec = _ilu.spec_from_file_location('openSim', _op_path)
        _op_mod = _ilu.module_from_spec(_op_spec)
        sys.modules['openSim'] = _op_mod
        _op_spec.loader.exec_module(_op_mod)
        openSim = _op_mod
    except Exception as _e:
        openSim = None
        _openSim_import_error = _e


def get_openSim():
    """Return the openSim helper module, resolving it late if init could not.

    ``openSim.py`` does a bare ``import utils`` (the legacy top-level copy of
    this package), so ``from . import openSim`` at the bottom of this file runs
    straight into a circular import and lands in the ``except`` above with
    ``openSim = None``. Callers that then did ``from bioscout.utils import
    openSim as _os`` got None -- and ``None.scale_model(...)`` is an
    AttributeError that names neither the module nor the real cause.
    ``bioscout/__main__.py`` has carried a hand-rolled workaround for exactly
    this, which is why the CLI could scale a model and ``python settings.py``
    could not.

    By the time anything CALLS this, ``bioscout.utils`` is fully initialised and
    the cycle resolves, so the plain import normally just works. Failing that,
    an already-loaded copy under another name is used. If nothing works the
    ORIGINAL exception is raised, not None.
    """
    global openSim
    if openSim is not None:
        return openSim
    import importlib as _il
    # "openSim" bare: the importlib fallback above registers it under that name.
    for _name in ("bioscout.utils.openSim", "utils.openSim", "openSim"):
        m = sys.modules.get(_name)
        if m is not None:
            openSim = m
            return m
    _last = globals().get("_openSim_import_error")
    for _name in ("bioscout.utils.openSim", "utils.openSim"):
        try:
            openSim = _il.import_module(_name)
            return openSim
        except Exception as _e:
            _last = _e
    raise ImportError(
        f"the openSim helper module could not be loaded: {_last!r}. "
        f"Every OpenSim stage (scaling, IK, ID, MA, SO, JRA) needs it."
    ) from (_last if isinstance(_last, BaseException) else None)

# CEINMS helpers are bound at the BOTTOM of this file (after analysis/emg/plot
# are loaded). Loading them here, mid-init, hit an import cycle (ceinms.py ->
# import utils/settings -> back into this module before it is complete) and
# silently failed, leaving utils.ceinms = None. Placeholder until then:
ceinms = None
HAS_CEINMS = False

try:
    import emg_normalise as _emg_mod
    emg_normalise = _emg_mod
    HAS_EMG_NORMALISE = True
except ImportError:
    HAS_EMG_NORMALISE = False
    emg_normalise = None

# Analysis object model (Project -> Subject -> Session -> Trial). Loaded here,
# after Analyse is defined, because Trial subclasses Analyse. These are the
# typed entry points re-exported by the top-level `bioscout` package.
try:
    from .analysis import (
        Subject, Session, Iteration, Project,
        build_model_config, discover_subjects, init_project,
        check_settings_version, migrate_settings, ensure_editor_paths,
        select_subjects, subjects_in_simulations, resolve_subject_selection,
        sessions_from_subjects, subjects_from_subjects,
    )
    from . import analysis
except Exception as _e:
    print(f"[bioscout.utils] analysis model not loaded: {_e}")


# Back-compat: `utils.Inputs()` used to be the trial-layout class. In 2.0 the
# canonical layout is a plain dict (analysis._default_layout_paths); expose a
# thin object here so legacy `utils.Inputs().id` / `.ceinms_exe_setup` etc. keep
# working (a few call sites in ceinms.py / summary.py still use it).
try:
    from .analysis import _default_layout_paths as _default_layout_paths

    class Inputs:
        """Attribute view over the canonical trial layout (back-compat shim)."""
        def __init__(self, parentdir=None):
            self._parentdir = parentdir
            _lay = _default_layout_paths()
            for _k, _v in _lay.items():
                setattr(self, _k, _v)
            # legacy attribute names some old call sites still use
            self.emg_normalised = _lay.get("emg_filtered_normalised")
except Exception:
    Inputs = None


# EMG processing consolidated into utils/emg.py — re-exported here so
# utils.filter_emg / utils.normalise_emg_across_session etc. keep working.
from .emg import (
    filter_emg, filter_emg_df, filter_emg_file, amplitude_normalise_emg,
    emg_processing_file, normalise_emg_across_session, plot_emg_results,
    emg_amplitude_normalise,
)

# Analyse now lives in utils/analysis.py (with Project/Subject/Session).
from .analysis import Analyse

# ---------------------------------------------------------------------------
# CEINMS helpers — bound LAST, on purpose.
#
# utils/ceinms.py holds the Python helpers (create_input_data, create_ceinms_cfg,
# create_ceinms_model, calibrate, …); the sibling binary package utils/ceinms/
# shadows it on import. The package __init__ re-exports the .py helpers, so the
# `ceinms` is an ordinary sub-package now (utils/ceinms/ with
# shared/configs/commands/modes/plot and the binaries under bin/),
# so there is nothing to shim: it imports like anything else and
# raises like anything else if OpenSim is missing.
#
# It is still bound lazily rather than here, because ceinms.configs
# imports `utils`, and importing it mid-init would re-enter this
# module before it is complete. analysis._force_load_helper binds it
# at first use.
