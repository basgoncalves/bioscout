"""One rule for every path in ``session.yaml``, and a report of which one applied.

The problem this replaces
-------------------------
There were three rules and nobody could say which applied where::

    setup_folder   os.path.join(project_dir, ...)          pipeline.py:964
    c3d_source     os.path.join(project_dir, ...)          pipeline.py:966
    markerset      search models/ -> generic models/ -> project root
    so_model       the same three-root search

``markerset`` went through the *model* resolver, so
``setup_files/markers_FAIS.xml`` landed correctly only because the third
fallback happened to be the project root. And the FAIS sessions write
``c3d_source: ../../../c3d_files/022``, which is session-relative, against a
resolver that joins it to the project — three levels above the project, at a
path that does not exist. It never bit anyone because the project stages its
c3d files with its own script, so bioscout was never asked to resolve it.

The rule
--------
Each key declares the bases it may resolve against, **best first**:

* **session-scoped** — data belonging to this session (``c3d_source``): the
  session folder, then the project.
* **project-scoped** — assets shared across sessions (``setup_folder``,
  ``markerset``): the project, then the session.
* **model** — ``so_model``, ``ceinms_model``, ``generic``: the iteration folder,
  ``models/``, ``generic models/``, then the project root. Models genuinely live
  in several places, so the search stays — what changes is that it now says
  which one answered.

An absolute path is used as-is. The first base where the file exists wins, and
:class:`Resolved` records it. Resolving through anything other than the first
base is not an error — plenty of real projects are laid out that way — but it is
reported, because "it worked, via a base you did not intend" is how a session
silently reads the wrong file.

Nothing here imports anything but the standard library, so preflight and the
session editor can both use it.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = ["Resolved", "BASES", "resolve", "resolve_all", "base_order"]

#: key -> the named bases it may resolve against, best first.
BASES: Dict[str, Tuple[str, ...]] = {
    "c3d_source": ("session", "project"),
    "setup_folder": ("project", "session"),
    "markerset": ("project", "models", "generic_models", "session"),
    "so_model": ("iteration", "models", "generic_models", "project"),
    "ceinms_model": ("iteration", "models", "generic_models", "project"),
    "generic": ("generic_models", "models", "project", "iteration"),
}

#: Anything not listed above: shared asset, project first.
DEFAULT_BASES: Tuple[str, ...] = ("project", "session")


@dataclass
class Resolved:
    """What a session.yaml path turned into, and how."""

    key: str
    raw: str
    path: Optional[Path] = None
    base: Optional[str] = None          #: which named base answered
    tried: List[Tuple[str, Path]] = field(default_factory=list)
    exists: bool = False

    @property
    def ok(self) -> bool:
        return self.exists

    @property
    def preferred(self) -> bool:
        """True when the FIRST base for this key is the one that answered."""
        order = base_order(self.key)
        return bool(self.base) and bool(order) and self.base == order[0]

    def note(self) -> Optional[str]:
        """One line for a human, or None when it resolved as intended."""
        if not self.exists:
            where = ", ".join(f"{b}: {p}" for b, p in self.tried[:3])
            return (f"{self.key}: '{self.raw}' not found — tried {where}"
                    + (" ..." if len(self.tried) > 3 else ""))
        if not self.preferred:
            first = base_order(self.key)[0]
            return (f"{self.key}: '{self.raw}' resolved against the {self.base} "
                    f"folder, not {first} — it works here, but the value reads as "
                    f"if it were {first}-relative")
        return None

    def __fspath__(self) -> str:                     # usable wherever a path is
        return str(self.path or self.raw)

    def __str__(self) -> str:
        return str(self.path or self.raw)


def base_order(key: str) -> Tuple[str, ...]:
    return BASES.get(key, DEFAULT_BASES)


def _base_dirs(session_dir, project_dir, iteration_dir) -> Dict[str, Optional[Path]]:
    session = Path(session_dir).resolve() if session_dir else None
    project = Path(project_dir).resolve() if project_dir else None
    if project is None and session is not None:
        # <project>/simulations/<subject>/<session> — three up. Only a guess, and
        # only used when the caller has no project to give.
        guess = session.parent.parent.parent
        project = guess if (guess / "simulations").is_dir() else None
    return {
        "session": session,
        "project": project,
        "models": (project / "models") if project else None,
        "generic_models": (project / "generic models") if project else None,
        "iteration": Path(iteration_dir).resolve() if iteration_dir else None,
    }


def resolve(key: str, raw, session_dir=None, project_dir=None,
            iteration_dir=None) -> Resolved:
    """Resolve one session.yaml value. Never raises; check ``.ok``."""
    out = Resolved(key=key, raw="" if raw is None else str(raw))
    if not out.raw:
        return out

    candidate = Path(out.raw.replace("\\", "/"))
    if candidate.is_absolute():
        out.path, out.base = candidate, "absolute"
        out.exists = candidate.exists()
        out.tried = [("absolute", candidate)]
        return out

    dirs = _base_dirs(session_dir, project_dir, iteration_dir)
    for name in base_order(key):
        root = dirs.get(name)
        if root is None:
            continue
        cand = (root / candidate).resolve()
        out.tried.append((name, cand))
        if cand.exists():
            out.path, out.base, out.exists = cand, name, True
            return out

    # Nothing existed. Report the preferred base as the intended location, so an
    # error message points at where the file SHOULD be rather than the last
    # place that happened to be checked.
    if out.tried:
        out.path, out.base = out.tried[0][1], out.tried[0][0]
    return out


def resolve_all(cfg: dict, session_dir=None, project_dir=None,
                iteration: Optional[str] = None,
                iteration_dir=None) -> List[Resolved]:
    """Resolve every path-like key in a loaded session.yaml, session keys first."""
    out: List[Resolved] = []
    for key in ("c3d_source", "setup_folder", "markerset"):
        if cfg.get(key):
            out.append(resolve(key, cfg[key], session_dir, project_dir, iteration_dir))

    blocks = cfg.get("iterations") or cfg.get("models") or {}
    for name, block in blocks.items():
        if iteration and name != iteration:
            continue
        if not isinstance(block, dict):
            continue
        for key in ("generic", "so_model", "ceinms_model", "markerset"):
            if block.get(key):
                r = resolve(key, block[key], session_dir, project_dir,
                            iteration_dir or (Path(session_dir) / "3_iterations" / name
                                              if session_dir else None))
                r.key = f"iterations.{name}.{key}"
                # keep the base order of the underlying key for .preferred
                BASES.setdefault(r.key, base_order(key))
                out.append(r)
    return out


def report(resolutions: Sequence[Resolved]) -> List[str]:
    """The notes worth showing, missing files first."""
    bad = [r.note() for r in resolutions if not r.ok]
    odd = [r.note() for r in resolutions if r.ok and not r.preferred]
    return [n for n in list(bad) + list(odd) if n]
