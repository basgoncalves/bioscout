"""Minimal OpenSim .osim reader + forward kinematics in pure numpy.

Only what IK/ID need: bodies, joint tree (Custom/Pin/Weld/Free/Ball/Universal),
coordinates (default, locked, range), CoordinateCouplerConstraints, markers.
"""
import xml.etree.ElementTree as ET
import numpy as np


def _vec(txt, n=3):
    v = np.array([float(x) for x in (txt or "").split()] or [0.0] * n)
    return v


def rot_xyz(a):
    """OpenSim frame 'orientation' = body-fixed X-Y-Z Euler angles."""
    return rot_axis([1, 0, 0], a[0]) @ rot_axis([0, 1, 0], a[1]) @ rot_axis([0, 0, 1], a[2])


def rot_axis(axis, q):
    k = np.asarray(axis, float)
    k = k / np.linalg.norm(k)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(q) * K + (1 - np.cos(q)) * K @ K


# ------------------------------------------------------------------ functions
class Func:
    def __init__(self, el):
        self.kind = "const0"
        if el is None:
            return
        KNOWN = ("LinearFunction", "Constant", "SimmSpline", "NaturalCubicSpline", "GCVSpline",
                 "MultiplierFunction", "PolynomialFunction")
        f = el if el.tag in KNOWN else next((c for c in el if c.tag in KNOWN), None)
        if f is None:
            return
        self.kind = f.tag
        if f.tag == "LinearFunction":
            self.c = _vec(f.findtext("coefficients"), 2)
        elif f.tag == "Constant":
            self.c = float(f.findtext("value"))
        elif f.tag in ("SimmSpline", "NaturalCubicSpline", "GCVSpline"):
            self.x = _vec(f.findtext("x")); self.y = _vec(f.findtext("y"))
            self._fmm_spline() if f.tag == "SimmSpline" else self._spline()
        elif f.tag == "MultiplierFunction":
            self.inner = Func(f.find("function"))
            self.scale = float(f.findtext("scale") or 1)
        elif f.tag == "PolynomialFunction":
            self.c = _vec(f.findtext("coefficients"))
        else:
            raise NotImplementedError(f"function {f.tag}")

    def _fmm_spline(self):
        """OpenSim's SimmSpline: the Forsythe-Malcolm-Moler cubic spline (SIMM's calc_spline_coefficients),
        end conditions from the third derivative of the cubic through the first / last four points
        (fewer than four points: the 'parabolic' ends). Coefficients as y + b dx + c dx^2 + d dx^3."""
        x, y = self.x.astype(float), self.y.astype(float); n = len(x)
        b = np.zeros(n); c = np.zeros(n); d = np.zeros(n)
        if n < 2:
            self.b, self.cc, self.d = b, c, d; return
        if n < 3:
            b[0] = b[1] = (y[1] - y[0]) / (x[1] - x[0])
            self.b, self.cc, self.d = b, c, d; return
        nm1 = n - 1
        d[0] = x[1] - x[0]
        c[1] = (y[1] - y[0]) / d[0]
        for i in range(1, nm1):
            d[i] = x[i + 1] - x[i]
            b[i] = 2.0 * (d[i - 1] + d[i])
            c[i + 1] = (y[i + 1] - y[i]) / d[i]
            c[i] = c[i + 1] - c[i]
        b[0] = -d[0]; b[nm1] = -d[n - 2]
        c[0] = 0.0; c[nm1] = 0.0
        if n > 3:
            c[0] = c[2] / (x[3] - x[1]) - c[1] / (x[2] - x[0])
            c[nm1] = c[n - 2] / (x[nm1] - x[n - 3]) - c[n - 3] / (x[n - 2] - x[n - 4])
            c[0] = c[0] * d[0] * d[0] / (x[3] - x[0])
            c[nm1] = -c[nm1] * d[n - 2] * d[n - 2] / (x[nm1] - x[n - 4])
        for i in range(1, n):                                  # forward elimination
            t = d[i - 1] / b[i - 1]
            b[i] -= t * d[i - 1]
            c[i] -= t * c[i - 1]
        c[nm1] /= b[nm1]                                       # back substitution
        for i in range(n - 2, -1, -1):
            c[i] = (c[i] - d[i] * c[i + 1]) / b[i]
        b[nm1] = (y[nm1] - y[n - 2]) / d[n - 2] + d[n - 2] * (c[n - 2] + 2.0 * c[nm1])
        for i in range(nm1):
            b[i] = (y[i + 1] - y[i]) / d[i] - d[i] * (c[i + 1] + 2.0 * c[i])
            d[i] = (c[i + 1] - c[i]) / d[i]
            c[i] = 3.0 * c[i]
        c[nm1] = 3.0 * c[nm1]; d[nm1] = d[n - 2]
        self.b, self.cc, self.d = b, c, d

    def _spline(self):          # natural cubic spline (NaturalCubicSpline; GCVSpline approximated)
        x, y = self.x, self.y; n = len(x)
        if n < 3:
            self.b = np.zeros(n); self.cc = np.zeros(n); self.d = np.zeros(n)
            if n == 2:
                self.b[:] = (y[1] - y[0]) / (x[1] - x[0])
            return
        h = np.diff(x); A = np.zeros((n, n)); r = np.zeros(n)
        A[0, 0] = A[-1, -1] = 1
        for i in range(1, n - 1):
            A[i, i - 1], A[i, i], A[i, i + 1] = h[i - 1], 2 * (h[i - 1] + h[i]), h[i]
            r[i] = 3 * ((y[i + 1] - y[i]) / h[i] - (y[i] - y[i - 1]) / h[i - 1])
        c = np.linalg.solve(A, r)
        self.cc = c
        self.b = np.r_[[(y[i + 1] - y[i]) / h[i] - h[i] * (2 * c[i] + c[i + 1]) / 3 for i in range(n - 1)], 0]
        self.d = np.r_[[(c[i + 1] - c[i]) / (3 * h[i]) for i in range(n - 1)], 0]
        # end slope for extrapolation
        i = n - 2
        self.b[-1] = self.b[i] + 2 * c[i] * h[i] + 3 * self.d[i] * h[i] ** 2

    def __call__(self, v):
        k = self.kind
        if k == "const0":
            return v                 # no function: identity on the single coordinate
        if k == "LinearFunction":
            return self.c[0] * v + self.c[1]
        if k == "Constant":
            return self.c
        if k == "PolynomialFunction":
            return np.polyval(self.c, v)
        if k == "MultiplierFunction":
            return self.scale * self.inner(v)
        x = self.x
        if v <= x[0]:
            return self.y[0] + self.b[0] * (v - x[0])
        if v >= x[-1]:
            return self.y[-1] + self.b[-1] * (v - x[-1])
        i = int(np.searchsorted(x, v) - 1)
        dx = v - x[i]
        return self.y[i] + self.b[i] * dx + self.cc[i] * dx ** 2 + self.d[i] * dx ** 3


