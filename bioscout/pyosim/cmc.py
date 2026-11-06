"""Computed muscle control in pure Python, after OpenSim's CMCTool (Thelen &
Anderson 2006): the muscle-driven model is integrated FORWARD while, every
``window`` seconds, a static optimisation picks the excitations that make it
follow the measured kinematics.

Per window [t, t+T]:

  1. desired accelerations, PD-corrected toward the experimental kinematics
         qdd* = qdd_exp + kv (qd_exp - qd) + kp (q_exp - q)     (kp from the
         CMC/RRA task file, kv = 2 sqrt(kp), at t + T/2)
  2. generalised forces that produce qdd* in the CURRENT state
         tau* = M(q) qdd* + b(q, qd) - Q_ext(t + T/2)
  3. static optimisation: end-of-window activations a_T (bounded by first-order
     activation dynamics from a(t) with excitation 0 / 1) and actuator controls u
     minimising sum a_T^2 + sum u^2 s.t. R (a_mean * Fa) + A u = tau*,
     a_mean = (a(t) + a_T) / 2, Fa = F0 fl(lm) fv(vm) cos(pennation)
  4. excitations u_m that take a(t) to a_T, then integrate q, qd, a over the
     window (semi-implicit Euler, ``dt``) with those excitations held.

Dynamics: M(q) = sum_b m J_v^T J_v + J_w^T I_g J_w and the bias b(q, qd) from the
body Jacobians of id.py (finite differences of the forward kinematics, so
couplers are honoured); J_dot qd by a finite difference along qd. Integrated
DOFs = the model's free, unlocked coordinates; couplers are recomputed.

Differences from OpenSim's CMC (stated, not hidden):
  * rigid tendon, as pyosim SO (no fibre-length states); muscle geometry, fl and
    fv are evaluated at the start of each window and held over it (10 ms);
  * pelvis residuals act as generalised forces on the six pelvis coordinates
    (optimal force from the FX..MZ Point/TorqueActuators), not at the COM;
  * passive fibre force left out unless passive=True (as SO).

Writes, into out_dir, OpenSim's CMC file names: CMC_Actuation_force.sto (muscle
forces + actuator forces), CMC_Kinematics_q.sto (deg), CMC_states.sto
(activations), CMC_controls.sto (excitations), CMC_pErr.sto (q_exp - q).
"""
import os
import re
import time as _time
import xml.etree.ElementTree as ET
import numpy as np
from scipy.interpolate import make_interp_spline
from scipy.optimize import minimize
from .model import Model, Kinematics
from .muscles import Paths
from .io import read_sto, write_mot
from . import id as idtool
from . import millard
from .so import read_actuators, f_active, f_velocity, f_passive

T_ACT, T_DEACT = 0.010, 0.040          # Thelen 2003 / OpenSim activation time constants
A_MIN = 0.01
PELVIS = ("pelvis_tilt", "pelvis_list", "pelvis_rotation", "pelvis_tx", "pelvis_ty", "pelvis_tz")


# --------------------------------------------------------------- activation dynamics
def _act_rate(u, a):
    tau = np.where(u > a, T_ACT * (0.5 + 1.5 * a), T_DEACT / (0.5 + 1.5 * a))
    return (u - a) / tau


def _act_after(a0, u, T, n=10):
    a = np.array(a0, float); h = T / n
    for _ in range(n):
        a = np.clip(a + h * _act_rate(u, a), A_MIN, 1.0)
    return a


def _excitation_for(a0, aT, T):
    """Excitation (held over T) that takes a0 to aT; bisection, monotone in u."""
    lo, hi = np.zeros_like(a0), np.ones_like(a0)
    for _ in range(22):
        mid = 0.5 * (lo + hi)
        up = _act_after(a0, mid, T) < aT
        lo, hi = np.where(up, mid, lo), np.where(up, hi, mid)
    return 0.5 * (lo + hi)


