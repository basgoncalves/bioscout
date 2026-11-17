"""Induced acceleration analysis (IAA) in pure Python -- the contribution of
every muscle, actuator, gravity and the velocity (Coriolis/centrifugal) terms
to each coordinate's acceleration, to the whole-body centre-of-mass
acceleration, and to the ground reaction force under each foot.

Each contributor's generalised force tau_i is applied ALONE to the model with
the feet replaced by kinematic constraints (OpenSim's IAA: the contact is a
constraint, not a spring), and the constrained equations of motion are solved:

    [ M   Jc^T ] [ qdd_i    ]   [ tau_i ]
    [ Jc   0   ] [ lambda_i ] = [ b_i   ]

M the mass matrix and Jc the contact Jacobian of the feet on the ground
(a foot is constrained while its measured |GRF| > force_threshold). Because the
system is linear, the qdd_i and the induced reactions -lambda_i add up to the
whole: sum_i qdd_i = the model's acceleration, sum_i (-lambda_i) = the GRF.

  * muscles   : tau = r(q) F_SO   (r = -dL/dq over every free coordinate, so
                wrapping is honoured; F_SO from static optimisation)
  * actuators : SO's reserves (CoordinateActuator), residuals (PointActuator /
                TorqueActuator on the pelvis), at their SO force
  * gravity   : tau = sum_b Jv_b^T m_b g
  * velocity  : tau = -(Coriolis/centrifugal), from the body kinematics; it
                also carries b = Jc qdd_measured, so the contact rows of the
                sum match the measured motion of the contact point

Contact models (``constraint``):
  * "rolling" (default): the foot point under the centre of pressure cannot
    slip (3 rows) and the foot cannot spin about the ground normal (1 row) --
    OpenSim's RollingOnSurfaceConstraint;
  * "point"  : the 3 linear rows only (PointConstraint);
  * "weld"   : the foot cannot translate or rotate (6 rows, WeldConstraint).

Coordinates coupled to others (patella, condyles) and locked ones are carried
by their independent coordinate, so the solve is over model.free.
"""
import os
import re
import numpy as np
from .model import Model, Kinematics
from .muscles import Paths
from .io import read_sto, write_mot
from . import id as idtool
import xml.etree.ElementTree as ET

DQ = 1e-6


# ------------------------------------------------------------------ actuators
def read_actuators_any(*paths):
    """CoordinateActuator / PointActuator / TorqueActuator from actuator .xml files
    -> {name: dict(kind, ...)} (geometry only; the force comes from the SO file)."""
    out = {}
    tf = lambda e, k, d: (e.findtext(k) or d).strip().lower() == "true"
    for p in paths:
        if not p or not os.path.isfile(p):
            continue
        for a in ET.parse(p).getroot().iter():
            if a.tag not in ("CoordinateActuator", "PointActuator", "TorqueActuator"):
                continue
            if (a.findtext("appliesForce") or "true").strip() == "false":
                continue
            n = a.get("name")
            if a.tag == "CoordinateActuator":
                out[n] = dict(kind="coord", coord=(a.findtext("coordinate") or "").strip())
            elif a.tag == "PointActuator":
                out[n] = dict(kind="point", body=(a.findtext("body") or "").strip(),
                              point=np.array((a.findtext("point") or "0 0 0").split(), float),
                              direction=np.array((a.findtext("direction") or "1 0 0").split(), float),
                              point_global=tf(a, "point_is_global", "false"),
                              force_global=tf(a, "force_is_global", "false"))
            else:
                out[n] = dict(kind="torque", bodyA=(a.findtext("bodyA") or "").strip().split("/")[-1],
                              bodyB=(a.findtext("bodyB") or "").strip().split("/")[-1],
                              axis=np.array((a.findtext("axis") or "0 0 1").split(), float),
                              global_=tf(a, "torque_is_global", "true"))
    return out


def model_actuators(osim_path):
    return read_actuators_any(osim_path)


