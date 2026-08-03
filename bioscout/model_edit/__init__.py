"""
bioscout.model_edit
===================

One consistent way to build and change an OpenSim model — scale it, set its
mass, change its strength, grow its moment arms, widen a coordinate, place its
markers, inspect it — reachable from Python, the command line, a YAML recipe,
and (next) the GUI.

    bioscout --model-edit                         # guided
    python -m bioscout.model_edit list
    python -m bioscout.model_edit apply mvic --model scaled_opt_N10.osim --factor 3
    python -m bioscout.model_edit recipe build_gpk.yaml --root .

    from bioscout.model_edit import apply, run_recipe
    res = apply("mvic", "scaled_opt_N10.osim", factor=3.0)
    res.ok, res.model, res.changed

This package **adds no biomechanics**. Every operation delegates to code that
was already here — ``utils/openSim.py``, ``utils/scale_measurements.py``,
``change_moment_arms``, ``muscle_inspect``, ``utils/model_report.py``. What it
adds is agreement between them:

* **no operation prompts.** ``utils/openSim.py`` uses ``input()`` as a lazy
  argument default in about forty places, which hangs a batch run and makes a
  GUI impossible.
* **one output-naming rule** (:mod:`~bioscout.model_edit.naming`) instead of the
  eight that were in use, and never writing over the input.
* **one description of each operation** (:mod:`~bioscout.model_edit.spec`), from
  which the prompt, the ``--flags``, the recipe validator and the GUI form are
  all generated. Adding an op is one decorator.
* **results are returned, not printed**, so a caller can assert on them.

The pure-XML / OpenSim split is deliberate and declared per op: wrap radii, path
points, coordinate ranges, marker removal, model comparison and diffing are
plain XML and run anywhere, including in tests and in a GUI on a machine with no
bindings. ``model_edit list`` marks the ones that cannot run where you are.
"""
from __future__ import annotations

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "apply", "plan", "list_ops", "describe_op",
    "run_recipe", "load_recipe", "validate_recipe",
    "info", "OpResult", "Op", "Param", "REGISTRY", "VERBS",
]


def __getattr__(name):
    """Lazy, so ``import bioscout.model_edit`` stays cheap and OpenSim-free."""
    if name in ("apply", "plan"):
        from . import run
        return getattr(run, name)
    if name in ("OpResult", "Op", "Param", "REGISTRY", "VERBS"):
        from . import spec
        if name == "REGISTRY":
            from . import ops as _ops  # noqa: F401  — populate first
        return getattr(spec, name)
    if name == "run_recipe":
        from .recipe import run
        return run
    if name == "load_recipe":
        from .recipe import load
        return load
    if name == "validate_recipe":
        from .recipe import validate_recipe
        return validate_recipe
    if name == "info":
        from .introspect import summary
        return summary
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def list_ops(verb=None):
    """List registered operations, optionally filtered to one group.

    Named ``list_ops`` and not ``ops``: the submodule holding the operations is
    ``bioscout.model_edit.ops``, and a module-level function of the same name
    shadows it, so ``from . import ops`` inside this package returns the
    function and the registry silently stays empty.

    >>> [o.name for o in list_ops("strength")]
    ['muscle_opt', 'mvic']
    """
    from .spec import REGISTRY, by_verb
    from . import ops as _ops  # noqa: F401
    if verb is None:
        return sorted(REGISTRY.values(), key=lambda o: (o.verb, o.name))
    return by_verb().get(verb, [])


def describe_op(name):
    """The :class:`~bioscout.model_edit.spec.Op` record for ``name``."""
    from .spec import get
    return get(name)