# --------------------------------------------------------------- tasks / actuators
def read_tasks(path):
    """CMC_Joint / RRA task file -> {coordinate: (kp, kv)} for active tasks."""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    for e in ET.parse(path).getroot().iter("CMC_Joint"):
        if (e.findtext("on") or "true").strip() == "false":
            continue
        c = (e.findtext("coordinate") or e.get("name") or "").strip()
        kp = float((e.findtext("kp") or "100").split()[0])
        kvt = e.findtext("kv")
        kv = float(kvt.split()[0]) if kvt and kvt.strip() else 2 * np.sqrt(kp)
        out[c] = (kp, kv)
    return out


def _residual_forces(path):
    """FX..MZ Point/TorqueActuators -> {pelvis coordinate: optimal force}."""
    out = {}
    if not path or not os.path.isfile(path):
        return out
    m = {"FX": "pelvis_tx", "FY": "pelvis_ty", "FZ": "pelvis_tz",
         "MX": "pelvis_list", "MY": "pelvis_rotation", "MZ": "pelvis_tilt"}
    for tag in ("PointActuator", "TorqueActuator"):
        for a in ET.parse(path).getroot().iter(tag):
            n = a.get("name")
            if n in m:
                out[m[n]] = float(a.findtext("optimal_force") or 1)
    return out


# --------------------------------------------------------------- multibody dynamics
class Dynamics:
    def __init__(self, model, kin, D, qref):
        self.m, self.kin, self.D = model, kin, np.asarray(D)
        self.names = list(model.bodies)
        self.mass = np.array([model.bodies[b]["mass"] for b in self.names])
        self.com = np.array([model.bodies[b]["com"] for b in self.names])
        I = []
        for b in self.names:
            xx, yy, zz, xy, xz, yz = model.bodies[b]["inertia"]
            I.append([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])
        self.Iloc = np.array(I, float)
        self.g = np.asarray(model.gravity, float)
        self.qref = np.array(qref, float)

    def full(self, qD, base=None):
        q = (self.qref if base is None else base).copy()
        q[self.D] = qD
        return self.kin.couple(q[None])[0]

    def _J(self, q):
        Jv, Jw = idtool._jacobians_all(self.m, q[None], self.names, self.kin)
        return Jv[0][self.D], Jw[0][self.D]                         # (nD, nb, 3)

    def _frames(self, q):
        T = self.kin.bodies(q[None])
        R = np.stack([np.asarray(T[b][0]).reshape(-1, 3, 3)[0] for b in self.names])
        O = np.stack([np.asarray(T[b][1]).reshape(-1, 3)[0] for b in self.names])
        return R, O, O + np.einsum("bij,bj->bi", R, self.com)

    def terms(self, q, qd, ext):
        """-> M (nD,nD), b (nD,): M qdd + b = tau + Q_ext, and Q_ext (nD,)."""
        Jv, Jw = self._J(q)
        h = 1e-5
        q2 = q.copy(); q2[self.D] = q[self.D] + h * qd
        Jv2, Jw2 = self._J(self.kin.couple(q2[None])[0])
        Jvd, Jwd = (Jv2 - Jv) / h, (Jw2 - Jw) / h
        R, O, C = self._frames(q)
        Ig = np.einsum("bij,bjk,blk->bil", R, self.Iloc, R)
        w = np.einsum("kbj,k->bj", Jw, qd)
        acb = np.einsum("kbj,k->bj", Jvd, qd)
        alb = np.einsum("kbj,k->bj", Jwd, qd)
        M = np.einsum("kbi,b,lbi->kl", Jv, self.mass, Jv) + np.einsum("kbi,bij,lbj->kl", Jw, Ig, Jw)
        Fb = self.mass[:, None] * (acb - self.g[None])
        Mb = np.einsum("bij,bj->bi", Ig, alb) + np.cross(w, np.einsum("bij,bj->bi", Ig, w))
        bias = np.einsum("kbj,bj->k", Jv, Fb) + np.einsum("kbj,bj->k", Jw, Mb)
        Fe = np.zeros_like(Fb); Me = np.zeros_like(Mb)
        for b, F, P, Tq, fin, pin in ext:
            if fin is not None:
                F = R[fin] @ F; Tq = R[fin] @ Tq
            if pin is not None:
                P = O[pin] + R[pin] @ P
            Fe[b] += F; Me[b] += np.cross(P - C[b], F) + Tq
        Qe = np.einsum("kbj,bj->k", Jv, Fe) + np.einsum("kbj,bj->k", Jw, Me)
        return M, bias, Qe


