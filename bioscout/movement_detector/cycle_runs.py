"""cycle_runs — turn a multi-cycle capture into one runnable folder per cycle.

A capture is one recording; a CYCLE is one thing to simulate. FAIS 073's
``walking1`` is 85 s, twelve walkways and forty-three gait cycles, and the
whole pipeline below ``2_experimental`` — inverse dynamics, static
optimisation, CEINMS — takes exactly one contiguous window with one
plate-to-body mapping. It therefore cannot run on the capture. It can run on a
cycle.

This module is the seam between the two. It reads the cycles
:func:`bioscout.movement_detector.gait_cycles` found and writes, per cycle::

    3_iterations/<iteration>/<trial>_r7/
        grf.mot     the capture's force, trimmed to this cycle
        GRF.xml     ExternalLoads for THIS cycle's plate-to-foot mapping
        cycle.yaml  what the folder is: window, leg, events, plates

Why the force is rewritten rather than referenced
-------------------------------------------------
Over a walkway every plate takes both feet, so "plate 2 is the left foot" is
a statement about one footfall, not about a trial: on walking1 plate 2 carries
four left and nine right footfalls. Worse, inside a single 1.1 s cycle a plate
is hit by BOTH feet on 17 of the 43 cycles — the trailing foot is still
rolling off as the leading foot lands — and no ExternalLoads file can say
that, because ``applied_to_body`` is one body for the whole file.

The fix is to give such a plate two columns in this cycle's own ``grf.mot``,
one per foot, each carrying the plate's force only over the frames that
foot was on it and zero elsewhere. The mapping is then one plate-column to one
body, which is what OpenSim can express, and nothing is invented: the split
comes from the per-frame centre-of-pressure assignment
:func:`bioscout.movement_detector.contact_feet` already makes.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Sequence

import numpy as np

from .mocap import MocapConfig, contact_feet, gait_cycles, read_grf

#: Force/moment suffixes an OpenSim ExternalForce reads, per plate.
_SUFFIX = ("vx", "vy", "vz", "px", "py", "pz")
_MOMENT = ("mx", "my", "mz")

#: How much of the capture to keep either side of a cycle. ID differentiates
#: and CEINMS filters; both need a run-up, and a window cut exactly at the
#: cycle boundary makes the first and last frames of every result unusable.
DEFAULT_PAD_S = 0.10


def _plate_ids(cols) -> List[str]:
    return sorted({c.split("_")[2] for c in cols
                   if c.startswith("ground_force_") and c.endswith("_vy")},
                  key=lambda p: (len(p), p))


def _cycle_plate_map(contacts: List[dict], t0: float, t1: float
                     ) -> Dict[str, Dict[str, List[dict]]]:
    """``{plate: {"l": [contact...], "r": [...]}}`` for one cycle's window."""
    out: Dict[str, Dict[str, List[dict]]] = {}
    for c in contacts:
        if c["t_off"] <= t0 or c["t_on"] >= t1:
            continue
        if c.get("side") not in ("l", "r"):
            continue
        for p in (c.get("plates") or [c["plate"]]):
            out.setdefault(p, {}).setdefault(c["side"], []).append(c)
    return out


