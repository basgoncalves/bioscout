"""The contract every model operation obeys, and the registry they live in.

One dataclass describes an operation completely: what it is called, what it
does, what parameters it takes and of what kind, how it names its output, and
whether it needs OpenSim. Everything else in this package -- the guided prompt,
the argparse CLI, the recipe runner, and (next) the GUI panel -- is *generated*
from that description rather than hand-written per operation. Adding an
operation is one ``@op`` decorator, and it appears in all of them at once.

That is the whole point. bioscout already had the capability three times over
(``utils/openSim.py``, ``change_moment_arms``, ``muscle_inspect``), but each
with its own calling convention, its own interactive prompt, and its own idea
of where the output goes. This module does not reimplement any of that work --
every op delegates -- it just makes them agree.

The three rules an op must follow, none of which the underlying functions
consistently did:

1. **Never prompt.** ``utils/openSim.py`` has ~40 bare ``input()`` calls used as
   lazy argument defaults; they block a GUI and hang a batch run. An op always
   passes every argument explicitly.
2. **Always take an explicit output path.** Callers of
   ``increase_isometric_force`` had no say in the ``_increased_3.00.osim`` it
   derived, and ``set_total_mass`` overwrites in place by default. Here the
   facade computes the name from ``Op.suffix`` and hands it down, so the naming
   rule lives in exactly one place (``naming.py``).
3. **Return a result, do not print one.** ``OpResult`` carries what changed, so
   a caller can assert on it. Ops may still print progress.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

__all__ = ["Param", "Op", "OpResult", "REGISTRY", "op", "get", "by_verb", "VERBS"]


#: Operation groups, in the order a model is normally built. The CLI and the
#: GUI both present ops in this order, so it is the one place that decides it.
VERBS: Tuple[str, ...] = (
    "scale",        # dimensional scaling from the static trial
    "mass",         # total / per-body mass, without touching geometry
    "strength",     # max isometric force, optimal fibre & tendon slack length
    "actuators",    # reserve and residual actuators (the SO force set)
    "moment_arms",  # wrap radii and path points
    "coordinates",  # ranges, locking
    "markers",      # marker placement and marker-set edits
    "inspect",      # read-only checks and reports
)


@dataclass(frozen=True)
class Param:
    """One argument of an operation, described well enough to build a UI from.

    ``kind`` drives how the value is asked for and parsed:
    ``float int str bool path choice list[str] list[float]``.

    ``choices_from`` names a *model-dependent* option list that cannot be known
    until a model is picked -- ``coordinates``, ``muscles``, ``wraps``,
    ``bodies``. The prompt resolves it by calling
    :func:`bioscout.model_edit.introspect.options_for`, so the CLI can offer the
    real coordinate names of the model in hand instead of a static list, and the
    GUI can fill a dropdown the same way.
    """
    name: str
    kind: str
    help: str
    default: Any = None
    required: bool = False
    choices: Tuple[Any, ...] = ()
    choices_from: Optional[str] = None
    unit: str = ""

    def __post_init__(self):
        allowed = {"float", "int", "str", "bool", "path", "choice",
                   "list[str]", "list[float]"}
        if self.kind not in allowed:
            raise ValueError(f"{self.name}: unknown kind {self.kind!r}")
        if self.kind == "choice" and not (self.choices or self.choices_from):
            raise ValueError(f"{self.name}: kind='choice' needs choices "
                             f"or choices_from")

    @property
    def label(self) -> str:
        return f"{self.name} [{self.unit}]" if self.unit else self.name


@dataclass(frozen=True)
class Op:
    """A single model operation.

    ``suffix`` is a format template evaluated against the resolved parameters,
    e.g. ``"_mvicx{factor:.2f}"`` -> ``scaled_opt_N10_mvicx3.00.osim``. It is
    how an output name is derived when the caller does not give one; an empty
    suffix means the caller MUST supply ``out``. See :mod:`naming`.

    ``needs_opensim`` is honest about the split that runs through this whole
    package: wrap radii and path points are plain XML and run anywhere, while
    anything that has to *evaluate* a model (moment-arm sweeps, ScaleTool, mass
    and inertia) needs the OpenSim Python bindings. The CLI reports this before
    it asks for anything, rather than failing halfway through a recipe.
    """
    name: str
    verb: str
    summary: str
    params: Tuple[Param, ...]
    fn: Callable[..., "OpResult"]
    suffix: str = ""
    needs_opensim: bool = True
    writes_model: bool = True
    delegates_to: str = ""          # provenance, shown in `list --long`
    notes: str = ""                 # caveats worth reading before running

    def param(self, name: str) -> Param:
        for p in self.params:
            if p.name == name:
                return p
        raise KeyError(f"{self.name}: no parameter {name!r}")

    @property
    def required_params(self) -> Tuple[Param, ...]:
        return tuple(p for p in self.params if p.required)


@dataclass
class OpResult:
    """What an operation did. Returned, never printed, so callers can assert."""
    ok: bool
    op: str
    source: str
    model: Optional[str] = None          # output path, None when writes_model=False
    changed: Dict[str, Any] = field(default_factory=dict)
    messages: list = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)   # inspect payloads
    reason: str = ""

    def __bool__(self) -> bool:
        return bool(self.ok)

    def summary_line(self) -> str:
        if not self.ok:
            return f"[model-edit] {self.op}: FAILED — {self.reason}"
        n = len(self.changed)
        what = f"{n} change(s)" if n else "no change"
        where = f" -> {self.model}" if self.model else ""
        return f"[model-edit] {self.op}: {what}{where}"


#: name -> Op. Populated by importing :mod:`bioscout.model_edit.ops`.
REGISTRY: Dict[str, Op] = {}


def op(name: str, *, verb: str, summary: str, params: Sequence[Param],
       suffix: str = "", needs_opensim: bool = True,
       writes_model: bool = True, delegates_to: str = "", notes: str = ""):
    """Register a function as an operation.

    The wrapped function is called as ``fn(model, out, **params)`` and must
    return an :class:`OpResult`. It must not prompt and must not invent an
    output path.
    """
    if verb not in VERBS:
        raise ValueError(f"{name}: verb {verb!r} not in {VERBS}")

    def deco(fn):
        if name in REGISTRY:
            raise ValueError(f"operation {name!r} is already registered")
        REGISTRY[name] = Op(name=name, verb=verb, summary=summary,
                            params=tuple(params), fn=fn, suffix=suffix,
                            needs_opensim=needs_opensim,
                            writes_model=writes_model,
                            delegates_to=delegates_to, notes=notes)
        return fn
    return deco


def get(name: str) -> Op:
    """Look an operation up by name, with a helpful error when it is absent."""
    from . import ops  # noqa: F401  — ensure the registry is populated
    try:
        return REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(REGISTRY))
        raise KeyError(f"unknown operation {name!r}. Known: {known}") from None


def by_verb() -> Dict[str, list]:
    """``{verb: [Op, ...]}`` in :data:`VERBS` order, for listing."""
    from . import ops  # noqa: F401
    out: Dict[str, list] = {v: [] for v in VERBS}
    for o in REGISTRY.values():
        out[o.verb].append(o)
    for v in out:
        out[v].sort(key=lambda o: o.name)
    return {v: ops_ for v, ops_ in out.items() if ops_}
