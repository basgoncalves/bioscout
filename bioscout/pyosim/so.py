"""Static optimisation in pure Python, as OpenSim's StaticOptimization with
use_muscle_physiology: per frame, the muscle activations a (0..1) and actuator
controls u that minimise sum(a^2) + sum(u^2) while the muscles and actuators
reproduce the inverse-dynamics generalised forces.

    muscle force = F0 * (a * fl(lm) * fv(vm) + fp(lm)) * cos(pennation)
    rigid tendon: fibre length from the musculotendon length, pennation at constant thickness

Moment arms come from muscles.Paths (via points + cylinder/sphere wrapping);
the inverse dynamics from id.py; actuators (reserves, lumbar, residuals) from
the model's CoordinateActuators and/or an actuators .xml."""
import os
import xml.etree.ElementTree as ET
import numpy as np
from scipy.optimize import minimize
from .model import Model
from .muscles import Paths
from .io import read_sto, write_mot
from . import id as idtool
from . import millard


def read_actuators(*paths):
    out = {}
    for p in paths:
        if not p or not os.path.isfile(p):
            continue
        for a in ET.parse(p).getroot().iter("CoordinateActuator"):
            c = (a.findtext("coordinate") or "").strip()
            if not c or c == "Unassigned" or (a.findtext("appliesForce") or "true").strip() == "false":
                continue
            out[a.get("name")] = (c, float(a.findtext("optimal_force") or 1),
                                  float(a.findtext("min_control") or -np.inf), float(a.findtext("max_control") or np.inf))
    return out


# curves (Thelen 2003 shapes; close to Millard's defaults over the physiological range)
def f_active(l):  return np.exp(-((l - 1.0) ** 2) / 0.45)
def f_passive(l):
    # capped at 1.4 x optimal length: with a rigid tendon the fibre stretch is overestimated in deep flexion
    # (deep squats), and the exponential would otherwise give kN of passive force from a silent muscle
    l = np.minimum(l, 1.4)
    return np.where(l > 1, (np.exp(4 * (l - 1) / 0.6) - 1) / (np.exp(4) - 1), 0.0)
def f_velocity(v):                     # v: fibre velocity / (vmax * lopt), shortening < 0
    v = np.clip(v, -0.999, 1.0)
    return np.where(v <= 0, (1 + v) / (1 - v / 0.25), 1.8 - 0.8 * (1 + 0.0) / (1 + v * 7.56))


