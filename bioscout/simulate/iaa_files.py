"""Induced acceleration analysis (IAA) files -- one layout for both engines.

<trial>/induced_accelerations/<engine>/      (engine = opensim | pyosim)
    IAA_<coordinate>.sto              rad/s^2 (m/s^2 for translations)
    IAA_center_of_mass_{X,Y,Z}.sto    m/s^2
    IAA_grf_<foot body>_{X,Y,Z}.sto   N, the force the ground puts on the foot
    iaa_info.json                     engine, contact model, muscle / actuator names
    iaa_summary.png                   muscle groups vs total vs measured
    raw/                              (opensim) OpenSim's own InducedAccelerations output

Every .sto has one column per contributor -- each muscle, each SO actuator
(reserves / residuals), ``gravity``, ``velocity`` -- plus ``total`` (their
sum) and ``measured`` (from the IK / GRF: the check that the decomposition
adds up). No OpenSim import here.
"""
import os
import re
import json
import numpy as np

AXES = "XYZ"


def _write(path, cols, data, name):
    from bioscout.pyosim.io import write_mot
    write_mot(path, cols, data, name=name, degrees=False)


def _read(path):
    from bioscout.pyosim.io import read_sto
    c, d, _ = read_sto(path)
    return c, d


def write(out_dir, res, log=print):
    """res: dict(t, labels, coords, qdd (n,nq,nc), com (n,3,nc), reactions {body: (n,3,nc)},
    measured {qdd (n,nq), com (n,3), grf {body: (n,3)}}, muscles, engine, constraint)."""
    os.makedirs(out_dir, exist_ok=True)
    for f in os.listdir(out_dir):                                   # no stale targets from an older run
        if f.startswith("IAA_") and f.endswith(".sto"):
            os.remove(os.path.join(out_dir, f))
    t, labels = np.asarray(res["t"]), list(res["labels"])
    meas = res.get("measured") or {}
    cols = ["time"] + labels + ["total", "measured"]
    nan = np.full(len(t), np.nan)

    def one(fname, X, m):
        _write(os.path.join(out_dir, fname), cols, np.column_stack([t, X, X.sum(1), nan if m is None else m]),
               name=f"Induced accelerations ({res.get('engine', '?')})")

    mc = list(meas.get("coords") or [])
    for j, c in enumerate(res["coords"]):
        one(f"IAA_{c}.sto", res["qdd"][:, j], meas["qdd"][:, mc.index(c)] if c in mc else None)
    for a in range(3):
        one(f"IAA_center_of_mass_{AXES[a]}.sto", res["com"][:, a], meas["com"][:, a] if "com" in meas else None)
    for b, R in (res.get("reactions") or {}).items():
        g = (meas.get("grf") or {}).get(b)
        for a in range(3):
            one(f"IAA_grf_{b}_{AXES[a]}.sto", R[:, a], None if g is None else g[:, a])
    info = dict(engine=res.get("engine"), constraint=res.get("constraint"),
                force_threshold=res.get("force_threshold"), muscles=list(res.get("muscles") or []),
                actuators=[l for l in labels if l not in (res.get("muscles") or []) and l not in ("gravity", "velocity")],
                coordinates=list(res["coords"]), feet=list((res.get("reactions") or {}).keys()),
                actuators_from_pyosim=list(res.get("actuators_from_pyosim") or []))
    with open(os.path.join(out_dir, "iaa_info.json"), "w") as f:
        json.dump(info, f, indent=1)
    log(f"[iaa] wrote {len(res['coords'])} coordinates + COM + {len(info['feet'])} foot reaction(s) -> {out_dir}")
    try:
        log(check_line(out_dir))
    except Exception as e:                                           # noqa: BLE001
        log(f"[iaa] check not computed: {e}")


