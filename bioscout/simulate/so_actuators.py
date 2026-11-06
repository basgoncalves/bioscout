"""SO reserve/residual actuators: which source is used, and helpers.

Rule (per iteration, session.yaml ``so_actuators``):
  * set   -> that file's actuators REPLACE the model's non-muscle actuators
             (SO runs on ``<model>_noact.osim`` + the file as force_set_files)
  * unset -> the model's own actuators are used, nothing appended
  * neither has any -> warning (SO would silently push muscles instead)
Pure XML, no opensim import, so scripts can use it too.
"""
import os
import warnings
from xml.etree import ElementTree as ET

ACTUATOR_TAGS = ("CoordinateActuator", "PointActuator", "TorqueActuator",
                 "ActivationCoordinateActuator")


def _objects(root):
    """The <objects> of the model's (or file's) ForceSet, skipping <defaults>."""
    fs = root.find("./Model/ForceSet/objects")
    return fs if fs is not None else root.find("./ForceSet/objects")


def actuator_names(path):
    """Names of the non-muscle actuators in an .osim or a force-set .xml."""
    if not path or not os.path.isfile(path):
        return []
    objs = _objects(ET.parse(path).getroot())
    if objs is None:
        return []
    return [e.get("name") for e in objs if e.tag in ACTUATOR_TAGS]


def extract_actuators(osim_path, out_xml):
    """Write the model's non-muscle actuators as a force-set file."""
    root = ET.parse(osim_path).getroot()
    doc = ET.Element("OpenSimDocument", Version=root.get("Version", "40000"))
    objs = ET.SubElement(ET.SubElement(doc, "ForceSet", name="so_actuators"), "objects")
    for e in _objects(root):
        if e.tag in ACTUATOR_TAGS:
            objs.append(e)
    ET.SubElement(doc[0], "groups")
    ET.indent(doc, space="   ")
    ET.ElementTree(doc).write(out_xml, encoding="UTF-8", xml_declaration=True)
    return out_xml


def stripped_model(osim_path):
    """``<model>_noact.osim`` next to the model (same Geometry), muscles only.
    Rebuilt when missing or older than the source."""
    out = os.path.splitext(osim_path)[0] + "_noact.osim"
    if os.path.isfile(out) and os.path.getmtime(out) >= os.path.getmtime(osim_path):
        return out
    tree = ET.parse(osim_path)
    objs = _objects(tree.getroot())
    for e in [e for e in objs if e.tag in ACTUATOR_TAGS]:
        objs.remove(e)
    tree.write(out, encoding="UTF-8", xml_declaration=True)
    return out


def strip_in_place(osim_path):
    """Remove every non-muscle actuator from ``osim_path`` itself.
    Returns how many were removed. For a model whose SO actuators come from an
    ``so_actuators`` file: the model stays muscles-only and there is ONE place
    (the file) that says which reserves/residuals SO gets."""
    tree = ET.parse(osim_path)
    objs = _objects(tree.getroot())
    gone = [e for e in (objs if objs is not None else []) if e.tag in ACTUATOR_TAGS]
    for e in gone:
        objs.remove(e)
    if gone:
        tree.write(osim_path, encoding="UTF-8", xml_declaration=True)
    return len(gone)


def plan(model_path, actuators_path=None):
    """-> (model_to_run, force_set_file_or_None, note). Warns if no actuators."""
    in_file = actuator_names(actuators_path)
    in_model = actuator_names(model_path)
    if in_file and not in_model:
        # a muscles-only model already: nothing to strip, no _noact copy
        return (model_path, actuators_path,
                f"{len(in_file)} from {actuators_path} (model has none)")
    if in_file:
        return (stripped_model(model_path), actuators_path,
                f"{len(in_file)} from {actuators_path} (replacing "
                f"{len(in_model)} in the model)")
    if actuators_path:
        warnings.warn(f"[SO WARNING] so_actuators file has no actuators or is "
                      f"missing: {actuators_path} -- falling back to the model's")
    if in_model:
        return model_path, None, f"{len(in_model)} from the model itself"
    msg = (f"[SO WARNING] no reserve/residual actuators in the model "
           f"({model_path}) nor in an so_actuators file ({actuators_path}). "
           f"SO will push the muscles to absorb every residual.")
    print(msg)   # once; warnings.warn duplicated it in the log with a traceback line
    return model_path, None, "NONE"