# ------------------------------------------------------------------ model
class Coordinate:
    def __init__(self, el):
        self.name = el.get("name")
        self.default = float(el.findtext("default_value") or 0)
        self.locked = (el.findtext("locked") or "").strip() == "true"
        self.clamped = (el.findtext("clamped") or "true").strip() == "true"   # OpenSim 4 default
        self.range = _vec(el.findtext("range"), 2)
        self.mtype = (el.findtext("motion_type") or "").strip()
        self.coupled = None          # (independent name, Func) when a coupler drives it


class Frame:
    def __init__(self, name, parent, R=np.eye(3), p=np.zeros(3)):
        self.name, self.parent, self.R, self.p = name, parent, R, p


class Joint:
    def __init__(self, el, model):
        self.name, self.type = el.get("name"), el.tag
        frames = {}
        fs = el.find("frames")
        if fs is not None:
            for f in fs:
                frames[f.get("name")] = Frame(
                    f.get("name"), _path_name(f.findtext("socket_parent")),
                    rot_xyz(_vec(f.findtext("orientation"))), _vec(f.findtext("translation")))
        self.parent = self._resolve(el.findtext("socket_parent_frame"), frames)
        self.child = self._resolve(el.findtext("socket_child_frame"), frames)
        self.coords = [Coordinate(c) for c in el.iter("Coordinate")]
        self.axes = []               # (kind 'r'/'t', axis, [coord names], Func)
        if el.tag == "CustomJoint":
            st = el.find("SpatialTransform")
            for ta in st.findall("TransformAxis"):
                names = (ta.findtext("coordinates") or "").split()
                self.axes.append(("r" if ta.get("name").startswith("rotation") else "t",
                                  _vec(ta.findtext("axis")), names, Func(_func_el(ta))))
        rr = {n for k, _, names, _ in self.axes if k == "r" for n in names}
        tr = {n for k, _, names, _ in self.axes if k == "t" for n in names} - rr
        if el.tag == "FreeJoint":
            tr |= {c.name for c in self.coords[3:]}
        if el.tag == "SliderJoint":
            tr |= {c.name for c in self.coords}
        for c in self.coords:
            c.translational = c.name in tr
        model.coords.update({c.name: c for c in self.coords})

    @staticmethod
    def _resolve(txt, frames):
        n = _path_name(txt)
        return frames.get(n) or Frame(n, n)     # a body itself

    def local(self, q):
        """X_FM: rotation R and position p of the child frame M in the parent frame F."""
        R, p = np.eye(3), np.zeros(3)
        t = self.type
        if t == "CustomJoint":
            rots = [a for a in self.axes if a[0] == "r"]
            trans = [a for a in self.axes if a[0] == "t"]
            for _, ax, names, f in rots:
                ang = f(q[names[0]]) if names else (f(0.0) if f.kind != "const0" else 0.0)
                R = R @ rot_axis(ax, ang)
            for _, ax, names, f in trans:
                d = f(q[names[0]]) if names else (f(0.0) if f.kind != "const0" else 0.0)
                p = p + np.asarray(ax) / np.linalg.norm(ax) * d
        elif t == "PinJoint":
            R = rot_axis([0, 0, 1], q[self.coords[0].name])
        elif t == "SliderJoint":
            p = np.array([q[self.coords[0].name], 0, 0])
        elif t in ("WeldJoint",):
            pass
        elif t == "UniversalJoint":
            R = rot_axis([1, 0, 0], q[self.coords[0].name]) @ rot_axis([0, 1, 0], q[self.coords[1].name])
        elif t in ("BallJoint", "GimbalJoint"):
            a = [q[c.name] for c in self.coords]
            R = rot_xyz(a)
        elif t == "FreeJoint":
            a = [q[c.name] for c in self.coords]
            R, p = rot_xyz(a[:3]), np.array(a[3:6])
        else:
            raise NotImplementedError(t)
        return R, p