# ------------------------------------------------------------------ OpenSim -> common layout
def from_opensim(raw_dir, prefix, forces_sto, out_dir, measured=None, muscles=(), constraints=None,
                 constraint="rolling", force_threshold=None, actuator_fill=None, log=print):
    """OpenSim's InducedAccelerations output in POTENTIALS mode (acceleration per 1 N / 1 N*m)
    x the SO force of each actuator -> the common layout. gravity / velocity are kept as they are.
    constraints: {constraint name: foot body}. The reactions OpenSim reports on the foot body are
    the foot's pull on the constraint; they are negated here to the force the ground puts on the foot.

    actuator_fill: a pyosim IAA result (bioscout.pyosim.iaa.run(write=False)). OpenSim 4.5's
    InducedAccelerations reports ZERO for every non-muscle actuator (CoordinateActuator reserves,
    Point/Torque residuals) in either mode -- tested on 4.5.2 -- so those columns are taken from
    the pyosim solve of the same constrained equations, and iaa_info.json says so."""
    fc, fd = _read(forces_sto)
    tf = fd[:, fc.index("time")]
    files = sorted(f for f in os.listdir(raw_dir) if f.startswith(prefix + "_") and f.endswith(".sto"))
    if not files:
        raise FileNotFoundError(f"no OpenSim IAA output '{prefix}_*.sto' in {raw_dir}")

    def scale(cols, data, strip=None):
        """-> labels, (n, nc) for the columns sharing one target (strip removes the suffix)."""
        t = data[:, cols.index("time")]
        labs, X = [], []
        for k, c in enumerate(cols):
            if c == "time":
                continue
            lab = strip(c) if strip else c
            if lab is None:
                continue
            if lab in ("gravity", "velocity"):
                v = data[:, k]
            elif lab in fc:
                v = data[:, k] * np.interp(t, tf, fd[:, fc.index(lab)])
            else:
                continue                                              # an actuator SO did not solve for
            labs.append(lab); X.append(v)
        return t, labs, np.column_stack(X)

    coords, qdd, labels, t = [], [], None, None
    com_f = f"{prefix}_center_of_mass.sto"
    reac_f = f"{prefix}_induced_constraint_reactions.sto"
    for f in files:
        if f in (com_f, reac_f):
            continue
        c = f[len(prefix) + 1:-4]
        cols, data = _read(os.path.join(raw_dir, f))
        t, labs, X = scale(cols, data)
        if labels is None:
            labels = labs
        coords.append(c); qdd.append(X[:, [labs.index(l) for l in labels]])
    com = None
    if os.path.isfile(os.path.join(raw_dir, com_f)):
        cols, data = _read(os.path.join(raw_dir, com_f))
        per = []
        for a in AXES:
            _, labs, X = scale(cols, data, lambda c, a=a: c[:-2] if c.endswith("_" + a) else None)
            per.append(X[:, [labs.index(l) for l in labels]])
        com = np.stack(per, 1)
    reactions = {}
    if constraints and os.path.isfile(os.path.join(raw_dir, reac_f)):
        cols, data = _read(os.path.join(raw_dir, reac_f))
        for cn, body in constraints.items():
            per = []
            for a in "xyz":
                suf = f"_{cn}_{body}_F{a}"
                _, labs, X = scale(cols, data, lambda c, s=suf: c[:-len(s)] if c.endswith(s) else None)
                per.append(X[:, [labs.index(l) for l in labels]])
            R = -np.stack(per, 1)
            reactions[body] = reactions.get(body, 0) + R              # two plates on one foot -> one foot
    QDD = np.stack(qdd, 1)
    COM = com if com is not None else np.zeros((len(t), 3, len(labels)))
    filled = []
    if actuator_fill is not None:
        P = actuator_fill; pl = list(P["labels"]); pc = list(P["coords"])
        it = lambda y: np.interp(t, P["t"], y)
        for j, lab in enumerate(labels):
            if lab in muscles or lab in ("gravity", "velocity") or lab not in pl:
                continue
            if np.nanmax(np.abs(QDD[..., j])) > 1e-9:
                continue                                              # OpenSim did give it
            k = pl.index(lab); filled.append(lab)
            for q, c in enumerate(coords):
                if c in pc:
                    QDD[:, q, j] = it(P["qdd"][:, pc.index(c), k])
            for a in range(3):
                COM[:, a, j] = it(P["com"][:, a, k])
            for b, R in reactions.items():
                if b in P["reactions"]:
                    for a in range(3):
                        R[:, a, j] = it(P["reactions"][b][:, a, k])
        if filled:
            log(f"[iaa] OpenSim gave zero for {len(filled)} non-muscle actuators ({', '.join(filled[:6])}"
                + (" ..." if len(filled) > 6 else "") + "): taken from the pyosim solve")
    res = dict(t=t, labels=labels, coords=coords, qdd=QDD,
               com=COM, reactions=reactions, actuators_from_pyosim=filled, measured=measured or {}, muscles=[m for m in muscles if m in labels],
               engine="opensim", constraint=constraint, force_threshold=force_threshold)
    write(out_dir, res, log=log)
    return res


