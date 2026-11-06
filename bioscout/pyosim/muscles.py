"""Muscle-tendon paths of an OpenSim model in pure Python: path points plus
wrapping over cylinders and spheres (tangent lines and the arc between them,
the side chosen by the wrap object's quadrant, else the shorter way), lengths
for many poses at once, and moment arms as -dL/dq. Tori are not wrapped (their
muscles follow their via points)."""
import re
import xml.etree.ElementTree as ET
import numpy as np
from .model import _vec, rot_xyz, _path_name, Kinematics

MUSCLE_TAGS = ("Millard2012EquilibriumMuscle", "Thelen2003Muscle", "DeGrooteFregly2016Muscle", "Millard2012AccelerationMuscle", "RigidTendonMuscle")


def _wrap_objects(root):
    out = {}
    for body in root.iter("Body"):
        ws = body.find("WrapObjectSet/objects")
        if ws is None:
            continue
        for w in ws:
            if (w.findtext("active") or "true").strip() == "false":
                continue
            q = (w.findtext("quadrant") or "all").strip().lower()
            qv = None
            m = re.fullmatch(r"([+-]?)([xyz])", q)
            if m:
                qv = np.zeros(3); qv["xyz".index(m.group(2))] = -1.0 if m.group(1) == "-" else 1.0
            out[w.get("name")] = dict(kind=w.tag, body=body.get("name"), R=rot_xyz(_vec(w.findtext("xyz_body_rotation"))),
                                      t=_vec(w.findtext("translation")), r=float(w.findtext("radius") or 0),
                                      length=float(w.findtext("length") or 0), q=qv)
    return out


def read_muscles(path):
    root = ET.parse(path).getroot()
    wraps = _wrap_objects(root)
    out = []
    for tag in MUSCLE_TAGS:
        for m in root.iter(tag):
            if (m.findtext("appliesForce") or "true").strip() == "false":
                continue
            pts = [(_path_name(p.findtext("socket_parent_frame") or p.findtext("body")), _vec(p.findtext("location")))
                   for p in m.find("GeometryPath/PathPointSet/objects") if p.tag.endswith("PathPoint")]
            wr = []
            for w in m.iterfind("GeometryPath/PathWrapSet/objects/PathWrap"):
                o = wraps.get((w.findtext("wrap_object") or "").strip())
                if o is None or o["kind"] not in ("WrapCylinder", "WrapSphere"):
                    continue
                rg = [int(float(x)) for x in (w.findtext("range") or "-1 -1").split()]
                wr.append(dict(o, range=None if rg[0] < 1 else (rg[0] - 1, rg[1] - 1)))   # path-point indices, 0-based
            if len(pts) < 2:                       # the <defaults> template, not a muscle
                continue
            g = lambda k, d: float(m.findtext(k) or d)
            out.append(dict(name=m.get("name"), pts=pts, wraps=wr, F0=g("max_isometric_force", 1000), lopt=g("optimal_fiber_length", 0.1),
                            lts=g("tendon_slack_length", 0.2), alpha=g("pennation_angle_at_optimal", 0), vmax=g("max_contraction_velocity", 10)))
    return out


def _circle(P, S, r, Q3, to3, force_ok=None):
    """Shortest admissible path P -> circle(r, origin) -> S in a plane, for many cases at once.
    P,S: (B,2). Returns wrapped length (B,) and a mask of where wrapping applies. Q3: quadrant
    direction (3,) or None; to3(angle) -> (B,3) the arc point in the wrap frame, for the quadrant test."""
    dP, dS = np.linalg.norm(P, axis=1), np.linalg.norm(S, axis=1)
    D = S - P; L2 = np.maximum((D * D).sum(1), 1e-18)
    t = np.clip(-(P * D).sum(1) / L2, 0, 1)
    C = P + t[:, None] * D
    near = np.linalg.norm(C, axis=1)
    ok = (dP > r * 1.0001) & (dS > r * 1.0001) & (near < r)
    if Q3 is not None:
        # with a quadrant the path may not pass the object on the other side: a line that misses
        # the object on the forbidden side wraps round the allowed side anyway (as OpenSim)
        cang = np.arctan2(C[:, 1], C[:, 0])
        forced = (dP > r * 1.0001) & (dS > r * 1.0001) & (to3(cang) @ Q3 < 0)
        ok |= forced if force_ok is None else forced & force_ok(t)
    if not ok.any():
        return None, ok
    aP, aS = np.arccos(np.clip(r / np.maximum(dP, r), -1, 1)), np.arccos(np.clip(r / np.maximum(dS, r), -1, 1))
    thP, thS = np.arctan2(P[:, 1], P[:, 0]), np.arctan2(S[:, 1], S[:, 0])
    tP, tS = np.sqrt(np.maximum(dP ** 2 - r ** 2, 0)), np.sqrt(np.maximum(dS ** 2 - r ** 2, 0))
    best, bestmid = None, None
    cands = []
    for d in (1, -1):
        t1, t2 = thP + d * aP, thS - d * aS
        arc = np.mod(d * (t2 - t1), 2 * np.pi)
        cands.append((tP + tS + r * arc, t1 + d * arc / 2))
    (l1, m1), (l2, m2) = cands
    if Q3 is None:
        L = np.minimum(l1, l2)
    else:
        good1 = to3(m1) @ Q3 >= 0
        good2 = to3(m2) @ Q3 >= 0
        L = np.where(good1 & ~good2, l1, np.where(good2 & ~good1, l2, np.minimum(l1, l2)))
    return L, ok


