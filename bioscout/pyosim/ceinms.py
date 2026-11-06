"""A Python version of CEINMS (calibration + execution), set up to run in the
browser. It is NOT CEINMS.exe: it follows the same ideas (Pizzolato et al. 2015,
Sartori et al. 2014) with a simpler muscle model, so its numbers will differ.

  muscle model   rigid tendon Hill-type (the curves of so.py), activation dynamics
                 u -> a (first order, 15 / 50 ms) and the non-linear EMG shape
                 a = (e^(A u) - 1) / (e^A - 1), A in [-3, 0)
  execution      per frame, over activations a in [0, 1]:
                     alpha |R F(a) - M_ID|^2  +  beta |a|^2  +  gamma |S (a - a_emg)|^2
                 F(a) is affine in a, so each frame is one bounded linear least squares
  calibration    alternates an execution (hybrid weights) with a bounded linear
                 fit of a strength factor per muscle group (0.5 - 2.5, pulled to 1),
                 over a grid of the EMG shape A; the best fit wins and is written as
                 a calibrated model (max_isometric_force x strength) + calibration.json
  modes          execution  one solve at the alpha / beta / gamma given
                 loop       one solve per gamma in a list -> each one kept + the median
                 optimise   a log sweep of gamma; the largest gamma whose moment RMSE stays
                            within the tolerance is chosen (the most EMG the moments allow)
"""
import os
import re
import json
import xml.etree.ElementTree as ET
import numpy as np
from scipy.optimize import lsq_linear
from scipy.signal import butter, filtfilt
from .model import Model
from .muscles import Paths
from .io import read_sto, write_mot
from . import id as idtool
from .so import f_active, f_passive, f_velocity

LEG = ("hip_flexion", "hip_adduction", "hip_rotation", "knee_angle", "ankle_angle", "subtalar_angle")
APPROACHES = {          # alpha, beta, gamma
    "static_optimisation": (100.0, 1.0, 0.0),
    "emg_informed": (100.0, 1.0, 30.0),
    "hybrid": (100.0, 0.5, 100.0),
    "emg_driven": (0.0, 0.01, 1000.0),
}
# EMG channel keyword -> model muscle name stems
EMG_MAP = [
    (r"tib.?ant|\bta\b", ["tibant", "tib_ant"]),
    (r"gas\w*.?med|gastro.?med|\bgm\b|med.?gas", ["gasmed", "med_gas"]),
    (r"gas\w*.?lat|gastro.?lat|\bgl\b|lat.?gas", ["gaslat", "lat_gas"]),
    (r"sol", ["soleus", "soleus"]),
    (r"vas\w*.?lat|\bvl\b", ["vaslat", "vasint", "vas_lat", "vas_int"]),
    (r"vas\w*.?med|\bvm\b", ["vasmed", "vas_med"]),
    (r"rec\w*.?fem|\brf\b", ["recfem", "rect_fem"]),
    (r"bic\w*.?fem|biceps|\bbf\b|lat.?ham", ["bflh", "bfsh", "bifemlh", "bifemsh"]),
    (r"semit|semim|\bst\b|med.?ham", ["semiten", "semimem"]),
    (r"glu\w*.?max|glmax", ["glmax", "glut_max"]),
    (r"glu\w*.?med|glmed", ["glmed", "glut_med"]),
    (r"add\w*.?long", ["addlong", "add_long"]),
    (r"tfl|tens", ["tfl"]),
    (r"per\w*.?lon", ["perlong", "per_long"]),
]
GROUPS = [   # strength groups for calibration (stem prefixes)
    ("gluteus maximus", ("glmax", "glut_max")), ("gluteus medius/minimus", ("glmed", "glmin", "glut_med", "glut_min")),
    ("iliopsoas", ("iliacus", "psoas")), ("adductors", ("addbrev", "addlong", "addmagdist", "addmagisch", "addmagmid", "addmagprox", "add", "grac")),
    ("hamstrings", ("bflh", "bfsh", "semimem", "semiten", "bifem")), ("rectus femoris", ("recfem", "rect_fem")),
    ("vasti", ("vas",)), ("gastrocnemius", ("gas", "med_gas", "lat_gas")), ("soleus", ("soleus",)),
    ("tibialis anterior", ("tibant", "tib_ant")), ("other", ("",)),
]


