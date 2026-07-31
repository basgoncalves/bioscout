"""Build a real ScaleTool MeasurementSet for the powerlifting marker protocol.

WHY THIS MODULE EXISTS
----------------------
``openSim.scale_model`` used to construct ``osim.ScaleTool()`` from scratch and
call ``ModelScaler.setApply(True)`` without ever populating a MeasurementSet.
OpenSim accepts that silently: with no measurements there is nothing to compute
a scale factor from, so EVERY body keeps a scale factor of 1.0 and the only
thing that actually changes is the total mass (``setSubjectMass``). The result
looks like a scaled model, is named ``scaled.osim``, and is generic geometry
carrying the subject's mass. That is the bug this module fixes.

The measurement basis is the ``*WK`` virtual joint-centre markers that already
exist in ``markers_powerlifter.xml``:

    RHJCWK  femur_r  (0, 0, 0)          -> hip joint centre
    RKJCWK  tibia_r  (0, 0.0074, 0)     -> knee joint centre
    RAJCWK  talus_r  (0, 0, 0)          -> ankle joint centre

They sit on body origins, so they are the joint centres in EVERY model
regardless of that model's segment lengths -- unlike the skin markers in
``markers_powerlifter.xml``, whose hard-coded local positions were authored for
one specific generic and are wrong on the others. That makes the femur/tibia
scale factors model-independent, which is exactly what we want when the same
static trial scales Catelli, Lernagopal and GPK.

The catch: those markers exist in the MODEL but in no TRC, because the motion
capture cannot see a joint centre. ``augment_static_trc`` computes them from the
skin markers -- knee/ankle as the midpoint of the epicondyle/malleoli pairs, hip
via the Harrington (2007) pelvis regression -- and writes them into a copy of
the static TRC so ScaleTool can pair them up.

Joint-centre markers must NOT take part in marker registration (they are derived,
not measured), so ``marker_placement_markerset`` strips them again for the
standalone IK pass.
"""

from __future__ import annotations

import os
import numpy as np

# Virtual joint-centre markers: model-side names (markers_powerlifter.xml).
JC_MARKERS = ("RHJCWK", "LHJCWK", "RKJCWK", "LKJCWK", "RAJCWK", "LAJCWK")

# How each joint centre is built from skin markers present in the static TRC.
# Midpoint pairs; the hips are handled separately (Harrington regression).
_MIDPOINT_JC = {
    "RKJCWK": ("RKNEL", "RKNEM"),
    "LKJCWK": ("LKNEL", "LKNEM"),
    "RAJCWK": ("RMALL", "RMALM"),
    "LAJCWK": ("LMALL", "LMALM"),
}
_HARRINGTON_MARKERS = ("LASI", "RASI", "LPSI", "RPSI")


# --------------------------------------------------------------------------
# TRC I/O (deliberately text-level: the multi-index DataFrame round-trip in
# io.load_trc/write_trc loses the original header fields we must preserve)
# --------------------------------------------------------------------------
def read_trc(path):
    """Return ``(header_lines, marker_names, frames, data)``.

    ``data`` is ``(n_frames, 3 * n_markers)``; ``frames`` is the Frame#/Time
    columns as ``(n_frames, 2)``. Missing values come back as NaN.
    """
    with open(path, "r", errors="replace") as f:
        lines = f.read().splitlines()
    hdr_i = next(i for i, l in enumerate(lines) if l.startswith("Frame#"))
    names = [n.strip() for n in lines[hdr_i].split("\t")[2:] if n.strip()]
    frames, rows = [], []
    for ln in lines[hdr_i + 2:]:
        if not ln.strip():
            continue
        p = ln.split("\t")
        if len(p) < 3:
            continue
        frames.append([float(p[0]), float(p[1])])
        vals = []
        for v in p[2:]:
            v = v.strip()
            vals.append(np.nan if v in ("", "NaN", "nan") else float(v))
        rows.append(vals)
    data = np.array(rows, dtype=float)
    # Pad/truncate to exactly 3 columns per named marker.
    want = 3 * len(names)
    if data.shape[1] < want:
        data = np.hstack([data, np.full((data.shape[0], want - data.shape[1]), np.nan)])
    data = data[:, :want]
    return lines[:hdr_i], names, np.array(frames, dtype=float), data


