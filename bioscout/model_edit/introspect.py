"""What is *in* a model — read without OpenSim, so a UI can be built offline.

Every option list a prompt or a dropdown needs (coordinates, muscles, wrap
surfaces, bodies, markers) is available straight from the ``.osim`` XML. Reading
them with ``opensim.Model`` would mean the GUI could not populate a single
dropdown on a machine without the bindings, and would cost a full model
initialisation per keystroke. These are plain ``xml.etree`` scans.

Only the *names* come from here. Anything that needs the model evaluated -- a
moment arm, a mass, a segment length -- belongs in an op, not in this module.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

__all__ = ["coordinates", "muscles", "wraps", "bodies", "markers",
           "options_for", "summary", "iter_real", "defaults_ids"]

#: OpenSim muscle classes. A ``<Thelen2003Muscle name="...">`` is a muscle; a
#: ``<CoordinateActuator>`` is not, and offering reserves as tunable muscles is
#: how a "change every muscle" request quietly edits the residual actuators.
_MUSCLE_TAGS = (
    "Thelen2003Muscle", "Millard2012EquilibriumMuscle",
    "Millard2012AccelerationMuscle", "RigidTendonMuscle",
    "DeGrooteFregly2016Muscle", "Schutte1993Muscle_Deprecated",
    "Delp1990Muscle_Deprecated", "McKibbenActuator",
)


def _root(model) -> ET.Element:
    return ET.parse(str(model)).getroot()


def defaults_ids(root: ET.Element) -> set:
    """ids of every element inside a ``<defaults>`` block.

    An .osim carries template objects under ``<defaults>`` -- typically one
    ``<Millard2012EquilibriumMuscle name="default">`` -- which are NOT part of
    the model. Counting them inflates every inventory by one and, worse, makes
    a correct SO/CEINMS pair look wrong: the template's
    ``max_isometric_force`` is not multiplied by the strength factor, so a
    check that "every muscle is exactly x3" fails on a model that is exactly
    x3. Every scan in this package filters through here.
    """
    out = set()
    for el in root.iter():
        if getattr(el, "tag", "") == "defaults":
            for kid in el.iter():
                out.add(id(kid))
    return out


def iter_real(root: ET.Element, tag: str = None):
    """Iterate elements that belong to the model, skipping ``<defaults>``."""
    skip = defaults_ids(root)
    for el in (root.iter(tag) if tag else root.iter()):
        if id(el) not in skip:
            yield el


def _named(root: ET.Element, *tags: str) -> List[str]:
    out, seen = [], set()
    skip = defaults_ids(root)
    for tag in tags:
        for el in root.iter(tag):
            if id(el) in skip:
                continue
            n = el.get("name")
            if n and n not in seen:
                seen.add(n)
                out.append(n)
    return out


def coordinates(model) -> List[str]:
    """Coordinate names, in model order."""
    return _named(_root(model), "Coordinate")


def muscles(model) -> List[str]:
    """Muscle names only — reserve/residual actuators are excluded."""
    return _named(_root(model), *_MUSCLE_TAGS)


def bodies(model) -> List[str]:
    return _named(_root(model), "Body")


def markers(model) -> List[str]:
    return _named(_root(model), "Marker")


def wraps(model) -> Dict[str, str]:
    """``{wrap name: kind}`` for every wrap surface, e.g. ``WrapCylinder``.

    Kind matters because only cylinders and spheres carry a single scalable
    ``<radius>``; an ellipsoid writes three numbers and cannot be grown by one
    factor without changing its shape.
    """
    out: Dict[str, str] = {}
    for el in iter_real(_root(model)):
        tag = getattr(el, "tag", "")
        if isinstance(tag, str) and tag.startswith("Wrap") and el.get("name"):
            out[el.get("name")] = tag
    return out


def options_for(what: str, model) -> List[str]:
    """Resolve a :attr:`~bioscout.model_edit.spec.Param.choices_from` name."""
    table = {
        "coordinates": lambda m: coordinates(m),
        "muscles": lambda m: muscles(m),
        "wraps": lambda m: sorted(wraps(m)),
        "bodies": lambda m: bodies(m),
        "markers": lambda m: markers(m),
    }
    try:
        fn = table[what]
    except KeyError:
        raise KeyError(f"unknown choices_from {what!r}; "
                       f"known: {', '.join(sorted(table))}") from None
    return fn(model)


def summary(model) -> Dict[str, object]:
    """One-line inventory, cheap enough to print before every operation."""
    model = Path(model)
    w = wraps(model)
    scalable = sum(1 for k in w.values() if k in ("WrapCylinder", "WrapSphere"))
    return {
        "model": str(model),
        "name": model.stem,
        "coordinates": len(coordinates(model)),
        "muscles": len(muscles(model)),
        "bodies": len(bodies(model)),
        "markers": len(markers(model)),
        "wraps": len(w),
        "wraps_scalable": scalable,
    }