def _side(name):
    m = re.search(r"_([rl])\d*$", name)
    return m.group(1) if m else None


def _group_of(name):
    stem = re.sub(r"_[rl]$", "", name)
    for g, pre in GROUPS:
        if any(stem.startswith(p) for p in pre if p) or pre == ("",):
            return g
    return "other"


# ------------------------------------------------------------------ EMG
def emg_envelopes(emg_path, t_out, muscles, log=print, emg_map=None):
    """-> (excitations (n, M) in [0,1] or NaN for muscles without EMG, {muscle: channel}).
    emg_map: {channel: [muscles]} (bioscout's session.yaml emg_map). With it the channels are
    used exactly as given -- already filtered and normalised, as CEINMS.exe reads them -- and
    mapped to exactly those muscles; without it the channels are recognised by name and
    enveloped / normalised here."""
    cols, data, _ = read_sto(emg_path)
    t = data[:, cols.index("time")]
    if emg_map:
        out = np.full((len(t_out), len(muscles)), np.nan); used = {}
        for ch, mus in emg_map.items():
            if ch not in cols:
                log(f"[ceinms] EMG channel {ch} not in {os.path.basename(emg_path)}")
                continue
            x = np.clip(np.interp(t_out, t, data[:, cols.index(ch)].astype(float)), 0, 1)
            for mu in (mus if isinstance(mus, (list, tuple)) else [mus]):
                if mu in muscles:
                    out[:, muscles.index(mu)] = x; used[mu] = ch
        log(f"[ceinms] EMG (emg_map): {len(set(used.values()))} channel(s) drive {len(used)} muscle(s)")
        return out, used
    fs = 1.0 / np.median(np.diff(t))
    out = np.full((len(t_out), len(muscles)), np.nan); used = {}
    for ci, c in enumerate(cols):
        if c == "time":
            continue
        lab = c.split(".")[-1].lower()
        m = re.search(r"(?:^|[_\s-])([lr])(?:[_\s-]|$)", lab) or re.match(r"([lr])", lab)
        if not m:
            continue
        side = m.group(1)
        stems = next((st for pat, st in EMG_MAP if re.search(pat, lab)), None)
        if not stems:
            continue
        x = data[:, ci].astype(float)
        if np.nanmax(np.abs(x)) > 1.5 or np.nanmin(x) < -0.05:            # raw: band-pass, rectify, low-pass
            x = np.where(np.abs(x) >= 0.98 * np.nanmax(np.abs(x)), 0.0, x)  # saturated samples (unplugged channel)
            if np.allclose(x, 0):
                continue
            if fs > 200:
                b, a = butter(2, [20 / (fs / 2), min(450 / (fs / 2), 0.99)], "band"); x = filtfilt(b, a, x)
            x = np.abs(x - np.mean(x))
            b, a = butter(2, 6 / (fs / 2)); x = filtfilt(b, a, x)
        x = np.interp(t_out, t, x)
        top = np.percentile(x, 99.5)
        if not top > 0:
            continue
        x = np.clip(x / top, 0, 1)
        for k, mu in enumerate(muscles):
            if _side(mu) == side and any(re.sub(r"_[rl]\d*$", "", mu).startswith(s) for s in stems):
                out[:, k] = x; used[mu] = c
    log(f"[ceinms] EMG: {len(set(used.values()))} channel(s) drive {len(used)} muscle(s)")
    return out, used


def activation(u, t, A=-1.0, t_act=0.015, t_deact=0.05):
    a = np.zeros_like(u); a[0] = u[0]
    for i in range(1, len(t)):
        dt = t[i] - t[i - 1]
        tau = np.where(u[i] > a[i - 1], t_act, t_deact)
        a[i] = a[i - 1] + dt * (u[i] - a[i - 1]) / tau
    a = np.clip(a, 0, 1)
    return a if abs(A) < 1e-6 else (np.exp(A * a) - 1) / (np.exp(A) - 1)


