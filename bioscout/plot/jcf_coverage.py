"""Where the joint contact forces of one trial land on the bones.

``bioscout plot jcf_coverage TRIAL`` draws ONE sagittal scene of the loaded limb,
posed at the instant of peak hip force, with each joint's contact force painted
onto the surface that receives it:

* hip -- the MRI femoral head AND the acetabulum (from the segmentations), so
  this doubles as the acetabular-coverage figure with load on it;
* tibiofemoral, patellofemoral and ankle -- the model's own bone meshes.

A surface point is coloured by the PEAK force that passed through it during the
trial: for every frame, the contact patch is the cone of half-angle
``spread/2`` around the force direction at the joint centre, and each point
keeps the largest magnitude it ever saw. One figure per force source (SO, and
CEINMS when that trial has it), written into the trial's
``joint_contact_forces/`` folder.

Everything about the trial is discovered from its path: the JRA ``.sto`` files,
the IK ``.mot``, the iteration's model, ``body_mass`` from ``session.yaml`` and
``mri_root`` from ``project.yaml`` (default: the ucloud MRI segmentation tree).

Frames: the MRI meshes are put into the model's pelvis frame from the pelvic
landmarks at ``<project>/mri/<subject>/landmarks.csv`` (ASIS_R, ASIS_L,
PUBIC_SYMPHYSIS). Without that file the meshes are drawn as-is and the figure
says so -- the heat SHAPE is still right, its place on the head is not.
"""
from __future__ import annotations

import argparse
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from bioscout.plot.jcf_direction import (OsimModel, force_triplets, keep_end,
                                         read_sto)
from bioscout.session.events import (definitions_for, load_definitions,
                                     resolve_events, trial_phases, trial_signals)

__all__ = ["discover", "jcf_coverage_figure", "main"]


def _jrf_coverage(label, plane):
    from bioscout.simulate.jra_files import coverage
    return coverage(label, plane)

BONE = "#d9d7cf"          # solid bone
BONE_EDGE = "#b8b6ad"
HEAT = "Blues"
LOAD = "#eb6834"
DEFAULT_MRI_ROOT = (r"C:\Users\Basilio\ucloud\MRI_segmentation_BG"
                    r"\acetabular_coverage")

#: JRA joint name -> (kind, the bone that receives it, mesh-name filter).
#: Model families differ: Rajagopal writes one knee joint on ``tibia_r``, while
#: GPK/Lerner splits tibiofemoral contact across the two condyles and hangs it
#: off massless frames. The contact is drawn on the BONE either way, and the
#: weld joints (which repeat a load already counted) are skipped.
KIND_RULES = (
    (r"^hip", "hip", "femur", ("femur",)),
    (r"med_cond_joint", "knee medial", "tibia", ("tibia",)),
    (r"lat_cond_joint", "knee lateral", "tibia", ("tibia",)),
    (r"^(?!.*weld).*knee", "knee", "tibia", ("tibia",)),
    (r"(fem_pat|patell)", "patellofemoral", "patella", ("patella",)),
    (r"^ankle", "ankle", "talus", ("talus",)),
)
#: a joint panel shows the END of each long bone, not the whole shaft:
#: stem -> (which end, fraction kept)
PANEL_CROP = {
    "hip": {"femur": ("proximal", 0.35)},
    "knee": {"femur": ("distal", 0.33), "tibia": ("proximal", 0.33)},
    "ankle": {"tibia": ("distal", 0.20)},
}


def _crop(faces, panel, stem):
    """Keep only the part of a long bone that belongs to this joint."""
    rule = PANEL_CROP.get(panel, {}).get(stem)
    if not rule or not faces:
        return faces
    end, frac = rule
    try:
        out = keep_end(faces, frac, end=end)
        return out if out else faces
    except Exception:                                   # noqa: BLE001
        return faces


SKIP = re.compile(r"weld|ground_pelvis|subtalar|mtp|sagittal_articulation", re.I)
#: bones drawn UNLOADED in each panel, for context (bone stem -> mesh filter)
PANEL_CONTEXT = {
    "hip": (("pelvis", ("pelvis", "sacrum")), ("femur", ("femur",))),
    "knee": (("femur", ("femur",)), ("patella", ("patella",)), ("tibia", ("tibia",))),
    "patellofemoral": (("femur", ("femur",)), ("tibia", ("tibia",))),
    "ankle": (("tibia", ("tibia",)), ("talus", ("talus",)), ("calcn", ("foot",))),
}
#: proximal first, so the legend and the drawing order read down the limb
#: one panel per row of this: the panel's own kinds, in drawing order. The
#: knee panel carries whatever that model family provides -- one tibiofemoral
#: joint (Rajagopal) or the two condyles (GPK/Lerner) -- plus the patella.
PANELS = (("hip", ("hip",)),
          ("knee", ("knee", "knee medial", "knee lateral", "patellofemoral")),
          ("ankle", ("ankle",)))
#: frontal splits the knee into its compartments -- a medio-lateral view is
#: the whole reason to look at a condylar model's two contacts separately
PANELS_FRONTAL = (("hip", ("hip",)),
                  ("knee", ("knee medial", "knee lateral", "knee",
                            "patellofemoral")),
                  ("ankle", ("ankle",)))


#: the patella is not one of jcf_angle's panel kinds, so this panel carries
#: its own spec: the patella itself, with the distal femur behind it.
def _pf_spec(side):
    s_ = side
    return dict(rlabel=340,
                bones=[dict(body=f"patella_{s_}", only=("patella",), keep=None,
                            end=None, at=None)],
                moving=dict(body=f"femur_{s_}", only=(f"{s_}_femur", f"femur_{s_}"),
                            keep=0.16, end="distal", at=None, axis_sign=+1.0,
                            drive=f"knee_angle_{s_}", coords=(f"knee_angle_{s_}",)))


def _bone_frame(panel: str, side: str, frame_body: str) -> str:
    """The frame the panel's BONES live in.

    GPK reports the knee in a condyle body (``med_cond_r``) and the
    patellofemoral joint in ``patella_r``. Posing the moving bone into those
    frames while the static bone sits in its own leaves the two drawn far
    apart -- the gap between tibia and femur. Anchor each panel to the bone
    its spec is written around instead.
    """
    if panel.startswith("knee"):
        return f"tibia_{side}"
    if panel == "patellofemoral":
        return f"patella_{side}"
    if panel == "ankle":
        return f"talus_{side}"
    return frame_body


def _clip_toward(faces, frac, ref):
    """Keep the fraction of a bone NEAREST ``ref``, cut flat.

    The knee panel needs the femur's distal third. Keeping the "lower" third in
    projected y only works while the femur points down: at mid swing the knee is
    flexed ~90 deg, the distal end is no longer the lower end, and the cut threw
    away the part we wanted -- which is why that cell came out empty.
    """
    if not faces or not frac:
        return faces
    P = np.vstack(faces)
    ref = np.asarray(ref, float)[:2]
    cut = float(np.percentile(np.linalg.norm(P - ref, axis=1), 100.0 * frac))

    def _mid(a, b):
        da, db = np.linalg.norm(a[:2] - ref), np.linalg.norm(b[:2] - ref)
        t = 0.0 if abs(db - da) < 1e-12 else (cut - da) / (db - da)
        return a + float(np.clip(t, 0.0, 1.0)) * (b - a)

    out = []
    for f in faces:
        poly, n = [], len(f)
        for i in range(n):
            a, b = f[i], f[(i + 1) % n]
            ia = np.linalg.norm(a[:2] - ref) <= cut
            ib = np.linalg.norm(b[:2] - ref) <= cut
            if ia:
                poly.append(a)
            if ia != ib:
                poly.append(_mid(a, b))
        if len(poly) >= 3:
            out.append(np.asarray(poly, float))
    return out


def _clip_below(faces, frac, keep_low=True):
    """Cut projected faces with a STRAIGHT line across the bone.

    ``keep_end`` keeps or drops whole triangles by their centroid, so the cut
    end comes out ragged -- the spiky femur. This clips each triangle against
    the cut line (Sutherland-Hodgman), so the shaft ends flat where a
    sectioned bone would.

    frac: fraction of the bone's height kept, measured from the end being kept.
    """
    if not faces or not frac:
        return faces
    P = np.vstack(faces)
    y0, y1 = float(P[:, 1].min()), float(P[:, 1].max())
    if y1 <= y0:
        return faces
    cut = (y0 + frac * (y1 - y0)) if keep_low else (y1 - frac * (y1 - y0))
    inside = (lambda p: p[1] <= cut) if keep_low else (lambda p: p[1] >= cut)

    def _x(a, b):
        d = b[1] - a[1]
        t = 0.0 if abs(d) < 1e-12 else (cut - a[1]) / d
        return a + t * (b - a)

    out = []
    for f in faces:
        poly, n = [], len(f)
        for i in range(n):
            a, b = f[i], f[(i + 1) % n]
            ia, ib = inside(a), inside(b)
            if ia:
                poly.append(a)
            if ia != ib:
                poly.append(_x(a, b))
        if len(poly) >= 3:
            out.append(np.asarray(poly, float))
    return out


def panel_bones_of(model, kind, side, frame_body, cols):
    """``jcf_direction.panel_bones`` with the panel kind given explicitly.

    The library version derives the kind from the JOINT name, which fails for
    a condylar knee (``med_cond_joint_r``) and for the patellofemoral joint.
    """
    from bioscout.plot.jcf_direction import panel_spec as _ps, keep_end

    def panel_spec(kind, side):
        return _pf_spec(side) if kind == "patellofemoral" else _ps(kind, side)
    out = []
    for b in panel_spec(kind, side)["bones"]:
        if b["body"] not in model.bodies:
            continue
        faces = keep_end(model.mesh_faces(b["body"], b["only"]),
                         b["keep"], b["end"] or "proximal")
        if not faces:
            continue
        at = b["at"]
        if at == "chain":
            got = model.chain_pose(b["body"], frame_body)
            if got is None:
                continue
            Rot, t = got
            faces = [f @ Rot.T + t for f in faces]
        elif at and at in model.joints:
            _, t = model.joint_neutral(at)
            faces = [f - t for f in faces]
        out += [f[:, list(cols)] for f in faces]
    return out


