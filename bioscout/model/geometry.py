"""Where an ``.osim`` model's bone meshes actually resolve to — or don't.

The failure this module exists to catch
---------------------------------------
OpenSim resolves a mesh filename **relative to the folder holding the .osim**.
Move a model, or move the geometry out from under it, and OpenSim opens the
model with every muscle, marker and joint intact and **no bones at all** — no
exception, no warning, nothing in the log. It looks like a rendering quirk. It
is a model whose provenance you can no longer check by eye, and it is the single
easiest way to publish a figure of the wrong skeleton.

Two more variants of the same silence:

* **Schema half-handling.** OpenSim 3.x writes ``<geometry_file>`` inside
  ``DisplayGeometry``; 4.x writes ``<mesh_file>`` inside ``Mesh``. Code that
  knows only one of them reports a clean bill of health for the other family.
  Both are checked here, everywhere in the document — not only under ``<Body>``,
  because ground meshes and contact geometry live outside it.
* **Case.** ``pelvis.vtp`` vs ``Pelvis.vtp`` resolves on Windows and fails on
  Linux. The model works for you and not for the collaborator you sent it to.

The tiers
---------
A reference is resolved by walking the same places OpenSim does, in order, and
recording *which* one hit. The tier is the point: "found it" is not the useful
answer, "found it, but only in the bioscout install" is.

    local      the model's own folder, or its Geometry/ subfolder.
               PORTABLE — the geometry travels with the .osim.
    parent     ../Geometry beside the model's parent. Portable within a project
               tree, not if the model alone is copied.
    bundled    the Geometry/ shipped inside bioscout. Works wherever bioscout is
               installed; silently different if that copy ever diverges.
    search     an explicit --search dir, or $OPENSIM_HOME/Geometry. Machine-local.
    absolute   the reference is an absolute path that exists. Machine-local, and
               the worst of the resolving tiers: it will point somewhere wrong
               on any other computer rather than fail loudly.
    case       resolved only by ignoring filename case. Works on Windows, breaks
               on Linux and macOS-with-case-sensitive-volumes.
    empty      the file resolved but is zero bytes. A 0-byte mesh is never valid.
    missing    nothing found. OpenSim will draw no bone here.

``local`` passes. Everything else that resolves is a warning — reported with its
tier, so the reason is legible — and ``--strict`` turns warnings into failures.
``empty`` and ``missing`` always fail.

Deliberately NOT searched: the current working directory. Some OpenSim versions
fall back to it, but a check whose answer depends on where you were standing
when you ran it is not a check.

Pure ``xml.etree`` + ``pathlib``: no OpenSim, no numpy, no bioscout imports at
module level, so this runs in a bare environment and inside preflight.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

__all__ = [
    "clear_cache",
    "GEOMETRY_TAGS",
    "TIER_ORDER",
    "PASSING_TIERS",
    "GeometryRef",
    "geometry_refs",
    "resolve_ref",
    "search_roots_for",
    "bundled_geometry_dir",
]

#: v3 writes ``geometry_file``, v4 writes ``mesh_file``. Handling one and not the
#: other is a silent pass for half of every mixed project.
GEOMETRY_TAGS = ("geometry_file", "mesh_file")

#: Worst-last. Used for ordering summaries, and for "the worst tier in this model".
TIER_ORDER = ("local", "parent", "bundled", "search", "absolute",
              "case", "empty", "missing", "unreadable")

#: The only tier that means "this model can be handed to anyone".
PASSING_TIERS = ("local",)

_FAILING_TIERS = ("empty", "missing", "unreadable")


@dataclass
class GeometryRef:
    """One ``<geometry_file>``/``<mesh_file>`` value and what became of it."""

    raw: str                       #: exactly as written in the XML
    tag: str                       #: geometry_file | mesh_file
    body: Optional[str] = None     #: owning Body, when the ref sits under one
    tier: str = "missing"
    resolved: Optional[Path] = None
    count: int = 1                 #: times this raw value appears in the model

    @property
    def ok(self) -> bool:
        """Resolvable at all — i.e. OpenSim will draw *something*."""
        return self.tier not in _FAILING_TIERS

    @property
    def portable(self) -> bool:
        """Resolvable from the model's own folder, so it survives being moved."""
        return self.tier in PASSING_TIERS

    @property
    def name(self) -> str:
        return basename(self.raw)


def basename(raw: str) -> str:
    """Basename of a reference, tolerating Windows separators on any OS.

    ``Path("Geometry\\pelvis.vtp").name`` returns the whole string on Linux,
    because a backslash is a legal filename character there. Models written on
    Windows are read on Linux constantly, so normalise first.
    """
    return Path(str(raw).replace("\\", "/")).name


# --------------------------------------------------------------------------- #
# reading the model
# --------------------------------------------------------------------------- #
def _parent_map(root: ET.Element) -> Dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in parent}


def _owning_body(el: ET.Element, parents: Dict[ET.Element, ET.Element]) -> Optional[str]:
    """Nearest enclosing ``<Body name=...>``, or None for ground/contact meshes."""
    cur = parents.get(el)
    while cur is not None:
        if cur.tag == "Body" and cur.get("name"):
            return cur.get("name")
        cur = parents.get(cur)
    return None


def geometry_refs(model_path) -> List[GeometryRef]:
    """Every geometry reference in a model, deduplicated by raw value.

    Scans the WHOLE document rather than only ``<Body>`` subtrees: v4 puts
    ground and contact meshes outside the body set, and a check that misses them
    reports a clean model that renders half a skeleton.

    Raises ``ET.ParseError`` / ``OSError`` — callers decide whether an unreadable
    model is fatal.
    """
    root = ET.parse(str(model_path)).getroot()
    parents = _parent_map(root)

    out: Dict[str, GeometryRef] = {}
    for tag in GEOMETRY_TAGS:
        for el in root.iter(tag):
            raw = (el.text or "").strip()
            if not raw:
                # An empty <mesh_file/> is a body with no mesh, not a broken
                # reference. Nothing to resolve, nothing to report.
                continue
            key = f"{tag}:{raw}"
            if key in out:
                out[key].count += 1
                continue
            out[key] = GeometryRef(raw=raw, tag=tag,
                                   body=_owning_body(el, parents))
    return list(out.values())