# ------------------------------------------------------------------ the shared set-up
class Problem:
    def __init__(self, model_path, coords_mot, id_sto, emg_mot=None, t_range=None, cutoff=6.0, log=print, emg_map=None,
                 weighting="ceinms", passive=False):
        self.weighting = weighting
        model = model_path if isinstance(model_path, Model) else Model(model_path)
        self.model, self.log = model, log
        paths = Paths(model, model.path)
        t, Q = idtool.read_coords(model, coords_mot)
        ic, idd, _ = read_sto(id_sto); tid = idd[:, ic.index("time")]
        lo, hi = max(t[0], tid[0]), min(t[-1], tid[-1])
        if t_range:
            lo, hi = max(lo, t_range[0]), min(hi, t_range[1])
        m = (t >= lo - 1e-9) & (t <= hi + 1e-9); t, Q = t[m], Q[m]
        Q = idtool._lowpass(Q, t, cutoff)
        coords = [c for c in model.coord_order if any(c.startswith(b) for b in LEG) and not model.coords[c].locked
                  and model.coords[c].coupled is None and (c + "_moment") in ic]
        L, R = paths.moment_arms(Q, coords)
        keep = np.abs(R).max(axis=(0, 1)) > 1e-4                    # muscles that cross a tracked coordinate
        self.mus = [mu for k, mu in enumerate(paths.mus) if keep[k]]
        L, R = L[:, keep], R[:, :, keep]
        self.names = [mu["name"] for mu in self.mus]
        self.t, self.coords, self.R = t, coords, R
        self.M = np.stack([np.interp(t, tid, idd[:, ic.index(c + "_moment")]) for c in coords], 1)
        F0 = np.array([mu["F0"] for mu in self.mus]); lopt = np.array([mu["lopt"] for mu in self.mus])
        lts = np.array([mu["lts"] for mu in self.mus]); a0 = np.array([mu["alpha"] for mu in self.mus])
        vmax = np.array([mu["vmax"] for mu in self.mus])
        lm = np.sqrt(np.maximum(L - lts, 1e-4) ** 2 + (lopt * np.sin(a0)) ** 2); cosa = np.maximum(L - lts, 1e-4) / lm
        # fibre velocity from the joint velocities (as so.py): dL/dt = -sum_c R_c qdot_c. A finite
        # difference of the length rings where a wrap object engages and gave single-frame spikes.
        qd = np.gradient(Q[:, [model.coord_order.index(c) for c in coords]], t, axis=0)
        vm = -np.einsum("ncm,nc->nm", R, qd) * cosa
        self.G = F0 * f_active(lm / lopt) * f_velocity(vm / (vmax * lopt)) * cosa      # force per unit activation
        # passive fibre force: off by default. With a rigid tendon the whole musculotendon stretch
        # lands in the fibre, so e.g. soleus sits on its passive curve all trial (~1-1.5 kN each,
        # ~4.5 kN summed over the legs on K2L walking) and the active muscles then fight it --
        # contact forces far above in vivo. CEINMS.exe's elastic tendon takes that stretch (its
        # passive forces stay near zero); OpenSim's static optimisation leaves passive out too.
        self.P = F0 * f_passive(lm / lopt) * cosa if passive else np.zeros_like(self.G)
        self.u_emg = None; self.emg_map = {}
        if emg_mot:
            self.u_emg, self.emg_map = emg_envelopes(emg_mot, t, self.names, log, emg_map=emg_map)
        log(f"[ceinms] {len(t)} frames, {len(self.names)} muscles, {len(coords)} coordinates: {', '.join(coords)}")

    def a_emg(self, A):
        if self.u_emg is None:
            return None
        out = np.full_like(self.u_emg, np.nan)
        for k in range(out.shape[1]):
            if np.isfinite(self.u_emg[0, k]):
                out[:, k] = activation(self.u_emg[:, k], self.t, A)
        return out

    def solve(self, alpha, beta, gamma, strength=None, A=-1.0, frames=None, delta=None, weighting=None):
        """-> activations (n, M), forces (n, M), moments (n, C).

        weighting "ceinms" (default): CEINMS's hybrid objective as CEINMS.exe sums it, per frame
            alpha * sum_dof (M_muscles - M_ID)^2 [N m]  +  beta * sum_m a^2  +  gamma * sum_emg (a - a_emg)^2
          so the moment term (N m^2) outweighs the EMG term (activation^2) unless gamma is large,
          as in CEINMS.exe. No smoothing term (delta 0).
        weighting "normalised" (the earlier browser version): moments in fractions of each
          coordinate's range, beta and gamma per muscle, plus a smoothing term delta (0.5)."""
        weighting = weighting or self.weighting
        if delta is None:
            delta = 0.5 if weighting == "normalised" else 0.0
        s = np.ones(len(self.names)) if strength is None else strength
        G, P = self.G * s, self.P * s
        ae = self.a_emg(A)
        idx = range(len(self.t)) if frames is None else frames
        nM = len(self.names); X = np.zeros((len(self.t), nM)); prev = np.full(nM, 0.05)
        if weighting == "normalised":
            sc = 1.0 / np.maximum(np.ptp(self.M, axis=0), 1.0)          # moments in fractions of each coordinate's range
            nb = np.sqrt(nM)
        else:
            sc = np.ones(len(self.coords)); nb = 1.0
        for i in idx:
            blocks, rhs = [], []
            if alpha > 0:
                blocks.append(np.sqrt(alpha) * sc[:, None] * (self.R[i] * G[i][None])); rhs.append(np.sqrt(alpha) * sc * (self.M[i] - self.R[i] @ P[i]))
            blocks.append(np.sqrt(beta + 1e-6) * np.eye(nM) / nb); rhs.append(np.zeros(nM))
            if gamma > 0 and ae is not None:
                have = np.isfinite(ae[i])
                if have.any():
                    ng = np.sqrt(have.sum()) if weighting == "normalised" else 1.0
                    blocks.append(np.sqrt(gamma) * np.eye(nM)[have] / ng); rhs.append(np.sqrt(gamma) * ae[i][have] / ng)
            if delta > 0 and frames is None:
                blocks.append(np.sqrt(delta) * np.eye(nM) / nb); rhs.append(np.sqrt(delta) * prev / nb)
            r = lsq_linear(np.vstack(blocks), np.concatenate(rhs), bounds=(0.0, 1.0), method="bvls")
            X[i] = prev = r.x
        F = X * G + P
        Mm = np.einsum("ncm,nm->nc", self.R, F)
        return X, F, Mm

    def scores(self, X, Mm, A=-1.0, frames=None):
        M, ae = self.M, self.a_emg(A)
        if frames is not None:
            M = M[frames]; ae = None if ae is None else ae[frames]
        rmse = np.sqrt(np.mean((Mm - M) ** 2, axis=0))
        emg = float(np.sqrt(np.nanmean((X - ae) ** 2))) if ae is not None and np.isfinite(ae).any() else float("nan")
        return rmse, emg


