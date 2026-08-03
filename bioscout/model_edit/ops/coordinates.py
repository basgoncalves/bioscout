"""Coordinate ranges and locking.

``set_range`` is the op behind "the generic model will not let the athlete get
that deep". It takes DEGREES, because every range you will ever read off a
figure, a paper or an IK output is in degrees, while ``.osim`` and
``edit_model_range_coordinates`` are in radians -- a units mismatch that turns a
138 deg hip into a 138 rad one with no error.

It also refuses to SHRINK a range by default. Narrowing a bound silently clips
motion the athlete performed, which shows up much later as a kinematic
difference between models rather than as an error.
"""
from __future__ import annotations

import math
import os
import re

from ..spec import OpResult, Param, op

__all__ = []

_COORD_BLOCK = r'(<Coordinate\s+name="{name}"[^>]*>)(.*?)(</Coordinate>)'


@op("set_range",
    verb="coordinates",
    summary="Widen a coordinate's range of motion (degrees)",
    delegates_to="text surgery on <range>, same contract as "
                 "bioscout.utils.openSim.edit_model_range_coordinates",
    needs_opensim=False,
    suffix="_rom",
    notes=("Degrees in, radians written. Text surgery rather than an OpenSim "
           "round-trip so every untouched byte of the model stays identical — "
           "re-serialising a model to change two numbers rewrites float "
           "precision across the whole file and makes any later diff useless."),
    params=[
        Param("coordinate", "str", required=True, choices_from="coordinates",
              help="Coordinate to edit, e.g. hip_flexion_r"),
        Param("lo", "float", default=None, unit="deg",
              help="New lower bound. Omit to leave it alone."),
        Param("hi", "float", default=None, unit="deg",
              help="New upper bound. Omit to leave it alone."),
        Param("mirror", "bool", default=True,
              help="Apply the same range to the _l/_r twin, so the model stays "
                   "bilaterally symmetric"),
        Param("allow_shrink", "bool", default=False,
              help="Permit narrowing a bound (off by default — narrowing clips "
                   "motion the athlete actually performed)"),
    ])
def set_range(model, out, *, coordinate, lo=None, hi=None, mirror=True,
              allow_shrink=False, **_):
    if lo is None and hi is None:
        return OpResult(False, "set_range", str(model),
                        reason="give lo= and/or hi= in degrees")

    with open(str(model), "r", encoding="utf-8", errors="replace",
              newline="") as fh:
        txt = fh.read()

    names = [coordinate]
    if mirror and coordinate[-2:] in ("_r", "_l"):
        twin = coordinate[:-2] + ("_l" if coordinate.endswith("_r") else "_r")
        if re.search(_COORD_BLOCK.format(name=re.escape(twin)), txt, re.S):
            names.append(twin)

    changed, messages = {}, []
    for name in names:
        m = re.search(_COORD_BLOCK.format(name=re.escape(name)), txt, re.S)
        if not m:
            return OpResult(False, "set_range", str(model),
                            reason=f"coordinate {name!r} not found in the model")
        head, body, tail = m.groups()
        rm = re.search(r'(<range>)([^<]*)(</range>)', body)
        if not rm:
            return OpResult(False, "set_range", str(model),
                            reason=f"{name} has no <range> element")
        old_lo, old_hi = (float(x) for x in rm.group(2).split())
        new_lo = math.radians(lo) if lo is not None else old_lo
        new_hi = math.radians(hi) if hi is not None else old_hi
        if not allow_shrink:
            new_lo, new_hi = min(new_lo, old_lo), max(new_hi, old_hi)
        if abs(new_lo - old_lo) < 1e-9 and abs(new_hi - old_hi) < 1e-9:
            messages.append(f"[model-edit] {name}: already "
                            f"[{math.degrees(old_lo):.1f}, {math.degrees(old_hi):.1f}] deg")
            continue
        new_body = body[:rm.start()] + f"{rm.group(1)}{new_lo!r} {new_hi!r}{rm.group(3)}" \
            + body[rm.end():]
        txt = txt[:m.start()] + head + new_body + tail + txt[m.end():]
        changed[name] = {
            "old_deg": [round(math.degrees(old_lo), 3), round(math.degrees(old_hi), 3)],
            "new_deg": [round(math.degrees(new_lo), 3), round(math.degrees(new_hi), 3)],
        }
        messages.append(
            f"[model-edit] {name}: [{math.degrees(old_lo):.1f}, {math.degrees(old_hi):.1f}]"
            f" -> [{math.degrees(new_lo):.1f}, {math.degrees(new_hi):.1f}] deg")

    if not changed:
        return OpResult(False, "set_range", str(model),
                        reason="nothing to change (use allow_shrink to narrow a bound)",
                        messages=messages)
    with open(str(out), "w", encoding="utf-8", newline="") as f:
        f.write(txt)
    return OpResult(True, "set_range", str(model), str(out),
                    changed=changed, messages=messages)


@op("lock",
    verb="coordinates",
    summary="Lock or unlock coordinates",
    delegates_to="bioscout.utils.openSim.lock_model_coordinates",
    suffix="_lock",
    params=[
        Param("coordinates", "list[str]", required=True, choices_from="coordinates",
              help="Coordinates to lock (or unlock)"),
        Param("unlock", "bool", default=False,
              help="Unlock instead of lock"),
    ])
def lock(model, out, *, coordinates, unlock=False, **_):
    from bioscout.utils import get_openSim
    _os = get_openSim()

    _os.lock_model_coordinates(str(model), coordinates_to_lock=list(coordinates),
                               save_path=str(out), unlock=bool(unlock))
    if not os.path.exists(out):
        return OpResult(False, "lock", str(model), reason="no model written")
    verb = "unlocked" if unlock else "locked"
    return OpResult(True, "lock", str(model), str(out),
                    changed={c: verb for c in coordinates},
                    messages=[f"[model-edit] {verb} {len(coordinates)} coordinate(s)"])