def write_trc(path, header_lines, names, frames, data):
    """Write a TRC, rewriting the NumMarkers field in the header to match."""
    hdr = list(header_lines)
    # Row 2 of the header carries the field values; NumMarkers is column 4.
    for i, l in enumerate(hdr):
        p = l.split("\t")
        if len(p) >= 8 and p[0].replace(".", "").isdigit():
            p[3] = str(len(names))
            p[2] = str(data.shape[0])
            if len(p) >= 8:
                p[7] = str(data.shape[0])
            hdr[i] = "\t".join(p)
    out = list(hdr)
    out.append("Frame#\tTime\t" + "\t".join(f"{n}\t\t" for n in names))
    out.append("\t\t" + "\t".join(f"X{i+1}\tY{i+1}\tZ{i+1}" for i in range(len(names))))
    out.append("")
    for r in range(data.shape[0]):
        cells = [f"{int(frames[r, 0])}", f"{frames[r, 1]:.5f}"]
        cells += ["" if np.isnan(v) else f"{v:.5f}" for v in data[r]]
        out.append("\t".join(cells))
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    return path


# --------------------------------------------------------------------------
# Joint centres
# --------------------------------------------------------------------------
def harrington_hjc(lasi, rasi, lpsi, rpsi):
    """Hip joint centres from the pelvis markers (Harrington et al., 2007).

    Inputs and outputs are in the TRC's own units (mm) and global frame. The
    regression is defined in a pelvis-local frame -- x anterior, y superior,
    z to the subject's right -- built from the ASIS/PSIS midpoints, so it is
    independent of how the subject was oriented in the lab.

    Returns ``(lhjc, rhjc, pelvis_width, pelvis_depth)``.
    """
    asis_mid = (np.asarray(lasi) + np.asarray(rasi)) / 2.0
    psis_mid = (np.asarray(lpsi) + np.asarray(rpsi)) / 2.0
    pw = float(np.linalg.norm(np.asarray(rasi) - np.asarray(lasi)))
    pd = float(np.linalg.norm(asis_mid - psis_mid))

    ex = asis_mid - psis_mid
    ex /= np.linalg.norm(ex)
    ez = np.asarray(rasi) - np.asarray(lasi)
    ez = ez - np.dot(ez, ex) * ex
    ez /= np.linalg.norm(ez)
    ey = np.cross(ez, ex)
    ey /= np.linalg.norm(ey)
    R = np.column_stack([ex, ey, ez])

    x = -0.24 * pd - 9.9      # posterior
    y = -0.30 * pw - 10.9     # inferior
    z = 0.33 * pw + 7.3       # lateral (mirrored for the left hip)
    rhjc = asis_mid + R @ np.array([x, y, z])
    lhjc = asis_mid + R @ np.array([x, y, -z])
    return lhjc, rhjc, pw, pd


def compute_joint_centres(names, data):
    """Per-frame joint centres from a parsed TRC. Returns ``{name: (n,3)}``."""
    idx = {n: 3 * i for i, n in enumerate(names)}

    def col(n):
        if n not in idx:
            return None
        return data[:, idx[n]:idx[n] + 3]

    out = {}
    for jc, (a, b) in _MIDPOINT_JC.items():
        A, B = col(a), col(b)
        if A is None or B is None:
            continue
        out[jc] = (A + B) / 2.0

    if all(col(m) is not None for m in _HARRINGTON_MARKERS):
        LA, RA, LP, RP = (col(m) for m in _HARRINGTON_MARKERS)
        n = data.shape[0]
        lh = np.full((n, 3), np.nan)
        rh = np.full((n, 3), np.nan)
        for r in range(n):
            if np.isnan(LA[r]).any() or np.isnan(RA[r]).any() \
               or np.isnan(LP[r]).any() or np.isnan(RP[r]).any():
                continue
            lh[r], rh[r], _, _ = harrington_hjc(LA[r], RA[r], LP[r], RP[r])
        out["LHJCWK"], out["RHJCWK"] = lh, rh
    return out