# ------------------------------------------------------------------ calibration
def calibrate(model_path, coords_mot, id_sto, emg_mot, out_dir, approach="hybrid", alpha=None, beta=None, gamma=None,
              shapes=(-3, -2, -1, -0.5, -0.01), t_range=None, log=print, emg_map=None):
    pb = Problem(model_path, coords_mot, id_sto, emg_mot, t_range, log=log, emg_map=emg_map)
    a0, b0, g0 = APPROACHES.get(approach, APPROACHES["hybrid"])
    alpha, beta, gamma = (a0 if alpha is None else alpha), (b0 if beta is None else beta), (g0 if gamma is None else gamma)
    if pb.u_emg is None or not pb.emg_map:
        log("[ceinms] calibration without EMG: strengths only, from the moment tracking")
        shapes = (-1.0,)
    groups = sorted({(_group_of(n), _side(n)) for n in pb.names})
    gi = np.array([groups.index((_group_of(n), _side(n))) for n in pb.names])
    frames = np.unique(np.linspace(0, len(pb.t) - 1, min(len(pb.t), 80)).astype(int))
    sc = 1.0 / np.maximum(np.ptp(pb.M, axis=0), 1.0)
    best = None
    for A in shapes:
        s = np.ones(len(pb.names))
        for it in range(4):
            X, F, Mm = pb.solve(alpha, beta, gamma, s, A, frames)
            # moments linear in the group strengths: M = sum_g s_g R (G a + P)
            Fg = X[frames] * pb.G[frames] + pb.P[frames]
            B = np.zeros((len(frames), len(pb.coords), len(groups)))
            for g in range(len(groups)):
                B[:, :, g] = np.einsum("ncm,nm->nc", pb.R[frames][:, :, gi == g], Fg[:, gi == g])
            Asys = (B * sc[None, :, None]).reshape(-1, len(groups)); y = (pb.M[frames] * sc).ravel()
            lam = 0.05 * np.sqrt(len(frames))
            r = lsq_linear(np.vstack([Asys, lam * np.eye(len(groups))]), np.concatenate([y, lam * np.ones(len(groups))]), bounds=(0.5, 2.5))
            s = r.x[gi]
        X, F, Mm = pb.solve(alpha, beta, gamma, s, A, frames)
        err = float(np.sqrt(np.mean(((Mm[frames] - pb.M[frames]) * sc) ** 2)))
        _, emg = pb.scores(X[frames], Mm[frames], A, frames)
        score = err + (0.5 * emg if np.isfinite(emg) else 0)
        log(f"[ceinms] shape A={A:+.2f}: moment error {100 * err:.1f} % of range, EMG error {emg:.3f}")
        if best is None or score < best[0]:
            best = (score, A, s.copy(), err, emg)
    _, A, s, err, emg = best
    os.makedirs(out_dir, exist_ok=True)
    gs = {f"{g} {sd or ''}".strip(): float(s[gi == k][0]) for k, (g, sd) in enumerate(groups)}
    base = os.path.basename(pb.model.path).replace(".osim", "")
    out_model = os.path.join(out_dir, f"{base}_calibrated.osim")
    _write_calibrated(pb.model.path, out_model, dict(zip(pb.names, s)))
    cal = dict(note="Python version of CEINMS calibration (bioscout web), not CEINMS.exe", approach=approach,
               alpha=alpha, beta=beta, gamma=gamma, shape_A=A, moment_error_pct_range=round(100 * err, 2),
               emg_error=None if not np.isfinite(emg) else round(emg, 4), strength_by_group=gs,
               emg_channels=pb.emg_map, model=os.path.basename(out_model))
    with open(os.path.join(out_dir, "calibration.json"), "w") as f:
        json.dump(cal, f, indent=1)
    with open(os.path.join(out_dir, "calibration.csv"), "w") as f:
        f.write("muscle,group,strength,emg_channel\n")
        for n, v in zip(pb.names, s):
            f.write(f"{n},{_group_of(n)},{v:.3f},{pb.emg_map.get(n, '')}\n")
    log(f"[ceinms] calibrated: A={A:+.2f}, strengths " + ", ".join(f"{k} {v:.2f}" for k, v in gs.items()))
    return cal