def _wrap_segment(Pl, Sl, w):
    """Wrapped length of the straight segments Pl->Sl (wrap-frame coordinates), NaN where it does not wrap."""
    B = len(Pl); out = np.full(B, np.nan); r = w["r"]
    if w["kind"] == "WrapCylinder":
        half = w["length"] / 2 if w["length"] > 0 else np.inf
        L2, ok = _circle(Pl[:, :2], Sl[:, :2], r, w["q"], lambda a: np.stack([r * np.cos(a), r * np.sin(a), np.zeros_like(a)], 1),
                         force_ok=lambda t: np.abs(Pl[:, 2] + t * (Sl[:, 2] - Pl[:, 2])) <= half)
        if L2 is None:
            return out
        dz = Sl[:, 2] - Pl[:, 2]
        out[ok] = np.sqrt(L2[ok] ** 2 + dz[ok] ** 2)
        return out
    # sphere: the great circle in the plane of P, S and the centre
    e1 = Pl / np.maximum(np.linalg.norm(Pl, axis=1, keepdims=True), 1e-12)
    n = np.cross(Pl, Sl); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    e2 = np.cross(n, e1)
    P2 = np.stack([(Pl * e1).sum(1), (Pl * e2).sum(1)], 1); S2 = np.stack([(Sl * e1).sum(1), (Sl * e2).sum(1)], 1)
    L2, ok = _circle(P2, S2, r, w["q"], lambda a: r * (np.cos(a)[:, None] * e1 + np.sin(a)[:, None] * e2))
    if L2 is not None:
        out[ok] = L2[ok]
    return out


# ------------------------------------------------------------------ several wrap objects on one path
def _circle_pts(P, S, r, Q3, to3, forced_ok=True):
    """Scalar version of _circle that also returns where the path touches the circle:
    (planar length, tP, tS, angle of the first tangent point, signed arc) or None."""
    dP, dS = np.linalg.norm(P), np.linalg.norm(S)
    if dP <= r * 1.0001 or dS <= r * 1.0001:
        return None
    D = S - P; L2 = max(D @ D, 1e-18)
    t = min(max(-(P @ D) / L2, 0.0), 1.0)
    C = P + t * D
    ok = np.linalg.norm(C) < r
    if Q3 is not None and not ok:
        cang = np.arctan2(C[1], C[0])
        ok = bool(to3(cang) @ Q3 < 0) and forced_ok(t)
    if not ok:
        return None
    aP, aS = np.arccos(np.clip(r / dP, -1, 1)), np.arccos(np.clip(r / dS, -1, 1))
    thP, thS = np.arctan2(P[1], P[0]), np.arctan2(S[1], S[0])
    tP, tS = np.sqrt(max(dP * dP - r * r, 0)), np.sqrt(max(dS * dS - r * r, 0))
    cands = []
    for d in (1, -1):
        t1, t2 = thP + d * aP, thS - d * aS
        arc = np.mod(d * (t2 - t1), 2 * np.pi)
        cands.append((tP + tS + r * arc, t1, d * arc))
    if Q3 is None:
        c = min(cands, key=lambda z: z[0])
    else:
        good = [bool(to3(t1 + a / 2) @ Q3 >= 0) for _, t1, a in cands]
        c = cands[0] if good[0] and not good[1] else cands[1] if good[1] and not good[0] else min(cands, key=lambda z: z[0])
    return c[0], tP, tS, c[1], c[2]


