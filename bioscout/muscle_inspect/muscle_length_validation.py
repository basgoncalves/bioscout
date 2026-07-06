"""Literature moment-arm AND muscle-architecture validation (reusable).

This is the muscle-length / fibre-architecture side of ``muscle_inspect`` (ported
from the standalone MuscleLengthsChecker). It:

  * loads digitized literature bands (validation/literature_moment_arms.csv or the
    consolidated literature_curves.csv), for moment arms, fascicle length and
    pennation angle,
  * computes the model's moment arms and produces a comparison figure (one ROW per
    moment DOF) + RMSE csv  -> ``run_validation``,
  * sweeps each joint coordinate and overlays the model's FASCICLE LENGTH and
    PENNATION vs literature (quantity=fascicle_length|pennation) -> ``run_fibre_validation``.

Distinct from ``literature_jcf`` (joint contact forces) and from bioscout's own
``validation`` module (moment-arm only, wired into run_moment_arm_inspection).
Requires ``import opensim`` at run time.
"""
from __future__ import annotations

import csv
import math
import os
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .core import LOG

MUSCLE_MAP = {
    "psoas": ["psoas"], "iliacus": ["iliacus"],
    "semitendinosus": ["semiten"], "semimembranosus": ["semimem"],
    "adductor_magnus": ["addmagProx", "addmagMid", "addmagDist", "addmagIsch"],
    "gluteus_maximus": ["glmax1", "glmax2", "glmax3"],
    "gluteus_medius": ["glmed1", "glmed2", "glmed3"],
    "soleus": ["soleus"],
    "gastrocnemius_lateralis": ["gaslat"],
    "gastrocnemius_medialis": ["gasmed"],
    "tibialis_anterior": ["tibant"], "tibialis_posterior": ["tibpost"],
    "peroneus_longus": ["perlong"], "peroneus_brevis": ["perbrev"],
    "edl": ["edl"], "ehl": ["ehl"], "fdl": ["fdl"], "fhl": ["fhl"],
    "biceps_femoris_lh": ["bflh"], "biceps_femoris_sh": ["bfsh"],
    "sartorius": ["sart"], "gracilis": ["grac"], "rectus_femoris": ["recfem"],
    "vastus_medialis": ["vasmed"], "vastus_lateralis": ["vaslat"], "vastus_intermedius": ["vasint"],
    "tfl": ["tfl"], "piriformis": ["piri"], "quadratus_femoris": ["quadfem"],
}
SIGN = {"hip_flexion": 1.0, "hip_adduction": 1.0, "hip_rotation": 1.0,
        "knee_angle": -1.0, "ankle_angle": -1.0}  # OpenSim: flexor/plantarflexor MA is negative
STUDY_COLORS = {
    "Arnold_James_2000": "#d62728", "Blemker_Delp_2005": "#17becf",
    "Nemeth_Ohlsen_1985": "#2ca02c", "Delp_1999": "#1f77b4",
    "Spoor_1990": "#9467bd", "ChenFranklin2024": "#e377c2",
    # fibre-architecture studies
    "Maganaris_1998": "#ff7f0e", "Kawakami_1998": "#8c564b",
    "Chleboun_2001": "#bcbd22", "Mao_2024": "#e377c2",
}


def _study_base(study):
    """Study label may carry a ' [task]' suffix (e.g. 'Spoor_1990 [cadaver]');
    strip it so colour lookups match the bare STUDY_COLORS keys."""
    return study.split(" [", 1)[0]


def study_color(study):
    return STUDY_COLORS.get(_study_base(study), "#888888")
# row order for the validation figure (one row per moment DOF)
DOF_ORDER = ["hip_flexion", "hip_adduction", "hip_rotation", "knee_angle", "ankle_angle"]