def _func_el(parent):
    """A TransformAxis keeps its function either as <function><X/></function> or <X name="function">."""
    for c in parent:
        if c.tag == "function" or c.get("name") == "function":
            return c
    return None


def _path_name(txt):
    txt = (txt or "").strip()
    return txt.rsplit("/", 1)[-1] if txt else txt


class Model:
    def __init__(self, path):
        root = ET.parse(path).getroot()
        m = root.find("Model")
        self.name = m.get("name")
        self.path = path
        self.gravity = _vec(m.findtext("gravity") or "0 -9.80665 0")
        self.coords = {}
        self.bodies = {}
        for b in m.find("BodySet/objects"):
            self.bodies[b.get("name")] = dict(
                mass=float(b.findtext("mass") or 0), com=_vec(b.findtext("mass_center")),
                inertia=_vec(b.findtext("inertia"), 6))
        self.joints = [Joint(j, self) for j in m.find("JointSet/objects")]
        self.coord_order = [c.name for j in self.joints for c in j.coords]
        cs = m.find("ConstraintSet/objects")
        for c in (cs if cs is not None else []):
            if c.tag == "CoordinateCouplerConstraint" and (c.findtext("isEnforced") or "true").strip() != "false":
                dep = (c.findtext("dependent_coordinate_name") or "").strip()
                ind = (c.findtext("independent_coordinate_names") or "").split()
                self.coords[dep].coupled = (ind[0], Func(c.find("coupled_coordinates_function")))
        self.markers = {}
        ms = m.find("MarkerSet/objects")
        for mk in (ms if ms is not None else []):
            self.markers[mk.get("name")] = (_path_name(mk.findtext("socket_parent_frame")),
                                            _vec(mk.findtext("location")))
        # joints ordered so parents come first
        known, order, todo = {"ground"}, [], list(self.joints)
        while todo:
            for j in list(todo):
                pb = self._body_of(j.parent)
                if pb in known:
                    order.append(j); todo.remove(j); known.add(self._body_of(j.child))
            if todo and not any(self._body_of(j.parent) in known for j in todo):
                raise ValueError("joint tree is not connected to ground")
        self.joints = order
        # free coordinates = the ones IK solves for
        self.free = [n for n in self.coord_order
                     if not self.coords[n].locked and self.coords[n].coupled is None]

    def load_markerset(self, path):
        """Replace the model's markers by a MarkerSet .xml (as Scale / the GUI 'Load markers' do)."""
        root = ET.parse(path).getroot()
        objs = root.find(".//MarkerSet/objects")
        if objs is None:
            raise ValueError(f"no MarkerSet in {path}")
        self.markers = {mk.get("name"): (_path_name(mk.findtext("socket_parent_frame") or mk.findtext("body")),
                                         _vec(mk.findtext("location")))
                        for mk in objs if mk.tag == "Marker"}
        # a lab marker set often covers the whole body; a lower-limb model keeps only the markers it can carry
        missing = {b for b, _ in self.markers.values()} - set(self.bodies) - {"ground"}
        if missing:
            dropped = sorted(n for n, (b, _) in self.markers.items() if b in missing)
            self.markers = {n: v for n, v in self.markers.items() if v[0] not in missing}
            self.dropped_markers = (dropped, sorted(missing))
            if not self.markers:
                raise ValueError(f"no marker of the marker set is on a body of the model (it uses {', '.join(sorted(missing))})")

    @staticmethod
    def _body_of(frame):
        return frame.parent if frame.parent != frame.name else frame.name

    def full_q(self, q):
        """Fill in defaults (locked / missing) and couplers. q: dict name -> value (rad/m)."""
        out = {n: self.coords[n].default for n in self.coord_order}
        for n, v in q.items():
            if n in out and not self.coords[n].locked:
                out[n] = v
        for n, c in self.coords.items():
            if c.coupled:
                out[n] = c.coupled[1](out[c.coupled[0]])
        return out

    def body_transforms(self, q):
        """Ground rotation R and origin p of every body."""
        q = self.full_q(q)
        T = {"ground": (np.eye(3), np.zeros(3))}
        for j in self.joints:
            Rb, pb = T[self._body_of(j.parent)]
            Rf, pf = Rb @ j.parent.R, pb + Rb @ j.parent.p            # parent frame F in ground
            Rj, pj = j.local(q)
            Rm, pm = Rf @ Rj, pf + Rf @ pj                             # child frame M in ground
            Rc, pc = j.child.R, j.child.p                              # M expressed in child body
            Rbody = Rm @ Rc.T
            T[self._body_of(j.child)] = (Rbody, pm - Rbody @ pc)
        return T

    def marker_positions(self, q, names=None):
        T = self.body_transforms(q)
        names = names or list(self.markers)
        out = {}
        for n in names:
            b, loc = self.markers[n]
            R, p = T[b]
            out[n] = p + R @ loc
        return out


