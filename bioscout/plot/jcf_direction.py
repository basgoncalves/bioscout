"""Polar plot of joint contact force DIRECTION and magnitude, on the model's bones.

One polar panel per joint. The BEARING is the direction of the contact force in
one anatomical plane of the receiving bone's reference frame (SUP up, ANT right
on the sagittal view); the RADIUS is the magnitude of the resultant, in body
weights when a body weight is given. A loop is therefore the contact-force
vector itself, traced over the trial. The grey silhouette behind each panel is
that bone, read out of the .osim itself (mesh file, scale factors, offset
frames) — its angles are exact, its radial size is arbitrary. With ``--ik`` the
neighbouring segment is also drawn dotted at the two extremes of its motion,
with a range-of-motion arc at the rim.

Works from any OpenSim JointReaction output — the analysis must have been run
with the reaction applied to the CHILD body and expressed in the CHILD frame
(OpenSim's default), giving columns like ``hip_r_on_femur_r_in_femur_r_fx``.

From a script::

    from bioscout.plot.jcf_direction import plot_jcf_direction
    plot_jcf_direction("model.osim",
                       {"SO": "jra_so.sto", "CEINMS": "jra_ceinms.sto"},
                       mass=95, ik="joint_angles.mot", out="jcf_direction.png")

From the terminal::

    bioscout plot jcf --model model.osim --jra jra_so.sto jra_ceinms.sto \
        --labels SO CEINMS --mass 95 --ik joint_angles.mot -o jcf_direction.png

The hip is special: OpenSim writes the hip reaction ON the femur IN the femur
frame. With ``--ik`` (the IK .mot of the same trial) the force is converted,
exactly, to the femoral head ON the acetabulum in the PELVIS frame — Newton's
third law for the sign and the hip joint's own SpatialTransform rotation for
the frame. Without ``--ik`` the hip is plotted as written (femur frame) and the
panel title says so.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import xml.etree.ElementTree as ET

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.collections as mcoll
import matplotlib.lines as mlines


# --------------------------------------------------------------------------- #
# .sto / .mot reading
# --------------------------------------------------------------------------- #
def read_sto(path):
    """OpenSim storage file -> (names list, (N, C) array)."""
    with open(path) as fh:
        lines = fh.readlines()
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip().lower() == "endheader":
            start = i + 1
            break
        if ln.split() and ln.split()[0] == "time":
            start = i
            break
    names = lines[start].split()
    data = np.loadtxt(lines[start + 1:], ndmin=2)
    return names, data


FORCE_RE = re.compile(r"^(?P<joint>.+)_on_(?P<body>.+)_in_(?P<frame>.+)_fx$")


def force_triplets(names):
    """{joint: (body, frame, [ix, iy, iz])} for every *_on_*_in_*_f{x,y,z}."""
    out = {}
    for i, n in enumerate(names):
        m = FORCE_RE.match(n)
        if not m:
            continue
        stem = n[:-2]
        try:
            idx = [names.index(stem + a) for a in ("fx", "fy", "fz")]
        except ValueError:
            continue
        out[m["joint"]] = (m["body"], m["frame"], idx)
    return out


# --------------------------------------------------------------------------- #
# the model as geometry: meshes, frames, joint transforms (plain XML, no API)
# --------------------------------------------------------------------------- #
def euler_xyz(a, b, c):
    ca, sa, cb, sb, cc, sc = np.cos(a), np.sin(a), np.cos(b), np.sin(b), np.cos(c), np.sin(c)
    Rx = np.array([[1, 0, 0], [0, ca, -sa], [0, sa, ca]])
    Ry = np.array([[cb, 0, sb], [0, 1, 0], [-sb, 0, cb]])
    Rz = np.array([[cc, -sc, 0], [sc, cc, 0], [0, 0, 1]])
    return Rx @ Ry @ Rz


def axis_rotation(axis, q):
    u = np.asarray(axis, float)
    n = np.linalg.norm(u)
    if n == 0:
        return np.broadcast_to(np.eye(3), (np.size(q), 3, 3)).copy()
    u = u / n
    q = np.atleast_1d(np.asarray(q, float))
    c, s = np.cos(q), np.sin(q)
    K = np.array([[0, -u[2], u[1]], [u[2], 0, -u[0]], [-u[1], u[0], 0]])
    return (np.eye(3)[None] + s[:, None, None] * K[None]
            + (1 - c)[:, None, None] * (K @ K)[None])


FUNCTION_TAGS = ("Constant", "LinearFunction", "SimmSpline",
                 "NaturalCubicSpline", "PiecewiseLinearFunction",
                 "MultiplierFunction")


def transform_function(axis_node):
    """A <TransformAxis> function as a plain callable f(q) -> float. Splines
    are linearly interpolated between their knots — good enough for a
    background drawing, not for driving a simulation."""
    fn = next((c for c in axis_node if c.tag in FUNCTION_TAGS), None)
    if fn is None:
        return lambda q: 0.0
    if fn.tag == "Constant":
        v = float(_text(fn, "value", "0") or 0)
        return lambda q, v=v: v
    if fn.tag == "LinearFunction":
        c = np.fromstring(_text(fn, "coefficients", "1 0"), sep=" ")
        c = c if c.size == 2 else np.array([1.0, 0.0])
        return lambda q, c=c: c[0] * q + c[1]
    if fn.tag == "MultiplierFunction":
        scale = float(_text(fn, "scale", "1") or 1)
        inner = fn.find("function")
        sub = transform_function(inner if inner is not None else fn)
        return lambda q, s=scale, f=sub: s * f(q)
    x = np.fromstring(_text(fn, "x"), sep=" ")
    y = np.fromstring(_text(fn, "y"), sep=" ")
    if x.size < 2 or x.size != y.size:
        return lambda q: 0.0
    return lambda q, x=x, y=y: float(np.interp(q, x, y))


def _text(node, tag, default=""):
    return (node.findtext(tag) or default).strip()


def _vec(node, tag, default=(0.0, 0.0, 0.0)):
    s = _text(node, tag)
    return np.fromstring(s.replace(",", " "), sep=" ") if s else np.array(default, float)


class OsimModel:
    """Meshes, offset frames and joint transforms of an .osim — hand-rolled XML
    so the plot needs no OpenSim install."""

    def __init__(self, path, geometry=None):
        self.path = path
        self.geometry = geometry            # extra folder(s) to search for .vtp
        self.root = ET.parse(path).getroot()
        self.bodies, self.joints = {}, {}
        self._mesh_cache = {}
        objs = self.root.find(".//BodySet/objects")
        for b in (objs if objs is not None else []):
            self.bodies[b.get("name")] = [
                (_text(m, "mesh_file"), _vec(m, "scale_factors", (1, 1, 1)))
                for m in b.iter("Mesh") if _text(m, "mesh_file")]
        objs = self.root.find(".//JointSet/objects")
        for j in (objs if objs is not None else []):
            frames = {f.get("name"): dict(body=_text(f, "socket_parent").split("/")[-1],
                                          t=_vec(f, "translation"),
                                          o=_vec(f, "orientation"))
                      for f in j.iter("PhysicalOffsetFrame")}
            pf = frames.get(_text(j, "socket_parent_frame"))
            cf = next((v for k, v in frames.items()
                       if k != _text(j, "socket_parent_frame")), None)
            if pf is None or cf is None:
                continue
            axes, spatial = [], []
            st = j.find(".//SpatialTransform")
            if st is not None:
                for ta in st:
                    kind = ta.get("name") or ""
                    spatial.append((kind, _vec(ta, "axis"),
                                    _text(ta, "coordinates"),
                                    transform_function(ta)))
                    if kind.startswith("rotation"):
                        axes.append((_vec(ta, "axis"), _text(ta, "coordinates")))
            else:
                # a PinJoint's motion is implied by its type, not spelled out
                coord = next((c.get("name") for c in j.iter("Coordinate")), "")
                if j.tag == "PinJoint" and coord:
                    z = np.array([0.0, 0.0, 1.0])
                    spatial = [("rotation1", z, coord, lambda q: q)]
                    axes = [(z, coord)]
            self.joints[j.get("name")] = dict(parent=pf, child=cf, axes=axes,
                                              spatial=spatial)

    # -- transforms --------------------------------------------------------
    def joint_transform(self, name, q=None):
        """(R, t) child body -> parent body at coordinates `q` (missing = 0)."""
        j = self.joints[name]
        q = q or {}
        Rp, Rc = euler_xyz(*j["parent"]["o"]), euler_xyz(*j["child"]["o"])
        Rj, tj = np.eye(3), np.zeros(3)
        for kind, axis, coord, fn in j.get("spatial", []):
            val = fn(float(q.get(coord, 0.0))) if coord else 0.0
            if kind.startswith("rotation"):
                Rj = Rj @ axis_rotation(axis, val)[0]
            else:
                n = np.linalg.norm(axis)
                if n:
                    tj = tj + val * (axis / n)
        Rot = Rp @ Rj @ Rc.T
        return Rot, j["parent"]["t"] + Rp @ tj - Rot @ j["child"]["t"]

    def joint_neutral(self, name):
        return self.joint_transform(name, None)

    def joint_rotation(self, name, q):
        """(N, 3, 3) rotation, child-frame vectors -> parent frame, at the
        coordinate arrays `q` (name -> radians). Axes and order are the
        joint's own SpatialTransform, not assumed."""
        j = self.joints[name]
        Rp, Rc = euler_xyz(*j["parent"]["o"]), euler_xyz(*j["child"]["o"])
        n = max((np.size(v) for v in q.values()), default=1)
        out = np.broadcast_to(np.eye(3), (n, 3, 3)).copy()
        for axis, coord in j["axes"]:
            vals = q.get(coord)
            if vals is not None:
                out = out @ axis_rotation(axis, np.broadcast_to(vals, (n,)))
        return Rp[None] @ out @ Rc.T[None]

    def chain_pose(self, frm, to, q=None):
        """(R, t) body `frm` -> body `to` at the pose `q`, walking the joints."""
        adj = {}
        for name, j in self.joints.items():
            p, c = j["parent"]["body"], j["child"]["body"]
            adj.setdefault(c, []).append((p, name, True))
            adj.setdefault(p, []).append((c, name, False))
        seen, stack = {frm}, [(frm, np.eye(3), np.zeros(3))]
        while stack:
            body, Rot, t = stack.pop()
            if body == to:
                return Rot, t
            for nxt, jname, up in adj.get(body, []):
                if nxt not in seen:
                    seen.add(nxt)
                    Rj, tj = self.joint_transform(jname, q)
                    if not up:
                        Rj, tj = Rj.T, -Rj.T @ tj
                    stack.append((nxt, Rj @ Rot, Rj @ t + tj))
        return None

    # -- meshes ------------------------------------------------------------
    def find_mesh(self, name):
        cands = [os.path.join(os.path.dirname(self.path), "Geometry", name),
                 os.path.join(os.path.dirname(self.path), name)]
        for g in ([self.geometry] if isinstance(self.geometry, str)
                  else (self.geometry or [])):
            cands.append(os.path.join(g, name))
        return next((c for c in cands if os.path.isfile(c)), None)

    def mesh_faces(self, body, only=None):
        """Faces of `body`'s display meshes, body coordinates, scaled.
        `only` filters by filename substring (a tuple = any of them); if it
        filters everything away the filter is dropped (mesh names vary across
        model families)."""
        only = (only,) if isinstance(only, str) else only
        for filt in (only, None):
            out = []
            for fname, scale in self.bodies.get(body, []):
                if filt and not any(f in fname for f in filt):
                    continue
                path = self.find_mesh(fname)
                faces = read_vtp(path, self._mesh_cache) if path else None
                if faces:
                    out += [f * scale for f in faces]
            if out:
                return out
        return []