def _wrap_points(Pl, Sl, w):
    """One straight segment Pl->Sl (wrap-frame coordinates) round one wrap object:
    None, or (wrapped length, first tangent point, second tangent point, arc length between them)."""
    r = w["r"]
    if w["kind"] == "WrapCylinder":
        half = w["length"] / 2 if w["length"] > 0 else np.inf
        to3 = lambda a: np.array([r * np.cos(a), r * np.sin(a), 0.0])
        res = _circle_pts(Pl[:2], Sl[:2], r, w["q"], to3,
                          forced_ok=lambda t: abs(Pl[2] + t * (Sl[2] - Pl[2])) <= half)
        if res is None:
            return None
        Lp, tP, tS, t1, arc = res
        dz = Sl[2] - Pl[2]
        z1 = Pl[2] + dz * tP / Lp; z2 = Pl[2] + dz * (Lp - tS) / Lp
        T1 = np.array([r * np.cos(t1), r * np.sin(t1), z1])
        T2 = np.array([r * np.cos(t1 + arc), r * np.sin(t1 + arc), z2])
        k = np.sqrt(1 + (dz / Lp) ** 2)
        return Lp * k, T1, T2, r * abs(arc) * k
    e1 = Pl / max(np.linalg.norm(Pl), 1e-12)
    n = np.cross(Pl, Sl); n /= max(np.linalg.norm(n), 1e-12)
    e2 = np.cross(n, e1)
    to3 = lambda a: r * (np.cos(a) * e1 + np.sin(a) * e2)
    res = _circle_pts(np.array([Pl @ e1, Pl @ e2]), np.array([Sl @ e1, Sl @ e2]), r, w["q"], to3)
    if res is None:
        return None
    L, tP, tS, t1, arc = res
    return L, to3(t1), to3(t1 + arc), r * abs(arc)


def _multiwrap_pass(nodes, wraps, frames):
    """One pass over the wrap objects in order: each removes its own tangent points from the path,
    then wraps the straight segment it lengthens least (the others' tangent points are path points)."""
    for wi, (w, (to_l, to_g)) in enumerate(zip(wraps, frames)):
        k = next((k for k, n in enumerate(nodes) if n[2] == wi), None)
        if k is not None:
            del nodes[k:k + 2]
            nodes[k - 1][3] = None
        best = None
        for i in range(len(nodes) - 1):
            a, b = nodes[i], nodes[i + 1]
            if a[3] is not None:                          # an arc of another wrap, not a straight line
                continue
            rg = w["range"]
            if rg is not None and not (rg[0] <= np.floor(a[1]) and np.ceil(b[1]) <= rg[1]):
                continue
            straight = np.linalg.norm(b[0] - a[0])
            res = _wrap_points(to_l(a[0]), to_l(b[0]), w)
            if res is None or res[0] < straight - 1e-9:
                continue
            if best is None or res[0] - straight < best[0]:
                best = (res[0] - straight, i, res)
        if best is None:
            continue
        _, i, (_, T1, T2, arc) = best
        mid = nodes[i][1] + 0.5
        nodes[i + 1:i + 1] = [[to_g(T1), mid, wi, arc], [to_g(T2), mid, wi, None]]
    return nodes


def _multiwrap_length(X, wraps, frames, geometric=False):
    """Path length with several wrap objects, reproducing OpenSim 4's GeometryPath: the wrap objects
    are applied in order, each on the path the earlier ones left. OpenSim runs that loop twice and
    its length is the straight segments between the FIRST pass's points plus the wrap (arc) lengths
    of the SECOND pass. That mix is OpenSim's, not geometry, but it is what OpenSim reports
    (checked on the GPK gastrocnemii, two cylinders each: <= 0.02 mm over a gait trial, vs ~4 mm
    for a plain wrap-on-wrap). X: [(3,) ground points]; frames: per wrap (to_local, to_ground)."""
    # node: [ground point, original index (tangent points: i + 0.5), owner wrap (None = path point), arc to next]
    first = _multiwrap_pass([[x, float(i), None, None] for i, x in enumerate(X)], wraps, frames)
    second = _multiwrap_pass([list(n) for n in first], wraps, frames)
    if geometric:                     # the path the force acts along: second pass, its segments and arcs
        return sum(a[3] if a[3] is not None else np.linalg.norm(b[0] - a[0]) for a, b in zip(second, second[1:]))
    arcs = {n[2]: n[3] for n in second if n[3] is not None}
    total = 0.0
    for k in range(len(first) - 1):
        a, b = first[k], first[k + 1]
        total += arcs.get(a[2], a[3]) if a[3] is not None else np.linalg.norm(b[0] - a[0])
    return total