#: pelvis residual actuator -> ID generalised-force column (Rajagopal/gait2392
#: pelvis: tilt about Z, list about X, rotation about Y).
RESIDUAL_ID_COLUMNS = {
    "FX": "pelvis_tx_force", "FY": "pelvis_ty_force", "FZ": "pelvis_tz_force",
    "MX": "pelvis_list_moment", "MY": "pelvis_rotation_moment",
    "MZ": "pelvis_tilt_moment",
}


def percent_spec(value):
    """``so_actuators: percent_40`` -> 40.0; anything else -> None.

    ``percent_XX`` is not a file. It asks for a reserve set built PER TRIAL:
    every reserve's optimal_force is XX % of the peak |ID moment| of its own
    coordinate in THAT trial. A file written once per session cannot do this --
    two trials of one session do not have the same joint moments.
    """
    import re
    m = re.fullmatch(r"\s*percent[_ ]?(\d+(?:\.\d+)?)\s*%?\s*", str(value or ""), re.I)
    return float(m.group(1)) if m else None


def percent_reserves(template_xml, id_sto, percent, out_xml, t0=None, t1=None,
                     floor=1.0):
    """Write ``out_xml`` = ``template_xml`` with each RESERVE at ``percent`` % of
    the trial's peak |ID moment| of its coordinate.

    A reserve is a CoordinateActuator whose name ends in ``_reserve``; its
    coordinate is its ``<coordinate>`` (else the name without the suffix) and
    the moment is the ``<coordinate>_moment`` column of the inverse dynamics
    over [t0, t1]. Reserves named in a ``<!-- percent_fixed: a b -->`` comment
    of the template keep the template's value. Everything else in the template -- pelvis residuals, lumbar
    actuators, control bounds -- is left exactly as written. ``floor`` (N*m)
    keeps an actuator from vanishing on a coordinate that carries no moment.
    Returns ``{actuator: (peak_ID_moment, optimal_force)}``; a reserve whose
    coordinate has no ID column is left at the template's value and reported
    with a peak of None.
    """
    import pandas as pd
    with open(id_sto, encoding="utf-8", errors="replace") as fh:
        skip = next(i for i, ln in enumerate(fh) if ln.strip().lower() == "endheader") + 1
    d = pd.read_csv(id_sto, sep=r"\s+", skiprows=skip)
    if t0 is not None:
        d = d[d["time"] >= t0 - 1e-9]
    if t1 is not None:
        d = d[d["time"] <= t1 + 1e-9]
    # Reserves the template pins at its own value, named in a comment
    #     <!-- percent_fixed: knee_adduction_r_reserve knee_adduction_l_reserve -->
    # (a comment, so OpenSim never sees it). E.g. knee adduction, carried mostly
    # by condyle contact and ligaments, kept at a fixed 50 N*m while every other
    # reserve is XX % of its peak ID moment.
    import re as _re
    with open(template_xml, encoding="utf-8", errors="replace") as fh:
        fixed = {n for m in _re.finditer(r"<!--\s*percent_fixed\s*:(.*?)-->", fh.read(), _re.S)
                 for n in m.group(1).replace(",", " ").split()}
    tree = ET.parse(template_xml)
    objs = _objects(tree.getroot())
    out = {}
    for e in (objs if objs is not None else []):
        name = e.get("name") or ""
        if e.tag != "CoordinateActuator" or not name.endswith("_reserve"):
            continue
        if name in fixed:
            _f = e.findall("optimal_force")
            out[name] = (None, float(_f[0].text) if _f else None)
            continue
        tags = e.findall("optimal_force")
        if not tags:
            continue
        coord = (e.findtext("coordinate") or name[:-len("_reserve")]).strip()
        col = f"{coord}_moment"
        if col not in d.columns or not len(d):
            out[name] = (None, float(tags[0].text))
            continue
        peak = float(d[col].abs().max())
        val = max(float(floor), float(percent) / 100.0 * peak)
        for t in tags:
            t.text = f"{val:.3f}"
        out[name] = (peak, val)
    fs = tree.getroot().find("ForceSet")
    if fs is not None:
        fs.set("name", f"so_actuators_percent_{float(percent):g}")
    os.makedirs(os.path.dirname(os.path.abspath(out_xml)), exist_ok=True)
    tree.write(out_xml, encoding="UTF-8", xml_declaration=True)
    return out