def read_vtp(path, cache):
    """Faces of an ASCII vtkPolyData .vtp as a list of (n, 3) arrays."""
    if path in cache:
        return cache[path]
    out = None
    try:
        piece = ET.parse(path).getroot().find(".//Piece")
        da = piece.find("Points").find("DataArray")
        if (da.get("format") or "ascii") == "ascii":
            pts = np.fromstring(da.text.replace("\n", " "), sep=" ").reshape(-1, 3)
            arr = {d.get("Name"): d for d in piece.find("Polys").findall("DataArray")}
            conn = np.fromstring(arr["connectivity"].text.replace("\n", " "), sep=" ").astype(int)
            offs = np.fromstring(arr["offsets"].text.replace("\n", " "), sep=" ").astype(int)
            out, s = [], 0
            for e in offs:
                out.append(pts[conn[s:e]])
                s = e
    except Exception as exc:
        print(f"  [warn] cannot read {os.path.basename(path)}: {exc}")
    cache[path] = out
    return out


def keep_end(faces, frac, end="proximal", axis=1):
    """Keep the `frac` of a mesh nearest one end of its long axis — the joint
    end is the part the contact force acts on, so it is the part drawn."""
    if not faces or frac is None:
        return faces
    v = np.concatenate([f[:, axis] for f in faces])
    lo, hi = v.min(), v.max()
    if end == "proximal":
        cut = hi - frac * (hi - lo)
        return [f for f in faces if f[:, axis].mean() >= cut]
    cut = lo + frac * (hi - lo)
    return [f for f in faces if f[:, axis].mean() <= cut]


