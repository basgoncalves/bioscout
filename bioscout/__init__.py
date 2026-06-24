__version__ = "1.4.0"

# The analysis object model (Project / Subject / Session / Trial) now lives in
# bioscout.utils.analysis, next to Analyse. It's exposed here lazily so that a
# bare `import bioscout` stays light — the heavy `utils` module (OpenSim/CEINMS)
# is only imported the first time one of these names is actually used.

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