# --------------------------------------------------------------- the tool
def run(model_path, coords_mot, loads_xml, out_dir, actuators=None, tasks=None, t_range=None,
        cutoff=6.0, window=0.01, dt=0.001, passive=False, loads_mot=None, log=print):
    t_start = _time.time()
    model = model_path if isinstance(model_path, Model) else Model(model_path)
    osim = model_path if isinstance(model_path, str) else model.path
    kin = Kinematics(model, [])
    paths = Paths(model, osim)

    # experimental kinematics: filtered, quintic spline -> q, qd, qdd at any t
    t, Q = idtool.read_coords(model, coords_mot)
    Q = idtool._lowpass(Q, t, cutoff)
    sp = make_interp_spline(t, Q, k=5, axis=0); spd = sp.derivative(); spdd = sp.derivative(2)
    t0, t1 = (t[0], t[-1]) if not t_range else (max(t[0], t_range[0]), min(t[-1], t_range[1]))
    D_names = [c for c in model.free if not model.coords[c].locked]
    D = [model.coord_order.index(c) for c in D_names]
    nD = len(D)
    dyn = Dynamics(model, kin, D, sp(t0))

    # tracking gains
    tk = read_tasks(tasks)
    kp = np.array([tk.get(c, (100.0, 20.0))[0] for c in D_names])
    kv = np.array([tk.get(c, (100.0, 20.0))[1] for c in D_names])
    untracked = [c for c in D_names if c not in tk]

    # external loads (ground-expressed CoP/force as bioscout's GRF.xml writes them)
    ext_series = []
    if loads_xml:
        datafile, forces = idtool.read_external_loads(loads_xml, loads_mot)
        if not os.path.isabs(datafile) and not os.path.isfile(datafile):
            datafile = os.path.join(os.path.dirname(loads_xml), datafile)
        cols, data, _ = read_sto(datafile)
        ts = data[:, cols.index("time")]
        bidx = {b: k for k, b in enumerate(dyn.names)}
        for f in forces:
            if f["body"] not in bidx:
                continue
            g3 = lambda ident: idtool._xyz(cols, data, ident, ts, ts)
            ext_series.append((bidx[f["body"]], g3(f["fid"]), g3(f["pid"]), g3(f["tid"]),
                               None if f["force_in"] == "ground" else bidx[f["force_in"]],
                               None if f["point_in"] == "ground" else bidx[f["point_in"]]))

        def ext_at(tt):
            return [(b, np.array([np.interp(tt, ts, F[:, a]) for a in range(3)]),
                     np.array([np.interp(tt, ts, P[:, a]) for a in range(3)]),
                     np.array([np.interp(tt, ts, T_[:, a]) for a in range(3)]), fi, pi)
                    for b, F, P, T_, fi, pi in ext_series]
    else:
        def ext_at(tt):
            return []

    # actuators: coordinate actuators (uncapped) + pelvis residuals + 1 N.m reserves
    act = read_actuators(osim, actuators)
    an, ac, aopt = [], [], []
    for n, (c, opt, _lo, _hi) in act.items():
        if c in D_names:
            an.append(n); ac.append(D_names.index(c)); aopt.append(opt)
    res = _residual_forces(actuators)
    for c in PELVIS:
        if c in D_names and D_names.index(c) not in ac:
            an.append(f"{c}_residual"); ac.append(D_names.index(c)); aopt.append(res.get(c, 100.0))
    added = []
    for k, c in enumerate(D_names):
        if k not in ac:
            an.append(f"{c}_reserve"); ac.append(k); aopt.append(1.0); added.append(c)
    aopt = np.array(aopt); nA = len(an)
    Ac = np.zeros((nD, nA)); Ac[ac, np.arange(nA)] = aopt
    log(f"[cmc] {nD} DOFs, {len(paths.mus)} muscles, {nA} actuators "
        f"({len(res)} pelvis residuals from FX..MZ; reserves added: {added or 'none'}); "
        f"window {window * 1000:.0f} ms, dt {dt * 1000:.1f} ms, {t0:.3f}-{t1:.3f} s")
    if untracked:
        log(f"[cmc] no task for {untracked}: kp=100, kv=20")

    mus = paths.mus
    F0 = np.array([m["F0"] for m in mus]); lopt = np.array([m["lopt"] for m in mus])
    lts = np.array([m["lts"] for m in mus]); al0 = np.array([m["alpha"] for m in mus])
    vmax = np.array([m["vmax"] for m in mus]); hgt = lopt * np.sin(al0)
    curves = millard.curves_from_osim(osim) if osim else {}

    def muscle_terms(q, qd):
        L, Rm = paths.moment_arms(q[None], D_names)                  # (1,M), (1,nD,M)
        L, Rm = L[0], Rm[0]
        lmt = np.maximum(L - lts, 1e-4)
        lm = np.sqrt(lmt ** 2 + hgt ** 2); cosa = lmt / lm
        vm = -(Rm.T @ qd) * cosa
        nl, nv = lm / lopt, vm / (vmax * lopt)
        fl, fv = f_active(nl), f_velocity(nv)
        for k, m in enumerate(mus):
            if m["name"] in curves:
                cfl, cfv = curves[m["name"]]
                fl[k] = cfl(np.atleast_1d(nl[k]))[0]; fv[k] = cfv(np.atleast_1d(nv[k]))[0]
        Fa = F0 * fl * fv * cosa
        Fp = F0 * f_passive(nl) * cosa if passive else np.zeros_like(Fa)
        return Rm, Fa, Fp

    def solve(a0, lo, hi, Rm, Fa, Fp, tau, x0):
        A = np.hstack([0.5 * Rm * Fa[None], Ac])
        b = tau - Rm @ (0.5 * a0 * Fa + Fp)
        lb = np.concatenate([lo, np.full(nA, -1e4)]); ub = np.concatenate([hi, np.full(nA, 1e4)])
        r = minimize(lambda z: z @ z, x0, jac=lambda z: 2 * z, method="SLSQP", bounds=list(zip(lb, ub)),
                     constraints=[{"type": "eq", "fun": lambda z: A @ z - b, "jac": lambda z: A}],
                     options={"maxiter": 300, "ftol": 1e-9})
        z = np.clip(r.x, lb, ub)
        return z, float(np.abs(A @ z - b).max())

    # initial state on the experimental trajectory; initial activations from a
    # static solve there (OpenSim CMC also solves for its initial state)
    q = sp(t0).copy(); qD = q[D].copy(); vD = spd(t0)[D].copy()
    M0, b0, Qe0 = dyn.terms(q, vD, ext_at(t0))
    Rm, Fa, Fp = muscle_terms(q, vD)
    tau0 = M0 @ spdd(t0)[D] + b0 - Qe0
    z, _ = solve(np.zeros(len(mus)), np.full(len(mus), A_MIN), np.ones(len(mus)),
                 2 * Rm, Fa, Fp, tau0, np.concatenate([np.full(len(mus), 0.05), np.zeros(nA)]))
    a = np.clip(z[:len(mus)], A_MIN, 1.0)
    x0 = np.concatenate([a, z[len(mus):]])

    T_out, Qout, Fout, Aout, Uout, Eout = [], [], [], [], [], []
    tt = t0; nwin = int(np.ceil((t1 - t0) / window - 1e-9)); worst = 0.0
    for w in range(nwin):
        T = min(window, t1 - tt)
        if T <= 1e-9:
            break
        tm = tt + 0.5 * T
        qdd_des = spdd(tm)[D] + kv * (spd(tm)[D] - vD) + kp * (sp(tm)[D] - qD)
        M, bvec, Qe = dyn.terms(q, vD, ext_at(tm))
        tau = M @ qdd_des + bvec - Qe
        Rm, Fa, Fp = muscle_terms(q, vD)
        lo = _act_after(a, np.zeros_like(a), T); hi = _act_after(a, np.ones_like(a), T)
        x0[:len(mus)] = np.clip(x0[:len(mus)], lo, hi)
        z, viol = solve(a, lo, hi, Rm, Fa, Fp, tau, x0)
        worst = max(worst, viol)
        aT, uA = z[:len(mus)], z[len(mus):]
        u = _excitation_for(a, aT, T)
        x0 = z
        nsub = max(1, int(round(T / dt))); h = T / nsub
        for s in range(nsub):
            ts_ = tt + s * h
            if s == 0:
                T_out.append(ts_); Qout.append(q.copy()); Aout.append(a.copy()); Uout.append(u.copy())
                Fout.append(np.concatenate([a * Fa + Fp, uA * aopt]))
                Eout.append(sp(ts_)[D] - qD)
            Ms, bs, Qs = (M, bvec, Qe) if s == 0 else dyn.terms(q, vD, ext_at(ts_))
            tau_s = Rm @ (a * Fa + Fp) + Ac @ uA
            qdd = np.linalg.solve(Ms, tau_s + Qs - bs)
            vD = vD + h * qdd; qD = qD + h * vD
            q = dyn.full(qD, q)
            a = np.clip(a + h * _act_rate(u, a), A_MIN, 1.0)
        tt += T
        if w % 10 == 0 or w == nwin - 1:
            err = np.degrees(np.abs(sp(tt)[D] - qD)[[not model.coords[c].translational for c in D_names]])
            log(f"[cmc] t = {tt:.3f} s ({w + 1}/{nwin}); max |q error| {err.max():.2f} deg; "
                f"SO residual {viol:.2g}")
        if not np.all(np.isfinite(qD)):
            raise RuntimeError(f"[cmc] integration diverged at t = {tt:.3f} s")
    # final row
    Rm, Fa, Fp = muscle_terms(q, vD)
    T_out.append(tt); Qout.append(q.copy()); Aout.append(a.copy()); Uout.append(u.copy())
    Fout.append(np.concatenate([a * Fa + Fp, uA * aopt])); Eout.append(sp(tt)[D] - qD)

    os.makedirs(out_dir, exist_ok=True)
    T_out = np.array(T_out); Qout = np.array(Qout)
    qcols = list(model.coord_order)
    Qdeg = Qout.copy()
    for k, n in enumerate(qcols):
        # coupled coordinates stay in rad, as pyosim IK writes them (read_coords
        # converts only independent rotational coordinates)
        if not model.coords[n].translational and model.coords[n].coupled is None:
            Qdeg[:, k] = np.degrees(Qdeg[:, k])
    write_mot(os.path.join(out_dir, "CMC_Kinematics_q.sto"), ["time"] + qcols,
              np.column_stack([T_out, Qdeg]), name="Coordinates", degrees=True)
    mn = [m["name"] for m in mus]
    write_mot(os.path.join(out_dir, "CMC_Actuation_force.sto"), ["time"] + mn + an,
              np.column_stack([T_out, np.array(Fout)]), name="Actuation_force", degrees=False)
    write_mot(os.path.join(out_dir, "CMC_states.sto"), ["time"] + [n + "/activation" for n in mn],
              np.column_stack([T_out, np.array(Aout)]), name="states", degrees=False)
    write_mot(os.path.join(out_dir, "CMC_controls.sto"), ["time"] + mn,
              np.column_stack([T_out, np.array(Uout)]), name="controls", degrees=False)
    E = np.array(Eout)
    for k, n in enumerate(D_names):
        if not model.coords[n].translational:
            E[:, k] = np.degrees(E[:, k])
    write_mot(os.path.join(out_dir, "CMC_pErr.sto"), ["time"] + D_names,
              np.column_stack([T_out, E]), name="position error (deg / m)", degrees=True)
    secs = _time.time() - t_start
    log(f"[cmc] done: {tt:.3f} of {t1:.3f} s in {secs:.0f} s; worst SO constraint residual {worst:.3g}")
    return dict(n_tasks=nD, cmc_reached=float(tt), cmc_seconds=secs, dropped_tasks=[],
                ok_forward=None, actuators=an)