def silhouette_outline(faces, n=160):
    """Outer boundary of 2-D faces as polylines (rasterise, contour at 0.5)."""
    if not faces:
        return []
    from matplotlib.path import Path
    P = np.vstack(faces)
    x0, x1, y0, y1 = P[:, 0].min(), P[:, 0].max(), P[:, 1].min(), P[:, 1].max()
    pad = 0.05 * max(x1 - x0, y1 - y0, 1e-6)
    xs = np.linspace(x0 - pad, x1 + pad, n)
    ys = np.linspace(y0 - pad, y1 + pad, n)
    X, Y = np.meshgrid(xs, ys)
    mask = np.zeros((n, n), bool)
    for f in faces:
        i0 = max(np.searchsorted(ys, f[:, 1].min()) - 1, 0)
        i1 = np.searchsorted(ys, f[:, 1].max()) + 1
        j0 = max(np.searchsorted(xs, f[:, 0].min()) - 1, 0)
        j1 = np.searchsorted(xs, f[:, 0].max()) + 1
        if i1 <= i0 or j1 <= j0:
            continue
        pts = np.c_[X[i0:i1, j0:j1].ravel(), Y[i0:i1, j0:j1].ravel()]
        mask[i0:i1, j0:j1] |= Path(f).contains_points(pts).reshape(i1 - i0, j1 - j0)
    if not mask.any():
        return []
    fig = plt.figure()
    try:
        cs = fig.add_subplot(111).contour(xs, ys, mask.astype(float), [0.5])
        return [np.asarray(sg) for sg in cs.allsegs[0] if len(sg) > 8]
    finally:
        plt.close(fig)


