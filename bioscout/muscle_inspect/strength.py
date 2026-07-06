"""Isometric joint-strength validation.

Compares the model's MAXIMUM ISOMETRIC joint moment (all agonists fully active)
against the pooled literature MVC band (validation/strength_isometric.csv).

Model max isometric moment about a coordinate =
    | sum over the joint's agonist muscles of  force(activation=1) * moment_arm |
computed with the muscles equilibrated at each joint angle (velocity = 0).

This validates moment arms + max isometric forces + force-length together (joint
strength), which is different from the pure moment-arm geometry check. Requires
``import opensim``.
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


def load_strength_lit(path, test=None):
    """joint_action -> (coordinate, [(x_value, mean_nm, sd_nm)]).

    Reads the consolidated ``literature_strength.csv``
    (test,joint_action,coordinate,x_value,x_unit,mean_nm,sd_nm,n_datasets), keeping
    only rows whose ``test`` matches (isometric | isokinetic). Also accepts the
    legacy per-test files (joint_action,coordinate,x,mean_nm,sd_nm,...). x_value is
    a joint angle (deg) for isometric and an angular velocity (deg/s) for isokinetic.
    """
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path) as f:
        rows = [r for r in csv.reader(f) if r and not r[0].strip().startswith("#")]
    if not rows:
        return out
    has_test = rows[0][0].strip() == "test"
    for row in rows[1:]:
        if not row or row[0].strip() in ("joint_action", "test"):
            continue
        if has_test:
            if test is not None and row[0].strip() != test:
                continue
            act, coord = row[1], row[2]
            x, mean, sd = float(row[3]), float(row[5]), float(row[6])
        else:
            act, coord = row[0], row[1]
            x, mean, sd = float(row[2]), float(row[3]), float(row[4])
        out.setdefault(act, [coord, []])[1].append((x, mean, sd))
    for a in out:
        out[a][1].sort()
    return out


def load_muscle_groups(path):
    """joint_action -> (coordinate_or_None, [model muscle names without side]).

    Reads the muscle-function matrix (muscle_functions.csv: action columns are 0/1)
    if given one; otherwise the legacy joint_action,coordinate,model_muscles layout.
    The action's coordinate is taken from literature_strength.csv at run time, so the
    coordinate slot is None when loading from the matrix."""
    from .core import load_function_matrix
    _, action_map = load_function_matrix(path)
    if action_map:
        return {a: (None, ms) for a, ms in action_map.items()}
    out = {}
    if not os.path.isfile(path):
        return out
    with open(path) as f:
        for row in csv.reader(f):
            if not row or row[0].strip().startswith("#") or row[0] == "joint_action":
                continue
            out[row[0]] = (row[1], [m.strip() for m in row[2].replace(",", ";").split(";") if m.strip()])
    return out


def _max_isometric_moment(mam, coord_name, muscle_names, degs):
    """|sum(force * moment arm)| in Nm at each angle, all muscles at activation=1."""
    import opensim
    model, state = mam.model, mam.state
    coord = mam.coord_set.get(coord_name)
    handles = [mam.muscles.get(m) for m in muscle_names]
    assemble = mam._assemble_needed(coord_name)
    out = np.full(len(degs), np.nan)
    mam.reset_pose()
    for k, d in enumerate(degs):
        mam._set_coord(coord, np.deg2rad(d), assemble=assemble)
        for h in handles:
            try:
                h.setActivation(state, 1.0)
            except Exception:
                pass
        try:
            model.equilibrateMuscles(state)
            model.realizeDynamics(state)
        except Exception:
            # fall back to a Velocity realization if Dynamics is unavailable
            try:
                model.realizeVelocity(state)
            except Exception:
                pass
        tot = 0.0
        for h in handles:
            try:
                tot += h.getActuation(state) * h.computeMomentArm(state, coord)
            except Exception:
                pass
        out[k] = abs(tot)
    mam.reset_pose()
    return out


def run_strength(model_path, lit_csv, groups_csv, out_dir, side="_r", n=40):
    """Isometric strength figure (model vs literature MVC band) + RMSE csv."""
    from .moment_arms import MomentArmModel
    lit = load_strength_lit(lit_csv, test="isometric")
    groups = load_muscle_groups(groups_csv)
    if not lit:
        LOG.warning("strength: no literature rows in %s", lit_csv)
        return None
    os.makedirs(out_dir, exist_ok=True)
    mam = MomentArmModel(model_path)
    present = {mam.coord_set.get(i).getName() for i in range(mam.coord_set.getSize())}
    have = set(mam.all_muscle_names())
    other = "_l" if side == "_r" else "_r"

    actions = sorted(lit.keys())
    cols = min(4, len(actions))
    rows = math.ceil(len(actions) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4.3 * cols, 3.2 * rows), squeeze=False)
    rmse_rows = [("joint_action", "side", "rmse_nm", "pct_within_sd")]

    for idx, act in enumerate(actions):
        ax = axes[idx // cols][idx % cols]
        coord_base, band = lit[act]
        a = np.array([p[0] for p in band]); m = np.array([p[1] for p in band]); s = np.array([p[2] for p in band])
        ax.plot(a, m, color="#e377c2", lw=1.8, label="Chen&Franklin2024")
        ax.fill_between(a, m - s, m + s, color="#e377c2", alpha=0.25)
        ax.set_title(act, fontsize=9)
        ax.set_xlabel(f"{coord_base} (deg)", fontsize=8)
        ax.set_ylabel("moment (Nm)", fontsize=8)
        ax.grid(True, alpha=0.3)

        grp = groups.get(act)
        if grp is None:
            ax.text(0.5, 0.5, "no muscle group defined", ha="center", va="center",
                    transform=ax.transAxes, fontsize=8, color="grey")
            continue

        for sd, ls in ((side, "--"), (other, ":")):
            coord = coord_base + sd
            muscles = [mm + sd for mm in grp[1] if (mm + sd) in have]
            if coord not in present or not muscles:
                continue
            deg = np.linspace(min(a), max(a), n)
            mom = _max_isometric_moment(mam, coord, muscles, deg)
            ax.plot(deg, mom, color="k", linestyle=ls, lw=2, label=f"model ({sd.strip('_').upper()})")
            model_at = np.interp(a, deg, mom)
            rmse = float(np.sqrt(np.nanmean((model_at - m) ** 2)))
            within = float(np.mean(np.abs(model_at - m) <= np.maximum(s, 1e-9)) * 100)
            rmse_rows.append((act, sd, f"{rmse:.1f}", f"{within:.0f}"))
            LOG.info("STRENGTH %-22s %s  RMSE=%.1f Nm  within-SD=%.0f%%", act, sd, rmse, within)

    for idx in range(len(actions), rows * cols):
        axes[idx // cols][idx % cols].axis("off")
    _hl = {}
    for row_ax in axes:
        for ax in row_ax:
            for h, l in zip(*ax.get_legend_handles_labels()):
                _hl.setdefault(l, h)
    if _hl:
        fig.legend(_hl.values(), _hl.keys(), loc="lower center",
                   ncol=len(_hl), fontsize=10, frameon=True)
    base = os.path.splitext(os.path.basename(model_path))[0]
    fig.suptitle(f"Isometric joint-strength validation -- {base} "
                 f"(model: {side.strip('_').upper()} dashed, {other.strip('_').upper()} dotted)", fontsize=13)
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    fig_path = os.path.join(out_dir, "strength_isometric.png")
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    with open(os.path.join(out_dir, "strength_rmse.csv"), "w", newline="") as f:
        csv.writer(f).writerows(rmse_rows)
    LOG.info("strength figure + rmse csv saved in %s", out_dir)
    return fig_path


# ===================================================================
# Isokinetic (concentric) peak moment vs angular velocity
# ===================================================================
def _hill_fv_concentric(vn, A=0.25):
    """Normalized Hill concentric force-velocity multiplier (vn = v_fiber / v_max)."""
    vn = max(0.0, float(vn))
    return max(0.0, (1.0 - vn) / (1.0 + vn / A))


def isokinetic_peaks(mam, coord_name, muscle_names, angles_deg, velocities_degps):
    """Model peak concentric moment (Nm) at each angular velocity.

    At each joint angle the agonists are equilibrated at activation=1 (isometric
    force F_iso, moment arm a, optimal fibre length L0, v_max). For a joint speed
    omega, each muscle's fibre velocity ~ a*omega (rigid tendon); its force is
    scaled by the Hill concentric multiplier fv(a*omega / (v_max*L0)). Peak moment
    = max over angle of |sum F_iso*fv*a|.
    """
    import opensim
    model, state = mam.model, mam.state
    coord = mam.coord_set.get(coord_name)
    handles = [mam.muscles.get(m) for m in muscle_names]
    assemble = mam._assemble_needed(coord_name)

    # per-angle, per-muscle isometric properties
    props = []  # list over angles of list of (F_iso, a, L0, vmax)
    mam.reset_pose()
    for d in angles_deg:
        mam._set_coord(coord, np.deg2rad(d), assemble=assemble)
        for h in handles:
            try:
                h.setActivation(state, 1.0)
            except Exception:
                pass
        try:
            model.equilibrateMuscles(state)
            model.realizeDynamics(state)
        except Exception:
            try:
                model.realizeVelocity(state)
            except Exception:
                pass
        row = []
        for h in handles:
            try:
                F = h.getActuation(state)
                a = h.computeMomentArm(state, coord)
                L0 = h.getOptimalFiberLength()
                vmax = h.getMaxContractionVelocity()  # optimal fibre lengths / s (default 10)
                row.append((F, a, L0, vmax if vmax > 0 else 10.0))
            except Exception:
                row.append((0.0, 0.0, 0.1, 10.0))
        props.append(row)
    mam.reset_pose()

    peaks = np.full(len(velocities_degps), np.nan)
    for vi, omega_deg in enumerate(velocities_degps):
        wr = np.deg2rad(omega_deg)
        best = 0.0
        for row in props:
            tot = 0.0
            for (F, a, L0, vmax) in row:
                vn = (abs(a) * wr) / (vmax * L0) if (vmax * L0) > 0 else 1.0
                tot += F * _hill_fv_concentric(vn) * a
            best = max(best, abs(tot))
        peaks[vi] = best
    return peaks


def run_isokinetic(model_path, iso_lit_csv, groups_csv, angle_lit_csv, out_dir,
                   side="_r", n_angle=25):
    """Isokinetic (concentric) peak moment vs velocity: model vs literature band."""
    from .moment_arms import MomentArmModel
    lit = load_strength_lit(iso_lit_csv, test="isokinetic")     # action -> (coord, [(vel, mean, sd)])
    angle_lit = load_strength_lit(angle_lit_csv, test="isometric")  # action -> (coord, [(angle, ...)]) for ROM
    groups = load_muscle_groups(groups_csv)
    if not lit:
        LOG.warning("isokinetic: no literature rows in %s", iso_lit_csv)
        return None
    os.makedirs(out_dir, exist_ok=True)
    mam = MomentArmModel(model_path)
    present = {mam.coord_set.get(i).getName() for i in range(mam.coord_set.getSize())}
    have = set(mam.all_muscle_names())
    other = "_l" if side == "_r" else "_r"

    actions = sorted(lit.keys())
    cols = min(4, len(actions))
    rows = math.ceil(len(actions) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4.3 * cols, 3.2 * rows), squeeze=False)
    rmse_rows = [("joint_action", "side", "rmse_nm", "pct_within_sd")]

    for idx, act in enumerate(actions):
        ax = axes[idx // cols][idx % cols]
        coord_base, band = lit[act]
        v = np.array([p[0] for p in band]); m = np.array([p[1] for p in band]); s = np.array([p[2] for p in band])
        ax.plot(v, m, color="#17becf", lw=1.8, label="Chen&Franklin2024")
        ax.fill_between(v, m - s, m + s, color="#17becf", alpha=0.25)
        ax.set_title(act, fontsize=9)
        ax.set_xlabel("angular velocity (deg/s)", fontsize=8)
        ax.set_ylabel("peak moment (Nm)", fontsize=8)
        ax.grid(True, alpha=0.3)

        grp = groups.get(act)
        if grp is None:
            ax.text(0.5, 0.5, "no muscle group", ha="center", va="center",
                    transform=ax.transAxes, fontsize=8, color="grey")
            continue
        # ROM to search for peak: from the isometric-angle band if available
        if act in angle_lit:
            aa = [p[0] for p in angle_lit[act][1]]; amin, amax = min(aa), max(aa)
        else:
            amin, amax = -60.0, 0.0
        angles = np.linspace(amin, amax, n_angle)

        for sd, ls in ((side, "--"), (other, ":")):
            coord = coord_base + sd
            muscles = [mm + sd for mm in grp[1] if (mm + sd) in have]
            if coord not in present or not muscles:
                continue
            peaks = isokinetic_peaks(mam, coord, muscles, angles, v)
            ax.plot(v, peaks, color="k", linestyle=ls, lw=2, label=f"model ({sd.strip('_').upper()})")
            rmse = float(np.sqrt(np.nanmean((peaks - m) ** 2)))
            within = float(np.mean(np.abs(peaks - m) <= np.maximum(s, 1e-9)) * 100)
            rmse_rows.append((act, sd, f"{rmse:.1f}", f"{within:.0f}"))
            LOG.info("ISOKINETIC %-22s %s  RMSE=%.1f Nm  within-SD=%.0f%%", act, sd, rmse, within)

    for idx in range(len(actions), rows * cols):
        axes[idx // cols][idx % cols].axis("off")
    _hl = {}
    for row_ax in axes:
        for ax in row_ax:
            for h, l in zip(*ax.get_legend_handles_labels()):
                _hl.setdefault(l, h)
    if _hl:
        fig.legend(_hl.values(), _hl.keys(), loc="lower center",
                   ncol=len(_hl), fontsize=10, frameon=True)
    base = os.path.splitext(os.path.basename(model_path))[0]
    fig.suptitle(f"Isokinetic (concentric) peak-moment validation -- {base} "
                 f"(model: {side.strip('_').upper()} dashed, {other.strip('_').upper()} dotted)", fontsize=13)
    fig.tight_layout(rect=[0, 0.04, 1, 0.96])
    fig_path = os.path.join(out_dir, "strength_isokinetic.png")
    fig.savefig(fig_path, dpi=130)
    plt.close(fig)
    with open(os.path.join(out_dir, "strength_isokinetic_rmse.csv"), "w", newline="") as f:
        csv.writer(f).writerows(rmse_rows)
    LOG.info("isokinetic figure + rmse csv saved in %s", out_dir)
    return fig_path