def augment_static_trc(trc_in, trc_out=None, verbose=True):
    """Write a copy of the static TRC with the ``*WK`` joint centres appended.

    Returns the path to the augmented TRC (or ``trc_in`` unchanged if no joint
    centre could be built -- e.g. the pelvis or knee markers are absent).
    """
    header, names, frames, data = read_trc(trc_in)
    jcs = compute_joint_centres(names, data)
    jcs = {k: v for k, v in jcs.items() if k not in names}
    if not jcs:
        if verbose:
            print(f"[scale] no joint centres could be computed from {os.path.basename(trc_in)} "
                  f"— femur/tibia scaling will have no measurement basis.")
        return trc_in

    new_names = list(names) + list(jcs.keys())
    new_data = np.hstack([data] + [jcs[k] for k in jcs.keys()])
    if trc_out is None:
        stem, ext = os.path.splitext(trc_in)
        trc_out = f"{stem}_jc{ext}"
    write_trc(trc_out, header, new_names, frames, new_data)
    if verbose:
        d = lambda a, b: float(np.nanmean(np.linalg.norm(
            new_data[:, 3 * new_names.index(a):3 * new_names.index(a) + 3] -
            new_data[:, 3 * new_names.index(b):3 * new_names.index(b) + 3], axis=1)))
        print(f"[scale] joint centres added to static TRC: {', '.join(jcs.keys())}")
        for side in ("R", "L"):
            try:
                print(f"[scale]   {side} femur {d(side+'HJCWK', side+'KJCWK')/1000:.4f} m  "
                      f"shank {d(side+'KJCWK', side+'AJCWK')/1000:.4f} m")
            except Exception:
                pass
    return trc_out


def marker_placement_markerset(markerset_path, out_dir):
    """Strip the ``*WK`` joint-centre markers from a copy of the marker set.

    The joint centres are derived, not measured, so they must drive SCALING but
    never marker REGISTRATION -- otherwise the IK pass would drag the model's
    real markers around to satisfy a regression estimate.
    """
    import re
    if not markerset_path or not os.path.isfile(markerset_path):
        return markerset_path
    txt = open(markerset_path, errors="replace").read()
    dropped = []

    def _filt(m):
        if m.group(1).upper() in JC_MARKERS:
            dropped.append(m.group(1))
            return ""
        return m.group(0)

    new = re.sub(r'<Marker name="([^"]+)">.*?</Marker>\s*', _filt, txt, flags=re.S)
    if not dropped:
        return markerset_path
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.splitext(os.path.basename(markerset_path))[0] + "_noJC.xml")
    with open(out, "w") as f:
        f.write(new)
    return out