# --------------------------------------------------------------------------- #
# panels
# --------------------------------------------------------------------------- #
PLANES = {
    "sagittal": dict(cols=(0, 1), dirs=("SUP", "ANT", "INF", "POS")),
    "frontal":  dict(cols=(2, 1), dirs=("SUP", "LAT", "INF", "MED")),
}


def panel_spec(kind, side):
    """Bones behind each joint kind + the segment that MOVES with the task.

    `at` says where a bone sits: a joint name moves the panel origin to that
    joint's centre; "chain" brings the body in through the model's own joint
    transforms. `moving` is the neighbouring segment, drawn dotted at the two
    extremes of `drive` when an IK file is given; `axis_sign` points its long
    axis away from the joint."""
    s = side
    if kind == "hip":
        return dict(
            rlabel=163,
            bones=[dict(body="pelvis", only=(f"{s}_pelvis", f"pelvis_{s}"), keep=None, end=None, at=f"hip_{s}")],
            moving=dict(body=f"femur_{s}", only=(f"{s}_femur", f"femur_{s}"), keep=0.30,
                        end="proximal", at=f"hip_{s}", axis_sign=-1.0,
                        drive=f"hip_flexion_{s}",
                        coords=(f"hip_flexion_{s}", f"hip_adduction_{s}",
                                f"hip_rotation_{s}")))
    if kind == "knee":
        return dict(
            rlabel=340,
            bones=[dict(body=f"tibia_{s}", only=(f"{s}_tibia", f"tibia_{s}"), keep=0.22,
                        end="proximal", at=None)],
            moving=dict(body=f"femur_{s}", only=(f"{s}_femur", f"femur_{s}"), keep=0.16,
                        end="distal", at=None, axis_sign=+1.0,
                        drive=f"knee_angle_{s}", coords=(f"knee_angle_{s}",)))
    if kind == "ankle":
        return dict(
            rlabel=340,
            bones=[dict(body=f"talus_{s}", only=None, keep=None, end=None, at=None),
                   dict(body=f"calcn_{s}", only=None, keep=None, end=None, at="chain"),
                   dict(body=f"toes_{s}", only=None, keep=None, end=None, at="chain")],
            moving=dict(body=f"tibia_{s}", only=(f"{s}_tibia", f"tibia_{s}"), keep=0.12,
                        end="distal", at=None, axis_sign=+1.0,
                        drive=f"ankle_angle_{s}", coords=(f"ankle_angle_{s}",)))
    return dict(rlabel=200, bones=[], moving=None)


