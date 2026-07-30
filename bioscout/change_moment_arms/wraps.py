"""Read and edit wrap-surface radii — pure ``xml.etree``, no OpenSim needed.

In OpenSim a wrap surface is the geometric stand-in for muscle bulk: the path
is held off the bone by the cylinder, so the cylinder's radius sets how far the
line of action sits from the joint axis. Growing it is therefore the *mechanism*
by which a larger muscle produces a larger moment arm, not a proxy for it — which
is why this, rather than translating attachment points, is the primary edit here.

Kept free of ``opensim`` so the file surgery can be unit-tested and so a model
can be inspected on a machine without an OpenSim install.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

__all__ = ["WrapInfo", "read_wraps", "muscle_wraps", "scale_wrap_radii",
           "set_wrap_radii"]


@dataclass
class WrapInfo:
    """One wrap surface and where it lives."""

    name: str
    body: str
    kind: str                  # WrapCylinder / WrapEllipsoid / WrapSphere ...
    radius: Optional[float]    # None for surfaces without a single radius
    muscles: List[str]

    @property
    def scalable(self) -> bool:
        """True when this surface has a single radius we can grow."""
        return self.radius is not None


def _parser() -> ET.XMLParser:
    """Keep OpenSim's property comments through a round trip."""
    return ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))


def _muscle_elements(root: ET.Element):
    """Yield every element that owns a GeometryPath (i.e. every muscle/force)."""
    for el in root.iter():
        if el.get("name") and el.find("GeometryPath") is not None:
            yield el


def muscle_wraps(root: ET.Element) -> Dict[str, List[str]]:
    """``{muscle: [wrap object names]}`` for every muscle that wraps."""
    out: Dict[str, List[str]] = {}
    for m in _muscle_elements(root):
        gp = m.find("GeometryPath")
        names = [w.findtext("wrap_object", "").strip()
                 for w in gp.iter("PathWrap")]
        names = [n for n in names if n]
        if names:
            out[m.get("name")] = names
    return out


def read_wraps(model: str | Path) -> Dict[str, WrapInfo]:
    """Every wrap surface in the model, keyed by name."""
    root = ET.parse(Path(model), parser=_parser()).getroot()
    by_muscle = muscle_wraps(root)
    users: Dict[str, List[str]] = {}
    for muscle, wnames in by_muscle.items():
        for w in wnames:
            users.setdefault(w, []).append(muscle)

    out: Dict[str, WrapInfo] = {}
    for body in root.iter("Body"):
        bname = body.get("name")
        for wo in body.iter():
            kind = wo.tag
            # comment nodes survive the round trip (see _parser) and carry a
            # callable tag, not a string — skip them before any tag matching
            if not isinstance(kind, str):
                continue
            if not kind.startswith("Wrap") or kind == "WrapObjectSet":
                continue
            name = wo.get("name")
            if not name:
                continue
            rtxt = wo.findtext("radius")
            radius = None
            if rtxt:
                try:                       # a sphere/cylinder has one radius;
                    radius = float(rtxt)   # an ellipsoid has three -> skip
                except ValueError:
                    radius = None
            out[name] = WrapInfo(name=name, body=bname, kind=kind,
                                 radius=radius, muscles=sorted(users.get(name, [])))
    return out


def set_wrap_radii(model: str | Path, out_path: str | Path,
                   radii: Dict[str, float]) -> Dict[str, tuple]:
    """Write absolute radii. Returns ``{wrap: (old, new)}`` for those changed."""
    tree = ET.parse(Path(model), parser=_parser())
    root = tree.getroot()
    changed: Dict[str, tuple] = {}
    for wo in root.iter():
        name = wo.get("name") if hasattr(wo, "get") else None
        if not name or name not in radii:
            continue
        el = wo.find("radius")
        if el is None or not el.text:
            continue
        old = float(el.text)
        new = float(radii[name])
        if new <= 0:
            raise ValueError(f"{name}: radius must be > 0, got {new}")
        el.text = repr(new)
        changed[name] = (old, new)
    missing = set(radii) - set(changed)
    if missing:
        raise KeyError(f"wrap surface(s) not found or without a radius: "
                       f"{', '.join(sorted(missing))}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    return changed


def scale_wrap_radii(model: str | Path, out_path: str | Path,
                     factors: Dict[str, float]) -> Dict[str, tuple]:
    """Multiply radii by per-wrap factors. Returns ``{wrap: (old, new)}``."""
    current = read_wraps(model)
    radii = {}
    for name, f in factors.items():
        info = current.get(name)
        if info is None:
            raise KeyError(f"wrap surface '{name}' not in {model}")
        if not info.scalable:
            raise ValueError(f"wrap surface '{name}' ({info.kind}) has no single "
                             "radius to scale")
        radii[name] = info.radius * float(f)
    return set_wrap_radii(model, out_path, radii)