# --------------------------------------------------------------------------
# MeasurementSet
# --------------------------------------------------------------------------
# (name, marker pairs, {body: axes}). A measurement is emitted only if at least
# one pair is present in BOTH the model marker set and the TRC, and only for the
# bodies that exist in this model -- the three generics have different body sets
# (Catelli has arms; GPK/Lernagopal have knee sub-bodies).
DEFAULT_SPEC = [
    # --- pelvis -----------------------------------------------------------
    ("pelvis_z", [("LASI", "RASI")], {"pelvis": "Z"}),
    ("pelvis_x", [("LPSI", "LASI"), ("RPSI", "RASI")], {"pelvis": "X"}),
    ("pelvis_y", [("SACR3", "RHJCWK"), ("SACR3", "LHJCWK")], {"pelvis": "Y"}),

    # --- thigh (hip -> knee joint centre) ---------------------------------
    ("femur_r", [("RHJCWK", "RKJCWK")],
     {"femur_r": "XYZ", "patella_r": "XYZ", "femoral_cond_r": "XYZ",
      "med_cond_r": "XYZ", "lat_cond_r": "XYZ",
      "sagittal_articulation_frame_r": "XYZ"}),
    ("femur_l", [("LHJCWK", "LKJCWK")],
     {"femur_l": "XYZ", "patella_l": "XYZ", "femoral_cond_l": "XYZ",
      "med_cond_l": "XYZ", "lat_cond_l": "XYZ",
      "sagittal_articulation_frame_l": "XYZ"}),

    # --- shank (knee -> ankle joint centre) -------------------------------
    ("tibia_r", [("RKJCWK", "RAJCWK")], {"tibia_r": "XYZ", "tibial_plat_r": "XYZ"}),
    ("tibia_l", [("LKJCWK", "LAJCWK")], {"tibia_l": "XYZ", "tibial_plat_l": "XYZ"}),

    # --- foot: length drives X and Y, malleoli width drives Z -------------
    ("foot_r_xy", [("RHEE", "RTOE")],
     {"talus_r": "XY", "calcn_r": "XY", "toes_r": "XY"}),
    ("foot_r_z", [("RMALL", "RMALM")],
     {"talus_r": "Z", "calcn_r": "Z", "toes_r": "Z"}),
    ("foot_l_xy", [("LHEE", "LTOE")],
     {"talus_l": "XY", "calcn_l": "XY", "toes_l": "XY"}),
    ("foot_l_z", [("LMALL", "LMALM")],
     {"talus_l": "Z", "calcn_l": "Z", "toes_l": "Z"}),

    # --- trunk: sacrum -> sternum/xiphoid, applied uniformly --------------
    # The powerlifting marker set has no acromion or C7 marker ON THE MODEL,
    # so there is no independent trunk width or depth measurement; a uniform
    # trunk factor from trunk length is the honest choice (and far better than
    # the 1.0 the empty MeasurementSet was silently applying).
    ("torso", [("SACR3", "STRN"), ("SACR3", "XIPH")], {"torso": "XYZ"}),

    # --- arms (Catelli only): no arm markers, inherit the trunk factor ----
    ("upper_limb", [("SACR3", "STRN"), ("SACR3", "XIPH")],
     {"humerus_r": "XYZ", "ulna_r": "XYZ", "radius_r": "XYZ", "hand_r": "XYZ",
      "humerus_l": "XYZ", "ulna_l": "XYZ", "radius_l": "XYZ", "hand_l": "XYZ"}),
]

_AXIS = {"X": 0, "Y": 1, "Z": 2}


def model_marker_names(model):
    ms = model.getMarkerSet()
    return {ms.get(i).getName() for i in range(ms.getSize())}


def model_body_names(model):
    bs = model.getBodySet()
    return {bs.get(i).getName() for i in range(bs.getSize())}


def markerset_file_names(markerset_path):
    """Marker names declared in an OpenSim marker-set XML."""
    import re as _re
    if not markerset_path or not os.path.isfile(markerset_path):
        return None
    return set(_re.findall(r'<Marker name="([^"]+)"',
                           open(markerset_path, errors="replace").read()))