def write_cycle_files(exp_dir: str, out_dir: str, cycle: dict,
                      contacts: Optional[List[dict]] = None,
                      body_mass: Optional[float] = None,
                      cfg: Optional[MocapConfig] = None,
                      pad_s: float = DEFAULT_PAD_S,
                      right_foot_body: str = "calcn_r",
                      left_foot_body: str = "calcn_l",
                      lowpass_cutoff: float = 6.0) -> Dict[str, str]:
    """Write ``grf.mot`` + ``GRF.xml`` + ``cycle.yaml`` for ONE cycle.

    Returns ``{"dir", "grf_mot", "grf_xml", "cycle_yaml"}``. The plate-to-foot
    mapping is decided inside the cycle's own window and nowhere else.
    """
    import yaml as _yaml

    cfg = cfg or MocapConfig()
    if contacts is None:
        contacts = contact_feet(exp_dir, body_mass, cfg)
    gm = os.path.join(exp_dir, "grf.mot")
    gt, gcols = read_grf(gm)
    if not gt.size:
        raise FileNotFoundError(f"{gm}: no force data to cut a cycle from")

    t0, t1 = float(cycle["time_range"][0]), float(cycle["time_range"][1])
    w0, w1 = t0 - pad_s, t1 + pad_s
    sel = (gt >= w0) & (gt <= w1)
    if sel.sum() < 2:
        raise ValueError(f"{cycle['name']}: window {w0:.3f}-{w1:.3f}s holds "
                         f"{int(sel.sum())} force frames")

    _map = _cycle_plate_map(contacts, t0, t1)
    _bodies = {"l": left_foot_body, "r": right_foot_body}
    # Force that reaches no foot is force that vanished from the cycle. It
    # should be a rounding error — every contact was already grown out to 1%
    # of body weight — but "should be" is not a measurement, so it is measured
    # and written into cycle.yaml. A cycle that quietly lost a tenth of its
    # impulse would produce a plausible, wrong joint moment.
    _seen_n = _kept_n = 0.0

    # --- build this cycle's columns -------------------------------------
    cols: Dict[str, np.ndarray] = {}
    forces: List[dict] = []          # one ExternalForce per entry
    notes: List[str] = []
    for pid in _plate_ids(gcols):
        sides = _map.get(f"ground_force_{pid}") or {}
        if not sides:
            # Not touched during this cycle. An ExternalForce carrying ~0 N
            # and an undefined centre of pressure is a phantom load, so the
            # plate is left out rather than parked on a foot.
            continue
        _shared = len(sides) > 1
        for sd, cs in sides.items():
            # Which frames of this plate belong to THIS foot. One contact per
            # foot per cycle in the ordinary case; the shared plate is where
            # this matters.
            _own = np.zeros(gt.size, bool)
            for c in cs:
                _own |= (gt >= c["t_on"]) & (gt <= c["t_off"])
            _tag = f"{pid}{sd}" if _shared else pid
            for _sfx in _SUFFIX:
                _src = gcols.get(f"ground_force_{pid}_{_sfx}")
                if _src is None:
                    continue
                _v = np.where(_own, np.nan_to_num(_src), 0.0)
                if _sfx == "vy":
                    _kept_n += float(np.nansum(np.abs(_v[sel])))
                cols[f"ground_force_{_tag}_{_sfx}"] = _v[sel]
            for _sfx in _MOMENT:
                _src = gcols.get(f"ground_moment_{pid}_{_sfx}")
                if _src is None:
                    continue
                _v = np.where(_own, np.nan_to_num(_src), 0.0)
                cols[f"ground_moment_{_tag}_{_sfx}"] = _v[sel]
            forces.append({"name": f"grf_{_tag}_{sd}",
                           "body": _bodies[sd],
                           "force_id": f"ground_force_{_tag}_v",
                           "point_id": f"ground_force_{_tag}_p",
                           "torque_id": (f"ground_moment_{_tag}_m"
                                         if any(k.startswith(
                                             f"ground_moment_{_tag}_")
                                             for k in cols) else "")})
            if _shared:
                notes.append(
                    f"plate {pid} carried BOTH feet inside this cycle; its "
                    f"{sd.upper()} share is column ground_force_{_tag}_v")

    for _pid in _plate_ids(gcols):
        _fy = gcols.get(f"ground_force_{_pid}_vy")
        if _fy is not None:
            _seen_n += float(np.nansum(np.abs(np.nan_to_num(_fy)[sel])))
    _kept = (_kept_n / _seen_n) if _seen_n > 0 else 1.0

    if not forces:
        raise ValueError(f"{cycle['name']}: no plate carried a foot in "
                         f"{t0:.3f}-{t1:.3f}s — nothing to apply")

    os.makedirs(out_dir, exist_ok=True)
    _mot = os.path.join(out_dir, "grf.mot")
    _write_mot(_mot, gt[sel], cols, name=cycle["name"])

    _xml = os.path.join(out_dir, "GRF.xml")
    _write_external_loads(_xml, forces, datafile="grf.mot",
                          lowpass_cutoff=lowpass_cutoff)

    _doc = dict(cycle)
    _doc["trial"] = os.path.basename(os.path.normpath(exp_dir))
    _doc["window"] = [round(float(gt[sel][0]), 4), round(float(gt[sel][-1]), 4)]
    _doc["pad_s"] = pad_s
    _doc["external_loads"] = [{"name": f["name"], "applied_to_body": f["body"],
                               "force_identifier": f["force_id"]}
                              for f in forces]
    _doc["force_kept_frac"] = round(float(_kept), 4)
    if _kept < 0.98:
        notes.append(f"{(1 - _kept) * 100:.1f}% of the vertical impulse in "
                     f"this window sat on a plate no foot was assigned to and "
                     f"is NOT in this file")
    if notes:
        _doc["notes"] = notes
    _cy = os.path.join(out_dir, "cycle.yaml")
    with open(_cy, "w", encoding="utf-8") as fh:
        _yaml.safe_dump(_doc, fh, sort_keys=False, default_flow_style=False,
                        allow_unicode=True)
    return {"dir": out_dir, "grf_mot": _mot, "grf_xml": _xml, "cycle_yaml": _cy}


