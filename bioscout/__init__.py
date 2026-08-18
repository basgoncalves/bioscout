__version__ = "2.0.0c1"

from typing import TYPE_CHECKING
if TYPE_CHECKING:  # editor autocomplete only — no runtime cost
    from .utils.analysis import (
        Project, Subject, init_project,
        build_model_config, discover_subjects,
        check_settings_version, migrate_settings,
    )
    from .utils.session import Session, Iteration   # session + runnable iteration
    from . import plot                              # comparison figures

# Public API. Everything except `test` lives in bioscout.utils and is loaded
# lazily by __getattr__ below, so a bare `import bioscout` stays light — it does
# NOT import OpenSim/CEINMS until you actually use one of these names.
__all__ = (
    "__version__", "test",
    "Project", "Subject", "Session", "Iteration", "init_project",
    "build_model_config", "discover_subjects",
    "check_settings_version", "migrate_settings",
    "summarize_results",
    "plot",                     # bioscout.plot — figures from a tidy table
    "pipeline",                 # bioscout.pipeline — run_subject / run_project
)

#: Names __getattr__ resolves to a SUBMODULE rather than to something in
#: bioscout.utils. Keeping them in one place is what stops the two branches
#: below drifting apart when a new one is added.
_SUBMODULES = ("plot", "pipeline")


def test(verbosity=2):
    """Run the bioscout self-test suite.

    ``python -c "import bioscout; bioscout.test()"``
    """
    from . import tests
    return tests.run(verbosity=verbosity)


def __getattr__(name):          # PEP 562: lazy, light `import bioscout`
    if name in ("Session", "Iteration"):   # session + runnable iteration
        import importlib
        return getattr(importlib.import_module(f"{__name__}.utils.session"), name)
    if name in _SUBMODULES:
        import importlib
        # NB: import via importlib, NOT `from . import <name>` — the latter does a
        # hasattr() check that re-enters this __getattr__ and recurses.
        return importlib.import_module(f"{__name__}.{name}")
    if name in __all__:
        from . import utils
        return getattr(utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """What `bs.<TAB>` offers in a notebook.

    Without this, tab-completion shows only what is physically in this module's
    namespace — `__version__` and `test` — because everything else arrives
    through the lazy `__getattr__` above and `dir()` cannot see it. The
    laziness is worth keeping (a bare `import bioscout` must not drag in
    OpenSim), so the module advertises its API explicitly instead.
    """
    return sorted(set(__all__) | set(globals()))