def panel_moving_of(model, kind, side, frame_body, q, cols, keep=None):
    """``jcf_direction.panel_moving``, kind given explicitly (see above)."""
    from bioscout.plot.jcf_direction import panel_spec as _ps, keep_end

    def panel_spec(kind, side):
        return _pf_spec(side) if kind == "patellofemoral" else _ps(kind, side)
    spec = panel_spec(kind, side).get("moving")
    if not spec or spec["body"] not in model.bodies:
        return []
    # `keep` overrides the spec's own trim. The knee panel wants the femur's
    # DISTAL THIRD, and the spec trims to 16% before we ever see it -- clipping
    # that fragment to a third leaves ~5% of the bone.
    faces = keep_end(model.mesh_faces(spec["body"], spec["only"]),
                     spec["keep"] if keep is None else keep, spec["end"])
    got = model.chain_pose(spec["body"], frame_body, q) if faces else None
    if got is None:
        return []
    Rot, t = got
    faces = [f @ Rot.T + t for f in faces]
    if spec["at"] and spec["at"] in model.joints:
        _, t0 = model.joint_neutral(spec["at"])
        faces = [f - t0 for f in faces]
    return [f[:, list(cols)] for f in faces]


def _panels_for(plane: str):
    return PANELS_FRONTAL if plane == "frontal" else PANELS


def _spec_kind(panel: str) -> str:
    """The jcf_angle panel spec a coverage panel borrows its bones from.

    GPK names its knee contacts ``med_cond_joint_r`` / ``lat_cond_joint_r``,
    which ``joint_kind`` does not recognise -- asking it gave the knee cells
    no bones at all. The PANEL name is what we actually know."""
    if panel == "patellofemoral":
        return "patellofemoral"
    return "knee" if panel.startswith("knee") else panel


def _match(joint: str):
    """(kind, bone stem, mesh filter) for a JRA joint, or None to skip it."""
    if SKIP.search(joint):
        return None
    for pat, kind, bone, meshes in KIND_RULES:
        if re.search(pat, joint, re.I):
            return kind, bone, meshes
    return None


def _side(joint: str) -> str:
    return "l" if re.search(r"(_l$|_l_|left)", joint.lower()) else "r"


# --------------------------------------------------------------------------- #
# discovery: everything from the trial path
# --------------------------------------------------------------------------- #
def coupled_coordinates(osim_path, q: dict) -> dict:
    """Add the coordinates driven by CoordinateCouplerConstraints.

    A patellofemoral joint is posed by a coordinate (``knee_angle_r_beta``)
    that IK never writes: it is coupled to the knee angle by a spline in the
    model. Without it the patella is drawn at its neutral pose, which is
    visibly too proximal -- what OpenSim's GUI gets right and a naive reader
    gets wrong.
    """
    import xml.etree.ElementTree as ET
    out = dict(q)
    try:
        root = ET.parse(str(osim_path)).getroot()
    except Exception:                                   # noqa: BLE001
        return out
    for c in root.iter("CoordinateCouplerConstraint"):
        dep = (c.findtext("dependent_coordinate_name") or "").strip()
        ind = (c.findtext("independent_coordinate_names") or "").split()
        spl = c.find(".//SimmSpline") or c.find(".//NaturalCubicSpline")
        if not dep or not ind or spl is None or ind[0] not in out:
            continue
        try:
            x = np.fromstring(spl.findtext("x"), sep=" ")
            y = np.fromstring(spl.findtext("y"), sep=" ")
            out[dep] = float(np.interp(out[ind[0]], x, y))
        except Exception:                               # noqa: BLE001
            continue
    return out


def _yaml(path):
    try:
        import yaml
        with open(path) as fh:
            return yaml.safe_load(fh) or {}
    except Exception:                                   # noqa: BLE001
        return {}


def _geometry_dirs(iteration_dir: Path, project: Path) -> list:
    """Everywhere a model's .vtp may sit, most project-specific first.

    The same order ``bioscout model check`` reports as its tiers: the model's
    own folder, the project's generic models (each with its own Geometry/), then
    bioscout's bundled Geometry as the last resort.
    """
    dirs = [iteration_dir, iteration_dir / "Geometry"]
    gen = project / "models" / "generic"
    if gen.is_dir():
        dirs += [gen] + sorted(gen.glob("*/Geometry")) + sorted(gen.glob("*/*/Geometry"))
    try:
        from bioscout.model.geometry import bundled_geometry_dir
        b = bundled_geometry_dir()
        if b:
            dirs.append(Path(b))
    except Exception:                                   # noqa: BLE001
        pass
    out = []
    for d in dirs:
        try:                                            # a cloud-synced folder
            if Path(d).is_dir():                        # can raise OSError here
                out.append(str(d))
        except OSError:
            continue
    return out


def discover(trial, model=None, mass=None, mri_root=None, side=None) -> dict:
    """Everything needed for the figure, from ``simulations/<S>/<sess>/3_iterations/<it>/<trial>``."""
    trial = Path(trial).resolve()
    if not trial.is_dir():
        raise FileNotFoundError(trial)
    parts = list(trial.parts)
    try:
        i = len(parts) - 1 - parts[::-1].index("3_iterations")
    except ValueError:
        raise ValueError(f"{trial} is not inside a 3_iterations/<iteration>/<trial> tree")
    iteration_dir = Path(*parts[:i + 2])
    session_dir = Path(*parts[:i])
    subject_dir = session_dir.parent
    project = subject_dir.parent.parent                 # .../simulations/<S>/.. -> repo

    jcf_dir = trial / "joint_contact_forces"
    sources = {}
    from bioscout.simulate import jra_files as _jrf
    so = Path(_jrf.pick(jcf_dir / _jrf.output("SO")))
    if so.is_file():
        sources["SO"] = so
    ce = Path(_jrf.pick(jcf_dir / _jrf.output("CEINMS")))
    if ce.is_file():
        sources["CEINMS"] = ce
    for pat in ("*CEINMS*.sto", "*ceinms*.sto"):
        for p in list(jcf_dir.glob(pat)) + list((trial / "ceinms").rglob(pat)):
            if "ReactionLoads" in p.name or "JRA" in p.name:
                sources.setdefault("CEINMS", p)
    cmc = Path(_jrf.pick(jcf_dir / _jrf.output("CMC")))     # forward stage (CMC)
    if cmc.is_file():
        sources["CMC"] = cmc
    ml = Path(_jrf.pick(jcf_dir / _jrf.output("ML")))      # machine_learning.predict
    if ml.is_file():
        sources["ML"] = ml
    if not sources:
        raise FileNotFoundError(f"no JRA .sto in {jcf_dir}")

    ik = trial / "external_biomechanics" / "joint_angles.mot"
    if not ik.is_file():
        cand = list((trial / "external_biomechanics").glob("*.mot"))
        ik = cand[0] if cand else None
    if ik is None:
        raise FileNotFoundError(f"no IK .mot in {trial / 'external_biomechanics'}")

    if model is None:                  # the iteration's model_scaled in session.yaml
        try:
            from bioscout.plot.task_figure import model_for
            model = model_for(trial)
        except Exception:                                # noqa: BLE001
            model = None
    if model is None:
        cands = sorted(iteration_dir.glob("*.osim")) or sorted(
            (project / "models" / "personalised" / subject_dir.name).glob("*.osim"))
        key = iteration_dir.name.lower()
        pref = [c for c in cands if key.split("_")[0] in c.name.lower()]
        model = (pref or cands or [None])[0]
    if model is None:
        raise FileNotFoundError("no .osim found — pass --model")

    if mass is None:
        mass = (_yaml(session_dir / "session.yaml") or {}).get("body_mass")
    if mri_root is None:
        mri_root = (_yaml(project / "project.yaml") or {}).get("mri_root", DEFAULT_MRI_ROOT)

    mri = Path(str(mri_root).replace("\\", "/")) / subject_dir.name / "Meshlab_BG"
    landmarks = project / "mri" / subject_dir.name / "landmarks.csv"
    return {"trial": trial, "subject": subject_dir.name, "session": session_dir.name,
            "iteration": iteration_dir.name, "model": Path(model), "ik": ik,
            "sources": sources, "mass": float(mass) if mass else None,
            "mri_dir": mri if mri.is_dir() else None,
            "landmarks": landmarks if landmarks.is_file() else None,
            "out_dir": jcf_dir, "geometry": _geometry_dirs(iteration_dir, project)}


# --------------------------------------------------------------------------- #
# the load map
# --------------------------------------------------------------------------- #
def peak_map(points, centre, u, mag, spread_deg=25.0):
    """Peak magnitude per point: for each frame, points within ``spread/2`` of
    the force direction (seen from ``centre``) take that frame's magnitude."""
    d = np.asarray(points, float) - np.asarray(centre, float)
    n = np.linalg.norm(d, axis=1)
    d = d / np.where(n > 0, n, 1)[:, None]
    cos_lim = math.cos(math.radians(spread_deg / 2))
    out = np.zeros(len(d))
    for i in range(0, u.shape[1], 200):
        cos = d @ u[:, i:i + 200]
        m = cos >= cos_lim
        if m.any():
            out = np.maximum(out, (m * mag[i:i + 200]).max(axis=1))
    return out


def _subdivide(tris, target=4000):
    """Split triangles until there are enough for a smooth per-face heat map.

    The model's display meshes are coarse (72-456 points), so a contact patch
    would otherwise be a handful of facets.
    """
    tris = np.asarray(tris, float)
    while len(tris) and len(tris) < target:
        a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
        ab, bc, ca = (a + b) / 2, (b + c) / 2, (c + a) / 2
        tris = np.concatenate([np.stack([a, ab, ca], 1), np.stack([ab, b, bc], 1),
                               np.stack([ca, bc, c], 1), np.stack([ab, bc, ca], 1)])
    return tris


def peak_map_projected(points, centre, u, mag, radius_mm=16.0, search_mm=45.0):
    """Peak magnitude per point, patch centred where the load line MEETS the
    surface -- not on the joint centre.

    For the patella the joint centre sits behind the bone, so a patch taken
    around the centre lands on whichever rim happens to be nearest. Here, for
    each frame, the contact point is the surface point best aligned with that
    frame's load direction, and the patch is what lies within ``radius_mm`` of
    it.
    """
    pts = np.asarray(points, float)
    d = pts - np.asarray(centre, float)
    dist = np.linalg.norm(d, axis=1)
    near = dist <= search_mm
    out = np.zeros(len(pts))
    if not near.any():
        return out
    pn, dn = pts[near], d[near] / np.where(dist[near] > 0, dist[near], 1)[:, None]
    hot = np.zeros(near.sum())
    for i in range(u.shape[1]):
        j = int(np.argmax(dn @ u[:, i]))                  # the contact point
        within = np.linalg.norm(pn - pn[j], axis=1) <= radius_mm
        hot[within] = np.maximum(hot[within], mag[i])
    out[near] = hot
    return out


