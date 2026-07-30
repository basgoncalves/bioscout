"""Loaders for landmark / marker data.

Consolidates the original ``MRIBoneMarkers`` (3D Slicer JSON) and
``OsimBoneMarkers`` (OpenSim marker XML) classes into plain functions that
return tidy ``pandas`` DataFrames indexed by marker name with ``r/a/s`` columns
(and ``body`` where applicable).

Changes vs original:
  * functions, not classes-with-side-effects,
  * no plotting (visualisation belongs elsewhere),
  * the mm<->m and Slicer-orientation conventions are explicit parameters
    instead of commented-out ``#*1000`` lines.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pandas as pd

_RAS = ["r", "a", "s"]


def load_mri_landmarks(
    path: str | Path,
    apply_orientation: bool = True,
) -> pd.DataFrame:
    """Load bone landmarks from a 3D Slicer ``.mrk.json`` file.

    Slicer stores position and orientation separately; the displayed coordinate
    is ``orientation @ position``. ``apply_orientation`` controls whether that
    multiplication is applied (the original default was True).

    Returns a DataFrame indexed by label with ``r/a/s`` columns.
    """
    path = Path(path)
    with open(path, "r") as fh:
        data = json.load(fh)
    points: dict[str, list[float]] = {}
    for item in data["markups"][0]["controlPoints"]:
        pos = np.asarray(item["position"], dtype=float)
        if apply_orientation:
            R = np.asarray(item["orientation"], dtype=float).reshape(3, 3)
            pos = R @ pos
        points[item["label"]] = pos.tolist()
    return pd.DataFrame.from_dict(points, orient="index", columns=_RAS)


def load_osim_bone_markers(path: str | Path) -> pd.DataFrame:
    """Parse OpenSim bone-marker XML into a DataFrame.

    Returns columns ``body``, ``r``, ``a``, ``s`` indexed by marker name.
    Equivalent to the original ``OsimBoneMarkers.data_frame``.

    Works on OpenSim 3.x models (``<body>``) as well as 4.x
    (``<socket_parent_frame>``), and on a standalone ``MarkerSet`` XML.
    """
    from .osim_format import frame_of

    path = Path(path)
    root = ET.parse(path).getroot()
    rows = []
    for marker in root.iter("Marker"):
        name = marker.attrib.get("name")
        loc_el = marker.find("location")
        if name is None or loc_el is None or not loc_el.text:
            continue
        loc = [float(v) for v in loc_el.text.split()]
        rows.append({
            "name": name, "body": frame_of(marker),
            "r": loc[0], "a": loc[1], "s": loc[2],
        })
    if not rows:
        raise ValueError(f"no markers with a <location> found in {path}")
    return pd.DataFrame(rows).set_index("name")


def _strip_socket(text: str | None) -> str | None:
    """Normalise a socket path like ``/bodyset/femur_r`` -> ``femur_r``."""
    from .osim_format import strip_socket
    return strip_socket(text)


def match_by_name(
    osim_df: pd.DataFrame, mri_df: pd.DataFrame
) -> tuple[list[str], list[str], list[str]]:
    """Return ``(matched, only_in_mri, only_in_osim)`` marker-name lists."""
    osim_names, mri_names = set(osim_df.index), set(mri_df.index)
    matched = [n for n in mri_df.index if n in osim_names]
    only_in_mri = [n for n in mri_df.index if n not in osim_names]
    only_in_osim = [n for n in osim_df.index if n not in mri_names]
    return matched, only_in_mri, only_in_osim


def split_by_body(df: pd.DataFrame, names: list[str] | None = None) -> dict[str, pd.DataFrame]:
    """Group a marker DataFrame (with a ``body`` column) into ``{body: df}``."""
    if names is not None:
        df = df.loc[names]
    return {b: g[_RAS] for b, g in df.groupby("body")}
