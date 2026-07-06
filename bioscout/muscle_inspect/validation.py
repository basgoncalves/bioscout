"""Literature moment-arm validation (reusable).

Loads digitized literature bands (validation/literature_moment_arms.csv), computes
the model's moment arms, and (a) produces a dedicated comparison figure laid out
with one ROW per moment DOF (flexion, adduction, rotation, ...) + RMSE csv, and
(b) provides band overlays for the sweep grids where the panel's moment axis ==
swept axis and the muscle maps 1:1 to a model muscle.
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

from .logutil import LOG

MUSCLE_MAP = {
    "psoas": ["psoas"], "iliacus": ["iliacus"],
    "semitendinosus": ["semiten"], "semimembranosus": ["semimem"],
    "adductor_magnus": ["addmagProx", "addmagMid", "addmagDist", "addmagIsch"],
    "gluteus_maximus": ["glmax1", "glmax2", "glmax3"],
    "gluteus_medius": ["glmed1", "glmed2", "glmed3"],
}
SIGN = {"hip_flexion": 1.0, "hip_adduction": 1.0, "hip_rotation": 1.0, "knee_angle": 1.0}
STUDY_COLORS = {
    "Arnold_James_2000": "#d62728", "Blemker_Delp_2005": "#17becf",
    "Nemeth_Ohlsen_1985": "#2ca02c", "Delp_1999": "#1f77b4",
}
# row order for the validation figure (one row per moment DOF)
DOF_ORDER = ["hip_flexion", "hip_adduction", "hip_rotation", "knee_angle"]


def load_literature(path, quantity="moment_arm"):
    """(muscle, moment_dof, x_dof) -> study -> sorted [(angle_deg, mean_cm, sd_cm)].

    Header-driven: accepts the consolidated ``literature_curves`` schema
    (quantity,muscle,moment_dof,x_dof,study,[task,]angle_deg,mean,sd) -- keeping
    only rows whose ``quantity`` matches -- as well as the legacy layout
    (muscle,moment_dof,x_dof,study,angle_deg,mean_cm,sd_cm). An optional ``task``
    column is folded into the study label so different measurement tasks stay as
    distinct series.
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
    idx = {name: i for i, name in enumerate(header)} if has_quantity else None
    if has_quantity and not all(k in idx for k in
                                ("muscle", "moment_dof", "x_dof", "study", "angle_deg", "mean")):
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
            if task:
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


def grid_overlays(lit, coord_name, model_muscle_names):
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
    out = {}
    for (muscle, mdof, xdof), studies in lit.items():
        if mdof != base or xdof != base:
            continue
        series = []
        for study, pts in studies.items():
            a = np.array([p[0] for p in pts]); m = np.array([p[1] for p in pts]); s = np.array([p[2] for p in pts])
            series.append((study, STUDY_COLORS.get(study, "#888888"),
                           a, SIGN.get(base, 1.0) * m * 10.0, s * 10.0))
        for comp in MUSCLE_MAP.get(muscle, [muscle]):
            mname = comp + side
            if mname in names:
                out.setdefault(mname, []).extend(series)
    return out


def _sweep_moment_arm(mam, x_coord_name, moment_coord_name, comps, amin, amax, n):
    x_coord = mam.coord_set.get(x_coord_name)
    m_coord = mam.coord_set.get(moment_coord_name)
    handles = [mam.muscles.get(m) for m in comps]
    assemble = mam._assemble_needed(x_coord_name)
    degs = np.linspace(amin, amax, n)
    out = np.full(n, np.nan)
    mam.reset_pose()
    for k, d in enumerate(degs):
        mam._set_coord(x_coord, np.deg2rad(d), assemble=assemble)
        vals = []
        for h in handles:
            try:
                vals.append(h.computeMomentArm(mam.state, m_coord))
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
    rmse_rows = [("muscle", "moment_dof", "x_dof", "study", "rmse_cm", "pct_within_sd")]

    for ri, mdof in enumerate(row_dofs):
        panels = by_mdof[mdof]
        for ci in range(ncols):
            ax = axes[ri][ci]
            if ci >= len(panels):
                ax.axis("off")
                continue
            muscle, _mdof, xdof = panels[ci]
            x_coord, m_coord = xdof + side, mdof + side
            comps = [m + side for m in MUSCLE_MAP.get(muscle, [muscle]) if (m + side) in have]
            ax.set_title(muscle, fontsize=9)
            ax.set_xlabel(f"{xdof} (deg)", fontsize=8)
            if ci == 0:
                ax.set_ylabel(f"{mdof} MA (cm)", fontsize=9)
            ax.set_ylim(-10, 10)
            ax.grid(True, alpha=0.3)
            if x_coord not in present or m_coord not in present or not comps:
                ax.text(0.5, 0.5, "missing in model", ha="center", va="center",
                        transform=ax.transAxes, fontsize=8, color="grey")
                continue

            angs = [a for st in lit[(muscle, mdof, xdof)].values() for (a, _, _) in st]
            deg, ma_m = _sweep_moment_arm(mam, x_coord, m_coord, comps, min(angs), max(angs), n)
            ma_cm = SIGN.get(mdof, 1.0) * ma_m * 100.0
            ax.plot(deg, ma_cm, "k--", lw=2, label="model")
            for study, pts in lit[(muscle, mdof, xdof)].items():
                a = np.array([p[0] for p in pts]); m = np.array([p[1] for p in pts]); s = np.array([p[2] for p in pts])
                col = STUDY_COLORS.get(study, "#888888")
                ax.plot(a, m, color=col, lw=1.6, label=study)
                if np.any(s > 0):
                    ax.fill_between(a, m - s, m + s, color=col, alpha=0.25)
                model_at = np.interp(a, deg, ma_cm)
                rmse = float(np.sqrt(np.mean((model_at - m) ** 2)))
                within = float(np.mean(np.abs(model_at - m) <= np.maximum(s, 1e-9)) * 100) if np.any(s > 0) else float("nan")
                rmse_rows.append((muscle, mdof, xdof, study, f"{rmse:.2f}", f"{within:.0f}"))
                LOG.info("VALIDATION %-16s %-13s vs %-13s | %-18s RMSE=%.2f cm within-SD=%.0f%%",
                         muscle, mdof, xdof, study, rmse, within)
            ax.legend(fontsize=6)

    base = os.path.splitext(os.path.basename(model_path))[0]
    fig.suptitle(f"Moment-arm validation vs literature -- {base} (side {side})", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig_path = os.path.join(out_dir, "validation_moment_arms.png")
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    with open(os.path.join(out_dir, "validation_rmse.csv"), "w", newline="") as f:
        csv.writer(f).writerows(rmse_rows)
    LOG.info("validation figure + rmse csv saved in %s", out_dir)
    return fig_path