def joint_kind(name):
    n = name.lower()
    for kind in ("hip", "knee", "ankle"):
        if kind in n:
            return kind
    return None


def joint_side(name):
    return "l" if name.endswith("_l") else "r"


def panel_bones(model, joint, frame_body, cols):
    """Grey silhouette faces for one panel, projected, origin at the joint."""
    spec = panel_spec(joint_kind(joint), joint_side(joint))
    out = []
    for b in spec["bones"]:
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


def panel_moving(model, joint, frame_body, q, cols):
    """The bone that MOVES within the panel, posed at `q`, projected."""
    spec = panel_spec(joint_kind(joint), joint_side(joint)).get("moving")
    if not spec or spec["body"] not in model.bodies:
        return []
    faces = keep_end(model.mesh_faces(spec["body"], spec["only"]),
                     spec["keep"], spec["end"])
    got = model.chain_pose(spec["body"], frame_body, q) if faces else None
    if got is None:
        return []
    Rot, t = got
    faces = [f @ Rot.T + t for f in faces]
    if spec["at"] and spec["at"] in model.joints:
        _, t0 = model.joint_neutral(spec["at"])
        faces = [f - t0 for f in faces]
    return [f[:, list(cols)] for f in faces]


def segment_bearing(model, joint, frame_body, q, cols):
    """Which way the moving segment points at pose `q`, as a bearing (rad)."""
    spec = panel_spec(joint_kind(joint), joint_side(joint)).get("moving")
    got = model.chain_pose(spec["body"], frame_body, q) if spec else None
    if got is None:
        return None
    v = got[0] @ np.array([0.0, spec.get("axis_sign", 1.0), 0.0])
    return float(np.arctan2(v[cols[0]], v[cols[1]]))


def pose_extremes(ik_names, ik_data, degrees, spec):
    """[(coords_dict, angle_deg), ...] at the drive's min, max and start."""
    curves = {}
    for c in spec["coords"]:
        if c in ik_names:
            v = np.asarray(ik_data[:, ik_names.index(c)], float)
            curves[c] = np.radians(v) if degrees else v
    drive = curves.get(spec["drive"])
    if drive is None or not np.isfinite(drive).any():
        return []
    lo, hi = int(np.nanargmin(drive)), int(np.nanargmax(drive))
    return [({c: float(v[i]) for c, v in curves.items()},
             float(np.degrees(drive[i]))) for i in (lo, hi, 0)]


def hip_to_pelvis(model, joint, F, ik_names, ik_data, degrees):
    """Reaction ON the femur IN the femur frame -> force ON the acetabulum IN
    the pelvis frame: Newton's third law + the hip's own rotation matrix."""
    q = {}
    for axis, coord in model.joints[joint]["axes"]:
        if coord and coord in ik_names:
            v = ik_data[:, ik_names.index(coord)]
            q[coord] = np.radians(v) if degrees else v
    if not q:
        return None
    n = min(F.shape[1], min(np.size(v) for v in q.values()))
    Rot = model.joint_rotation(joint, {k: v[:n] for k, v in q.items()})
    return -np.einsum("nij,jn->in", Rot, F[:, :n])


# --------------------------------------------------------------------------- #
# drawing (the manuscript figure's own grammar)
# --------------------------------------------------------------------------- #
COLORS = ["#E39A2B", "#C4472A", "#4C9A51", "#8E5BA6", "#3B7BB8", "#7A7A7A"]


class Style:
    dpi = 200
    col_w, row_h = 3.35, 3.5
    title_fs, tick_fs, dir_fs, marker_ms = 12, 9, 10, 5.5
    bone_frac = 1.25       # fraction of the rim the widest bone spans (>1 = past it)


def nice_ceiling(v, steps=(0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 10.0)):
    v = float(v)
    if not np.isfinite(v) or v <= 0:
        return 1.0
    for s in steps:
        if v / s <= 4:
            return float(np.ceil(v / s) * s)
    return float(np.ceil(v / steps[-1]) * steps[-1])