# ------------------------------------------------------------------ reading / grouping
GROUPS = [("Gluteus maximus", ("glmax", "glut_max")), ("Gluteus med+min", ("glmed", "glmin", "glut_med", "glut_min")),
          ("Adductors", ("add", "grac")), ("Hamstrings", ("bf", "semimem", "semiten", "bifem")),
          ("Iliopsoas", ("iliacus", "psoas")), ("Rectus femoris", ("recfem", "rect_fem")),
          ("Vasti", ("vas",)), ("Triceps surae", ("gas", "soleus", "med_gas", "lat_gas")),
          ("Dorsiflexors", ("tibant", "tib_ant", "edl", "ehl", "ext_dig", "ext_hal")),
          ("Tibialis post + plantar", ("tibpost", "tib_post", "fdl", "fhl", "flex_dig", "flex_hal", "per"))]


def group_of(label, muscles):
    """'Vasti R', 'gravity', 'velocity', 'Reserves/residuals', 'Other muscles L' ..."""
    if label in ("gravity", "velocity", "total", "measured"):
        return label
    if label not in muscles:
        return "Reserves/residuals"
    m = re.match(r"(.*)_([rl])$", label)
    stem, sd = (m.group(1), " " + m.group(2).upper()) if m else (label, "")
    for g, pre in GROUPS:
        if any(stem.startswith(p) for p in pre):
            return g + sd
    return "Other muscles" + sd


def read(out_dir, target, grouped=True):
    """One IAA target ('knee_angle_r', 'center_of_mass_Y', 'grf_calcn_r_Y') -> pandas DataFrame;
    grouped=True sums the muscles into groups (time, groups..., total, measured)."""
    import pandas as pd
    cols, data = _read(os.path.join(out_dir, f"IAA_{target}.sto"))
    df = pd.DataFrame(data, columns=cols)
    if not grouped:
        return df
    info = json.load(open(os.path.join(out_dir, "iaa_info.json")))
    mus = set(info.get("muscles") or [])
    out = {"time": df["time"]}
    for c in cols[1:]:
        g = group_of(c, mus)
        out[g] = out.get(g, 0) + df[c]
    return pd.DataFrame(out)


def check_line(out_dir):
    """How well total matches measured: RMS error / RMS measured, for COM Y and the feet's Y."""
    parts = []
    for tg in ["center_of_mass_Y"] + sorted(f[4:-4] for f in os.listdir(out_dir)
                                             if f.startswith("IAA_grf_") and f.endswith("_Y.sto")):
        df = read(out_dir, tg, grouped=False)
        tot, mea = df["total"].to_numpy(), df["measured"].to_numpy()
        ok = np.isfinite(mea)
        if ok.sum() < 3:
            continue
        e = np.sqrt(np.mean((tot[ok] - mea[ok]) ** 2)); r = np.sqrt(np.mean(mea[ok] ** 2)) or 1.0
        parts.append(f"{tg} {100 * e / r:.0f}%")
    return "[iaa] sum of contributions vs measured (RMS error / RMS): " + (", ".join(parts) or "n/a")


# ------------------------------------------------------------------ figures
def _panels(out_dir):
    have = {f[4:-4] for f in os.listdir(out_dir) if f.startswith("IAA_") and f.endswith(".sto")}
    want = ["center_of_mass_Y", "center_of_mass_X", "grf_calcn_r_Y", "grf_calcn_l_Y",
            "hip_flexion_r", "knee_angle_r", "ankle_angle_r", "hip_flexion_l", "knee_angle_l", "ankle_angle_l"]
    return [w for w in want if w in have]


def _unit(target):
    if target.startswith("center_of_mass"):
        return 1.0, "m/s²"
    if target.startswith("grf_"):
        return 1.0, "N"
    return 180 / np.pi, "deg/s²"


def plot(out_dir, save=None, top=8):
    """iaa_summary.png: the stacked contributions (see stack())."""
    import matplotlib.pyplot as plt
    save = save or os.path.join(out_dir, "iaa_summary.png")
    fig = stack(out_dir, top=top, save=save)
    plt.close(fig)
    return save