def peak_map_near(points, centre, u, mag, radius_mm=14.0):
    """Peak magnitude per point for a joint whose centre sits ON the contact
    surface (knee, patellofemoral, ankle).

    The hip's cone-from-the-centre rule degenerates there: the centre is a few
    millimetres from the surface, so an angular cone paints almost nothing.
    Here a point is in the patch when it lies within ``radius_mm`` of the
    centre AND on the side the load pushes from.
    """
    d = np.asarray(points, float) - np.asarray(centre, float)
    dist = np.linalg.norm(d, axis=1)
    near = dist <= radius_mm
    out = np.zeros(len(d))
    if not near.any():
        return out
    dn = d[near] / np.where(dist[near] > 0, dist[near], 1)[:, None]
    for i in range(0, u.shape[1], 200):
        side = (dn @ u[:, i:i + 200]) > 0.0
        if side.any():
            out[near] = np.maximum(out[near], (side * mag[i:i + 200]).max(axis=1))
    return out


def _tri(faces):
    """mesh_faces() polygons (metres) -> (M, 3, 3) triangles in mm."""
    out = []
    for f in faces:
        f = np.asarray(f, float) * 1000.0
        for k in range(1, len(f) - 1):                  # fan-triangulate
            out.append([f[0], f[k], f[k + 1]])
    return np.asarray(out) if out else np.zeros((0, 3, 3))


def _pose(tris, R, t):
    """Triangles from a body frame into the pelvis frame (t in metres)."""
    if len(tris) == 0:
        return tris
    return tris @ np.asarray(R, float).T + np.asarray(t, float) * 1000.0


#: every triangle drawn, so the view can be scaled to the real bounds
_drawn: list = []


#: pelvis frame is x ANT, y SUP, z RIGHT; matplotlib's 3rd axis is the vertical
#: one, so the drawing order is (anterior, right, superior).
_TO_PLOT = [0, 2, 1]


def _arrow(ax, centre, vec, label=None):
    """The peak load vector at a joint centre — the contact patch itself can
    face medially, where a sagittal view cannot show it."""
    c = np.asarray(centre, float)[_TO_PLOT]
    v = np.asarray(vec, float)[_TO_PLOT]
    ax.quiver(*c, *v, color=LOAD, lw=1.6, arrow_length_ratio=0.25, label=label)
    _drawn.append(np.vstack([c, c + v]))


def _bare(ax):
    """No grid, panes or ticks: once the camera moves off sagittal the axes
    stop meaning anterior/superior, and a wrong label is worse than none."""
    ax.set_xticks([]); ax.set_yticks([]); ax.set_zticks([])
    ax.set_xlabel(""); ax.set_ylabel(""); ax.set_zlabel("")
    ax.grid(False)
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.pane.set_alpha(0.0)
        a.line.set_color((1, 1, 1, 0))


#: the joint cells are drawn FLAT, like bioscout's jcf_angle panels: the bone
#: is a plain grey silhouette in the panel's view and the contact patch is
#: painted on top of it. A shaded 3-D mesh spends its contrast on surface
#: shading and depth cues, which is exactly the contrast the heat map needs.
SILHOUETTE = "#d9d6d2"
SILHOUETTE_CONTEXT = "#ecebe9"


def _basis(elev, azim):
    """Orthonormal (right, up, view) for a camera at (elev, azim), plot space."""
    e, a = math.radians(elev), math.radians(azim)
    view = np.array([math.cos(e) * math.cos(a), math.cos(e) * math.sin(a),
                     math.sin(e)])
    ref = np.array([0.0, 0.0, 1.0])
    right = np.cross(ref, view)
    if np.linalg.norm(right) < 1e-9:
        right = np.array([1.0, 0.0, 0.0])
    right = right / np.linalg.norm(right)
    return right, np.cross(view, right), view


def _flat(ax, tris, basis, values=None, vmax=None, cmap=HEAT,
          grey=SILHOUETTE, alpha=1.0):
    """One bone, projected onto the camera plane and filled flat.

    Unloaded faces all take the SAME grey, so the bone reads as one silhouette
    rather than a shaded solid; loaded faces take the ramp. Painter's order by
    depth, so a patch on the near wall covers the far wall.
    """
    from matplotlib.collections import PolyCollection
    tris = np.asarray(tris, float)
    if len(tris) == 0:
        return None
    t3 = tris[..., _TO_PLOT]
    right, up, view = basis
    P = np.stack([t3 @ right, t3 @ up], axis=-1)
    order = np.argsort(t3.mean(axis=1) @ view)
    if values is None:
        cols = np.tile(matplotlib.colors.to_rgba(grey), (len(tris), 1))
    else:
        vmax = max(float(vmax), 1e-9)
        cols = plt.get_cmap(cmap)(0.25 + 0.75 * plt.Normalize(0.0, vmax)(values))
        cols[values <= 0.02 * vmax] = matplotlib.colors.to_rgba(grey)
    pc = PolyCollection(P[order], facecolors=cols[order], edgecolors="none",
                        alpha=alpha, antialiased=True)
    ax.add_collection(pc)
    return P.reshape(-1, 2)


def _camera(vec):
    """(elev, azim) for a camera that looks STRAIGHT AT a patch whose outward
    direction is ``vec`` (pelvis frame). A contact patch on the far side of a
    bone is invisible from any fixed view, so each panel picks its own."""
    v = np.asarray(vec, float)[_TO_PLOT]
    n = np.linalg.norm(v)
    if n == 0:
        return 8.0, -70.0
    v = v / n
    return float(np.degrees(np.arcsin(np.clip(v[2], -1, 1)))), \
        float(np.degrees(np.arctan2(v[1], v[0])))


def _facing(tris, centre, cam, keep=0.0):
    """Faces on the camera-facing side of a bone: the near wall of a closed
    surface would otherwise hide the patch painted on its far wall."""
    d = tris.mean(axis=1) - np.asarray(centre, float)
    n = np.linalg.norm(d, axis=1)
    return (d @ np.asarray(cam, float)) / np.where(n > 0, n, 1) > keep


def _draw(ax, tris, values=None, vmax=None, alpha=1.0, cmap=HEAT, label=None):
    if len(tris) == 0:
        return None
    tris = np.asarray(tris, float)[..., _TO_PLOT]
    if values is None:
        pc = Poly3DCollection(tris, facecolor=BONE, edgecolor="none",
                              alpha=alpha, label=label)
    else:
        vmax = max(float(vmax), 1e-9)
        cold = values <= 0.02 * vmax
        # loaded faces span the ramp from a visible light blue, not from white,
        # so a small patch on a coarse mesh is still legible
        norm = plt.Normalize(0.0, vmax)
        cols = plt.get_cmap(cmap)(0.25 + 0.75 * norm(values))
        cols[cold] = matplotlib.colors.to_rgba(BONE)
        pc = Poly3DCollection(tris, facecolors=cols, edgecolor="none",
                              alpha=alpha, label=label)
    ax.add_collection3d(pc)
    _drawn.append(tris.reshape(-1, 3))      # 3D collections do not autoscale
    return pc


# --------------------------------------------------------------------------- #
# the figure
# --------------------------------------------------------------------------- #
def grf_for(info: dict):
    """(time, {side: vy}, {side: vx}) -- vertical AND anterior, plates mapped
    to feet by GRF.xml. Push-off is defined on the anterior component, so the
    vertical trace alone is not enough."""
    t = info["trial"]
    exp = t.parents[2] / "2_experimental" / t.name
    mot, xml = exp / "grf.mot", exp / "GRF.xml"
    if not mot.is_file():
        return None
    names, data = read_sto(str(mot))
    sides = {}
    if xml.is_file():
        from bioscout.session.movement_detector.mocap import _plate_sides
        sides = _plate_sides(str(xml))          # {force_identifier: 'l'|'r'}
    out, ant = {}, {}
    for side in ("l", "r"):
        ax_cols = [i for i, n in enumerate(names)
                   if n.endswith("_vx") and sides.get(n[:-1], "") == side]
        if ax_cols:
            ant[side] = np.sum([data[:, i] for i in ax_cols], axis=0)
        # column "ground_force_1_vy" belongs to force_identifier
        # "ground_force_1_v" -- drop the trailing axis letter only
        cols = [i for i, n in enumerate(names)
                if n.endswith("_vy") and sides.get(n[:-1], "") == side]
        if cols:
            out[side] = np.abs(np.sum([data[:, i] for i in cols], axis=0))
    if not out:                                  # no GRF.xml: take the two busiest plates
        vy = [i for i, n in enumerate(names) if n.endswith("_vy")]
        vy.sort(key=lambda i: -np.nanmax(np.abs(data[:, i])))
        for side, i in zip(("r", "l"), vy[:2]):
            out[side] = np.abs(data[:, i])
    return data[:, 0], out, ant


def measured_side(info: dict):
    """The side this subject is analysed on: 'Measured Leg' in
    ``subject_demographics.csv``, else None. session.yaml's
    ``measured_side: l|r`` wins when it names one leg."""
    import csv as _csv
    try:
        from bioscout.session.config import session_measured_side as _sms
        _s = _sms(info["trial"].parents[2])
        if _s in ("l", "r"):
            return _s
    except Exception:                                   # noqa: BLE001
        pass
    f = info["trial"].parents[4] / "subject_demographics.csv"
    if not f.is_file():
        return None
    try:
        with open(f, newline="") as fh:
            for row in _csv.DictReader(fh):
                sid = (row.get("Subject") or "").strip()
                if sid and sid.zfill(3) == str(info["subject"]).zfill(3):
                    v = (row.get("Measured Leg") or "").strip().lower()
                    return "r" if v.startswith("r") else ("l" if v.startswith("l") else None)
    except Exception:                                   # noqa: BLE001
        return None
    return None


def detected_cycle(info: dict, t0: float, t1: float, side=None):
    """The detected cycle that best overlaps [t0, t1], from the trial's
    ``movement_detection.yaml``: (name, side, start, end, [(label, time)]).

    bioscout's movement detector already found the cycles and their foot
    strikes and foot-offs, including which plate belongs to which foot -- far
    safer than re-deriving them, and it is what the rest of the pipeline uses.
    """
    t = info["trial"]
    y = _yaml(t.parents[2] / "2_experimental" / t.name / "movement_detection.yaml")
    best = None
    for c in (y.get("cycles") or []):
        tr = c.get("time_range") or []
        if len(tr) != 2:
            continue
        if side and (c.get("side") or "")[:1].lower() != side:
            continue                                    # the analysed leg only
        ov = min(t1, float(tr[1])) - max(t0, float(tr[0]))
        if ov > 0 and (best is None or ov > best[0]):
            ev = [(f"{sd} {lab}", float(x)) for sd, lab, x in (c.get("events") or [])]
            best = (ov, c.get("name", "cycle"), (c.get("side") or "l")[0],
                    float(tr[0]), float(tr[1]), ev)
    return best[1:] if best else None


