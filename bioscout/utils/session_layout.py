"""Where things live inside a session folder — old and new layouts.

A session used to be a flat pile of folders::

    <session>/
        c3dfiles/            raw captures
        experimental/        model-independent exports (markers, GRF, EMG)
        cateli/              model iteration
        gpk/                 model iteration
        logs/  results/  ...

which sorts alphabetically into an order that says nothing about the pipeline,
and mixes iterations in with shared inputs. The numbered layout fixes both::

    <session>/
        1_c3dfiles/
        2_experimental/
        3_iterations/
            cateli/
            gpk/
        logs/  results/  ...

**Both are supported.** Every resolver here prefers whichever form already
exists on disk and falls back to the numbered name when creating something new,
so existing sessions (and other projects, and collaborators' copies) keep
working untouched while new output adopts the numbered names. Nothing here
renames anything — migration is a deliberate, separate act.

Call the resolvers rather than joining these names by hand; that is the only
thing keeping the two layouts from drifting apart.
"""
from __future__ import annotations

import os
from typing import Iterable, Optional

__all__ = [
    "C3D_DIRS", "EXPERIMENTAL_DIRS", "ITERATIONS_DIRS", "NON_ITERATION_DIRS",
    "c3d_root", "experimental_root", "iterations_root", "iteration_path",
    "is_numbered_layout",
]

#: Accepted names per role, **preferred first**. The first entry is what gets
#: created; later entries are recognised for back-compatibility.
C3D_DIRS = ("1_c3dfiles", "c3dfiles")
EXPERIMENTAL_DIRS = ("2_experimental", "experimental")
ITERATIONS_DIRS = ("3_iterations",)

#: Folders directly under a session that are never model iterations. Includes
#: both spellings of the shared dirs plus the iteration parent itself.
NON_ITERATION_DIRS = frozenset(
    set(C3D_DIRS) | set(EXPERIMENTAL_DIRS) | set(ITERATIONS_DIRS)
    | {"logs", "results", "manuscript", "recordings", "models", "setup_files",
       "setupFiles"}
)


def _first_existing(session_dir: str, names: Iterable[str]) -> Optional[str]:
    for n in names:
        p = os.path.join(session_dir, n)
        if os.path.isdir(p):
            return p
    return None


def _resolve(session_dir: str, names, create: bool = False) -> str:
    """Existing folder for a role, else the preferred (numbered) name."""
    found = _first_existing(session_dir, names)
    if found:
        return found
    path = os.path.join(session_dir, names[0])
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def is_numbered_layout(session_dir: str) -> bool:
    """True when this session already uses the numbered folder names."""
    return any(
        os.path.isdir(os.path.join(session_dir, n))
        for n in (C3D_DIRS[0], EXPERIMENTAL_DIRS[0], ITERATIONS_DIRS[0])
    )


def c3d_root(session_dir: str, create: bool = False) -> str:
    """Folder holding this session's raw ``.c3d`` captures."""
    return _resolve(session_dir, C3D_DIRS, create)


def experimental_root(session_dir: str, subdir: Optional[str] = None,
                      create: bool = False) -> str:
    """Folder holding model-independent exports (markers, GRF, EMG).

    ``subdir`` overrides the name entirely — that is how a downsample run
    redirects to e.g. ``experimental_ds10``. An override is used verbatim
    (no numbered/plain resolution), since it names one specific variant.
    """
    if subdir and subdir not in EXPERIMENTAL_DIRS:
        path = os.path.join(session_dir, subdir)
        if create:
            os.makedirs(path, exist_ok=True)
        return path
    return _resolve(session_dir, EXPERIMENTAL_DIRS, create)


def iterations_root(session_dir: str, create: bool = False) -> str:
    """Parent folder of the model iterations.

    Resolution order:
      1. ``<session>/3_iterations`` if it exists;
      2. ``<session>/3_iterations`` if the session is otherwise numbered
         (``1_c3dfiles``/``2_experimental`` present) — a numbered session
         should not start dropping iterations at the top level;
      3. the session folder itself if the session is in the old flat layout;
      4. ``<session>/3_iterations`` for a session with nothing in it yet, so
         new sessions get the numbered layout.
    """
    found = _first_existing(session_dir, ITERATIONS_DIRS)
    if found:
        return found
    numbered = os.path.join(session_dir, ITERATIONS_DIRS[0])
    if not is_numbered_layout(session_dir) and _first_existing(
        session_dir, C3D_DIRS[1:] + EXPERIMENTAL_DIRS[1:]
    ):
        return session_dir                      # established old-layout session
    if create:
        os.makedirs(numbered, exist_ok=True)
    return numbered


def iteration_path(session_dir: str, iteration: str) -> str:
    """Folder for one model iteration.

    Looks under ``3_iterations/`` first, then directly under the session, so a
    half-migrated session still resolves. Falls back to the layout's canonical
    location when neither exists yet (i.e. for a folder about to be created).
    """
    for base in (iterations_root(session_dir), session_dir):
        p = os.path.join(base, iteration)
        if os.path.isdir(p):
            return p
    return os.path.join(iterations_root(session_dir), iteration)