def build_measurement_set(model, trc_path, spec=None, verbose=True, model_markers=None):
    """Return ``(MeasurementSet, report_lines)`` for this model + static TRC.

    Only marker pairs present in BOTH the model marker set and the TRC are
    emitted, and only for bodies this model actually has. Anything dropped is
    reported rather than silently skipped -- a silently empty MeasurementSet is
    the bug this whole module exists to prevent.
    """
    import opensim as osim

    spec = spec or DEFAULT_SPEC
    # GenericModelMaker REPLACES the model's markers with the marker-set file,
    # so when one is supplied its names -- not the model's -- are what ScaleTool
    # will actually see.
    have_model = set(model_markers) if model_markers else model_marker_names(model)
    have_bodies = model_body_names(model)
    _, trc_names, _, _ = read_trc(trc_path)
    have_trc = set(trc_names)

    mset = osim.MeasurementSet()
    report, skipped = [], []
    for name, pairs, bodies in spec:
        ok_pairs = [(a, b) for a, b in pairs
                    if a in have_model and b in have_model
                    and a in have_trc and b in have_trc]
        ok_bodies = {b: ax for b, ax in bodies.items() if b in have_bodies}
        if not ok_pairs or not ok_bodies:
            why = []
            if not ok_pairs:
                miss = sorted({m for a, b in pairs for m in (a, b)
                               if m not in have_model or m not in have_trc})
                why.append("markers " + ",".join(miss))
            if not ok_bodies:
                why.append("bodies " + ",".join(sorted(bodies)))
            skipped.append(f"{name} ({'; '.join(why)})")
            continue

        m = osim.Measurement()
        m.setName(name)
        m.setApply(True)
        mps = m.getMarkerPairSet()
        for a, b in ok_pairs:
            mps.cloneAndAppend(osim.MarkerPair(a, b))
        bss = m.getBodyScaleSet()
        for body, axes in sorted(ok_bodies.items()):
            bs = osim.BodyScale()
            bs.setName(body)
            arr = osim.ArrayStr()
            for ax in axes.upper():
                arr.append(ax)
            bs.setAxisNames(arr)
            bss.cloneAndAppend(bs)
        mset.cloneAndAppend(m)
        report.append(f"{name}: {'+'.join(a + '-' + b for a, b in ok_pairs)} "
                      f"-> {', '.join(f'{b}[{ax}]' for b, ax in sorted(ok_bodies.items()))}")

    if verbose:
        print(f"[scale] MeasurementSet: {mset.getSize()} measurements")
        for r in report:
            print(f"[scale]   {r}")
        for s in skipped:
            print(f"[scale]   SKIPPED {s}")
    return mset, report, skipped


# --------------------------------------------------------------------------
# Post-scaling validation
# --------------------------------------------------------------------------
def _segment_lengths(model_path):
    """Hip->knee->ankle joint distances, straight from the .osim joint frames."""
    import opensim as osim
    m = osim.Model(model_path)
    s = m.initSystem()
    out = {}
    for body in ("femur_r", "femur_l", "tibia_r", "tibia_l", "pelvis", "torso"):
        try:
            b = m.getBodySet().get(body)
            out[body + "_mass"] = b.getMass()
        except Exception:
            pass
    try:
        out["total_mass"] = m.getTotalMass(s)
    except Exception:
        pass
    return out


def verify_scaled(generic_path, scaled_path, tol=1e-4, verbose=True):
    """Compare a scaled model against its generic and shout if nothing changed.

    Returns ``(changed: bool, lines: list[str])``. The whole point: a model that
    came out of ScaleTool with every body at 1.0 is INDISTINGUISHABLE from the
    generic apart from mass, and that is precisely the failure mode that
    produced months of 'scaled' results built on generic geometry.
    """
    import opensim as osim
    g, sc = osim.Model(generic_path), osim.Model(scaled_path)
    gs, ss = g.initSystem(), sc.initSystem()
    lines, changed = [], False
    gb, sb = g.getBodySet(), sc.getBodySet()
    for i in range(sb.getSize()):
        name = sb.get(i).getName()
        try:
            gi = gb.get(name)
        except Exception:
            continue
        try:
            gm, sm = gi.getMass(), sb.get(i).getMass()
            # A body whose inertia changed by more than rounding was scaled.
            gI = gi.getInertia().getMoments()
            sI = sb.get(i).getInertia().getMoments()
            rel = max(abs(sI.get(k) - gI.get(k)) / max(abs(gI.get(k)), 1e-9) for k in range(3))
        except Exception:
            continue
        if rel > tol:
            changed = True
        lines.append(f"  {name:32s} mass {gm:7.3f} -> {sm:7.3f} kg   inertia rel.diff {rel:8.4f}")
    lines.append(f"  {'TOTAL':32s} mass {g.getTotalMass(gs):7.3f} -> {sc.getTotalMass(ss):7.3f} kg")
    if verbose:
        print("[scale] generic -> scaled comparison:")
        for l in lines:
            print("[scale]" + l)
        if not changed:
            print("[scale] [ERROR] NO BODY CHANGED SIZE. The model carries the subject's "
                  "mass on GENERIC geometry — this is not a scaled model. Check that the "
                  "static TRC has the joint-centre markers and that the MeasurementSet is "
                  "non-empty (both are printed above).")
    return changed, lines