class Paths:
    def __init__(self, model, osim_path):
        self.m = model
        self.mus = read_muscles(osim_path)
        self.kin = Kinematics(model, [])
        self.names = [x["name"] for x in self.mus]

    def lengths(self, Q, geometric=False):
        """Q: (B, n_coords) full coordinates -> (B, n_muscles) musculotendon lengths.
        geometric: for several wrap objects, the length of the path the force acts along (OpenSim's
        moment arms follow it) instead of OpenSim's reported length."""
        T = self.kin.bodies(Q); B = len(Q)
        g = lambda b, loc: T[b][1] + (T[b][0] @ loc if np.ndim(T[b][0]) == 3 else T[b][0] @ loc)
        out = np.zeros((B, len(self.mus)))
        for k, mu in enumerate(self.mus):
            X = [g(b, loc) for b, loc in mu["pts"]]
            if len(mu["wraps"]) > 1:                  # several wrap objects: OpenSim applies them one after another
                fr = []
                for w in mu["wraps"]:
                    Rb, pb = T[w["body"]]
                    Rb = np.broadcast_to(Rb, (B, 3, 3)); pb = np.broadcast_to(pb, (B, 3))
                    fr.append((Rb, pb, w))
                for f in range(B):
                    frames = [(lambda x, Rb=Rb[f], pb=pb[f], w=w: w["R"].T @ (Rb.T @ (x - pb) - w["t"]),
                               lambda x, Rb=Rb[f], pb=pb[f], w=w: pb + Rb @ (w["t"] + w["R"] @ x)) for Rb, pb, w in fr]
                    out[f, k] = _multiwrap_length([x[f] for x in X], mu["wraps"], frames, geometric)
                continue
            nseg = len(X) - 1
            seg = np.stack([np.linalg.norm(X[i + 1] - X[i], axis=1) for i in range(nseg)], 1)   # (B, nseg)
            for w in mu["wraps"]:
                # a wrap object acts on ONE segment of the path (as OpenSim): of the segments in its
                # range that wrap, the one it lengthens least
                Rb, pb = T[w["body"]]
                Rb = np.broadcast_to(Rb, (B, 3, 3))
                to = lambda x: np.einsum("ji,bj->bi", w["R"], np.einsum("bji,bj->bi", Rb, x - pb) - w["t"])
                add = np.full((B, nseg), np.inf)
                for i in range(nseg):
                    if w["range"] is not None and not (w["range"][0] <= i and i + 1 <= w["range"][1]):
                        continue
                    wl = _wrap_segment(to(X[i]), to(X[i + 1]), w)
                    good = ~np.isnan(wl) & (wl >= seg[:, i] - 1e-9)
                    add[good, i] = wl[good] - seg[good, i]
                j = np.argmin(add, 1); best = add[np.arange(B), j]
                hit = np.isfinite(best)
                seg[hit, j[hit]] += best[hit]
            out[:, k] = seg.sum(1)
        return out

    def moment_arms(self, Q, coords, h=1e-4):
        """Q: (n, n_coords). -> lengths (n, M), moment arms (n, len(coords), M) = -dL/dq (central differences)."""
        n, nc = Q.shape; idx = [self.m.coord_order.index(c) for c in coords]
        Qs = [Q]
        for ci in idx:
            for s in (h, -h):
                P = Q.copy(); P[:, ci] += s; Qs.append(self.kin.couple(P))
        # moment arms from the path the force acts along: for a muscle with several wrap objects
        # OpenSim's reported length mixes two wrapping passes and is not what its moment arms
        # follow (GPK gastrocnemii: -dL/dq of that length is up to 15 mm off OpenSim's moment arm)
        L0 = self.lengths(Q)
        L = self.lengths(np.concatenate(Qs), geometric=True)
        R = np.zeros((n, len(idx), L.shape[1]))
        Lg = L[:n]                                   # unperturbed, same (geometric) length definition
        for k in range(len(idx)):
            Lp = L[n * (1 + 2 * k): n * (2 + 2 * k)]; Lm = L[n * (2 + 2 * k): n * (3 + 2 * k)]
            R[:, k] = -(Lp - Lm) / (2 * h)
            # a wrap object switching on/off between q-h and q+h makes the path length jump: the
            # central difference then explodes (e.g. -78 m for glmax1 at one frame). Where the two
            # one-sided slopes disagree, take the one-sided slope on the smooth side.
            rp, rm = -(Lp - Lg) / h, -(Lg - Lm) / h
            jump = np.abs(rp - rm) > 0.02 + 0.5 * np.minimum(np.abs(rp), np.abs(rm))
            if jump.any():
                R[:, k] = np.where(jump, np.where(np.abs(rp) < np.abs(rm), rp, rm), R[:, k])
        return L0, R


def muscle_names(path):
    """Muscle names in model-file order (as OpenSim's model.getMuscles() lists them)."""
    root = ET.parse(path).getroot()
    objs = root.find("./Model/ForceSet/objects")
    return [e.get("name") for e in (objs if objs is not None else []) if e.tag in MUSCLE_TAGS]
