__version__ = "1.3.0"


def __getattr__(name):
    # Lazy access so `import bioscout` stays light, while `bioscout.init_project`
    # (and `bioscout.Project`) pull in the heavier modules only when used.
    if name in ("init_project",):
        from .project import init_project
        return init_project
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