# --------------------------------------------------------------------------- #
# where to look
# --------------------------------------------------------------------------- #
def bundled_geometry_dir() -> Optional[Path]:
    """The ``Geometry/`` folder shipped inside bioscout, if it can be located.

    Derived from this file's own position first — that works in a source
    checkout with nothing installed — and only then from an import.
    """
    here = Path(__file__).resolve().parent.parent / "models" / "Geometry"
    if here.is_dir():
        return here
    try:                                        # installed elsewhere
        import bioscout                         # noqa: PLC0415  (deliberately lazy)
        cand = Path(bioscout.__file__).resolve().parent / "models" / "Geometry"
        if cand.is_dir():
            return cand
    except Exception:
        pass
    return None


def search_roots_for(model_path, extra: Optional[Sequence] = None) -> List[tuple]:
    """``[(tier, directory), ...]`` to try, in order, for one model.

    Every entry is a directory that exists. ``extra`` comes from ``--search``
    and is tried before ``$OPENSIM_HOME/Geometry``, both under tier ``search``.
    """
    model_dir = Path(model_path).resolve().parent
    roots: List[tuple] = [
        ("local", model_dir),
        ("local", model_dir / "Geometry"),
        ("parent", model_dir.parent / "Geometry"),
    ]
    bundled = bundled_geometry_dir()
    if bundled is not None:
        roots.append(("bundled", bundled))
    for e in (extra or []):
        roots.append(("search", Path(e)))
    opensim_home = os.environ.get("OPENSIM_HOME")
    if opensim_home:
        roots.append(("search", Path(opensim_home) / "Geometry"))
    return [(t, d) for t, d in roots if d.is_dir()]


# --------------------------------------------------------------------------- #
# directory index
#
# A full-body model carries ~100 mesh references, and each one would otherwise
# be stat-ed against every candidate root — tens of thousands of stat calls for
# a 54-model project, which on a network mount is minutes rather than seconds.
# List each directory ONCE instead and answer from a dict. The case-insensitive
# map comes free from the same listing, which is why the case check costs
# nothing extra.
#
# The cache lives for the process. This is a read-only checker; a model tree
# that changes underneath a single verification run is not a case worth being
# slow for.
# --------------------------------------------------------------------------- #
_DIR_CACHE: Dict[str, tuple] = {}


def _dir_index(directory: Path) -> tuple:
    """``({name: Path}, {lowercase_name: Path})`` of the FILES in a directory."""
    key = str(directory)
    hit = _DIR_CACHE.get(key)
    if hit is not None:
        return hit
    exact: Dict[str, Path] = {}
    lower: Dict[str, Path] = {}
    try:
        with os.scandir(directory) as it:
            for entry in it:
                try:
                    if not entry.is_file():
                        continue
                except OSError:
                    continue
                p = Path(entry.path)
                exact[entry.name] = p
                # first spelling wins, so the report is stable across runs
                lower.setdefault(entry.name.lower(), p)
    except OSError:
        pass
    _DIR_CACHE[key] = (exact, lower)
    return exact, lower


def clear_cache() -> None:
    """Forget indexed directories. Call between runs if the tree changed."""
    _DIR_CACHE.clear()


def resolve_ref(ref: GeometryRef, model_path, extra: Optional[Sequence] = None) -> GeometryRef:
    """Fill in ``ref.tier`` and ``ref.resolved``. Mutates and returns ``ref``."""
    model_dir = Path(model_path).resolve().parent
    q = Path(ref.raw.replace("\\", "/"))

    # 1. absolute — resolves on this machine only, so it is a warning even when
    #    it works. It is also the one case where a wrong path can point at a
    #    real-but-different mesh instead of failing.
    if q.is_absolute():
        if q.is_file():
            return _settle(ref, "absolute", q)
        ref.tier = "missing"
        return ref

    roots = search_roots_for(model_path, extra)
    sub = q.parent                      # '.' for a bare filename

    # 2. exact case. A reference may carry its own sub-path
    #    (``Geometry/pelvis.vtp``), so try the directory it names as well as the
    #    root itself — OpenSim finds a mesh by basename in the search dirs too.
    for tier, root in roots:
        dirs = [root] if sub in (Path("."), Path("")) else [root / sub, root]
        for d in dirs:
            hit = _dir_index(d)[0].get(q.name)
            if hit is not None:
                return _settle(ref, tier, hit)

    # 3. the same walk ignoring case. Reported as its own tier: this is exactly
    #    the model that works for you and not for the person you sent it to.
    lower_name = q.name.lower()
    for _tier, root in roots:
        dirs = [root] if sub in (Path("."), Path("")) else [root / sub, root]
        for d in dirs:
            hit = _dir_index(d)[1].get(lower_name)
            if hit is not None:
                return _settle(ref, "case", hit)

    ref.tier = "missing"
    ref.resolved = None
    return ref


def _settle(ref: GeometryRef, tier: str, path: Path) -> GeometryRef:
    """Record a hit, downgrading to ``empty`` for a zero-byte mesh."""
    ref.resolved = path
    try:
        if path.stat().st_size == 0:
            ref.tier = "empty"
            return ref
    except OSError:
        ref.tier = "missing"
        ref.resolved = None
        return ref
    ref.tier = tier
    return ref