def _write_mot(path: str, time: np.ndarray, cols: Dict[str, np.ndarray],
               name: str = "grf") -> str:
    """An OpenSim storage file, columns in the order they were built."""
    keys = list(cols)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"{name}\nversion=1\nnRows={len(time)}\n"
                 f"nColumns={len(keys) + 1}\ninDegrees=no\nendheader\n")
        fh.write("time\t" + "\t".join(keys) + "\n")
        for i, t in enumerate(time):
            fh.write(f"{t:.8f}\t"
                     + "\t".join(f"{float(cols[k][i]):.8f}" for k in keys)
                     + "\n")
    return path


def _write_external_loads(path: str, forces: Sequence[dict], datafile: str,
                          lowpass_cutoff: float = 6.0) -> str:
    import xml.etree.ElementTree as ET
    from xml.dom import minidom

    root = ET.Element("OpenSimDocument"); root.set("Version", "40000")
    el = ET.SubElement(root, "ExternalLoads"); el.set("name", "externalloads")
    objs = ET.SubElement(el, "objects")
    for f in forces:
        ef = ET.SubElement(objs, "ExternalForce"); ef.set("name", f["name"])
        ET.SubElement(ef, "applied_to_body").text = f["body"]
        ET.SubElement(ef, "force_expressed_in_body").text = "ground"
        ET.SubElement(ef, "point_expressed_in_body").text = "ground"
        ET.SubElement(ef, "force_identifier").text = f["force_id"]
        ET.SubElement(ef, "point_identifier").text = f["point_id"]
        ET.SubElement(ef, "torque_identifier").text = f.get("torque_id", "")
        ET.SubElement(ef, "data_source_name").text = ""
    ET.SubElement(el, "groups")
    ET.SubElement(el, "datafile").text = datafile
    ET.SubElement(el, "external_loads_model_kinematics_file").text = ""
    ET.SubElement(el, "lowpass_cutoff_frequency_for_load_kinematics").text = \
        str(lowpass_cutoff)
    _s = minidom.parseString(ET.tostring(root)).toprettyxml(indent="   ")
    _s = "\n".join(l for l in _s.splitlines() if l.strip())
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(_s)
    return path


def prepare_cycle_runs(exp_dir: str, out_root: str,
                       body_mass: Optional[float] = None,
                       cfg: Optional[MocapConfig] = None,
                       cycles: Optional[List[dict]] = None,
                       pad_s: float = DEFAULT_PAD_S,
                       quiet: bool = False, **kw) -> List[dict]:
    """One run folder per gait cycle of ``exp_dir``, under ``out_root``.

        prepare_cycle_runs("…/2_experimental/walking1",
                           "…/3_iterations/rajagopal_fai")
        # -> …/3_iterations/rajagopal_fai/walking1_l1/{grf.mot,GRF.xml,cycle.yaml}

    Returns one dict per cycle written; a cycle that cannot be written (no
    plate under either foot in its window) is reported and skipped rather than
    written wrong.
    """
    cfg = cfg or MocapConfig()
    if cycles is None:
        cycles = gait_cycles(exp_dir, body_mass, cfg)
    if not cycles:
        if not quiet:
            print(f"[cycles] {os.path.basename(exp_dir)}: no gait cycles — "
                  f"nothing to split")
        return []
    contacts = contact_feet(exp_dir, body_mass, cfg)
    out, skipped = [], []
    for cy in cycles:
        _d = os.path.join(out_root, cy["name"])
        try:
            _r = write_cycle_files(exp_dir, _d, cy, contacts=contacts,
                                   body_mass=body_mass, cfg=cfg, pad_s=pad_s,
                                   **kw)
        except Exception as e:
            skipped.append((cy["name"], f"{type(e).__name__}: {e}"))
            continue
        _r["cycle"] = cy
        out.append(_r)
    if not quiet:
        _sh = sum(1 for r in out
                  if any("BOTH feet" in n for n in
                         (r["cycle"].get("notes") or [])))
        print(f"[cycles] {os.path.basename(os.path.normpath(exp_dir))}: "
              f"wrote {len(out)} cycle run folder(s) under {out_root}")
        for _n, _why in skipped:
            print(f"[cycles]   skipped {_n}: {_why}")
    return out