def load_literature(path, quantity="moment_arm"):
    """(muscle, moment_dof, x_dof) -> study -> sorted [(angle_deg, mean, sd)].

    Reads the consolidated ``literature_curves.csv``
    (quantity,muscle,moment_dof,x_dof,study,[task,]angle_deg,mean,sd), keeping only
    rows whose ``quantity`` matches. Header-driven: column order is resolved by name,
    so an optional ``task`` column (measurement condition: passive|MVC|walking|
    running|cadaver|...) can be present or absent without breaking parsing. Also
    accepts the legacy ``literature_moment_arms.csv`` layout
    (muscle,moment_dof,x_dof,study,angle_deg,mean,sd). For fascicle_length /
    pennation the moment_dof field is blank.
    """
    data = defaultdict(lambda: defaultdict(list))
    if not os.path.isfile(path):
        return data
    with open(path) as f:
        rows = [r for r in csv.reader(f) if r and not r[0].strip().startswith("#")]
    if not rows:
        return data
    header = [c.strip() for c in rows[0]]
    has_quantity = header[0] == "quantity"
    if has_quantity:
        idx = {name: i for i, name in enumerate(header)}
        need = ("muscle", "moment_dof", "x_dof", "study", "angle_deg", "mean")
        if not all(k in idx for k in need):  # fall back to fixed layout
            idx = {"quantity": 0, "muscle": 1, "moment_dof": 2, "x_dof": 3,
                   "study": 4, "angle_deg": 5, "mean": 6, "sd": 7}
    for row in rows[1:]:
        if not row or row[0].strip() in ("muscle", "quantity") or row[0].startswith("EXAMPLE"):
            continue
        if has_quantity:
            if row[idx["quantity"]].strip() != quantity:
                continue
            def g(name, default=""):
                i = idx.get(name)
                return row[i] if (i is not None and i < len(row)) else default
            muscle, mdof, xdof, study = g("muscle"), g("moment_dof"), g("x_dof"), g("study")
            task = g("task").strip()
            if task:  # keep different measurement tasks as distinct series
                study = f"{study} [{task}]"
            ang, mean = float(g("angle_deg")), float(g("mean"))
            sd_s = g("sd")
            sd = float(sd_s) if sd_s.strip() else 0.0
        else:
            muscle, mdof, xdof, study = row[0], row[1], row[2], row[3]
            ang, mean = float(row[4]), float(row[5])
            sd = float(row[6]) if len(row) > 6 and row[6].strip() else 0.0
        data[(muscle, mdof, xdof)][study].append((ang, mean, sd))
    for k in data:
        for s in data[k]:
            data[k][s].sort()
    return data


def _split_side(coord_name):
    for side in ("_l", "_r"):
        if coord_name.endswith(side):
            return coord_name[: -len(side)], side
    return coord_name, ""


def load_muscle_map(path):
    """literature_muscle -> [model muscles] from a CSV (col1=name, col2=';'-separated)."""
    import csv as _csv
    m = {}
    if not os.path.isfile(path):
        return m
    with open(path) as f:
        for i, row in enumerate(_csv.reader(f)):
            if not row or i == 0 or row[0].strip().startswith("#"):
                continue
            comps = [c.strip() for c in str(row[1]).replace(",", ";").split(";") if c.strip()]
            if row[0].strip() and comps:
                m[row[0].strip()] = comps
    return m


def muscle_map_for(csv_path):
    """Effective literature->model mapping: built-in MUSCLE_MAP overridden by the
    muscle-function matrix (validation/muscle_functions.csv) if present, else the
    legacy validation/muscle_map.csv. Both live next to ``csv_path``."""
    from .core import load_function_matrix
    m = dict(MUSCLE_MAP)
    d = os.path.dirname(csv_path)
    lit_map, _ = load_function_matrix(os.path.join(d, "muscle_functions.csv"))
    if lit_map:
        m.update(lit_map)
    else:
        m.update(load_muscle_map(os.path.join(d, "muscle_map.csv")))
    return m


def grid_overlays(lit, coord_name, model_muscle_names, muscle_map=None):
    """Bands to draw on a sweep grid for `coord_name`.

    Includes any literature panel whose moment axis == swept axis == this
    coordinate's base. The band is attached to every model compartment of the
    muscle present in the grid (for lumped muscles like gluteus maximus the same
    whole-muscle band is shown on each compartment -- approximate; the dedicated
    validation figure does the proper compartment-averaged comparison).
    Returns {model_muscle: [(label, color, ang_deg, mean_mm, sd_mm)]} (cm->mm).
    """
    base, side = _split_side(coord_name)
    names = set(model_muscle_names)
    mm = muscle_map or MUSCLE_MAP
    out = {}
    for (muscle, mdof, xdof), studies in lit.items():
        if mdof != base or xdof != base:
            continue
        series = []
        for study, pts in studies.items():
            a = np.array([p[0] for p in pts]); m = np.array([p[1] for p in pts]); s = np.array([p[2] for p in pts])
            series.append((study, study_color(study),
                           a, SIGN.get(base, 1.0) * m * 10.0, s * 10.0))
        for comp in mm.get(muscle, [muscle]):
            mname = comp + side
            if mname in names:
                out.setdefault(mname, []).extend(series)
    return out


