__version__ = "1.2.9"

from typing import TYPE_CHECKING
if TYPE_CHECKING:  # editor autocomplete only — no runtime cost
    from .utils.analysis import (
        Project, Subject, Session, init_project,
        build_model_config, discover_subjects,
        check_settings_version, migrate_settings,
    )

# Public API. Everything except `test` lives in bioscout.utils and is loaded
# lazily by __getattr__ below, so a bare `import bioscout` stays light — it does
# NOT import OpenSim/CEINMS until you actually use one of these names.
__all__ = (
    "__version__", "test",
    "Project", "Subject", "Session", "init_project",
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
    if name in __all__:
        from . import utils
        return getattr(utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