def run(model_path, coords_mot, id_sto, out_dir, actuators=None, t_range=None, cutoff=6.0, log=print, prefix="SO",
        passive=False):
    """passive=False (default) matches OpenSim's StaticOptimization, which applies only the active
    fibre force a * F0 * fl * fv * cos(pennation); True adds the passive fibre force on top."""
    model = model_path if isinstance(model_path, Model) else Model(model_path)
    osim = model_path if isinstance(model_path, str) else getattr(model, "path", None)
    paths = Paths(model, osim)
    t, Q = idtool.read_coords(model, coords_mot)
    if t_range:
        m = (t >= t_range[0] - 1e-9) & (t <= t_range[1] + 1e-9); t, Q = t[m], Q[m]
    Q = idtool._lowpass(Q, t, cutoff)
    ic, idd, _ = read_sto(id_sto)
    tid = idd[:, ic.index("time")]
    act = read_actuators(osim, actuators)
    # coordinates to satisfy: every non-locked coordinate a muscle or an actuator can move
    acts_on = {c for c, *_ in act.values()}
    names_c = [c for c in model.free if not model.coords[c].locked]
    L, R = paths.moment_arms(Q, names_c)                         # (n, M), (n, C, M)
    R_all = R
    moves = (np.abs(R).max(axis=(0, 2)) > 1e-4) | np.array([c in acts_on for c in names_c])
    cidx = [k for k, c in enumerate(names_c) if moves[k]]
    coords = [names_c[k] for k in cidx]; R = R[:, cidx]
    tau = np.stack([np.interp(t, tid, idd[:, ic.index(c + ("_force" if model.coords[c].translational else "_moment"))])
                    if (c + "_moment") in ic or (c + "_force") in ic else np.zeros(len(t)) for c in coords], 1)
    mus = paths.mus
    F0 = np.array([m["F0"] for m in mus]); lopt = np.array([m["lopt"] for m in mus]); lts = np.array([m["lts"] for m in mus])
    a0 = np.array([m["alpha"] for m in mus]); vmax = np.array([m["vmax"] for m in mus])
    h = lopt * np.sin(a0)
    lm = np.sqrt(np.maximum(L - lts, 1e-4) ** 2 + h ** 2); cosa = np.maximum(L - lts, 1e-4) / lm
    # fibre velocity as OpenSim: musculotendon speed = -sum(moment arm x coordinate speed), coordinate
    # speeds from a quintic spline of the filtered coordinates; with a rigid tendon the fibre moves
    # at that speed x cos(pennation). Differentiating the length itself rings wherever a path
    # jumps onto or off a wrap surface (a kink in the length), e.g. -9 l0/s for one frame of glmax1.
    from scipy.interpolate import make_interp_spline
    Qd = make_interp_spline(t, Q, k=5, axis=0).derivative()(t) if len(t) > 6 else np.gradient(Q, t, axis=0)
    ci_all = [model.coord_order.index(c) for c in names_c]
    vm = -np.einsum("ncm,nc->nm", R_all, Qd[:, ci_all]) * cosa
    nl, nv = lm / lopt, vm / (vmax * lopt)
    fl, fv = f_active(nl), f_velocity(nv)                                     # Thelen-type, for non-Millard muscles
    curves = millard.curves_from_osim(osim) if osim else {}
    for k, m in enumerate(mus):
        if m["name"] in curves:                                               # the model's own Millard curves
            cfl, cfv = curves[m["name"]]
            fl[:, k] = cfl(nl[:, k]); fv[:, k] = cfv(nv[:, k])
    Fa = F0 * fl * fv * cosa                                                  # per unit activation
    Fp = F0 * f_passive(nl) * cosa if passive else np.zeros_like(Fa)
    log(f"[so] {sum(m['name'] in curves for m in mus)}/{len(mus)} muscles on Millard curves; passive fibre force "
        + ("included" if passive else "left out (as OpenSim)"))
    an = list(act); A_c = np.zeros((len(coords), len(an))); opt = np.array([act[a][1] for a in an])
    for j, a in enumerate(an):
        if act[a][0] in coords: A_c[coords.index(act[a][0]), j] = opt[j]
    lb = np.concatenate([np.full(len(mus), 0.01), [max(act[a][2], -1e3) for a in an]])
    ub = np.concatenate([np.ones(len(mus)), [min(act[a][3], 1e3) for a in an]])
    log(f"[so] {len(t)} frames, {len(mus)} muscles, {len(an)} actuators, {len(coords)} coordinates")
    n = len(t); X = np.zeros((n, len(mus) + len(an))); x = np.full(len(mus) + len(an), 0.05); x[len(mus):] = 0
    viol = np.zeros(n)
    for i in range(n):
        A = np.hstack([R[i] * Fa[i][None], A_c]); b = tau[i] - R[i] @ Fp[i]
        res = minimize(lambda z: z @ z, x, jac=lambda z: 2 * z, method="SLSQP", bounds=list(zip(lb, ub)),
                       constraints=[{"type": "eq", "fun": lambda z: A @ z - b, "jac": lambda z: A}],
                       options={"maxiter": 200, "ftol": 1e-8})
        x = np.clip(res.x, lb, ub); X[i] = x; viol[i] = np.abs(A @ x - b).max()
        if i % 50 == 0:
            log(f"[so] frame {i + 1}/{n}")
    forces = X[:, :len(mus)] * Fa + Fp
    acts = X[:, :len(mus)]
    os.makedirs(out_dir, exist_ok=True)
    cols = ["time"] + [m["name"] for m in mus] + an
    write_mot(os.path.join(out_dir, f"{prefix}_StaticOptimization_force.sto"), cols,
              np.column_stack([t, forces, X[:, len(mus):] * opt]), name="Static Optimization", degrees=False)
    write_mot(os.path.join(out_dir, f"{prefix}_StaticOptimization_activation.sto"), cols,
              np.column_stack([t, acts, X[:, len(mus):]]), name="Static Optimization", degrees=False)
    bad = int((viol > 1.0).sum())
    log(f"[so] done; moments matched to {np.median(viol):.3f} N·m median" + (f", {bad} frames off by > 1 N·m (raise the reserves)" if bad else ""))
    return t, [m["name"] for m in mus], forces, acts