def _write_calibrated(src, dst, strength):
    tree = ET.parse(src)
    for el in tree.getroot().iter():
        n = el.get("name")
        if n in strength:
            f = el.find("max_isometric_force")
            if f is not None and f.text:
                f.text = f"{float(f.text) * strength[n]:.4f}"
    tree.write(dst, xml_declaration=True, encoding="UTF-8")


# ------------------------------------------------------------------ execution
def _write(pb, out_dir, tag, X, F, Mm, A):
    cols = ["time"] + pb.names
    write_mot(os.path.join(out_dir, f"CEINMS{tag}_forces.sto"), cols, np.column_stack([pb.t, F]), name="CEINMS muscle forces", degrees=False)
    write_mot(os.path.join(out_dir, f"CEINMS{tag}_activations.sto"), cols, np.column_stack([pb.t, X]), name="CEINMS activations", degrees=False)
    mc = ["time"] + [c + "_moment" for c in pb.coords]
    write_mot(os.path.join(out_dir, f"CEINMS{tag}_moments.sto"), mc, np.column_stack([pb.t, Mm]), name="CEINMS joint moments (muscles)", degrees=False)
    ae = pb.a_emg(A)
    if ae is not None and not tag:
        keep = [k for k in range(len(pb.names)) if np.isfinite(ae[0, k])]
        write_mot(os.path.join(out_dir, "CEINMS_emg_activations.sto"), ["time"] + [pb.names[k] for k in keep],
                  np.column_stack([pb.t, ae[:, keep]]), name="EMG-driven activations (measured)", degrees=False)


