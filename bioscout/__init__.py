__version__ = "3.1.1"

from typing import TYPE_CHECKING
if TYPE_CHECKING:  # editor autocomplete only — no runtime cost
    from .core.analysis import (
        Project, Subject,
        build_model_config, discover_subjects,
        check_settings_version, migrate_settings,
    )
    from .session.recording import Session           # one recording-session folder
    from .session.iteration import Iteration         # one model iteration (runnable)
    from . import plot                              # comparison figures
    from .simulate import mew                       # Python muscle solver
    from . import results                           # load / plot / export results

# Public API. Everything except `test` lives in bioscout.utils and is loaded
# lazily by __getattr__ below, so a bare `import bioscout` stays light — it does
# NOT import OpenSim/CEINMS until you actually use one of these names.
__all__ = (
    "__version__", "test",
    "Project", "Subject", "Session", "Iteration",
    "build_model_config", "discover_subjects",
    "check_settings_version", "migrate_settings",
    "summarize_results",
    "start_logging", "capture_output", "stop_logging",   # run log (bioscout.utils.shared)
    "utils",                    # bioscout.utils — the helper namespace
    "plot",                     # bioscout.plot — figures from a tidy table
    "pipeline",                 # bioscout.pipeline — run_project (batch settings runs)
    "mew",                      # bioscout.simulate.mew — Python muscle solver + its readers
    "results",                  # bioscout.results — load / plot / export simulation results
)

#: Names __getattr__ resolves to a SUBMODULE rather than to something in
#: bioscout.utils. Keeping them in one place is what stops the two branches
#: below drifting apart when a new one is added.
#:
#: "utils" is here because a subpackage only becomes an attribute of its parent
#: once something has IMPORTED it. `from bioscout.utils import x` does that
#: import; a bare `bs.utils.x` right after `import bioscout as bs` did not, so
#: it raised AttributeError until some earlier call happened to load utils.
_SUBMODULES = ("utils", "plot", "pipeline", "mew", "results")
#: submodules that do not live directly under bioscout/
_SUBMODULE_PATHS = {"mew": "simulate.mew"}


def test(verbosity=2):
    """Run the bioscout self-test suite.

    ``python -c "import bioscout; bioscout.test()"``
    """
    from . import tests
    return tests.run(verbosity=verbosity)


def __getattr__(name):          # PEP 562: lazy, light `import bioscout`
    if name in ("Session", "Iteration"):   # session + runnable iteration
        import importlib
        mod = "recording" if name == "Session" else "iteration"
        return getattr(importlib.import_module(f"{__name__}.session.{mod}"), name)
    if name in _SUBMODULES:
        import importlib
        # NB: import via importlib, NOT `from . import <name>` — the latter does a
        # hasattr() check that re-enters this __getattr__ and recurses.
        return importlib.import_module(f"{__name__}.{_SUBMODULE_PATHS.get(name, name)}")
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