def bone_scale(groups, rmax, frac=None):
    """ONE radial scale shared by every bone in a panel, sized so the widest
    spans `frac` of the rim — the loop should sit INSIDE the joint."""
    frac = Style.bone_frac if frac is None else frac
    P = [np.vstack(g) for g in groups if g]
    if not P or not np.isfinite(rmax) or rmax <= 0:
        return None
    P = np.vstack(P)
    ref = np.percentile(np.hypot(P[:, 0], P[:, 1]), 96)
    return frac * rmax / ref if np.isfinite(ref) and ref > 0 else None


def to_polar(xy, k):
    return np.c_[np.arctan2(xy[:, 0], xy[:, 1]), np.hypot(xy[:, 0], xy[:, 1]) * k]


def draw_bone(ax, faces, k, color="0.92"):
    if faces and k:
        ax.add_collection(mcoll.PolyCollection([to_polar(f, k) for f in faces],
                                               facecolor=color, edgecolor=color,
                                               lw=0.4, zorder=0))


def draw_pose(ax, segs, k, color="0.55"):
    for sg in segs:
        if len(sg):
            pol = to_polar(np.asarray(sg), k)
            ax.plot(pol[:, 0], pol[:, 1], color=color, ls=(0, (2, 2)), lw=0.9,
                    zorder=1, solid_capstyle="butt")


def draw_rom_arc(ax, rom, rmax, color="0.45", lw=4.0, fs=8):
    """(bearing_min, bearing_max, deg_min, deg_max, bearing_at_start)."""
    if not rom:
        return
    b0, b1, a0, a1, b_start = rom
    if not (np.isfinite(b0) and np.isfinite(b1)):
        return
    d = (b1 - b0 + np.pi) % (2 * np.pi) - np.pi     # the short way round
    r = rmax * 0.97
    th = np.linspace(b0, b0 + d, 96)
    ax.plot(th, np.full_like(th, r), color=color, lw=lw, alpha=0.45,
            solid_capstyle="butt", zorder=1)
    for b in (b0, b0 + d):
        ax.plot([b, b], [r * 0.955, r * 1.045], color=color, lw=lw * 0.5,
                alpha=0.7, solid_capstyle="butt", zorder=1)
    if np.isfinite(b_start):
        ax.plot([b_start], [r], marker="o", ms=4.5, color=color, alpha=0.8,
                mec="w", mew=0.7, ls="none", zorder=2)
    ax.text(b0 + d / 2.0, r * 0.90, f"{a0:.0f}–{a1:.0f}°", color=color,
            fontsize=fs, ha="center", va="center", zorder=6,
            bbox=dict(fc="white", ec="none", alpha=0.7, pad=0.6))


def draw_panel(ax, faces, ghosts, rom, curves, rmax, unit, title, rlabel,
               rings, dirs, dir_names):
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_title(title, fontsize=Style.title_fs, pad=14)
    ax.set_ylim(0, rmax)
    k = bone_scale([faces] + list(ghosts), rmax)
    draw_bone(ax, faces, k)
    for segs in ghosts:
        draw_pose(ax, segs, k)
    draw_rom_arc(ax, rom, rmax)
    for col, lab, r, th in curves:
        r = np.where(r <= rmax, r, np.nan)
        # unwrap: the knee/ankle bearings sit on the +/-pi wrap, and a raw jump
        # from +179 to -179 draws a line the long way round
        ax.plot(np.unwrap(th), r, color=col, lw=1.8, zorder=4,
                solid_capstyle="round", label=lab)
        ok = np.flatnonzero(np.isfinite(r) & np.isfinite(th))
        for i, mk, ms in ((ok[0], "o", Style.marker_ms),
                          (ok[-1], "X", Style.marker_ms * 1.25)) if ok.size else ():
            ax.plot([th[i]], [r[i]], marker=mk, color=col, ms=ms,
                    mec="w", mew=0.7, ls="none", zorder=5)
    step = nice_ceiling(rmax / 3.0)
    ticks = np.arange(step, rmax, step)
    ax.set_yticks(ticks)
    # one scale throughout, so the ring values are written once — first panel
    ax.set_yticklabels([f"{v:g} {unit}" for v in ticks] if rings else [],
                       fontsize=Style.tick_fs)
    ax.set_rlabel_position(rlabel)
    for lab in ax.get_yticklabels():
        lab.set_bbox(dict(fc="white", ec="none", alpha=0.85, pad=0.8))
    ax.set_thetagrids([0, 90, 180, 270], labels=[""] * 4)
    if dirs:    # the compass, on the first panel only, inside the rim
        for t, lab in zip((0, 90, 180, 270), dir_names):
            ax.text(np.radians(t), rmax * 0.80, lab, ha="center", va="center",
                    fontsize=Style.dir_fs, zorder=6,
                    bbox=dict(fc="white", ec="none", alpha=0.85, pad=1.0))
    ax.grid(color="0.72", lw=0.6, zorder=2)
    ax.spines["polar"].set_color("0.45")