# ------------------------------------------------------------------ kinematics
class _State:
    """Everything per frame that does not depend on who pulls: mass matrix, Jacobians over
    the free coordinates, body kinematics, measured accelerations."""

    def __init__(self, model, t, Q, log=print):
        self.m, self.t, self.Q = model, t, Q
        kin = self.kin = Kinematics(model, [])
        self.free = list(model.free)
        fi = np.array([model.coord_order.index(c) for c in self.free])
        self.fi = fi
        n, nf = len(t), len(fi)
        names = self.names = list(model.bodies)
        self.bidx = {b: k for k, b in enumerate(names)}
        nb = len(names)
        mass = self.mass = np.array([model.bodies[b]["mass"] for b in names])
        com = np.array([model.bodies[b]["com"] for b in names])
        Iloc = np.zeros((nb, 3, 3))
        for k, b in enumerate(names):
            xx, yy, zz, xy, xz, yz = model.bodies[b]["inertia"]
            Iloc[k] = [[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]]
        _, C, R = idtool._body_state(model, Q, t, kin)
        self.C, self.R = C, R
        V = np.gradient(C, t, axis=0); self.A = np.gradient(V, t, axis=0)
        Rd = np.gradient(R, t, axis=0)
        S = np.einsum("nbij,nbkj->nbik", Rd, R)
        self.W = np.stack([S[..., 2, 1] - S[..., 1, 2], S[..., 0, 2] - S[..., 2, 0], S[..., 1, 0] - S[..., 0, 1]], -1) / 2
        self.AL = np.gradient(self.W, t, axis=0)
        self.Ig = np.einsum("nbij,bjk,nblk->nbil", R, Iloc, R)
        # Jacobians over the free coordinates (a perturbed coordinate drags its couplers)
        Jv = np.zeros((n, nf, nb, 3)); Jw = np.zeros((n, nf, nb, 3))
        step = max(1, 4000 // (nf + 1))
        for a in range(0, n, step):
            Qs = Q[a:a + step]; mm = len(Qs)
            P = np.repeat(Qs[:, None, :], nf + 1, axis=1)
            P[:, np.arange(1, nf + 1), fi] += DQ
            P = kin.couple(P.reshape(-1, Q.shape[1]))
            T = kin.bodies(P)
            Rb = np.stack([np.broadcast_to(T[b][0], (len(P), 3, 3)) for b in names], 1).reshape(mm, nf + 1, nb, 3, 3)
            Cb = np.stack([T[b][1] + T[b][0] @ com[k] for k, b in enumerate(names)], 1).reshape(mm, nf + 1, nb, 3)
            Jv[a:a + mm] = (Cb[:, 1:] - Cb[:, :1]) / DQ
            dR = np.einsum("mqbij,mbkj->mqbik", Rb[:, 1:], Rb[:, 0])
            Jw[a:a + mm] = np.stack([dR[..., 2, 1] - dR[..., 1, 2], dR[..., 0, 2] - dR[..., 2, 0],
                                     dR[..., 1, 0] - dR[..., 0, 1]], -1) / (2 * DQ)
        self.Jv, self.Jw = Jv, Jw
        self.M = (np.einsum("nkbi,b,nlbi->nkl", Jv, mass, Jv)
                  + np.einsum("nkbi,nbij,nlbj->nkl", Jw, self.Ig, Jw))
        qf = Q[:, fi]
        self.qdd = np.gradient(np.gradient(qf, t, axis=0), t, axis=0)
        # bias (Coriolis/centrifugal): what the body accelerations are beyond J qdd
        aC_b = self.A - np.einsum("nkbi,nk->nbi", Jv, self.qdd)                 # Jv_dot qd
        al_b = self.AL - np.einsum("nkbi,nk->nbi", Jw, self.qdd)                # Jw_dot qd
        Mw = np.einsum("nbij,nbj->nbi", self.Ig, al_b) + np.cross(self.W, np.einsum("nbij,nbj->nbi", self.Ig, self.W))
        self.h = np.einsum("nkbi,b,nbi->nk", Jv, mass, aC_b) + np.einsum("nkbi,nbi->nk", Jw, Mw)
        self.aC_bias = aC_b
        self.tau_g = np.einsum("nkbi,b,i->nk", Jv, mass, np.asarray(model.gravity))
        self.mtot = mass.sum()
        self.com_acc = np.einsum("b,nbi->ni", mass, self.A) / self.mtot
        log(f"[iaa] {n} frames, {nf} free coordinates, {nb} bodies")

    def origin(self, b):
        k = self.bidx[b]
        return self.C[:, k] - np.einsum("nij,j->ni", self.R[:, k], self.m.bodies[b]["com"])

    def point_jac(self, b, P):
        """Jacobian of a point P (n,3, ground) fixed on body b: (n, nf, 3)."""
        k = self.bidx[b]
        r = P - self.C[:, k]
        return self.Jv[:, :, k] + np.cross(self.Jw[:, :, k], r[:, None, :])


# ------------------------------------------------------------------ contact
def _contacts(st, loads_xml, loads_mot=None, threshold=20.0):
    """Per foot body: summed measured GRF (n,3), centre of pressure (n,3), on-mask (n,)."""
    if not loads_xml:
        return {}
    datafile, forces = idtool.read_external_loads(loads_xml, loads_mot)
    if not os.path.isabs(datafile) and not os.path.isfile(datafile):
        datafile = os.path.join(os.path.dirname(loads_xml), datafile)
    cols, data, _ = read_sto(datafile)
    ts = data[:, cols.index("time")]; t = st.t
    feet = {}
    for f in forces:
        b = f["body"]
        if b not in st.bidx:
            continue
        F = idtool._xyz(cols, data, f["fid"], ts, t); P = idtool._xyz(cols, data, f["pid"], ts, t)
        if f["force_in"] != "ground":
            F = np.einsum("nij,nj->ni", st.R[:, st.bidx[f["force_in"]]], F)
        if f["point_in"] != "ground":
            P = st.origin(f["point_in"]) + np.einsum("nij,nj->ni", st.R[:, st.bidx[f["point_in"]]], P)
        F0, P0 = feet.get(b, (np.zeros_like(F), np.zeros_like(P)))
        w0, w1 = np.abs(F0[:, 1:2]), np.abs(F[:, 1:2])                            # COP weighted by vertical load
        Pm = np.where(w0 + w1 > 1e-9, (P0 * w0 + P * w1) / np.maximum(w0 + w1, 1e-9), P)
        feet[b] = (F0 + F, Pm)
    return {b: (F, P, np.linalg.norm(F, axis=1) > threshold) for b, (F, P) in feet.items()}


# ------------------------------------------------------------------ the analysis
def measured(model_path, coords_mot, loads_xml, t_eval=None, loads_mot=None, cutoff=6.0, log=print):
    """The measured side of the IAA check, on the coordinate times (optionally interpolated to
    t_eval): free-coordinate accelerations, COM acceleration, GRF per foot body."""
    model = model_path if isinstance(model_path, Model) else Model(model_path)
    t, Q = idtool.read_coords(model, coords_mot)
    Q = idtool._lowpass(Q, t, cutoff)
    if t_eval is not None:
        m = (t >= t_eval[0] - 0.05) & (t <= t_eval[-1] + 0.05); t, Q = t[m], Q[m]
    st = _State(model, t, Q, log=lambda *a, **k: None)
    feet = _contacts(st, loads_xml, loads_mot)
    out = dict(t=t, coords=st.free, qdd=st.qdd, com=st.com_acc, grf={b: F for b, (F, _, _) in feet.items()})
    if t_eval is not None:
        it = lambda X: np.stack([np.interp(t_eval, t, X[:, j]) for j in range(X.shape[1])], 1)
        out = dict(t=np.asarray(t_eval), coords=st.free, qdd=it(st.qdd), com=it(st.com_acc),
                   grf={b: it(F) for b, F in out["grf"].items()})
    return out


def run(model_path, coords_mot, forces_sto, loads_xml, out_dir, actuators=None, loads_mot=None,
        constraint="rolling", force_threshold=20.0, cutoff=6.0, t_range=None, log=print, write=True):
    """IAA of one trial -> files in out_dir (see bioscout.simulate.iaa_files.write). Returns the
    result dict that write() takes (write=False: only return it)."""
    model = model_path if isinstance(model_path, Model) else Model(model_path)
    osim = model.path
    fc, fd, _ = read_sto(forces_sto)
    tf = fd[:, fc.index("time")]
    t, Q = idtool.read_coords(model, coords_mot)
    Q = idtool._lowpass(Q, t, cutoff)
    lo, hi = (tf[0], tf[-1]) if t_range is None else (max(tf[0], t_range[0]), min(tf[-1], t_range[1]))
    msk = (t >= lo - 1e-9) & (t <= hi + 1e-9)
    t, Q = t[msk], Q[msk]
    n = len(t)
    if n < 5:
        raise ValueError("the SO forces and the joint angles hardly overlap in time")
    st = _State(model, t, Q, log)
    nf = len(st.free)
    F_of = lambda name: np.interp(t, tf, fd[:, fc.index(name)])

    # ---- generalised force of every contributor: (n, nf) each
    taus, labels = [st.tau_g, -st.h], ["gravity", "velocity"]
    paths = Paths(model, osim)
    mus = [m["name"] for m in paths.mus]
    used = [k for k, m in enumerate(mus) if m in fc]
    log(f"[iaa] moment arms of {len(used)} muscles about {nf} coordinates")
    _, Rm = paths.moment_arms(Q, st.free)                                     # (n, nf, M)
    for k in used:
        taus.append(Rm[:, :, k] * F_of(mus[k])[:, None]); labels.append(mus[k])
    acts = model_actuators(osim)
    acts.update(read_actuators_any(*(actuators if isinstance(actuators, (list, tuple)) else [actuators])))
    skipped = []
    for name, a in acts.items():
        if name not in fc or name in labels:
            continue
        F = F_of(name)
        if a["kind"] == "coord":
            if a["coord"] not in st.free:
                skipped.append(name); continue
            tau = np.zeros((n, nf)); tau[:, st.free.index(a["coord"])] = F
        elif a["kind"] == "point":
            b = a["body"]
            if b not in st.bidx:
                skipped.append(name); continue
            Rb = st.R[:, st.bidx[b]]
            P = a["point"][None] if a["point_global"] else st.origin(b) + np.einsum("nij,j->ni", Rb, a["point"])
            P = np.broadcast_to(P, (n, 3))
            d = a["direction"] / max(np.linalg.norm(a["direction"]), 1e-12)
            dg = np.broadcast_to(d, (n, 3)) if a["force_global"] else np.einsum("nij,j->ni", Rb, d)
            tau = np.einsum("nki,ni->nk", st.point_jac(b, P), dg) * F[:, None]
        else:
            ax = a["axis"] / max(np.linalg.norm(a["axis"]), 1e-12)
            tau = np.zeros((n, nf))
            for b, s in ((a["bodyA"], 1.0), (a["bodyB"], -1.0)):
                if b not in st.bidx:
                    continue
                k = st.bidx[b]
                axg = np.broadcast_to(ax, (n, 3)) if a["global_"] else np.einsum("nij,j->ni", st.R[:, st.bidx[a["bodyA"]]], ax)
                tau += s * np.einsum("nki,ni->nk", st.Jw[:, :, k], axg) * F[:, None]
        taus.append(tau); labels.append(name)
    if skipped:
        log(f"[iaa] actuators not applied (coordinate/body not free in the model): {', '.join(skipped)}")
    missing = [c for c in fc if c != "time" and c not in labels
               and not re.search(r"_(F|p|T)[xyz]$", c)]                      # the external loads SO echoes
    if missing:
        log(f"[iaa] SO force columns with no actuator found (left out): {', '.join(missing[:12])}"
            + (" ..." if len(missing) > 12 else ""))
    TAU = np.stack(taus, -1)                                                  # (n, nf, nc)
    nc = TAU.shape[-1]

    # ---- contact constraints
    feet = _contacts(st, loads_xml, loads_mot, force_threshold)
    nrm = -np.asarray(model.gravity) / max(np.linalg.norm(model.gravity), 1e-12)
    rows = {"rolling": 4, "point": 3, "weld": 6}[constraint]
    log(f"[iaa] contact: {constraint} constraint on " + (", ".join(
        f"{b} ({int(on.sum())}/{n} frames)" for b, (_, _, on) in feet.items()) or "no foot"))
    QDD = np.zeros((n, nf, nc))
    REAC = {b: np.zeros((n, 3, nc)) for b in feet}
    for i in range(n):
        Jc, b_rhs, blocks = [], [], []
        for b, (Fm, P, on) in feet.items():
            if not on[i]:
                continue
            k = st.bidx[b]
            r = P[i] - st.C[i, k]
            Jp = st.Jv[i, :, k] + np.cross(st.Jw[i, :, k], r)                 # (nf, 3)
            Jr = st.Jw[i, :, k]
            if constraint == "rolling":
                J = np.column_stack([Jp, Jr @ nrm])
            elif constraint == "point":
                J = Jp
            else:
                J = np.column_stack([Jp, Jr])
            blocks.append((b, sum(x.shape[0] for x in Jc)))
            Jc.append(J.T)
        Mi = st.M[i]
        if Jc:
            J = np.vstack(Jc); m = J.shape[0]
            K = np.zeros((nf + m, nf + m)); K[:nf, :nf] = Mi; K[:nf, nf:] = J.T; K[nf:, :nf] = J
            RHS = np.zeros((nf + m, nc)); RHS[:nf] = TAU[i]
            RHS[nf:, 1] = J @ st.qdd[i]                                       # contact rows of the measured motion
            X = np.linalg.lstsq(K, RHS, rcond=None)[0]
            QDD[i] = X[:nf]
            for b, o in blocks:
                REAC[b][i] = -X[nf + o: nf + o + 3]                          # force the ground puts on the foot
        else:
            QDD[i] = np.linalg.solve(Mi, TAU[i])
        if i % 50 == 0:
            log(f"[iaa] frame {i + 1}/{n}")

    # ---- centre of mass: sum_b m_b Jv_b qdd / M_total (+ the velocity bias)
    COM = np.einsum("b,nkbi,nkc->nic", st.mass, st.Jv, QDD) / st.mtot
    COM[:, :, 1] += np.einsum("b,nbi->ni", st.mass, st.aC_bias) / st.mtot
    res = dict(t=t, labels=labels, coords=st.free, muscles=[mus[k] for k in used], tau=TAU, qdd=QDD, com=COM,
               reactions=REAC, measured=dict(coords=st.free, qdd=st.qdd, com=st.com_acc,
                                             grf={b: F for b, (F, _, _) in feet.items()}),
               engine="pyosim", constraint=constraint, force_threshold=force_threshold)
    if write:
        from bioscout.simulate import iaa_files
        iaa_files.write(out_dir, res, log=log)
    return res
