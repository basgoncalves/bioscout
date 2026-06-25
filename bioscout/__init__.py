__version__ = "1.7.0"

# The analysis object model (Project / Subject / Session / Trial) now lives in
# bioscout.utils.analysis, next to Analyse. It's exposed here lazily so that a
# bare `import bioscout` stays light — the heavy `utils` module (OpenSim/CEINMS)
# is only imported the first time one of these names is actually used.

from typing import TYPE_CHECKING

# For Pylance/Pyright only: import the real classes so editors resolve
# `bioscout.Project`, `bioscout.Subject`, … to their true types (full
# autocomplete). At runtime TYPE_CHECKING is False, so this costs nothing and
# the lazy __getattr__ below does the actual (deferred) loading.
if TYPE_CHECKING:
    from .utils.analysis import (
        Project, Subject, Session, init_project,
        build_model_config, discover_subjects,
        check_settings_version, migrate_settings,
    )

_LAZY = {
    "Project", "Subject", "Session", "init_project",
    "build_model_config", "discover_subjects",
    "check_settings_version", "migrate_settings",
}

__all__ = ["__version__", *sorted(_LAZY)]


def __getattr__(name):                      # PEP 562 module-level lazy attrs
    if name in _LAZY:
        from . import utils                 # pulls in the analysis model
        return getattr(utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(list(globals()) + list(_LAZY)))
