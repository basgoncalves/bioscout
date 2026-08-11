__version__ = "2.0.0"

from typing import TYPE_CHECKING
if TYPE_CHECKING:  # editor autocomplete only — no runtime cost
    from .utils.analysis import (
        Project, Subject, init_project,
        build_model_config, discover_subjects,
        check_settings_version, migrate_settings,
    )
    from .utils.session import Session, Iteration   # session + runnable iteration

# Public API. Everything except `test` lives in bioscout.utils and is loaded
# lazily by __getattr__ below, so a bare `import bioscout` stays light — it does
# NOT import OpenSim/CEINMS until you actually use one of these names.
__all__ = (
    "__version__", "test",
    "Project", "Subject", "Session", "Iteration", "init_project",
    "build_model_config", "discover_subjects",
    "check_settings_version", "migrate_settings",
    "summarize_results",
)


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
    if name in __all__:
        from . import utils
        return getattr(utils, name)
    if name == "pipeline":      # bioscout.pipeline.run_subject / reset_simulations / run_project
        import importlib
        # NB: import via importlib, NOT `from . import pipeline` — the latter does a
        # hasattr() check that re-enters this __getattr__('pipeline') and recurses.
        return importlib.import_module(f"{__name__}.pipeline")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