# ------------------------------------------------------------------ fast batched path
def _feval(f, v):
    """Vectorised Func evaluation (v: array)."""
    k = f.kind
    if k == "const0":
        return v
    if k == "LinearFunction":
        return f.c[0] * v + f.c[1]
    if k == "Constant":
        return np.full_like(v, f.c)
    if k == "PolynomialFunction":
        return np.polyval(f.c, v)
    if k == "MultiplierFunction":
        return f.scale * _feval(f.inner, v)
    x = f.x
    i = np.clip(np.searchsorted(x, v) - 1, 0, len(x) - 2)
    dx = v - x[i]
    y = f.y[i] + f.b[i] * dx + f.cc[i] * dx ** 2 + f.d[i] * dx ** 3
    y = np.where(v <= x[0], f.y[0] + f.b[0] * (v - x[0]), y)
    return np.where(v >= x[-1], f.y[-1] + f.b[-1] * (v - x[-1]), y)


def _rot_batch(axis, ang):
    k = np.asarray(axis, float); k = k / np.linalg.norm(k)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    s, c = np.sin(ang)[:, None, None], np.cos(ang)[:, None, None]
    return np.eye(3) + s * K + (1 - c) * (K @ K)


class Kinematics:
    """Batched forward kinematics: many poses at once (IK Jacobians, whole trials)."""

    def __init__(self, model, marker_names):
        self.m = model
        self.idx = {n: i for i, n in enumerate(model.coord_order)}
        self.default = np.array([model.coords[n].default for n in model.coord_order])
        self.free_idx = np.array([self.idx[n] for n in model.free])
        self.couplers = [(self.idx[n], self.idx[c.coupled[0]], c.coupled[1])
                         for n, c in model.coords.items() if c.coupled]
        self.names = list(marker_names)
        self.mk = [(model.markers[n][0], model.markers[n][1]) for n in self.names]

    def full(self, X):
        Q = np.repeat(self.default[None], len(X), 0)
        Q[:, self.free_idx] = X
        for d, i, f in self.couplers:
            Q[:, d] = _feval(f, Q[:, i])
        return Q

    def _plan(self):
        """Per joint, once: parent/child frames and the transform axes, with unit axes and
        cross-product matrices precomputed and constant axes folded into fixed matrices."""
        if getattr(self, "_p", None) is not None:
            return self._p
        m, plan = self.m, []
        for j in m.joints:
            steps = []                               # ("R", K, KK, coord_idx|None, func) / ("Rc", R) / ("t", unit, idx, func) / ("tc", vec)
            if j.type == "CustomJoint":
                for kind, ax, names, f in j.axes:
                    a = np.asarray(ax, float); a = a / np.linalg.norm(a)
                    if not names:                    # constant along this axis
                        v = 0.0 if f.kind == "const0" else float(_feval(f, np.zeros(1))[0])
                        if abs(v) < 1e-15:
                            continue
                        if kind == "r":
                            steps.append(("Rc", rot_axis(a, v)))
                        else:
                            steps.append(("tc", a * v))
                        continue
                    if kind == "r":
                        K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
                        steps.append(("R", K, K @ K, self.idx[names[0]], f))
                    else:
                        steps.append(("t", a, self.idx[names[0]], f))
            elif j.type == "PinJoint":
                K = np.array([[0., -1, 0], [1, 0, 0], [0, 0, 0]])
                steps.append(("R", K, K @ K, self.idx[j.coords[0].name], None))
            elif j.type != "WeldJoint":
                steps = None                         # rare joint types: per-pose fallback
            plan.append((j, m._body_of(j.parent), m._body_of(j.child), steps))
        self._p = plan
        return plan

    def couple(self, Q):
        """Full coordinate rows with the coupled (dependent) coordinates recomputed."""
        Q = np.array(Q, float)
        for d, i, f in self.couplers:
            Q[:, d] = _feval(f, Q[:, i])
        return Q

    def markers(self, X):
        """X: (B, n_free) -> (B, n_markers, 3)."""
        T = self.bodies(self.full(np.atleast_2d(X)))
        return np.stack([T[b][1] + T[b][0] @ loc for b, loc in self.mk], axis=1)

    def bodies(self, Q):
        """Q: (B, n_coords) full coordinates -> {body: (R (B,3,3), origin (B,3))}."""
        B = len(Q); m = self.m
        I3 = np.eye(3)
        T = {"ground": (np.broadcast_to(I3, (B, 3, 3)), np.zeros((B, 3)))}
        for j, pbody, cbody, steps in self._plan():
            Rb, pb = T[pbody]
            Rf = Rb @ j.parent.R; pf = pb + Rb @ j.parent.p
            R = None; p = None
            if steps is None:
                Rs, ps = zip(*[j.local({n: Q[b, i] for n, i in self.idx.items()}) for b in range(B)])
                R, p = np.array(Rs), np.array(ps)
            else:
                for st in steps:
                    if st[0] == "R":
                        _, K, KK, ci, f = st
                        v = Q[:, ci] if f is None or f.kind == "const0" else _feval(f, Q[:, ci])
                        Ri = I3 + np.sin(v)[:, None, None] * K + (1 - np.cos(v))[:, None, None] * KK
                        R = Ri if R is None else R @ Ri
                    elif st[0] == "Rc":
                        R = st[1] if R is None else R @ st[1]
                    elif st[0] == "t":
                        _, a, ci, f = st
                        v = Q[:, ci] if f.kind == "const0" else _feval(f, Q[:, ci])
                        d = v[:, None] * a
                        p = d if p is None else p + d
                    else:
                        p = st[1] if p is None else p + st[1]
            Rm = Rf if R is None else Rf @ R
            pm = pf if p is None else (pf + (np.einsum("bij,bj->bi", Rf, p) if np.ndim(p) == 2 else Rf @ p))
            Rbody = Rm @ j.child.R.T
            T[cbody] = (np.broadcast_to(Rbody, (B, 3, 3)) if Rbody.ndim == 2 else Rbody, pm - Rbody @ j.child.p)
        return T