def peak_id_residuals(id_sto, t0=None, t1=None):
    """{actuator: peak |ID residual|} over [t0, t1] of an inverse_dynamics.sto."""
    import pandas as pd
    with open(id_sto, encoding="utf-8", errors="replace") as fh:
        skip = next(i for i, ln in enumerate(fh) if ln.strip().lower() == "endheader") + 1
    d = pd.read_csv(id_sto, sep=r"\s+", skiprows=skip)
    if t0 is not None:
        d = d[d["time"] >= t0 - 1e-9]
    if t1 is not None:
        d = d[d["time"] <= t1 + 1e-9]
    return {a: float(d[c].abs().max()) for a, c in RESIDUAL_ID_COLUMNS.items()
            if c in d.columns and len(d)}


def scale_residuals(actuators_xml, id_sto, t0=None, t1=None, margin=1.0,
                    out_xml=None):
    """Raise each pelvis residual's optimal_force to >= margin x its peak ID
    residual, so control <= 1 can carry the whole residual. Never lowers a
    value. Every <optimal_force> of the actuator is set (some files carry the
    tag twice). Returns {actuator: (old, new)} for the ones changed."""
    peaks = peak_id_residuals(id_sto, t0, t1)
    tree = ET.parse(actuators_xml)
    objs = _objects(tree.getroot())
    changed = {}
    for e in (objs if objs is not None else []):
        name = e.get("name")
        if e.tag not in ACTUATOR_TAGS or name not in peaks:
            continue
        tags = e.findall("optimal_force")
        if not tags:
            continue
        old = float(tags[0].text)
        need = float(__import__("math").ceil(peaks[name] * margin))
        if need > old:
            for t in tags:
                t.text = f"{need:g}"
            changed[name] = (old, need)
    tree.write(out_xml or actuators_xml, encoding="UTF-8", xml_declaration=True)
    return changed


def bound_controls(actuators_xml, id_sto, t0=None, t1=None, margin=1.1, out_xml=None):
    """Every non-muscle actuator to control -1..1 (2026-11-03).

    OpenSim SO with -Inf..Inf controls can diverge at a frame where the optimiser
    does not converge (K2L Gehen_01, 6.43 s: MX 712 kN*m, control 891). With every
    control in -1..1 an actuator can never exceed its optimal_force. An actuator that
    was unbounded (pelvis residuals, lumbar, ...) has its optimal_force raised to
    margin x the peak |ID| of what it actuates if smaller, so it can still carry the
    whole load; actuators that already had finite limits (reserves) keep their
    optimal_force. Returns {name: (old_limits, old_force, new_force)} for the changed."""
    import math
    import pandas as pd
    from bioscout import utils as _u
    d = _u.load_any_data_file(id_sto)
    if t0 is not None and t1 is not None and "time" in d:
        tt = pd.to_numeric(d["time"], errors="coerce")
        d = d[(tt >= t0 - 1e-9) & (tt <= t1 + 1e-9)]
    peak = {c: float(pd.to_numeric(d[c], errors="coerce").abs().max()) for c in d if c != "time"}
    tree = ET.parse(actuators_xml)
    objs = _objects(tree.getroot())
    changed = {}
    for e in (objs if objs is not None else []):
        if e.tag not in ACTUATOR_TAGS:
            continue
        name = e.get("name")
        lo, hi = e.find("min_control"), e.find("max_control")
        old = (lo.text.strip() if lo is not None and lo.text else "-Inf",
               hi.text.strip() if hi is not None and hi.text else "Inf")
        unbounded = any(not math.isfinite(float(v)) for v in old)
        for tag, val in (("min_control", "-1"), ("max_control", "1")):
            x = e.find(tag)
            if x is None:
                x = ET.SubElement(e, tag)
            x.text = val
        tags = e.findall("optimal_force")
        f_old = float(tags[0].text) if tags else None
        f_new = f_old
        if unbounded and tags:
            col = RESIDUAL_ID_COLUMNS.get(name)
            if col is None:
                c = (e.findtext("coordinate") or "").strip()
                col = next((k for k in (c + "_moment", c + "_force") if k in peak), None)
            if col in peak and math.isfinite(peak[col]):
                need = float(math.ceil(peak[col] * margin))
                if need > f_old:
                    f_new = need
                    for t in tags:
                        t.text = f"{need:g}"
        if old != ("-1", "1") or f_new != f_old:
            changed[name] = (old, f_old, f_new)
    tree.write(out_xml or actuators_xml, encoding="UTF-8", xml_declaration=True)
    return changed