def cycle_window(t, vy_r, t0, t1, threshold=20.0):
    """Right foot-off to the NEXT right foot-off, clipped to [t0, t1].

    That is the cycle the lab defines for running; when the simulated window is
    shorter than a full cycle (JRA often is) the clip is reported by the caller.
    """
    on = vy_r > threshold
    offs = np.where(on[:-1] & ~on[1:])[0]                 # last loaded frame
    offs = [float(t[i]) for i in offs]
    inside = [x for x in offs if t0 - 0.05 <= x <= t1 + 0.05]
    if len(inside) >= 2:
        return inside[0], inside[1], True
    if len(inside) == 1:
        nxt = [x for x in offs if x > inside[0]]
        return inside[0], (nxt[0] if nxt else t1), bool(nxt)
    return t0, t1, False


def detect_events(t, vy, t0, t1, threshold=20.0, names=None):
    """Gait events of ONE foot inside [t0, t1] from its vertical GRF."""
    win = (t >= t0) & (t <= t1)
    stance = win & (vy > threshold)
    out = []
    if stance.any():
        idx = np.where(stance)[0]
        i_on, i_off = idx[0], idx[-1]
        i_max = idx[int(np.argmax(vy[idx]))]
        out.append(("foot strike", float(t[i_on])))
        third = idx[idx < i_on + max(2, (i_off - i_on) // 3)]
        if len(third) > 2:
            mid = third[1:-1]
            loc = mid[(vy[mid] > vy[third[:-2]]) & (vy[mid] > vy[third[2:]])]
            loc = [i for i in loc if abs(i - i_max) > 2]
            if loc:
                out.append(("impact peak", float(t[loc[int(np.argmax(vy[loc]))]])))
        out.append(("active peak", float(t[i_max])))
        out.append(("toe-off", float(t[i_off])))
        sw = t[i_off] + 0.2 * (t[i_off] - t[i_on])
        if sw <= t1:
            out.append(("early swing", float(sw)))
    else:
        out = [(f"t={x:.2f}s", float(x)) for x in np.linspace(t0, t1, 4)]
    if names:
        out = [(n, x) for n, x in out if n in names]
    return out


def _lab_yaw(geo, q_at, times):
    """Constant yaw (about the lab's vertical) that turns the subject to face
    the page's +x, so a fixed side camera sees them the way OpenSim's GUI
    side view does. It is the mean anterior axis of the pelvis over the
    cycle -- one number for the whole strip, never a per-frame correction,
    so the pelvis keeps every degree of tilt, list and rotation IK gave it."""
    a = np.zeros(3)
    for tt in times:
        a += _pelvis_in_ground(geo, q_at(tt)) @ np.array([1.0, 0.0, 0.0])
    a[1] = 0.0
    if np.linalg.norm(a) < 1e-9:
        return np.eye(3)
    th = math.atan2(a[2], a[0])
    c, sn = math.cos(th), math.sin(th)
    return np.array([[c, 0.0, sn], [0.0, 1.0, 0.0], [-sn, 0.0, c]])


def _pelvis_in_ground(geo, q):
    """Pelvis orientation in the lab, from the model's OWN ground joint.

    The joint's SpatialTransform is used as written (for GPK / Rajagopal:
    tilt about z, list about x, rotation about y, in that order), with every
    coordinate at its IK value. Nothing is dropped or offset: an earlier
    version built its own tilt/list/rotation matrix and subtracted the mean
    list and heading, and the poses stopped matching the OpenSim GUI, which
    shows the ground_pelvis joint and nothing else.
    """
    name = next((n for n, j in geo.joints.items()
                 if j["parent"]["body"] == "ground" and j["child"]["body"] == "pelvis"),
                None)
    if name is None:
        name = next((n for n in geo.joints if "pelvis" in n and "ground" in n), None)
    if name is None:
        return np.eye(3)
    return geo.joint_transform(name, q)[0]


def stride_events(side, t0, t1, grf, ik_names, ik_data, degrees):
    """The five events of one running stride, for the leg that has the GRF.

    hip drive (peak hip flexion VELOCITY), mid swing (peak hip flexion ANGLE),
    first impact peak (first vGRF peak), mid stance (the second, active vGRF
    peak) and push off (peak ANTERIOR GRF). Foot-off is deliberately not one of
    them: it bounds the cycle, it is not a loading event, and the cell at the
    cycle's first sample says nothing the next four do not.

    Anything the data cannot support is left out rather than guessed.
    """
    out, notes = [], {}
    coord = f"hip_flexion_{side}"
    if coord in ik_names:
        t = ik_data[:, 0]
        m = (t >= t0) & (t <= t1)
        if m.any():
            v, tt = ik_data[m, ik_names.index(coord)], t[m]
            if len(v) > 5:
                # hip drive = peak angular ACCELERATION into flexion. The
                # second derivative of a marker-driven angle is noisy, so it is
                # smoothed over ~15 ms before the peak is taken; without that
                # the event lands on whichever sample happened to jitter most.
                deg = v if degrees else np.degrees(v)
                dt = float(np.median(np.diff(tt))) or 1e-3
                w = max(3, int(round(0.015 / dt))) | 1
                sm = np.convolve(deg, np.ones(w) / w, mode="same")
                acc = np.gradient(np.gradient(sm, tt), tt)
                k = slice(w, len(acc) - w) if len(acc) > 3 * w else slice(None)
                i_acc = int(np.arange(len(acc))[k][int(np.argmax(acc[k]))])
                out.append((f"{side} hip drive", float(tt[i_acc])))
                notes[f"{side} hip drive"] = f"{acc[i_acc]:,.0f} deg/s²"
            out.append((f"{side} mid swing", float(tt[int(np.argmax(v))])))
    if grf and side in grf[1]:
        tg, vy = grf[0], grf[1][side]
        stance = (tg >= t0) & (tg <= t1) & (vy > 20.0)
        if stance.any():
            idx = np.where(stance)[0]
            i_on, i_off = idx[0], idx[-1]
            i_max = idx[int(np.argmax(vy[idx]))]
            # impact peak: a local maximum in the first third of stance that is
            # not the active peak itself. A rearfoot strike has one; a forefoot
            # strike often does not, and then this event simply does not exist.
            third = idx[idx < i_on + max(2, (i_off - i_on) // 3)]
            if len(third) > 2:
                mid = third[1:-1]
                loc = mid[(vy[mid] > vy[third[:-2]]) & (vy[mid] > vy[third[2:]])]
                loc = [i for i in loc if abs(i - i_max) > 2]
                if loc:
                    out.append((f"{side} impact peak",
                                float(tg[loc[int(np.argmax(vy[loc]))]])))
            out.append((f"{side} mid stance", float(tg[i_max])))
            # push off = peak hip EXTENSION during stance. Taken from the
            # kinematics rather than the anterior GRF: this trial's anterior
            # trace carries an impact transient in the first 20 ms that is
            # larger than the propulsive peak it would be measured from.
            if coord in ik_names:
                ti = ik_data[:, 0]
                st_ik = (ti >= tg[i_on]) & (ti <= tg[i_off])
                if st_ik.any():
                    v_st = ik_data[st_ik, ik_names.index(coord)]
                    out.append((f"{side} push off",
                                float(ti[st_ik][int(np.argmin(v_st))])))
    return (sorted({(n, round(x, 4)) for n, x in out}, key=lambda e: e[1]),
            notes)


#: what the dashed line should point AT, per event: the reader checks the
#: pose against the curve through one body part, and it is not the same part
#: for a swing event as for a stance one
#: the structure each contact acts ON: a patellofemoral arrow drawn from the
#: joint centre says nothing about where the load lands, and a tibiofemoral one
#: acts at the plateau, not at the panel origin.
_APPLY_AT = {"patellofemoral": ("patella", ("patella",)),
             "knee medial": ("tibia", ("tibia",)),
             "knee lateral": ("tibia", ("tibia",)),
             "knee": ("tibia", ("tibia",))}


#: one colour ramp per side, so a cell's side is never in doubt
SIDE_CMAP = {"r": "Reds", "l": "Blues"}
SIDE_COLOR = {"r": "#c0392b", "l": "#2a78d6"}


def _side_joints(data, names, trips, side, scale):
    joints = {}
    for j, (body, frame, idx) in trips.items():
        if "articulation" in body.lower():
            continue
        hit = _match(j)
        if not hit or _side(j) != side or body != frame:
            continue
        kind, bone, meshes = hit
        F = data[:, idx].T
        m = np.linalg.norm(F, axis=0) / scale
        joints.setdefault(kind, {"bone": f"{bone}_{side}", "meshes": meshes,
                                 "loads": [], "peak": 0.0})
        joints[kind]["loads"].append((j, body, F, m))
        joints[kind]["peak"] = max(joints[kind]["peak"], float(m.max()))
    return joints


# --------------------------------------------------------------------------- #
# the force polygon: WHO makes up the contact force (--add_polygon)
# --------------------------------------------------------------------------- #
def load_contributions(jra, label):
    """``contributions_<label>.sto`` next to the JRA file (written by
    ``run_jra_contributions``; the legacy ``contributions_<label>/contributions.csv``
    is still read), or None when the trial has none."""
    from bioscout.core.jcf_contributions import read_contributions
    for path in (Path(jra).parent / f"contributions_{label.lower()}.sto",
                 Path(jra).parent / f"contributions_{label.lower()}" / "contributions.csv"):
        if path.exists():
            return read_contributions(str(path))[0]
    return None


def _contribution_series(df, joint_key, t):
    """{source: (3, n) N} of one joint, interpolated onto the JRA time base."""
    out = {}
    for src, g in df[df["joint"] == joint_key].groupby("source", sort=False):
        g = g.sort_values("time")
        tt = g["time"].to_numpy()
        out[src] = np.vstack([np.interp(t, tt, g[c].to_numpy())
                              for c in ("fx", "fy", "fz")])
    return out


def _polygon_parts(parts, n_top=6):
    """Order one instant's contributions for the chain: the non-muscle baseline
    first, then the ``n_top`` largest muscle groups, then the pooled rest --
    nothing is dropped, so the chain still ends on the resultant."""
    base = [(n, v) for n, v in parts if str(n).startswith("Non-muscle")]
    mus = sorted([(n, v) for n, v in parts if not str(n).startswith("Non-muscle")],
                 key=lambda nv: -float(np.hypot(*nv[1])))
    out = [("Non-muscle", sum(v for _n, v in base))] if base else []
    out += [(re.sub(r"^[RL]\s+", "", str(n)), v) for n, v in mus[:n_top]]
    if mus[n_top:]:
        out.append(("other", sum(v for _n, v in mus[n_top:])))
    return out


def _force_polygon(ax, base_xy, parts, lw=2.6):
    """Head-to-tail chain of the contribution vectors on a polar axes, starting
    at ``base_xy`` (cartesian: x = theta 90 deg, y = theta 0). Segments are
    annotations so they are STRAIGHT on screen (``ax.plot`` bends them), and
    are clipped to the cell: opposing muscles can swing the chain past the rim."""
    from bioscout.core.jcf_contributions import source_color
    x, y = float(base_xy[0]), float(base_xy[1])
    used = []
    for name, v in parts:
        x2, y2 = x + float(v[0]), y + float(v[1])
        if np.hypot(x2 - x, y2 - y) > 1e-6:
            col = source_color("other" if name == "other" else name)
            an = ax.annotate("", xy=(math.atan2(x2, y2), math.hypot(x2, y2)),
                             xytext=(math.atan2(x, y), math.hypot(x, y)),
                             arrowprops=dict(arrowstyle="-", lw=lw, color=col,
                                             shrinkA=0, shrinkB=0,
                                             capstyle="round"),
                             zorder=5, annotation_clip=False)
            an.arrow_patch.set_clip_path(ax.patch)
            # the legend names only what the eye can find in the cell
            if np.hypot(x2 - x, y2 - y) >= 0.03 * ax.get_ylim()[1]:
                used.append((name, col))
        x, y = x2, y2
    return used, (x, y)


def jcf_coverage_figure(info: dict, label: str, out=None, spread_deg=25.0,
                        patch_mm=16.0, window_ms=30.0, n_poses=6, events=None,
                        sides=None, strip_sides=("r", "l"),
                        plane: str = "sagittal", add_polygon: bool = False,
                        polygon_top: int = 6) -> dict:
    """One figure for the whole trial: the posed limb and the GRF of both feet
    on top, then one row per joint x one column per gait event, each cell the
    contact surface seen from above. Only the analysed leg's joints are drawn
    (``sides``); the strip keeps both limbs so the pose reads as a stride."""
    jra = info["sources"][label]
    geo = OsimModel(str(info["model"]), info["geometry"])
    names, data = read_sto(str(jra))
    t_jra = data[:, 0]
    trips = force_triplets(names)
    ik_names, ik_data = read_sto(str(info["ik"]))
    with open(info["ik"]) as fh:
        degrees = "indegrees=yes" in fh.read(2000).replace(" ", "").lower()
    mass = info.get("mass")
    unit, scale = ("BW", mass * 9.80665) if mass else ("N", 1.0)

    cyc_side = info.get("cycle_side") or measured_side(info) or "r"
    sides = tuple(sides) if sides else (cyc_side,)
    by_side = {sd: _side_joints(data, names, trips, sd, scale) for sd in sides}
    by_side = {sd: j for sd, j in by_side.items() if j}
    if not by_side:
        raise ValueError(f"no joint force columns in {jra.name}")
    vmax = max(j["peak"] for js in by_side.values() for j in js.values())

    # ---- the cycle and its events ----------------------------------------
    grf = grf_for(info)
    t0, t1 = float(t_jra[0]), float(t_jra[-1])
    cyc = (detected_cycle(info, t0, t1, side=cyc_side)
           or detected_cycle(info, t0, t1))
    _det = _yaml(info["trial"].parents[2] / "2_experimental" / info["trial"].name
                 / "movement_detection.yaml")
    cycle_name, ev, covered = "simulated window", [], 1.0
    if cyc:
        cycle_name, cyc_side, c0, c1, cev = cyc
        # the cycle is foot-off to foot-off of the analysed leg; the simulated
        # window is often shorter, so say how much of it is actually there
        t0, t1 = max(t0, c0), min(t1, c1)
        covered = (t1 - t0) / (c1 - c0) if c1 > c0 else 1.0
        cycle_name = (f"{'right' if cyc_side == 'r' else 'left'} foot-off to "
                      f"foot-off ({cycle_name})")
    else:
        # no gait cycle (a squat, a hold): the detected TASK is the window
        _task0, _ph0 = trial_phases(_det, cyc_side, t0, t1)
        _tw = [tk for tk in (_det.get("tasks") or [])
               if tk.get("task") == _task0 and tk.get("phases")]
        if _tw:
            _tr = _tw[0].get("time_range") or [t0, t1]
            c0, c1 = float(_tr[0]), float(_tr[1])
            t0, t1 = max(t0, c0), min(t1, c1)
            covered = (t1 - t0) / (c1 - c0) if c1 > c0 else 1.0
            cycle_name = f"{_task0.replace('_', ' ')} ({_tw[0].get('name') or info['trial'].name})"
        elif grf and cyc_side in grf[1]:
            t0, t1, _ = cycle_window(grf[0], grf[1][cyc_side], t0, t1)
    # The events are DEFINED in bioscout/session/events.yaml (overridable in
    # project.yaml / session.yaml), per task, and resolved on this trial's IK
    # and GRF within the phases the movement detector found.
    _task, _phases = trial_phases(_det, cyc_side, t0, t1)
    _session_dir = info["trial"].parents[2]
    _defs = load_definitions(_session_dir.parent.parent.parent, _session_dir)
    _events = resolve_events(definitions_for(_defs, _task), cyc_side, _phases,
                             trial_signals(ik_names, ik_data, degrees, grf))
    ev = [(f"{cyc_side} {e.name}", e.time) for e in _events]
    ev_meta = {f"{cyc_side} {e.name}": e for e in _events}
    if events:
        ev = [(n, x) for n, x in ev if any(k in n for k in events)]
    if not ev:
        ev = [(f"t={x:.2f}s", float(x)) for x in np.linspace(t0, t1, 4)]
    full = bool(cyc) and t0 <= (cyc[2] + 1e-6) and t1 >= (cyc[3] - 1e-6)

    panels_here = _panels_for(plane)
    rows = [(panel, sd) for panel, kinds in panels_here for sd in sides
            if sd in by_side and any(k in by_side[sd] for k in kinds)]
    panels_of = {panel: kinds for panel, kinds in panels_here}
    # one column per event, plus a last one carrying the WHOLE cycle's
    # path -- the event cells show only that instant's vector, so the
    # trace has to live somewhere
    ncol, nrow = len(ev) + 1, len(rows)

    fig = plt.figure(figsize=(2.8 * ncol + 1.8, 1.55 * nrow + 4.2), dpi=170)
    outer = fig.add_gridspec(2 + len(panels_here), ncol,
                             height_ratios=[2.8, 1.0] + [2.0 * sum(
                                 1 for p, sd in rows if p == panel)
                                 for panel, _ in panels_here],
                             hspace=0.14, wspace=0.04, top=0.96, bottom=0.07)

    q_at = _q_maker(ik_names, ik_data, degrees, info["model"])
    # The pelvis goes into the lab exactly as the model's ground_pelvis
    # joint puts it (tilt, list AND rotation, nothing removed) -- that is what
    # the OpenSim GUI shows. The only freedom is the camera: one constant yaw
    # turns the subject to face +x, so the side view is a true lab-side view
    # and the front view a true lab-front view (both fixed for the whole strip).
    R_yaw = _lab_yaw(geo, q_at, np.linspace(t0, t1, 25))

    # row 1: the GRF of both feet, with the events
    axc = fig.add_subplot(outer[1, :len(ev)])
    if grf:
        tg, vys = grf[0], grf[1]
        m = (tg >= t0 - 0.05) & (tg <= t1 + 0.05)
        for sd, vy in vys.items():
            axc.plot(tg[m], vy[m] / scale, color=SIDE_COLOR[sd], lw=1.8,
                     label=f"{'right' if sd == 'r' else 'left'} foot")
            axc.fill_between(tg[m], 0, vy[m] / scale, color=SIDE_COLOR[sd], alpha=0.10)
    ytop = max((vy.max() / scale for vy in (grf[1].values() if grf else [])), default=1.0)
    axc.set_ylim(0, ytop * 1.5)
    # the line, and the INSTANT beside it: the event is named once, under its
    # pose (with its letter), and the leader joins the two. Neighbouring
    # events (impact peak / mid stance, ~50 ms apart) stagger their labels so
    # neither hides the other.
    # The instant sits BELOW the x axis, under its own line, where a time
    # belongs (it was floating at the top of the line, between the pose
    # labels, reading as a third caption). Neighbouring events (~50 ms apart)
    # stagger downwards so neither hides the other.
    _t_prev, _stag = None, 0
    for i, (name, tt) in enumerate(ev):
        axc.axvline(tt, color="#555", lw=0.8, ls="--")
        _close = _t_prev is not None and (tt - _t_prev) < 0.07 * (t1 - t0)
        _stag = (_stag + 1) % 2 if _close else 0
        axc.text(tt, -0.30 - 0.32 * _stag, f"{tt:.2f}s",
                 transform=axc.get_xaxis_transform(),
                 ha="center", va="top", fontsize=6.5, color="#333",
                 bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none",
                           alpha=0.85), clip_on=False)
        _t_prev = tt
    axc.set_xlim(t0 - 0.02, t1 + 0.02)
    axc.set_xlabel("time (s)", fontsize=7, loc="right", labelpad=1)
    axc.tick_params(axis="x", pad=1.5)
    axc.set_ylabel(f"vertical GRF ({unit})", fontsize=7)
    axc.tick_params(labelsize=6)
    # outside the axes, to the right: inside it the entries sat on top of the
    # event labels, which are the thing the row exists to place
    axc.legend(fontsize=7, frameon=False, loc="center left",
               bbox_to_anchor=(1.01, 0.5), ncol=1, handlelength=1.6,
               borderaxespad=0.0)
    for sp in ("top", "right"):
        axc.spines[sp].set_visible(False)

    # The poses go WHERE THEIR EVENT IS, not in equal columns: a pose above
    # the middle of the row when its event is at the edge of stance is a
    # picture that contradicts the curve under it.
    strip_axes = []
    _row = outer[0, :len(ev)].get_position(fig)
    _w = min(0.155, _row.width / max(len(ev) - 0.2, 1))
    for _i, (ename, tt) in enumerate(ev):
        _want = ev_meta[ename].landmark if ename in ev_meta else None
        _x = fig.transFigure.inverted().transform(
            axc.transData.transform((tt, 0.0)))[0]
        # the outer two get a nudge outwards: events cluster in stance, and
        # spreading the ends buys room without moving anything misleadingly
        if _want is None:            # nothing to align on: nudge the ends apart
            if _i == 0:
                _x -= 0.35 * _w
            elif _i == len(ev) - 1:
                _x += 0.35 * _w
        axp = fig.add_axes([min(max(_x - _w / 2, 0.0), 1.0 - _w),
                            _row.y0, _w, _row.height], projection="3d")
        # transparent: neighbouring poses overlap where their events are close,
        # and an opaque panel would erase the one beside it
        axp.patch.set_visible(False)
        axp.set_facecolor("none")
        strip_axes.append(axp)
        q_t = q_at(tt)
        Rg = R_yaw @ _pelvis_in_ground(geo, q_t)
        for k, sd in enumerate(strip_sides):
            _draw_skeleton(axp, geo, q_t, sd, keep_axes=(k > 0),
                           color=SIDE_COLOR[sd], R_ground=Rg,
                           # frontal: camera IN FRONT of the subject, so their
                           # right leg is on the viewer's left (as a clinician
                           # facing them, and as an AP radiograph, sees it)
                           azim=(180.0 if plane == "frontal" else -90.0))
        _note = ev_meta[ename].note if ename in ev_meta else ""
        # slide the panel so the event's own landmark sits ON the dashed line:
        # a foot-strike pose whose foot is 3 cm to the left of its own marker
        # reads as a different instant
        if _want:
            # Landmarks come from the POSED MESH, not from joint frames.
            # In this model chain_pose returns ~zero translation (the mesh
            # vertices carry the position), so every joint-frame landmark
            # resolved to the pelvis -- which is why the poses lined up on the
            # pelvis instead of the knee. The drawn geometry cannot lie.
            _pt = None
            if _want == "tibia":                      # the KNEE: distal femur
                _fs = geo.mesh_faces(f"femur_{cyc_side}", ("femur",))
                _fp = geo.chain_pose(f"femur_{cyc_side}", "pelvis", q_t)
                if _fs and _fp is not None:
                    _v = _pose(_tri(_fs), *_fp).reshape(-1, 3)
                    _d = np.linalg.norm(_v - _v.mean(axis=0), axis=1)
                    _far = _v[_d >= np.percentile(_d, 92)]
                    # of the two ends, the knee is the one nearer the shank
                    _ts = geo.mesh_faces(f"tibia_{cyc_side}", ("tibia",))
                    _tp = geo.chain_pose(f"tibia_{cyc_side}", "pelvis", q_t)
                    if _ts and _tp is not None:
                        _tv = _pose(_tri(_ts), *_tp).reshape(-1, 3).mean(axis=0)
                        _pt = _far[np.argmin(np.linalg.norm(_far - _tv, axis=1))]
                    else:
                        _pt = _far.mean(axis=0)
            else:                                     # the FOOT
                _fs = geo.mesh_faces(f"calcn_{cyc_side}", ("foot",))
                _fp = geo.chain_pose(f"calcn_{cyc_side}", "pelvis", q_t)
                if _fs and _fp is not None:
                    _pt = _pose(_tri(_fs), *_fp).reshape(-1, 3).mean(axis=0)
            if _pt is not None:
                _pt = (np.asarray(Rg) @ np.asarray(_pt, float))[_TO_PLOT]
            _pose_ok = _pt is not None
            if _pose_ok:

                from mpl_toolkits.mplot3d import proj3d as _p3
                _ext = np.vstack(_drawn) if _drawn else None
                # PROJECT the landmark: a 3-D axes with a box_aspect does not
                # fill its own box, so working the fraction out from get_xlim()
                # lands the panel a few percent off every time.
                fig.canvas.draw()

                def _screen_x(pt):
                    _sx, _sy, _ = _p3.proj_transform(pt[0], pt[1], pt[2],
                                                     axp.get_proj())
                    return float(axp.transData.transform((_sx, _sy))[0])

                # Measure against the DRAWING, not the axes box: a 3-D axes
                # with a box_aspect leaves margins, so a fraction of the axes
                # width is not a fraction of the skeleton -- which is why the
                # panels kept landing a few percent off.
                _xd = _screen_x(_pt)
                if _ext is not None and len(_ext) > 1:
                    _lo = _screen_x([_ext[:, 0].min(), _pt[1], _pt[2]])
                    _hi = _screen_x([_ext[:, 0].max(), _pt[1], _pt[2]])
                else:
                    _lo, _hi = _xd - 1.0, _xd + 1.0
                _f = float(np.clip((_xd - _lo) / max(_hi - _lo, 1e-9), 0.0, 1.0))
                # CLOSE THE LOOP instead of modelling the projection: place the
                # panel, measure where the landmark actually landed in pixels,
                # shift by the error, repeat. Two passes get it under a pixel,
                # and it cannot drift the way an open-loop formula does.
                _left = min(max(_x - _f * _w, 0.0), 1.0 - _w)
                axp.set_position([_left, _row.y0, _w, _row.height])
                _target = axc.transData.transform((tt, 0.0))[0]
                for _it in range(3):
                    fig.canvas.draw()
                    _err = _screen_x(_pt) - _target
                    if abs(_err) < 1.0:
                        break
                    _left = min(max(_left - _err / fig.bbox.width, 0.0), 1.0 - _w)
                    axp.set_position([_left, _row.y0, _w, _row.height])
                if os.environ.get("BIOSCOUT_ALIGN_DEBUG"):
                    fig.canvas.draw()
                    print(f"[align] {ename:14} pt_x={_pt[0]:7.1f} f={_f:.3f} "
                          f"left={_left:.4f} residual="
                          f"{_screen_x(_pt) - _target:+6.1f}px after {_it + 1} pass(es)")
        _let = ev_meta[ename].letter if ename in ev_meta else ""
        axp.text2D(0.5, -0.02,
                   ename + (f"$^{{{_let}}}$" if _let else ""),
                   transform=axp.transAxes,
                   ha="center", va="top", fontsize=8.5, color="#333",
                   linespacing=1.3)

    # what the letters mean, once (drawn at the very end, with the knee note)
    _knee_note = {}
    _key = [f"$^{{{e.letter}}}$ {e.name}: {e.label}"
            + (f"  [{e.note}]" if e.note else "")
            for n, _ in ev if n in ev_meta for e in [ev_meta[n]] if e.letter]
    if _key:
        # under the last row, not in the strip: the first pose sits above
        # its (early) event, i.e. exactly in the strip's top-left corner,
        # and the key was written across its meshes.
        pass  # drawn after the panel rows, once _knee_note is known

    # Events cluster in stance (impact peak and mid stance are ~50 ms apart),
    # and two poses drawn on top of each other read as one wrong pose. Push
    # neighbours apart to a minimum gap; the leaders below still tie each
    # pose to its own event, so a pose that had to move is not mislabelled.
    # A STANCE pose is anchored: its foot on the plate must sit on its GRF
    # line, that is the one alignment the reader checks. Swing poses yield:
    # they slide outwards (away from the nearest anchored pose) as far as
    # the strip allows; two anchored poses that collide are left alone.
    _gap = 0.92 * _w
    _lefts = [ax_.get_position().x0 for ax_ in strip_axes]
    _fixed = [n in ev_meta and ev_meta[n].landmark == "calcn" for n, _ in ev]
    for _pass in range(3):
        for _i in range(len(_lefts)):
            if _fixed[_i]:
                continue
            lo = max([_lefts[j] + _gap for j in range(_i) ] + [0.0])
            hi = min([_lefts[j] - _gap for j in range(_i + 1, len(_lefts))]
                     + [1.0 - _w])
            # an anchored neighbour on one side: move away from it; on both
            # sides: sit between them (overlap is then unavoidable)
            if lo <= hi:
                _lefts[_i] = min(max(_lefts[_i], lo), hi)
            else:
                _lefts[_i] = 0.5 * (lo + hi)
    for ax_, _l in zip(strip_axes, _lefts):
        ax_.set_position([_l, _row.y0, _w, _row.height])

    # ---- the grid: (joint, side) x event ---------------------------------
    metrics = {"subject": info["subject"], "session": info["session"],
               "iteration": info["iteration"], "trial": info["trial"].name,
               "source": label, "force_unit": unit, "spread_deg": spread_deg,
               "patch_mm": patch_mm, "full_cycle": full, "cycle_name": cycle_name,
               "plane": plane,
               "cycle": f"{t0:.3f}-{t1:.3f}s", "cycle_side": cyc_side,
               "cycle_covered_pct": round(100 * covered, 1),
               "events": ", ".join(n for n, _ in ev)}
    mri = {sd: _mri_hip(info, sd, geo, by_side[sd], ik_names, ik_data, degrees, t_jra)
           for sd in by_side}
    metrics["alignment"] = next((m["align"] for m in mri.values() if m), "no MRI meshes")

    # ---- the grid: (joint, side) x event, polar like jcf_angle_sagittal ----
    from bioscout.plot.jcf_direction import (panel_bones, panel_moving,
                                             panel_spec, bone_scale, draw_bone,
                                             nice_ceiling, hip_to_pelvis,
                                             joint_kind)
    from bioscout.plot.jcf_direction import PLANES
    COLS = PLANES[plane]["cols"]        # sagittal (ANT, SUP) or frontal (LAT, SUP)
    DIR_NAMES = PLANES[plane]["dirs"]

    # every cell shares ONE rim, so the loops are comparable across joints and
    # across events -- that comparability is the point of the layout
    traces, rim = {}, 0.0
    # --add_polygon: the muscle-group contributions of run_jra_contributions
    contrib_df = load_contributions(jra, label) if add_polygon else None
    polygons, _poly_used, _poly_skipped = {}, {}, set()
    if add_polygon and contrib_df is None:
        print(f"  ! {label}: --add_polygon asked for, but there is no "
              f"contributions_{label.lower()}.sto next to the JRA "
              f"file -- run the JCF contributions first; drawing plain arrows")
    for sd, js in by_side.items():
        for kind2, spec in js.items():
            jn, body, F, _m = spec["loads"][0]
            frame_body, Fp = body, F
            if kind2 == "hip":
                conv = hip_to_pelvis(geo, jn, F, ik_names, ik_data, degrees)
                if conv is not None:
                    Fp = conv
                    frame_body = geo.joints[jn]["parent"]["body"]
            r = np.linalg.norm(Fp, axis=0) / scale
            th = np.arctan2(Fp[COLS[0]], Fp[COLS[1]])
            traces[(sd, kind2)] = (jn, frame_body, r, th)
            if contrib_df is not None:
                _n = Fp.shape[1]
                _cs = {}
                for _src, _C in _contribution_series(
                        contrib_df, f"{kind2}_{sd}", t_jra).items():
                    if Fp is not F:      # the hip: same femur -> pelvis step
                        _C = hip_to_pelvis(geo, jn, _C, ik_names, ik_data, degrees)
                    _cs[_src] = _C[[COLS[0], COLS[1]], :_n] / scale
                if _cs:
                    polygons[(sd, kind2)] = _cs
            rim = max(rim, float(np.nanmax(r)))
    rim = nice_ceiling(rim)
    metrics["rim_%s" % unit] = rim

    col_axes = []
    for pi, (panel, kinds) in enumerate(panels_here):
        prows = [sd for p, sd in rows if p == panel]
        if not prows:
            continue
        sg = outer[2 + pi, :].subgridspec(len(prows), ncol, hspace=0.02, wspace=0.04)
        for ri, sd in enumerate(prows):
            js = by_side[sd]
            here = [k for k in kinds if k in js]
            if not here:
                continue
            kind2 = here[0]
            jn, frame_body, r, th = traces[(sd, kind2)]
            pspec = (_pf_spec(sd) if panel == "patellofemoral"
                     else panel_spec(_spec_kind(panel), sd))
            bframe = _bone_frame(panel, sd, frame_body)
            for c, (ename, tt) in enumerate(list(ev) + [("full cycle", None)]):
                ax = fig.add_subplot(sg[ri, c], projection="polar")
                if pi == 0 and ri == 0 and c < len(ev):
                    col_axes.append(ax)
                whole = tt is None
                lbl = ""
                if whole:
                    tt = float(t_jra[int(np.argmax(r))])   # pose at the peak
                ax.set_theta_zero_location("N")
                ax.set_theta_direction(-1)
                ax.set_ylim(0, rim)
                q = q_at(tt)
                faces = panel_bones_of(geo, _spec_kind(panel), sd,
                                       bframe, COLS)
                # the knee panel needs the WHOLE femur so the clip below can
                # take its distal third; the spec would hand us 16% already
                _keep = 1.0 if panel.startswith("knee") else None
                moving = (panel_moving_of(geo, _spec_kind(panel), sd,
                                          bframe, q, COLS, keep=_keep)
                          if pspec.get("moving") else [])
                # the DISTAL THIRD of the whole femur: the third NEAREST the
                # tibia, not the "lower" third -- at mid swing the knee is
                # flexed 90 deg and the distal end is not the lower end.
                if moving and panel.startswith("knee") and faces:
                    moving = _clip_toward(moving, 0.33,
                                          np.vstack(faces).mean(axis=0))
                # the knee panel is tibia + femur + PATELLA: leaving the patella
                # out of a sagittal knee drops the bone the PF force acts on
                if panel.startswith("knee"):
                    _pf = geo.mesh_faces(f"patella_{sd}", ("patella",))
                    _pp = (geo.chain_pose(f"patella_{sd}", bframe, q)
                           if _pf else None)
                    if _pp is not None:
                        _R, _t = _pp
                        faces = list(faces) + [(f @ np.asarray(_R).T
                                                + np.asarray(_t))[:, list(COLS)]
                                               for f in _pf]
                k = bone_scale([faces, moving], rim)
                draw_bone(ax, faces, k)
                if moving:
                    draw_bone(ax, moving, k, color="0.86")
                i_ev = int(np.argmin(np.abs(t_jra - tt)))
                peak_here = float(r[i_ev])
                if whole:
                    # the last column: the path over the whole cycle, with the
                    # start and the end marked, as in jcf_angle_sagittal
                    rr = np.where(r <= rim, r, np.nan)
                    ax.plot(np.unwrap(th), rr, color=SIDE_COLOR[sd], lw=1.5,
                            zorder=4, solid_capstyle="round")
                    ok = np.flatnonzero(np.isfinite(rr) & np.isfinite(th))
                    for i, mk, ms in ((ok[0], "o", 5.0),
                                      (ok[-1], "X", 6.0)) if ok.size else ():
                        ax.plot([th[i]], [rr[i]], marker=mk, ms=ms,
                                color=SIDE_COLOR[sd], mec="w", mew=0.8,
                                ls="none", zorder=6)
                    peak_here = float(np.nanmax(r))
                    # a condylar knee: the peak of EACH contact over the cycle,
                    # in the same order as the event cells (med · lat · PF)
                    if len(here) > 1:
                        lbl = "  ".join(f"{np.nanmax(traces[(sd, k2)][2]):.1f}"
                                        for k2 in here)
                else:
                    # One arrow per CONTACT the panel carries: a condylar knee
                    # has tibiofemoral and patellofemoral loads in the same
                    # bones, and splitting them across rows hides that they act
                    # together. Solid = tibiofemoral, dashed = patellofemoral.
                    vals = []
                    for ki, k2 in enumerate(here):
                        _jn, _fb, r2, th2 = traces[(sd, k2)]
                        if i_ev >= len(r2):
                            continue
                        v = float(r2[i_ev])
                        vals.append((k2, v))
                        # the arrow starts where the contact ACTS: the patella
                        # for the PF force, the tibial plateau for the
                        # tibiofemoral ones. Everything else starts at the
                        # joint centre, which is the polar origin.
                        _base = (0.0, 0.0)
                        _spec_at = _APPLY_AT.get(k2)
                        if _spec_at and k:
                            _bd, _fl = _spec_at
                            _fs = geo.mesh_faces(f"{_bd}_{sd}", _fl)
                            _bp = (geo.chain_pose(f"{_bd}_{sd}", bframe, q)
                                   if _fs else None)
                            if _bp is not None:
                                _c = _tri(_fs).reshape(-1, 3)
                                _c = (_c @ np.asarray(_bp[0]).T
                                      + np.asarray(_bp[1]))[:, list(COLS)]
                                # the plateau is the PROXIMAL tibia, not the
                                # whole bone's centroid
                                _pick = (_c[:, 1] >= np.percentile(_c[:, 1], 85)
                                         if _bd == "tibia"
                                         else np.ones(len(_c), bool))
                                _m2 = _c[_pick].mean(axis=0)
                                _br = float(np.hypot(*_m2) * k)
                                # CLIP: an unclipped base radius pushes the
                                # annotation outside the axes, and a tight
                                # bbox then tries to allocate a canvas big
                                # enough to hold it (std::bad_alloc).
                                # the ORIGIN moves to the plateau/patella;
                                # the arrow's LENGTH stays the magnitude on the
                                # shared rim. Keep the base well inside the rim
                                # so the vector has room to be read.
                                if np.isfinite(_br):
                                    _base = (math.atan2(_m2[0], _m2[1]),
                                             min(_br, 0.25 * rim))
                        _tipr = min(v, rim)
                        _x2 = _base[1] * math.sin(_base[0]) + _tipr * math.sin(th2[i_ev])
                        _y2 = _base[1] * math.cos(_base[0]) + _tipr * math.cos(th2[i_ev])
                        _tr = float(np.hypot(_x2, _y2))
                        if not np.isfinite(_tr):
                            continue
                        _poly = False
                        _cs = polygons.get((sd, k2))
                        if _cs:
                            _parts = [(n_, c_[:, i_ev]) for n_, c_ in _cs.items()
                                      if i_ev < c_.shape[1]]
                            _sum = sum(v_ for _n, v_ in _parts)
                            _tot = np.array([v * math.sin(th2[i_ev]),
                                             v * math.cos(th2[i_ev])])
                            # only draw a chain that CLOSES on this arrow: a
                            # GPK condyle is not the joint the csv decomposed
                            if np.hypot(*(_sum - _tot)) <= 0.02 * v + 0.02:
                                _pp = _polygon_parts(_parts, polygon_top)
                                _u, _end = _force_polygon(
                                    ax, (_base[1] * math.sin(_base[0]),
                                         _base[1] * math.cos(_base[0])), _pp)
                                _poly_used.update(_u)
                                _poly = True
                                _big = max((p_ for p_ in _pp
                                            if p_[0] not in ("Non-muscle", "other")),
                                           key=lambda p_: float(np.hypot(*p_[1])),
                                           default=None)
                                if _big:
                                    metrics[f"{k2}_{sd}_{ename.replace(' ', '_')}"
                                            f"_top_muscle"] = _big[0]
                            else:
                                _poly_skipped.add(k2)
                        elif add_polygon and contrib_df is not None:
                            _poly_skipped.add(k2)
                        # do NOT clip the tip to the rim: clipping the radius
                        # bends the arrow's direction, which is the one thing
                        # it exists to show. The polar axes clips it visually.
                        ax.annotate("", xy=(math.atan2(_x2, _y2), _tr),
                                    xytext=_base,
                                    arrowprops=dict(
                                        arrowstyle="-|>",
                                        lw=1.0 if _poly else 2.0 - 0.6 * ki,
                                        color="#222" if _poly else SIDE_COLOR[sd],
                                        shrinkA=0,
                                        shrinkB=0, alpha=1.0 - 0.25 * ki,
                                        linestyle="-" if ki == 0 else (0, (3, 2))),
                                    zorder=6, annotation_clip=False)
                    if vals:
                        peak_here = max(v for _k, v in vals)
                        lbl = "  ".join(f"{v:.1f}" for _k, v in vals)
                metrics[f"{kind2}_{sd}_{ename.replace(' ', '_')}_{unit}"] = \
                    round(peak_here, 2)
                step = nice_ceiling(rim / 3.0)
                ax.set_yticks(np.arange(step, rim, step))
                first = (pi == 0 and ri == 0 and c == 0)
                ax.set_yticklabels([f"{v:g} {unit}" for v in
                                    np.arange(step, rim, step)] if first else [],
                                   fontsize=6)
                ax.set_rlabel_position(pspec.get("rlabel", 135))
                ax.set_thetagrids([0, 90, 180, 270], labels=[""] * 4)
                if first:
                    for tdeg, lab in zip((0, 90, 180, 270), DIR_NAMES):
                        ax.text(math.radians(tdeg), rim * 0.80, lab,
                                ha="center", va="center", fontsize=6, zorder=7,
                                bbox=dict(fc="white", ec="none", alpha=0.85,
                                          pad=0.8))
                ax.grid(color="0.78", lw=0.5, zorder=2)
                ax.spines["polar"].set_color("0.5")
                if whole and pi == 0 and ri == 0:
                    ax.set_title("full cycle", fontsize=7, color="#555", pad=4)
                if c == 0:
                    _star = "*" if (panel.startswith("knee") and len(here) > 1) else ""
                    ax.text(-0.10, 0.5, f"{panel} {sd.upper()}{_star}",
                            transform=ax.transAxes, rotation=90, va="center",
                            ha="center", fontsize=8, color=SIDE_COLOR[sd])
                    if _star and sd not in _knee_note:
                        _knee_note[sd] = (
                            "* knee values: " + " · ".join(here)
                            + f"  (peak |F| in {unit} at the event; solid arrow = "
                            + here[0] + ", dashed = the others)")
                ax.text(0.5, -0.06,
                        lbl if len(here) > 1 else f"{peak_here:.1f}",
                        transform=ax.transAxes, ha="center", fontsize=7,
                        color=SIDE_COLOR[sd])

    # no colourbar: the radial axis IS the force scale, and a second, unused
    # scale next to it only invites the reader to look for a colour meaning
    # The columns are evenly spaced; the events are not. Without a line from
    # each event's GRF marker to its column, the reader matches them by
    # position and gets it wrong -- "impact peak" sits above the LEFT foot's
    # stance. These leaders say which column belongs to which instant.
    import matplotlib.lines as _mlines
    for (name, tt), axc_top, axc_bot in zip(ev, strip_axes, col_axes):
        x_grf = axc.transData.transform((tt, 0.0))[0]
        y_lo = axc.get_window_extent().y0
        y_hi = axc.get_window_extent().y1
        for target, y_from, y_to in (
                (axc_bot, y_lo, axc_bot.get_window_extent().y1),
                (axc_top, y_hi, axc_top.get_window_extent().y0)):
            bb = target.get_window_extent()
            x_col = 0.5 * (bb.x0 + bb.x1)
            p0 = fig.transFigure.inverted().transform((x_grf, y_from))
            p1 = fig.transFigure.inverted().transform((x_col, y_to))
            fig.add_artist(_mlines.Line2D([p0[0], p1[0]], [p0[1], p1[1]],
                                          transform=fig.transFigure,
                                          color="#aaa", lw=0.7, ls=(0, (3, 3)),
                                          zorder=0))
    fig.suptitle(f"{info['subject']} {info['session']} · {info['trial'].name} · "
                 f"{info['iteration']} · {label} · {plane}  —  {cycle_name}"
                 f"{'' if full else f' — only {covered * 100:.0f}% of it is simulated'}"
                 f"  {t0:.2f}-{t1:.2f}s, ±{window_ms:.0f} ms per event", fontsize=10)
    out = (Path(out) if out else
           info["out_dir"] / _jrf_coverage(label, plane))
    out.parent.mkdir(parents=True, exist_ok=True)
    _foot = list(_key) + list(_knee_note.values())
    if _poly_used:
        import matplotlib.lines as _ml
        fig.legend(handles=[_ml.Line2D([], [], color=c_, lw=2.6, label=n_,
                                       solid_capstyle="round")
                            for n_, c_ in _poly_used.items()],
                   loc="upper left", bbox_to_anchor=(0.005, 0.0), ncol=8,
                   fontsize=6.5, frameon=False, handlelength=1.6,
                   columnspacing=1.2, title="contribution to the contact force",
                   title_fontsize=6.5)
        _foot.append(
            "force polygon: the coloured chain adds up, head to tail, to the thin "
            f"black resultant (non-muscle first, then the {polygon_top} largest "
            "muscle groups at that instant, then the pooled rest); clipped at "
            "the rim" + (f"  ·  no polygon for: {', '.join(sorted(_poly_skipped))} "
                         "(not the joint the contributions were computed on)"
                         if _poly_skipped else ""))
    metrics["polygon"] = bool(_poly_used)
    if _foot:
        fig.text(0.01, 0.005, "\n".join(_foot), ha="left", va="bottom",
                 fontsize=6.5, color="#444", linespacing=1.5)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    metrics["figure"] = str(out)
    return metrics


def _q_maker(ik_names, ik_data, degrees, model):
    """t -> the model's coordinates at that instant (coupled ones included)."""
    def q_at(tt):
        i = int(np.argmin(np.abs(ik_data[:, 0] - tt)))
        q = {}
        for nm in ik_names[1:]:
            v = float(ik_data[i, ik_names.index(nm)])
            # only the pelvis TRANSLATIONS are lengths; pelvis_tilt is an angle
            trans = nm in ("pelvis_tx", "pelvis_ty", "pelvis_tz")
            q[nm] = math.radians(v) if (degrees and not trans) else v
        return coupled_coordinates(model, q)
    return q_at


def _draw_skeleton(ax, geo, q, side, keep_axes=False, color=None, tilt_deg=0.0,
                   R_ground=None, azim=-90.0):
    """The whole limb at one instant, small, for the sequence strip."""
    if not keep_axes:
        _drawn.clear()
    bones = ((f"femur_{side}", ("femur",)),) if keep_axes else (
        ("pelvis", ("pelvis", "sacrum")), (f"femur_{side}", ("femur",)))
    for body, filt in bones + ((
                       f"tibia_{side}", ("tibia",)), (f"patella_{side}", ("patella",)),
                       (f"talus_{side}", ("talus",)), (f"calcn_{side}", ("foot",))):
        faces = geo.mesh_faces(body, filt)
        pose = geo.chain_pose(body, "pelvis", q)
        if faces and pose is not None:
            tris = _pose(_tri(faces), *pose)
            if R_ground is not None:
                tris = tris @ np.asarray(R_ground, float).T
            pc = _draw(ax, tris, alpha=0.5)
            if pc is not None and color and body != "pelvis":
                pc.set_facecolor(color)
                pc.set_alpha(0.35)
    if not _drawn:
        return
    pts = np.vstack(_drawn)
    lo, hi = pts.min(axis=0) - 2, pts.max(axis=0) + 2
    ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(tuple(hi - lo))
    ax.view_init(elev=0, azim=azim)         # as in the OpenSim GUI
    ax.set_proj_type("ortho")
    _bare(ax)


def _mri_hip(info, side, geo, joints, ik_names, ik_data, degrees, t_jra):
    """The MRI head/acetabulum in the pelvis frame, plus the hip load in it."""
    from bioscout.model.measure import (load_mesh, fit_head_sphere, find_hip_meshes,
                                        mri_to_pelvis_rotation, read_landmarks)
    if not info.get("mri_dir") or "hip" not in joints:
        return None
    f = find_hip_meshes(info["mri_dir"], side)
    if not (f["acetabulum"] and f["femoral_head"]):
        return None
    acet, head = load_mesh(f["acetabulum"]), load_mesh(f["femoral_head"])
    c, r, rms = fit_head_sphere(head.vertices)
    Rm, align = np.eye(3), "none (MRI meshes in scanner orientation)"
    if info.get("landmarks"):
        Rm = mri_to_pelvis_rotation(read_landmarks(info["landmarks"]))
        align = "pelvic landmarks (anterior pelvic plane)"
    jname, _, Fh, mh = joints["hip"]["loads"][0]
    qs = {}
    for axis, coord in geo.joints[jname]["axes"]:
        if coord and coord in ik_names:
            v = ik_data[:, ik_names.index(coord)]
            qs[coord] = np.radians(v) if degrees else v
    if not qs:
        return None
    n = min(Fh.shape[1], min(len(v) for v in qs.values()))
    Rot = geo.joint_rotation(jname, {k: v[:n] for k, v in qs.items()})
    Facet = -np.einsum("nij,jn->in", Rot, Fh[:, :n])
    hjc = np.asarray(geo.joints[jname]["parent"]["t"], float) * 1000.0
    shift = hjc - c
    return {"head": _tri([head.vertices[t] / 1000.0 for t in head.faces]) + shift,
            "acet": _tri([acet.vertices[t] / 1000.0 for t in acet.faces]) + shift,
            "u": Rm.T @ (Facet / np.linalg.norm(Facet, axis=0)),
            "mag": mh[:n], "centre": hjc, "r": float(r), "align": align,
            "rms": float(rms)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="bioscout plot jcf_coverage",
        description="where a trial's joint contact forces land on the bones")
    ap.add_argument("trial", metavar="TRIAL",
                    help="simulations/<S>/<session>/3_iterations/<it>/<trial>")
    ap.add_argument("--side", nargs="+", choices=["r", "l"],
                    help="joints to draw (default: the analysed leg only)")
    ap.add_argument("--model", metavar="OSIM")
    ap.add_argument("--mass", type=float, metavar="KG")
    ap.add_argument("--mri-root", metavar="DIR")
    ap.add_argument("--plane", nargs="+", default=["sagittal", "frontal"],
                    choices=["sagittal", "frontal"],
                    help="which plane(s) to draw (default: both)")
    ap.add_argument("--spread", type=float, default=25.0, metavar="DEG")
    ap.add_argument("--tilt", type=float, default=60.0, metavar="DEG",
                    help="rotation of the anatomy row away from sagittal (default 60)")
    ap.add_argument("--patch", type=float, default=16.0, metavar="MM",
                    help="knee/ankle contact patch radius around the joint centre "
                         "(default 16)")
    ap.add_argument("--window", type=float, default=30.0, metavar="MS",
                    help="half-window around each event that the patch sums over "
                         "(default 30 ms)")
    ap.add_argument("--cycle-side", choices=["r", "l"],
                    help="the leg whose foot-off to foot-off cycle frames the "
                         "figure (default: 'Measured Leg' from "
                         "subject_demographics.csv, else right)")
    ap.add_argument("--events", nargs="+", metavar="NAME",
                    help="keep only these events, e.g. 'foot strike' 'active peak'")
    ap.add_argument("--joints", nargs="+", metavar="PANEL",
                    choices=[n for n, _ in PANELS],
                    help="panels to draw (default: every joint with a force)")
    ap.add_argument("--add_polygon", "--add-polygon", dest="add_polygon",
                    action="store_true",
                    help="decompose each contact-force arrow into a head-to-tail "
                         "chain of muscle-group contributions (needs "
                         "joint_contact_forces/contributions_<source>/"
                         "contributions_<t>.sto from the JCF contributions run; "
                         "falls back to the plain arrow without it)")
    ap.add_argument("--polygon-top", type=int, default=6, metavar="N",
                    help="muscle groups drawn individually per arrow, the rest "
                         "are pooled as 'other' (default 6)")
    ap.add_argument("-o", "--out-dir", metavar="DIR")
    ns = ap.parse_args(argv)

    info = discover(ns.trial, model=ns.model, mass=ns.mass, mri_root=ns.mri_root)
    print(f"{info['subject']} {info['session']} {info['iteration']} "
          f"{info['trial'].name}: {', '.join(info['sources'])}"
          f"{'' if info['mri_dir'] else '  (no MRI meshes found)'}"
          f"{'' if info['landmarks'] else '  (no landmarks)'}")
    bad = 0
    for label in info["sources"]:
        for plane in ns.plane:
            try:
                m = jcf_coverage_figure(
                    {**info, "joints": ns.joints, "cycle_side": ns.cycle_side},
                    label,
                    out=(Path(ns.out_dir) / _jrf_coverage(label, plane))
                    if ns.out_dir else None,
                    spread_deg=ns.spread, patch_mm=ns.patch,
                    window_ms=ns.window, events=ns.events,
                    sides=tuple(ns.side) if ns.side else None, plane=plane,
                    add_polygon=ns.add_polygon, polygon_top=ns.polygon_top)
            except Exception as e:                       # noqa: BLE001
                print(f"  ✗ {label} {plane}: {e}")
                bad += 1
                continue
            print(f"  ✓ {label} {plane}: {m['cycle']}"
                  f"{'' if m['full_cycle'] else ' (window shorter than a cycle)'}"
                  f" → {m['figure']}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
