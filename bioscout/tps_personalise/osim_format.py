"""Read/write helpers that work on **both** OpenSim 3.x and 4.x ``.osim`` XML.

Why this module exists
----------------------
The original pipeline was written against OpenSim 4 models (GPK, Catelli,
Lernagopal — all ``Version 40000``+). ``Rajagopal2015.osim`` as distributed is
``Version 30000``, and the two schemas differ in every place this package
touches:

===================  ==========================  ================================
concept              OpenSim 3.x                 OpenSim 4.x
===================  ==========================  ================================
marker's body        ``<body>femur_r</body>``    ``<socket_parent_frame>/bodyset/femur_r``
path point's body    ``<body>``                  ``<socket_parent_frame>``
joint centre         ``<location_in_parent>``    ``PhysicalOffsetFrame/<translation>``
bone mesh            ``DisplayGeometry/``        ``Mesh/<mesh_file>``
                     ``<geometry_file>``
===================  ==========================  ================================

Rather than force every model through an OpenSim round-trip (which needs the
``opensim`` python package just to *read* a file), the accessors below
normalise the two layouts. Everything here is ``xml.etree`` only.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator, Optional, Tuple

__all__ = [
    "model_version",
    "is_v3",
    "frame_of",
    "mesh_elements",
    "path_point_elements",
    "set_joint_centre",
    "strip_socket",
]


def strip_socket(text: Optional[str]) -> Optional[str]:
    """Normalise ``/bodyset/femur_r`` (v4) or ``femur_r`` (v3) -> ``femur_r``."""
    if text is None:
        return None
    text = text.strip()
    if "/bodyset/" in text:
        text = text.split("/bodyset/")[-1]
    text = text.lstrip("/")
    # v4 offset frames appear as "femur_r_offset" sockets on some components;
    # callers that care about the body strip the suffix themselves.
    return text or None


def model_version(root: ET.Element) -> int:
    """Return the ``OpenSimDocument`` Version integer (0 when absent)."""
    try:
        return int(root.get("Version") or 0)
    except (TypeError, ValueError):
        return 0


def is_v3(root: ET.Element) -> bool:
    """True for OpenSim 3.x documents (Version < 40000)."""
    v = model_version(root)
    return 0 < v < 40000


def frame_of(element: ET.Element) -> Optional[str]:
    """Body/frame name a Marker or PathPoint is attached to, either schema."""
    for tag in ("socket_parent_frame", "body", "socket_parent"):
        el = element.find(tag)
        if el is not None and el.text:
            return strip_socket(el.text)
    return None


def mesh_elements(root: ET.Element) -> Iterator[Tuple[str, str, ET.Element, str]]:
    """Yield ``(body, mesh_name, element, file_tag)`` for every bone mesh.

    ``file_tag`` is the child tag holding the filename (``mesh_file`` on v4,
    ``geometry_file`` on v3) so callers can read or rewrite it uniformly. On v3
    a ``DisplayGeometry`` has no name attribute, so the geometry filename stem
    is used as the mesh name — stable enough to key a rename map on.
    """
    v3 = is_v3(root)
    for body in root.iter("Body"):
        body_name = body.get("name")
        if v3:
            for dg in body.iter("DisplayGeometry"):
                gf = dg.find("geometry_file")
                if gf is None or not gf.text:
                    continue
                name = dg.get("name") or Path(gf.text.strip()).stem
                yield body_name, name, dg, "geometry_file"
        else:
            for mesh in body.iter("Mesh"):
                yield body_name, mesh.get("name"), mesh, "mesh_file"


def path_point_elements(root: ET.Element) -> Iterator[ET.Element]:
    """Yield every muscle path point element, on either schema.

    v4 calls them ``PathPoint``; v3 uses ``PathPoint`` too, but also
    ``ConditionalPathPoint`` and ``MovingPathPoint`` which have no fixed
    ``location`` and must be skipped (a moving point is a function of a
    coordinate — warping its constant would silently corrupt the model).
    """
    for tag in ("PathPoint",):
        for el in root.iter(tag):
            if el.find("location") is not None:
                yield el


def set_joint_centre(joint: ET.Element, offset_name: str, text: str) -> bool:
    """Write a joint-centre translation, on either schema. Returns True if set.

    v4: the ``PhysicalOffsetFrame`` named ``offset_name`` -> ``<translation>``.
    v3: the joint's own ``<location_in_parent>`` (there are no offset frames,
    so ``offset_name`` is only used for the v4 lookup).
    """
    for frame in joint.iter("PhysicalOffsetFrame"):
        if frame.get("name") == offset_name:
            tr = frame.find("translation")
            if tr is not None:
                tr.text = text
                return True
    lip = joint.find("location_in_parent")
    if lip is not None:
        lip.text = text
        return True
    return False
