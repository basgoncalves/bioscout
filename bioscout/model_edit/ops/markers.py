"""Marker placement and marker-set edits.

``place_markers`` is the standalone-IK registration that replaced ScaleTool's
MarkerPlacer (whose internal IK segfaults on the Catelli and MRI models). It is
exposed as its own op because it is useful on a model that is already scaled --
re-registering markers does not require re-scaling, and re-scaling is the
expensive step.

``drop_markers`` is the fix for a marker that is not on the body: BL and BR are
barbell/rack references bound to ``/ground``, and IK matching a ground-fixed
virtual marker against a bar travelling 1.4 m through a lift is worth hundreds of
millimetres of marker RMS on every loaded trial.
"""
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from ..spec import OpResult, Param, op

__all__ = []


@op("place_markers",
    verb="markers",
    summary="Register model markers to the static pose by standalone IK",
    delegates_to="bioscout.utils.openSim.place_markers_via_ik",
    suffix="_mk",
    notes=("Does not change segment dimensions — only where the virtual markers "
           "sit on the bodies. Safe to run on an already-scaled model, which is "
           "the point: it is the cheap half of scaling."),
    params=[
        Param("static_trc", "path", required=True,
              help="Static trial marker file"),
        Param("marker_set", "path", default=None,
              help="Marker set XML to register against"),
        Param("time_range", "list[float]", default=None, unit="s",
              help="Window of the static trial to average, as two numbers"),
    ])
def place_markers(model, out, *, static_trc, marker_set=None, time_range=None, **_):
    from bioscout.utils import get_openSim
    _os = get_openSim()

    if not os.path.exists(static_trc):
        return OpResult(False, "place_markers", str(model),
                        reason=f"static trial not found: {static_trc}")
    shutil.copy2(str(model), str(out))
    written = _os.place_markers_via_ik(
        str(out), str(static_trc), str(out),
        marker_set_file=str(marker_set) if marker_set else None,
        time_range=list(time_range) if time_range else None,
        work_dir=str(Path(out).parent))
    if not os.path.exists(written or out):
        return OpResult(False, "place_markers", str(model),
                        reason="marker registration produced no model")
    return OpResult(True, "place_markers", str(model), str(out),
                    changed={"registered_to": str(static_trc)},
                    messages=["[model-edit] markers registered to the static pose"])


@op("drop_markers",
    verb="markers",
    summary="Remove markers from a model (pure XML, no OpenSim)",
    needs_opensim=False,
    suffix="_nomk",
    notes=("Removes them from the MODEL. The matching change on the analysis "
           "side is an <IKMarkerTask> with <apply>false</apply> in "
           "setupFiles/IK_task_set.xml, which leaves published models untouched "
           "while still giving a correct marker error — prefer that when the "
           "model is someone else's."),
    params=[
        Param("markers", "list[str]", required=True, choices_from="markers",
              help="Marker names to remove, e.g. BL BR"),
        Param("ground_bound", "bool", default=False,
              help="Also remove every marker parented to ground"),
    ])
def drop_markers(model, out, *, markers, ground_bound=False, **_):
    import xml.etree.ElementTree as ET

    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    tree = ET.parse(str(model), parser=parser)
    root = tree.getroot()
    wanted = set(markers)
    removed = {}

    for parent in root.iter():
        for el in list(parent):
            if getattr(el, "tag", "") != "Marker":
                continue
            name = el.get("name")
            if not name:
                continue
            frame = el.find("socket_parent_frame")
            frame_txt = (frame.text or "").strip() if frame is not None else ""
            is_ground = bool(re.search(r"(^|/)ground$", frame_txt))
            if name in wanted or (ground_bound and is_ground):
                parent.remove(el)
                removed[name] = frame_txt or "?"

    missing = wanted - set(removed)
    if missing and not ground_bound:
        return OpResult(False, "drop_markers", str(model),
                        reason=f"not in the model: {', '.join(sorted(missing))}")
    if not removed:
        return OpResult(False, "drop_markers", str(model),
                        reason="no marker matched — nothing written")
    tree.write(str(out), encoding="utf-8", xml_declaration=True)
    return OpResult(True, "drop_markers", str(model), str(out),
                    changed={k: {"was_on": v} for k, v in removed.items()},
                    messages=[f"[model-edit] removed {len(removed)} marker(s): "
                              f"{', '.join(sorted(removed))}"])