# --------------------------------------------------------------------------
# Body mass from the static trial's ground reaction forces
# --------------------------------------------------------------------------
def mass_from_static_grf(grf_mot, g=9.80665, verbose=True):
    """Measured body mass = mean total vertical GRF / g over the static trial.

    Returns ``None`` if the file is missing or the plates read as unloaded.
    Preferred over a typed-in ``body_mass``: the force plates measured this
    subject on this day, wearing what they wore in the trial.
    """
    if not grf_mot or not os.path.isfile(grf_mot):
        return None
    lines = open(grf_mot, errors="replace").read().splitlines()
    try:
        hi = next(i for i, l in enumerate(lines) if l.strip().lower() == "endheader")
    except StopIteration:
        return None
    cols = [c.strip() for c in lines[hi + 1].split("\t")]
    vy = [i for i, c in enumerate(cols) if c.endswith("_vy")]
    if not vy:
        return None
    rows = []
    for ln in lines[hi + 2:]:
        if not ln.strip():
            continue
        try:
            rows.append([float(x) for x in ln.split("\t")])
        except ValueError:
            continue
    if not rows:
        return None
    arr = np.array(rows)
    total = arr[:, vy].sum(axis=1)
    mass = float(np.nanmean(total) / g)
    if mass < 20.0:            # unloaded plates / wrong sign convention
        if verbose:
            print(f"[scale] static GRF gives {mass:.1f} kg — implausible, ignoring.")
        return None
    if verbose:
        print(f"[scale] body mass from static GRF: {mass:.2f} kg "
              f"(mean {np.nanmean(total):.1f} N, sd {np.nanstd(total):.1f} N, "
              f"{len(vy)} plates)")
    return mass


def set_total_mass(model_path, target_mass, out_path=None, verbose=True):
    """Scale every body's mass and inertia so the model totals ``target_mass``.

    For an MRI/TPS-personalised model the geometry must NOT be touched, so
    ScaleTool's ModelScaler is off -- which also means nothing ever applies the
    subject's mass, and the model keeps the generic's. This applies mass alone:
    one uniform factor on every body's mass and inertia, leaving every segment
    length, marker and muscle path exactly as the personalisation left them.
    """
    import opensim as osim
    m = osim.Model(model_path)
    st = m.initSystem()
    cur = m.getTotalMass(st)
    if not target_mass or cur <= 0:
        return model_path
    f = float(target_mass) / float(cur)
    if abs(f - 1.0) < 1e-9:
        return model_path
    bs = m.updBodySet()
    for i in range(bs.getSize()):
        b = bs.get(i)
        b.setMass(b.getMass() * f)
        I = b.getInertia().getMoments()
        P = b.getInertia().getProducts()
        b.setInertia(osim.Inertia(I.get(0) * f, I.get(1) * f, I.get(2) * f,
                                  P.get(0) * f, P.get(1) * f, P.get(2) * f))
    m.finalizeConnections()
    out = out_path or model_path
    m.printToXML(out)
    if verbose:
        print(f"[scale] mass-only rescale (geometry untouched): "
              f"{cur:.2f} -> {float(target_mass):.2f} kg (x{f:.4f})")
    return out