# --------------------------------------------------------------------------- #
# the figure
# --------------------------------------------------------------------------- #
def plot_jcf_direction(model, jra, out="jcf_direction.png", joints=None,
                       bodyweight=None, mass=None, plane="sagittal", ik=None,
                       geometry=None, title=None, dpi=None):
    """Draw the figure. Returns the output path.

    model       .osim path (bones + hip frame conversion)
    jra         one .sto path, a list of paths, or {label: path}
    joints      joint names as in the JRA columns (default: hip/knee/ankle
                joints found in the first file, right side preferred)
    bodyweight  N — radius in body weights; `mass` (kg) is the alternative;
                neither -> radius in kN
    plane       "sagittal" (SUP/ANT) or "frontal" (SUP/LAT)
    ik          IK .mot of the same trial -> hip re-expressed in the pelvis
                frame, plus the dotted extreme poses and the ROM arc
    geometry    extra folder(s) to search for .vtp meshes
    """
    if isinstance(jra, str):
        jra = {os.path.splitext(os.path.basename(jra))[0]: jra}
    elif not isinstance(jra, dict):
        jra = {os.path.splitext(os.path.basename(p))[0]: p for p in jra}
    bw = float(bodyweight) if bodyweight else (float(mass) * 9.80665 if mass else None)
    unit, scale = ("BW", bw) if bw else ("kN", 1000.0)
    cols = PLANES[plane]["cols"]
    dir_names = PLANES[plane]["dirs"]

    series = {lab: read_sto(p) for lab, p in jra.items()}
    trips = force_triplets(next(iter(series.values()))[0])
    if joints is None:
        joints = [j for j in trips if joint_kind(j)]
        rs = [j for j in joints if j.endswith("_r")]
        joints = rs or joints
        order = {"hip": 0, "knee": 1, "ankle": 2}
        joints.sort(key=lambda j: order.get(joint_kind(j), 9))
    if not joints:
        sys.exit("no *_on_*_in_*_f{x,y,z} force columns found in " + next(iter(jra.values())))

    geo = OsimModel(model, geometry)
    ik_names = ik_data = None
    degrees = True
    if ik:
        ik_names, ik_data = read_sto(ik)
        with open(ik) as fh:
            degrees = "indegrees=yes" in fh.read(2000).replace(" ", "").lower()

    # gather every panel's curves first: ONE rim for all panels, so the loops
    # are directly comparable — the point of putting them side by side
    panels = {}
    top = 0.0
    for joint in joints:
        curves, note, frame_body = [], "", trips.get(joint, (None, None, None))[1]
        for i, (lab, (names, data)) in enumerate(series.items()):
            t = force_triplets(names).get(joint)
            if t is None:
                continue
            F = data[:, t[2]].T                             # (3, N)
            frame_body = t[1]
            if joint_kind(joint) == "hip" and ik_names:
                conv = hip_to_pelvis(geo, joint, F, ik_names, ik_data, degrees)
                if conv is not None:
                    F = conv
                    frame_body = geo.joints[joint]["parent"]["body"]
                    note = "*"
            elif joint_kind(joint) == "hip":
                note = f"  (in the {t[1]} frame)"
            r = np.linalg.norm(F, axis=0) / scale
            th = np.arctan2(F[cols[0]], F[cols[1]])         # 0 = SUP
            curves.append((COLORS[i % len(COLORS)], lab, r, th))
            top = max(top, float(np.nanmax(r)))
        panels[joint] = dict(curves=curves, note=note, frame=frame_body)
    rim = nice_ceiling(top)

    n = len(joints)
    fig, axes = plt.subplots(1, n, figsize=(Style.col_w * n, Style.row_h + 1.1),
                             subplot_kw=dict(projection="polar"))
    axes = np.atleast_1d(axes)

    for i, (ax, joint) in enumerate(zip(axes, joints)):
        p = panels[joint]
        faces = panel_bones(geo, joint, p["frame"], cols)
        ghosts, rom = [], None
        spec = panel_spec(joint_kind(joint), joint_side(joint))
        if ik_names and spec.get("moving"):
            ext = pose_extremes(ik_names, ik_data, degrees, spec["moving"])
            if len(ext) == 3:
                ghosts = [o for o in
                          (silhouette_outline(panel_moving(geo, joint, p["frame"], q, cols))
                           for q, _ in ext[:2]) if o]
                bear = [segment_bearing(geo, joint, p["frame"], q, cols)
                        for q, _ in ext]
                if all(b is not None for b in bear):
                    rom = (bear[0], bear[1], ext[0][1], ext[1][1], bear[2])
        kind = joint_kind(joint) or joint
        draw_panel(ax, faces, ghosts, rom, p["curves"], rim, unit,
                   title=kind + p["note"],
                   rlabel=spec["rlabel"], rings=(i == 0), dirs=(i == 0),
                   dir_names=dir_names)

    # one legend for the whole figure, under the panels
    handles = [mlines.Line2D([], [], color=COLORS[i % len(COLORS)], lw=2.2, label=lab)
               for i, lab in enumerate(jra)]
    fig.legend(handles=handles, loc="lower center", ncol=max(len(handles), 1),
               frameon=False, fontsize=10,
               bbox_to_anchor=(0.5, 0.075))
    note = ("grey = the panel's own bone · radius = |JCF| in %s, one scale "
            "throughout · bearing = force direction in that bone's frame "
            "(%s plane) · ● start, ✖ end of trial" % (unit, plane))
    if ik:
        note += " · dotted = the neighbouring segment at both extremes, arc = its range of motion"
    if any(p["note"] == "*" for p in panels.values()):
        note += " · * moved from the frame OpenSim wrote it in"
    fig.text(0.5, 0.015, note, ha="center", fontsize=8, color="0.35")
    if title:
        fig.suptitle(title, fontsize=13)
    fig.subplots_adjust(left=0.03, right=0.97, top=0.86, bottom=0.22, wspace=0.15)
    fig.savefig(out, dpi=dpi or Style.dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out)
    return out


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="bioscout plot jcf", description=__doc__.split("\n\n")[0],
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--model", required=True, metavar="MODEL.osim")
    ap.add_argument("--jra", required=True, nargs="+", metavar="JRA.sto",
                    help="one or more JointReaction ReactionLoads files")
    ap.add_argument("--labels", nargs="+", metavar="NAME",
                    help="legend label per --jra file (default: file names)")
    ap.add_argument("--joints", nargs="+", metavar="JOINT",
                    help="joint names as in the columns, e.g. hip_r walker_knee_r "
                         "ankle_r (default: hip/knee/ankle found in the file)")
    ap.add_argument("--bw", type=float, metavar="N", help="body weight in newtons")
    ap.add_argument("--mass", type=float, metavar="KG", help="body mass in kg")
    ap.add_argument("--ik", metavar="MOT", help="IK angles of the same trial -> "
                    "hip in the pelvis frame + dotted extreme poses + ROM arc")
    ap.add_argument("--plane", choices=list(PLANES), default="sagittal")
    ap.add_argument("--geometry", nargs="*", metavar="DIR",
                    help="extra folders to search for .vtp bone meshes")
    ap.add_argument("--title")
    ap.add_argument("-o", "--out", default="jcf_direction.png")
    ns = ap.parse_args(argv)

    if ns.labels and len(ns.labels) != len(ns.jra):
        ap.error("--labels needs one name per --jra file")
    jra = dict(zip(ns.labels, ns.jra)) if ns.labels else list(ns.jra)
    plot_jcf_direction(ns.model, jra, out=ns.out, joints=ns.joints,
                       bodyweight=ns.bw, mass=ns.mass, plane=ns.plane,
                       ik=ns.ik, geometry=ns.geometry, title=ns.title)
    return 0


if __name__ == "__main__":
    sys.exit(main())