def _sweep_moment_arm(mam, x_coord_name, moment_coord_name, comps, amin, amax, n):
    from .moment_arms import canonical_flip
    x_coord = mam.coord_set.get(x_coord_name)
    m_coord = mam.coord_set.get(moment_coord_name)
    xflip = canonical_flip(x_coord)   # canonical angle -> model coordinate value
    mflip = canonical_flip(m_coord)   # moment-arm sign in the canonical frame
    handles = [mam.muscles.get(m) for m in comps]
    assemble = mam._assemble_needed(x_coord_name)
    degs = np.linspace(amin, amax, n)   # canonical (literature) angles
    out = np.full(n, np.nan)
    mam.reset_pose()
    for k, d in enumerate(degs):
        mam._set_coord(x_coord, np.deg2rad(d * xflip), assemble=assemble)
        vals = []
        for h in handles:
            try:
                vals.append(h.computeMomentArm(mam.state, m_coord) * mflip)
            except Exception:
                pass
        if vals:
            out[k] = np.mean(vals)
    mam.reset_pose()
    return degs, out


def run_validation(model_path, csv_path, out_dir, side="_r", n=60):
    """Comparison figure (one row per moment DOF) + RMSE csv. Returns figure path or None."""
    from .moment_arms import MomentArmModel
    lit = load_literature(csv_path)
    if not lit:
        LOG.warning("validation: no literature rows in %s (skipping)", csv_path)
        return None
    os.makedirs(out_dir, exist_ok=True)
    mam = MomentArmModel(model_path)
    present = {mam.coord_set.get(i).getName() for i in range(mam.coord_set.getSize())}
    have = set(mam.all_muscle_names())
    mmap = muscle_map_for(csv_path)

    # group panels by moment DOF -> one row each
    by_mdof = defaultdict(list)
    for (muscle, mdof, xdof) in lit.keys():
        by_mdof[mdof].append((muscle, mdof, xdof))
    row_dofs = [d for d in DOF_ORDER if d in by_mdof] + [d for d in by_mdof if d not in DOF_ORDER]
    for d in row_dofs:
        by_mdof[d].sort(key=lambda k: (k[2], k[0]))  # by x_dof then muscle
    nrows = len(row_dofs)
    ncols = max(len(by_mdof[d]) for d in row_dofs)

    fig, axes = plt.subplots(nrows, ncols, figsize=(3.7 * ncols, 3.0 * nrows), squeeze=False)
    rmse_rows = [("muscle", "moment_dof", "x_dof", "side", "study", "rmse_cm", "pct_within_sd")]

    other = "_l" if side == "_r" else "_r"
    # (side, line style, label) -- primary side dashed, other side dotted; both black
    side_styles = [(side, "--", f"model ({side.strip('_').upper()})"),
                   (other, ":", f"model ({other.strip('_').upper()})")]

    for ri, mdof in enumerate(row_dofs):
        panels = by_mdof[mdof]
        for ci in range(ncols):
            ax = axes[ri][ci]
            if ci >= len(panels):
                ax.axis("off")
                continue
            muscle, _mdof, xdof = panels[ci]
            _comps = mmap.get(muscle, [muscle])
            ax.set_title(f"{muscle}\n[{'+'.join(_comps)}]", fontsize=8)
            ax.set_xlabel(f"{xdof} (deg)", fontsize=8)
            if ci == 0:
                ax.set_ylabel(f"{mdof} MA (cm)", fontsize=9)
            ax.set_ylim(-10, 10)
            ax.grid(True, alpha=0.3)

            # literature bands (side-independent), drawn first
            for study, pts in lit[(muscle, mdof, xdof)].items():
                a = np.array([p[0] for p in pts]); m = np.array([p[1] for p in pts]); s = np.array([p[2] for p in pts])
                col = study_color(study)
                ax.plot(a, m, color=col, lw=1.6, label=study)
                if np.any(s > 0):
                    ax.fill_between(a, m - s, m + s, color=col, alpha=0.25)

            # model curves: right (dashed) and left (dotted), both black
            plotted = False
            for sd, ls, lbl in side_styles:
                x_coord, m_coord = xdof + sd, mdof + sd
                comps = [c + sd for c in mmap.get(muscle, [muscle]) if (c + sd) in have]
                if x_coord not in present or m_coord not in present or not comps:
                    continue
                angs = [a for st in lit[(muscle, mdof, xdof)].values() for (a, _, _) in st]
                deg, ma_m = _sweep_moment_arm(mam, x_coord, m_coord, comps, min(angs), max(angs), n)
                ma_cm = SIGN.get(mdof, 1.0) * ma_m * 100.0
                ax.plot(deg, ma_cm, color="k", linestyle=ls, lw=2, label=lbl)
                plotted = True
                for study, pts in lit[(muscle, mdof, xdof)].items():
                    a = np.array([p[0] for p in pts]); m = np.array([p[1] for p in pts]); s = np.array([p[2] for p in pts])
                    model_at = np.interp(a, deg, ma_cm)
                    rmse = float(np.sqrt(np.mean((model_at - m) ** 2)))
                    within = float(np.mean(np.abs(model_at - m) <= np.maximum(s, 1e-9)) * 100) if np.any(s > 0) else float("nan")
                    rmse_rows.append((muscle, mdof, xdof, sd, study, f"{rmse:.2f}", f"{within:.0f}"))
                    LOG.info("VALIDATION %-16s %-13s vs %-13s | %-3s %-18s RMSE=%.2f cm within-SD=%.0f%%",
                             muscle, mdof, xdof, sd, study, rmse, within)
            if not plotted:
                ax.text(0.5, 0.5, "missing in model", ha="center", va="center",
                        transform=ax.transAxes, fontsize=8, color="grey")
            ax.legend(fontsize=6)

    base = os.path.splitext(os.path.basename(model_path))[0]
    fig.suptitle(f"Moment-arm validation vs literature -- {base} "
                 f"(model: {side.strip('_').upper()} dashed, {other.strip('_').upper()} dotted)",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig_path = os.path.join(out_dir, "validation_moment_arms.png")
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    with open(os.path.join(out_dir, "validation_rmse.csv"), "w", newline="") as f:
        csv.writer(f).writerows(rmse_rows)
    LOG.info("validation figure + rmse csv saved in %s", out_dir)
    return fig_path


def run_validation_motion(model_path, motion_df, csv_path, out_dir, side="_r",
                          max_frames=150):
    """Moment-arm validation over the ACTUAL TRIAL MOTION (not a synthetic ROM
    sweep). For every literature (muscle, moment-DOF, x-DOF) entry the model's
    moment arm is evaluated at each recorded pose of ``motion_df`` (the trial
    IK), then plotted against the x-DOF angle the motion actually visited and
    overlaid on the literature band. This shows how well the model matches the
    literature over the range the task genuinely used. Saved as
    ``validation_moment_arms_motion.png`` (+ ``validation_motion_rmse.csv``)."""
    from .moment_arms import MomentArmModel, canonical_flip
    lit = load_literature(csv_path)
    if not lit:
        LOG.warning("motion-validation: no literature rows in %s", csv_path)
        return None
    if motion_df is None or "time" not in getattr(motion_df, "columns", []):
        LOG.warning("motion-validation: motion_df has no 'time' column")
        return None
    os.makedirs(out_dir, exist_ok=True)

    # Downsample the motion so the per-frame assemble stays cheap.
    if len(motion_df) > max_frames:
        step = int(np.ceil(len(motion_df) / max_frames))
        motion_df = motion_df.iloc[::step].reset_index(drop=True)

    mam = MomentArmModel(model_path)
    present = {mam.coord_set.get(i).getName() for i in range(mam.coord_set.getSize())}
    have = set(mam.all_muscle_names())
    mmap = muscle_map_for(csv_path)
    mcols = set(motion_df.columns)

    by_mdof = defaultdict(list)
    for (muscle, mdof, xdof) in lit.keys():
        by_mdof[mdof].append((muscle, mdof, xdof))
    row_dofs = [d for d in DOF_ORDER if d in by_mdof] + [d for d in by_mdof if d not in DOF_ORDER]
    for d in row_dofs:
        by_mdof[d].sort(key=lambda k: (k[2], k[0]))
    nrows = len(row_dofs)
    ncols = max(len(by_mdof[d]) for d in row_dofs)

    fig, axes = plt.subplots(nrows, ncols, figsize=(3.7 * ncols, 3.0 * nrows), squeeze=False)
    rmse_rows = [("muscle", "moment_dof", "x_dof", "side", "study", "rmse_cm", "n_frames")]

    other = "_l" if side == "_r" else "_r"
    side_styles = [(side, "--", f"model ({side.strip('_').upper()})"),
                   (other, ":", f"model ({other.strip('_').upper()})")]

    for ri, mdof in enumerate(row_dofs):
        panels = by_mdof[mdof]
        for ci in range(ncols):
            ax = axes[ri][ci]
            if ci >= len(panels):
                ax.axis("off"); continue
            muscle, _mdof, xdof = panels[ci]
            _comps = mmap.get(muscle, [muscle])
            ax.set_title(f"{muscle}\n[{'+'.join(_comps)}]", fontsize=8)
            ax.set_xlabel("time (s)", fontsize=8)
            if ci == 0:
                ax.set_ylabel(f"{mdof} MA (cm)", fontsize=9)
            ax.set_ylim(-10, 10); ax.grid(True, alpha=0.3)

            # x-axis is TIME. The literature moment arm is a function of the JOINT
            # ANGLE, so it is remapped onto time by evaluating each study's
            # moment-arm(angle) curve at the angle the joint is actually in at every
            # instant (motion pose). Frames whose angle falls outside a study's
            # measured angle range are left blank (no extrapolation).
            plotted = False
            prim_t = prim_ang = None   # primary-side time + canonical angle trajectory
            for sd, ls, lbl in side_styles:
                x_coord, m_coord = xdof + sd, mdof + sd
                comps = [c + sd for c in mmap.get(muscle, [muscle]) if (c + sd) in have]
                if x_coord not in present or m_coord not in present or not comps:
                    continue
                if x_coord not in mcols:
                    continue  # motion doesn't drive this x-DOF
                xflip = canonical_flip(mam.coord_set.get(x_coord))
                mflip = canonical_flip(mam.coord_set.get(m_coord))
                # moment arm of the muscle group over the motion = mean over comps
                _t, ma_by = mam.moment_arm_over_motion(motion_df, m_coord, comps)
                stack = np.vstack([ma_by[c] for c in comps])
                ma_cm = SIGN.get(mdof, 1.0) * mflip * np.nanmean(stack, axis=0) * 100.0
                tt = np.asarray(_t, dtype=float)                 # time (s)
                xang = np.asarray(motion_df[x_coord], dtype=float) * xflip  # canonical angle at each t
                ok = np.isfinite(tt) & np.isfinite(ma_cm)
                ax.plot(tt[ok], ma_cm[ok], color="k", linestyle=ls, lw=2, label=lbl)  # model vs TIME
                plotted = True
                if prim_t is None:
                    prim_t, prim_ang = tt, xang                  # first valid side drives lit mapping
                # RMSE vs each study: model MA vs literature-at-current-angle, per frame
                for study, pts in lit[(muscle, mdof, xdof)].items():
                    a = np.array([p[0] for p in pts]); m = np.array([p[1] for p in pts])
                    _sa = np.argsort(a); a, m = a[_sa], m[_sa]
                    inb = ok & (xang >= a.min()) & (xang <= a.max())
                    if inb.sum() >= 2:
                        lit_at = np.interp(xang[inb], a, m)
                        rmse = float(np.sqrt(np.mean((ma_cm[inb] - lit_at) ** 2)))
                    else:
                        rmse = float("nan")
                    rmse_rows.append((muscle, mdof, xdof, sd, study, f"{rmse:.2f}", int(ok.sum())))

            # literature bands remapped onto time via the primary side's pose
            if prim_ang is not None:
                for study, pts in lit[(muscle, mdof, xdof)].items():
                    a = np.array([p[0] for p in pts]); m = np.array([p[1] for p in pts]); s = np.array([p[2] for p in pts])
                    _sa = np.argsort(a); a, m, s = a[_sa], m[_sa], s[_sa]
                    lit_m = np.interp(prim_ang, a, m)
                    lit_s = np.interp(prim_ang, a, s)
                    outside = (prim_ang < a.min()) | (prim_ang > a.max())
                    lit_m[outside] = np.nan; lit_s[outside] = np.nan
                    col = study_color(study)
                    ax.plot(prim_t, lit_m, color=col, lw=1.6, label=study)
                    if np.any(s > 0):
                        ax.fill_between(prim_t, lit_m - lit_s, lit_m + lit_s, color=col, alpha=0.25)

            if not plotted:
                ax.text(0.5, 0.5, "not driven by motion\nor missing in model",
                        ha="center", va="center", transform=ax.transAxes,
                        fontsize=7, color="grey")
            ax.legend(fontsize=6)

    base = os.path.splitext(os.path.basename(model_path))[0]
    fig.suptitle(f"Moment-arm validation over MOTION -- {base} "
                 f"(model: {side.strip('_').upper()} dashed, {other.strip('_').upper()} dotted)",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig_path = os.path.join(out_dir, "validation_moment_arms_motion.png")
    fig.savefig(fig_path, dpi=130); plt.close(fig)
    with open(os.path.join(out_dir, "validation_motion_rmse.csv"), "w", newline="") as f:
        csv.writer(f).writerows(rmse_rows)
    LOG.info("motion moment-arm validation saved in %s", out_dir)
    return fig_path


# ===================================================================
# Muscle-architecture validation: fascicle length & pennation vs joint angle
# ===================================================================
FIBRE_QUANTITIES = [("fascicle_length", "fascicle length (cm)"),
                    ("pennation", "pennation (deg)")]


def _sweep_fibre(mam, x_coord_name, comps, quantity, amin, amax, n):
    """Model fascicle length (cm) or pennation (deg) vs joint angle, averaged over comps."""
    from .moment_arms import canonical_flip
    x_coord = mam.coord_set.get(x_coord_name)
    xflip = canonical_flip(x_coord)   # canonical angle -> model coordinate value
    handles = [mam.muscles.get(m) for m in comps]
    assemble = mam._assemble_needed(x_coord_name)
    model, state = mam.model, mam.state
    degs = np.linspace(amin, amax, n)   # canonical (literature) angles
    out = np.full(n, np.nan)
    mam.reset_pose()
    for k, d in enumerate(degs):
        mam._set_coord(x_coord, np.deg2rad(d * xflip), assemble=assemble)
        for h in handles:
            try:
                h.setActivation(state, 0.02)  # near-passive resting architecture
            except Exception:
                pass
        try:
            model.equilibrateMuscles(state)
        except Exception:
            try:
                model.realizeVelocity(state)
            except Exception:
                pass
        vals = []
        for h in handles:
            try:
                if quantity == "fascicle_length":
                    vals.append(h.getFiberLength(state) * 100.0)      # m -> cm
                else:
                    vals.append(math.degrees(h.getPennationAngle(state)))  # rad -> deg
            except Exception:
                pass
        if vals:
            out[k] = float(np.mean(vals))
    mam.reset_pose()
    return degs, out


def run_fibre_validation(model_path, csv_path, out_dir, side="_r", n=40):
    """Muscle-architecture validation: model fascicle length & pennation vs joint
    angle overlaid on literature (validation/literature_curves.csv rows with
    quantity=fascicle_length|pennation). Returns figure path or None if no such rows."""
    from .moment_arms import MomentArmModel
    quantised = []
    for q, ylab in FIBRE_QUANTITIES:
        lit = load_literature(csv_path, quantity=q)
        if lit:
            quantised.append((q, ylab, lit))
    if not quantised:
        LOG.info("fibre validation: no fascicle_length/pennation rows in %s (skipping)", csv_path)
        return None
    os.makedirs(out_dir, exist_ok=True)
    mam = MomentArmModel(model_path)
    present = {mam.coord_set.get(i).getName() for i in range(mam.coord_set.getSize())}
    have = set(mam.all_muscle_names())
    mmap = muscle_map_for(csv_path)
    other = "_l" if side == "_r" else "_r"
    side_styles = [(side, "--", f"model ({side.strip('_').upper()})"),
                   (other, ":", f"model ({other.strip('_').upper()})")]

    nrows = len(quantised)
    ncols = max(len(lit) for _, _, lit in quantised)
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.9 * ncols, 3.1 * nrows), squeeze=False)
    rmse_rows = [("quantity", "muscle", "x_dof", "side", "study", "rmse", "pct_within_sd")]

    for ri, (q, ylab, lit) in enumerate(quantised):
        panels = sorted(lit.keys(), key=lambda k: (k[2], k[0]))
        for ci in range(ncols):
            ax = axes[ri][ci]
            if ci >= len(panels):
                ax.axis("off")
                continue
            muscle, _mdof, xdof = panels[ci]
            _comps = mmap.get(muscle, [muscle])
            ax.set_title(f"{muscle}\n[{'+'.join(_comps)}]", fontsize=8)
            ax.set_xlabel(f"{xdof} (deg)", fontsize=8)
            if ci == 0:
                ax.set_ylabel(ylab, fontsize=9)
            ax.grid(True, alpha=0.3)
            for study, pts in lit[(muscle, _mdof, xdof)].items():
                a = np.array([p[0] for p in pts]); m = np.array([p[1] for p in pts]); s = np.array([p[2] for p in pts])
                col = study_color(study)
                ax.plot(a, m, color=col, lw=1.6, label=study)
                if np.any(s > 0):
                    ax.fill_between(a, m - s, m + s, color=col, alpha=0.25)
            plotted = False
            for sd, ls, lbl in side_styles:
                x_coord = xdof + sd
                comps = [c + sd for c in mmap.get(muscle, [muscle]) if (c + sd) in have]
                if x_coord not in present or not comps:
                    continue
                angs = [a for st in lit[(muscle, _mdof, xdof)].values() for (a, _, _) in st]
                deg, val = _sweep_fibre(mam, x_coord, comps, q, min(angs), max(angs), n)
                ax.plot(deg, val, color="k", linestyle=ls, lw=2, label=lbl)
                plotted = True
                for study, pts in lit[(muscle, _mdof, xdof)].items():
                    a = np.array([p[0] for p in pts]); m = np.array([p[1] for p in pts]); s = np.array([p[2] for p in pts])
                    model_at = np.interp(a, deg, val)
                    rmse = float(np.sqrt(np.mean((model_at - m) ** 2)))
                    within = float(np.mean(np.abs(model_at - m) <= np.maximum(s, 1e-9)) * 100) if np.any(s > 0) else float("nan")
                    rmse_rows.append((q, muscle, xdof, sd, study, f"{rmse:.2f}", f"{within:.0f}"))
                    LOG.info("FIBRE %-14s %-22s vs %-3s %-16s RMSE=%.2f within-SD=%.0f%%",
                             q, muscle, sd, study, rmse, within)
            if not plotted:
                ax.text(0.5, 0.5, "missing in model", ha="center", va="center",
                        transform=ax.transAxes, fontsize=8, color="grey")

    _hl = {}
    for row_ax in axes:
        for ax in row_ax:
            for h, l in zip(*ax.get_legend_handles_labels()):
                _hl.setdefault(l, h)
    if _hl:
        fig.legend(_hl.values(), _hl.keys(), loc="lower center",
                   ncol=min(6, len(_hl)), fontsize=9, frameon=True)
    base = os.path.splitext(os.path.basename(model_path))[0]
    s1 = side.strip("_").upper()
    s2 = other.strip("_").upper()
    fig.suptitle("Muscle-architecture validation vs literature -- %s (model: %s dashed, %s dotted)" % (base, s1, s2), fontsize=13)
    fig.tight_layout(rect=[0, 0.05, 1, 0.96])
    fig_path = os.path.join(out_dir, "validation_fibre.png")
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    with open(os.path.join(out_dir, "validation_fibre_rmse.csv"), "w", newline="") as f:
        csv.writer(f).writerows(rmse_rows)
    LOG.info("fibre-architecture validation figure + rmse csv saved in %s", out_dir)
    return fig_path