def plot_lines(out_dir, save=None, top=8):
    import matplotlib.pyplot as plt
    panels = _panels(out_dir)
    if not panels:
        return None
    nc = 3 if len(panels) > 4 else 2
    nr = int(np.ceil(len(panels) / nc))
    fig, axs = plt.subplots(nr, nc, figsize=(5 * nc, 3.2 * nr), squeeze=False)
    eng = json.load(open(os.path.join(out_dir, "iaa_info.json"))).get("engine", "?")
    for ax, tg in zip(axs.flat, panels):
        df = read(out_dir, tg); k, u = _unit(tg)
        gs = [c for c in df.columns if c not in ("time", "total", "measured")]
        gs = sorted(gs, key=lambda c: -np.nanmax(np.abs(df[c].to_numpy())))[:top]
        for c in gs:
            ax.plot(df["time"], k * df[c], lw=1.2, label=c)
        ax.plot(df["time"], k * df["total"], "k", lw=2, label="total")
        if np.isfinite(df["measured"]).any():
            ax.plot(df["time"], k * df["measured"], "k--", lw=1.2, label="measured")
        ax.set_title(tg); ax.set_ylabel(u); ax.axhline(0, color="0.8", lw=0.6)
    for ax in axs.flat[len(panels):]:
        ax.axis("off")
    axs.flat[0].legend(fontsize=6, ncol=2)
    fig.suptitle(f"Induced accelerations ({eng}) — {len(panels)} targets, largest {top} contributors each")
    fig.tight_layout()
    save = save or os.path.join(out_dir, "iaa_summary.png")
    fig.savefig(save, dpi=130); plt.close(fig)
    return save


def compare(dir_a, dir_b, save, targets=("center_of_mass_Y", "grf_calcn_r_Y", "knee_angle_r", "hip_flexion_r"), top=6):
    """Two engines side by side: same groups, solid = a, dashed = b."""
    import matplotlib.pyplot as plt
    ea = json.load(open(os.path.join(dir_a, "iaa_info.json"))).get("engine", "a")
    eb = json.load(open(os.path.join(dir_b, "iaa_info.json"))).get("engine", "b")
    targets = [t for t in targets if os.path.isfile(os.path.join(dir_a, f"IAA_{t}.sto"))
               and os.path.isfile(os.path.join(dir_b, f"IAA_{t}.sto"))]
    fig, axs = plt.subplots(1, len(targets), figsize=(5 * len(targets), 3.6), squeeze=False)
    for ax, tg in zip(axs[0], targets):
        A, B = read(dir_a, tg), read(dir_b, tg); k, u = _unit(tg)
        gs = [c for c in A.columns if c not in ("time", "measured") and c in B.columns]
        gs = sorted(gs, key=lambda c: -np.nanmax(np.abs(A[c].to_numpy())))[:top]
        for i, c in enumerate(gs):
            col = "k" if c == "total" else f"C{i}"
            ax.plot(A["time"], k * A[c], color=col, lw=1.4, label=c)
            ax.plot(B["time"], k * B[c], color=col, lw=1.2, ls="--")
        ax.set_title(tg); ax.set_ylabel(u); ax.axhline(0, color="0.8", lw=0.6)
    axs[0][0].legend(fontsize=6)
    fig.suptitle(f"IAA: {ea} (solid) vs {eb} (dashed)")
    fig.tight_layout(); fig.savefig(save, dpi=130); plt.close(fig)
    return save


# ------------------------------------------------------------------ stacked contributions
DEFAULT_STACK = ("center_of_mass_Y", "center_of_mass_X", "grf_calcn_r_Y", "grf_calcn_l_Y",
                 "hip_flexion_r", "knee_angle_r", "ankle_angle_r",
                 "hip_flexion_l", "knee_angle_l", "ankle_angle_l")