def execute(model_path, coords_mot, id_sto, out_dir, emg_mot=None, approach="hybrid", mode="execution",
            alpha=None, beta=None, gamma=None, gammas=(1, 10, 30, 100, 300), tol=None, calibration=None,
            t_range=None, log=print, emg_map=None):
    pb = Problem(model_path, coords_mot, id_sto, emg_mot, t_range, log=log, emg_map=emg_map)
    a0, b0, g0 = APPROACHES.get(approach, APPROACHES["hybrid"])
    alpha, beta, gamma = (a0 if alpha is None else alpha), (b0 if beta is None else beta), (g0 if gamma is None else gamma)
    A = -1.0
    if calibration and os.path.isfile(calibration):
        A = json.load(open(calibration)).get("shape_A", A); log(f"[ceinms] calibration: EMG shape A={A:+.2f}")
    if pb.u_emg is None and gamma > 0:
        log("[ceinms] no EMG: gamma has nothing to track (runs as static optimisation)")
    os.makedirs(out_dir, exist_ok=True)
    rng = np.maximum(np.ptp(pb.M, axis=0), 1.0)
    summary = []

    def one(a, b, g, tag):
        X, F, Mm = pb.solve(a, b, g, None, A)
        rmse, emg = pb.scores(X, Mm, A)
        pct = float(np.mean(rmse / rng) * 100)
        summary.append((a, b, g, pct, emg))
        log(f"[ceinms] alpha {a:g} beta {b:g} gamma {g:g}: moment RMSE {pct:.1f} % of range, EMG RMSE {emg:.3f}")
        if tag is not None:
            _write(pb, out_dir, tag, X, F, Mm, A)
        return X, F, Mm

    if mode == "loop":
        runs = [one(alpha, beta, g, f"_a{alpha:g}_b{beta:g}_g{g:g}") for g in gammas]
        X, F, Mm = (np.median(np.stack([r[k] for r in runs]), 0) for k in range(3))
        log(f"[ceinms] loop: {len(runs)} runs; CEINMS_forces.sto is their median")
    elif mode == "optimise":
        tol = tol if tol else 5.0
        grid = [1, 3, 10, 30, 100, 300, 1000]
        res = [one(alpha, beta, g, None) for g in grid]
        ok = [k for k, r in enumerate(summary) if r[3] <= tol] or [int(np.argmin([r[3] for r in summary]))]
        k = max(ok); gamma = grid[k]; X, F, Mm = res[k]
        log(f"[ceinms] optimise: gamma {gamma:g} (largest with moment RMSE <= {tol:g} % of range)")
    else:
        X, F, Mm = one(alpha, beta, gamma, None)
    _write(pb, out_dir, "", X, F, Mm, A)
    with open(os.path.join(out_dir, "CEINMS_summary.csv"), "w") as f:
        f.write("alpha,beta,gamma,moment_rmse_pct_range,emg_rmse\n")
        for r in summary:
            f.write(",".join(f"{v:g}" if isinstance(v, float) or isinstance(v, int) else str(v) for v in r) + "\n")
    with open(os.path.join(out_dir, "CEINMS_run.json"), "w") as f:
        json.dump(dict(note="Python version of CEINMS execution (bioscout web), not CEINMS.exe", approach=approach, mode=mode,
                       alpha=alpha, beta=beta, gamma=gamma, shape_A=A, emg_channels=pb.emg_map), f, indent=1)
    return pb.names, F
