"""
bioscout.project — one-call project bootstrap for notebooks and scripts.

Lets you run a *pure* BioScout pipeline without any project-local helper file:

    import bioscout
    utils, settings = bioscout.init_project()          # cwd is the project root
    # or
    utils, settings = bioscout.init_project(r"C:/path/to/project")

What it does
------------
1. Imports ``bioscout.utils``.
2. Force-loads the OpenSim / CEINMS helper modules. ``utils`` imports these
   lazily at the end of its own import and can leave them as ``None``; this
   loads them explicitly (and prints the real traceback for OpenSim if it
   still fails, instead of hiding it).
3. Loads the project's ``settings.py`` **by path** and injects it as
   ``utils.settings``. Loading by path matters because BioScout ships its own
   ``settings.py``; a plain ``import settings`` could resolve to the package's.
4. Points ``utils.MODELS_DIR / SIMULATIONS_DIR / RESULTS_DIR`` at the project.

Returns ``(utils, settings)``.
"""
import os
import sys
import importlib
import importlib.util
import traceback
from pathlib import Path


def _force_load_helper(utils, name):
    """Load a lazily-imported helper (openSim/ceinms) onto ``utils``."""
    if getattr(utils, name, None) is not None:
        return
    mod = None
    try:                                   # bare import (utils/ dir is on sys.path)
        mod = importlib.import_module(name)
    except Exception:
        try:                               # package-qualified fallback
            mod = importlib.import_module(f"bioscout.utils.{name}")
        except Exception:
            if name == "openSim":
                print(f"[bioscout.init_project] could not load '{name}' — traceback:")
                traceback.print_exc()
            return
    setattr(utils, name, mod)
    sys.modules.setdefault(name, mod)


def init_project(project_dir=None, verbose=True):
    """Bootstrap BioScout for a project folder. Returns ``(utils, settings)``.

    Parameters
    ----------
    project_dir : str | os.PathLike | None
        The project root (folder holding ``models/``, ``simulations/``,
        ``results/`` and ``settings.py``). Defaults to the current working
        directory.
    verbose : bool
        Print a one-line status summary.
    """
    project_dir = Path(project_dir or os.getcwd()).resolve()
    sys.path.insert(0, str(project_dir))

    from bioscout import utils

    _force_load_helper(utils, "openSim")
    _force_load_helper(utils, "ceinms")

    # Load THIS project's settings.py by path (not a plain import).
    settings = None
    settings_path = project_dir / "settings.py"
    if settings_path.exists():
        spec = importlib.util.spec_from_file_location("settings", str(settings_path))
        settings = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(settings)
        sys.modules["settings"] = settings
        utils.settings = settings
    else:
        settings = getattr(utils, "settings", None)
        if verbose:
            print(f"[bioscout.init_project] no settings.py in {project_dir} — using package defaults")

    # Point BioScout's directory constants at this project's data.
    utils.PROJECT_DIR     = str(project_dir)
    utils.MODELS_DIR      = str(project_dir / "models")
    utils.SIMULATIONS_DIR = str(project_dir / "simulations")
    utils.RESULTS_DIR     = str(project_dir / "results")

    if verbose:
        import bioscout
        print(f"BioScout {getattr(bioscout, '__version__', '?')}  |  project: {project_dir.name}")
        print(f"openSim ready: {utils.openSim is not None}   "
              f"ceinms ready: {getattr(utils, 'ceinms', None) is not None}   "
              f"settings.SESSION: {getattr(settings, 'SESSION', None)}")
    return utils, settings
