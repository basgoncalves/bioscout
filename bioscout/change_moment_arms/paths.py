"""Translate a muscle's path points — the fallback for muscles without a wrap.

Glute medius and minimus in the GPK model have no wrap surface on their paths,
so there is no radius to grow; the only way to move their line of action is to
move the attachment points themselves. This is a weaker model of "the muscle got
bigger" than growing a wrap — it moves the attachment rather than the bulk — so
prefer ``wraps.py`` wherever a wrap exists, and say which route was used when
reporting the result.

Pure ``xml.etree``; also shifts along the coordinate axis by rotating points
about a joint axis, which is the mechanically correct way to move a moment-arm
curve left/right in ``q``.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

__all__ = ["read_path_points", "translate_path_points", "rotate_path_points"]

_AXES = {"x": 0, "y": 1, "z": 2}


def _parser() -> ET.XMLParser:
    return ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))


def _frame_of(el: ET.Element) -> Optional[str]:
    for tag in ("socket_parent_frame", "body"):
        t = el.findtext(tag)
        if t:
            return t.strip().split("/")[-1]
    return None


def _points_of(root: ET.Element, muscle: str) -> List[ET.Element]:
    for m in root.iter():
        if m.get("name") != muscle:
            continue
        gp = m.find("GeometryPath")
        if gp is None:
            continue
        # Only fixed PathPoints: a MovingPathPoint's location is a function of a
        # coordinate, so translating its constant would corrupt the model.
        return [pp for pp in gp.iter("PathPoint") if pp.find("location") is not None]
    return []


def read_path_points(model: str | Path, muscle: str) -> List[Tuple[str, str, np.ndarray]]:
    """``[(point name, body, xyz)]`` for one muscle's fixed path points."""
    root = ET.parse(Path(model), parser=_parser()).getroot()
    out = []
    for pp in _points_of(root, muscle):
        loc = [float(v) for v in pp.findtext("location").split()]
        out.append((pp.get("name"), _frame_of(pp), np.asarray(loc, float)))
    return out


def _edit(model, out_path, muscle, bodies, fn) -> Dict[str, tuple]:
    tree = ET.parse(Path(model), parser=_parser())
    root = tree.getroot()
    pts = _points_of(root, muscle)
    if not pts:
        raise KeyError(f"muscle '{muscle}' has no fixed path points in {model}")
    bodies = set(bodies) if bodies else None
    moved: Dict[str, tuple] = {}
    for pp in pts:
        body = _frame_of(pp)
        if bodies is not None and body not in bodies:
            continue
        old = np.asarray([float(v) for v in pp.findtext("location").split()], float)
        new = fn(old)
        pp.find("location").text = " ".join(repr(float(v)) for v in new)
        moved[pp.get("name")] = (old.tolist(), np.asarray(new, float).tolist())
    if not moved:
        raise ValueError(
            f"muscle '{muscle}': no path points on body/bodies "
            f"{sorted(bodies) if bodies else '(any)'}")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out_path, encoding="utf-8", xml_declaration=True)
    return moved


def translate_path_points(model: str | Path, out_path: str | Path, muscle: str,
                          offset_m: Sequence[float],
                          bodies: Optional[Iterable[str]] = None) -> Dict[str, tuple]:
    """Rigidly translate a muscle's path points by ``offset_m`` (metres).

    Restrict to ``bodies`` to move only, say, the pelvic attachments.
    """
    d = np.asarray(offset_m, float).ravel()[:3]
    if d.size != 3:
        raise ValueError("offset_m must have 3 components")
    return _edit(model, out_path, muscle, bodies, lambda p: p + d)


def rotate_path_points(model: str | Path, out_path: str | Path, muscle: str,
                       angle_deg: float, axis: str = "x",
                       centre_m: Sequence[float] = (0.0, 0.0, 0.0),
                       bodies: Optional[Iterable[str]] = None) -> Dict[str, tuple]:
    """Rotate path points about a joint axis — shifts the curve along ``q``.

    A moment-arm curve moves left/right in the coordinate when the attachment
    rotates about that coordinate's axis, so this is the correct edit for a
    left/right shift. Note it has no justification from muscle volume: bulk
    changes the height of the curve, not where along the range its peak sits.
    """
    if axis not in _AXES:
        raise ValueError(f"axis must be one of {sorted(_AXES)}, got {axis!r}")
    c = np.asarray(centre_m, float).ravel()[:3]
    t = np.radians(float(angle_deg))
    ct, st = np.cos(t), np.sin(t)
    R = {
        "x": np.array([[1, 0, 0], [0, ct, -st], [0, st, ct]]),
        "y": np.array([[ct, 0, st], [0, 1, 0], [-st, 0, ct]]),
        "z": np.array([[ct, -st, 0], [st, ct, 0], [0, 0, 1]]),
    }[axis]
    return _edit(model, out_path, muscle, bodies, lambda p: R @ (p - c) + c)