def _stack_one(ax, df, k, top, others=True):
    """Stacked areas: positive parts stack up from 0, negative parts down; small
    contributors lumped into 'others'. Returns the plotted names (for one legend)."""
    t = df["time"].to_numpy()
    cs = [c for c in df.columns if c not in ("time", "total", "measured")]
    peak = {c: np.nanmax(np.abs(df[c].to_numpy())) for c in cs}
    keep = sorted(cs, key=lambda c: -peak[c])[:top]
    series = [(c, k * df[c].to_numpy()) for c in keep]
    rest = [c for c in cs if c not in keep]
    if others and rest:
        series.append(("others", k * df[rest].sum(1).to_numpy()))
    up = np.zeros_like(t); dn = np.zeros_like(t)
    for i, (c, y) in enumerate(series):
        y = np.nan_to_num(y)
        col = "0.75" if c == "others" else _COLORS.get(c, f"C{i % 10}")
        p, n = np.clip(y, 0, None), np.clip(y, None, 0)
        ax.fill_between(t, up, up + p, color=col, lw=0, alpha=0.85, label=c)
        ax.fill_between(t, dn, dn + n, color=col, lw=0, alpha=0.85)
        up, dn = up + p, dn + n
    ax.plot(t, k * df["total"], "k", lw=1.6, label="total")
    if np.isfinite(df["measured"]).any():
        ax.plot(t, k * df["measured"], "k--", lw=1.1, label="measured")
    ax.axhline(0, color="0.3", lw=0.5)
    return [c for c, _ in series]


# a fixed colour per contributor group, so a group keeps its colour in every panel
_COLORS = {}


def _colour_groups(names):
    import matplotlib as _mpl
    from matplotlib.colors import to_hex
    pal = [to_hex(c) for m in ("tab20", "tab20b") for c in _mpl.colormaps[m].colors
           if to_hex(c) not in ("#7f7f7f", "#c7c7c7")]           # greys are gravity / velocity / others
    fixed = {"gravity": "#555555", "velocity": "#aaaaaa", "Reserves/residuals": "#f2b134"}
    i = len([n for n in _COLORS if n not in fixed])
    for n in names:
        if n in _COLORS:
            continue
        _COLORS[n] = fixed.get(n) or pal[i % len(pal)]
        if n not in fixed:
            i += 1


def stack(out_dir, targets=DEFAULT_STACK, grouped=True, top=8, ncols=3, save=None, title=None, bw=None):
    """Stacked contributions of each muscle group (grouped=True) or muscle (False), plus
    gravity, velocity and reserves/residuals, to each target: the COM acceleration, the
    foot GRF and the joint accelerations. Positive contributions stack above zero,
    negative below; the black line is their sum, the dashed one the measured value.
    bw: body weight in N -> GRF panels in BW."""
    import matplotlib.pyplot as plt
    have = {f[4:-4] for f in os.listdir(out_dir) if f.startswith("IAA_") and f.endswith(".sto")}
    targets = [t for t in targets if t in have]
    if not targets:
        raise FileNotFoundError(f"none of the targets in {out_dir}")
    dfs = {t: read(out_dir, t, grouped=grouped) for t in targets}
    allc = []
    for d in dfs.values():
        allc += [c for c in d.columns if c not in allc and c not in ("time", "total", "measured")]
    _colour_groups(allc)
    nr = int(np.ceil(len(targets) / ncols))
    fig, axs = plt.subplots(nr, ncols, figsize=(5.2 * ncols, 3.3 * nr), squeeze=False, sharex=True)
    shown = []
    for ax, tg in zip(axs.flat, targets):
        k, u = _unit(tg)
        if bw and tg.startswith("grf_"):
            k, u = 1.0 / bw, "BW"
        for c in _stack_one(ax, dfs[tg], k, top):
            if c not in shown:
                shown.append(c)
        ax.set_title(tg, fontsize=10); ax.set_ylabel(u)
    for ax in axs.flat[len(targets):]:
        ax.axis("off")
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    h = [Patch(color="0.75" if c == "others" else _COLORS.get(c, "C0"), label=c) for c in shown]
    h += [Line2D([], [], color="k", lw=1.6, label="total"), Line2D([], [], color="k", ls="--", label="measured")]
    fig.legend(handles=h, loc="lower center", ncol=min(6, len(h)), fontsize=8, frameon=False)
    eng = json.load(open(os.path.join(out_dir, "iaa_info.json"))).get("engine", "?")
    fig.suptitle(title or f"Induced accelerations ({eng}): contributions, stacked", fontsize=12)
    fig.tight_layout(rect=(0, 0.04 + 0.025 * np.ceil(len(h) / 6), 1, 0.97))
    if save:
        fig.savefig(save, dpi=130)
    return fig
