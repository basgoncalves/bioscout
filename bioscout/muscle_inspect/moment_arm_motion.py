"""Moment-arm QC over the ACTUAL TRIAL MOTION (not a ROM sweep).

Reads the OpenSim MuscleAnalysis moment-arm ``.sto`` files (already produced by the
muscle-analysis stage — no OpenSim call, no literature) plus the trial's IK joint
angles, and for every DOF plots each spanning muscle's moment arm against the JOINT
ANGLE the motion actually visited, flagging discontinuities (wrap-point glitches)
that occurred DURING the movement.

This is the motion-driven counterpart to the ``validate``/``inspect`` model checks:
those sweep each coordinate over its full range to compare against literature; this
one only asks "are the moment arms that drove ID/SO/CEINMS smooth over THIS task?".
Fast, per-trial, standalone.

    from bioscout.muscle_inspect.moment_arm_motion import inspect_moment_arms_over_motion
    inspect_moment_arms_over_motion("…/muscle_analysis",
                                    "…/external_biomechanics/joint_angles.mot")
"""
from __future__ import annotations

import os
from io import StringIO

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .discontinuity import detect_discontinuities

# Default lower-limb DOFs to inspect (stems, no side). Only those with a moment-arm
# .sto AND an IK column are used.
DEFAULT_DOFS = ["hip_flexion", "hip_adduction", "hip_rotation",
                "knee_angle", "knee_adduction", "ankle_angle", "subtalar_angle"]


def _read_sto(path):
    """Read an OpenSim ``.sto``/``.mot`` into a DataFrame (NUL-safe, header-skipping).

    Returns ``(df, in_degrees)`` where ``in_degrees`` reflects the file's
    ``inDegrees`` header flag (None if absent)."""
    raw = open(path, "rb").read().replace(b"\x00", b"").decode("latin1")
    L = raw.splitlines()
    h = next(i for i, l in enumerate(L) if l.strip().lower() == "endheader")
    in_deg = None
    for l in L[:h]:
        if l.strip().lower().startswith("indegrees"):
            in_deg = l.split("=")[-1].strip().lower() == "yes"
    df = pd.read_csv(StringIO("\n".join(L[h + 1:])), sep=r"\s+", engine="python")
    return df.apply(pd.to_numeric, errors="coerce"), in_deg


def inspect_moment_arms_over_motion(ma_dir, ik_mot, out_dir=None, dofs=None,
                                    side="_r", min_ma_mm=3.0, min_jump_mm=1.0,
                                    max_muscles=14, title=None):
    """QC the model's moment arms over the trial motion.

    Parameters
    ----------
    ma_dir : str
        Folder holding ``_MuscleAnalysis_MomentArm_<dof>.sto`` (the trial's
        ``muscle_analysis/``).
    ik_mot : str
        The trial's IK ``joint_angles.mot`` — supplies the joint-angle x-axis.
    out_dir : str, optional
        Where to write ``moment_arm_motion_check.png`` (default: ``ma_dir``).
    dofs : list[str], optional
        DOF stems (no side) to inspect, e.g. ``["hip_flexion", "knee_angle"]``.
        Default: the standard lower-limb set present on disk.
    side : str
        ``"_r"`` or ``"_l"``.
    min_ma_mm : float
        Only inspect muscles whose peak |moment arm| exceeds this (mm) for a DOF —
        i.e. the muscles that actually span it.
    min_jump_mm : float
        Discontinuity sensitivity (mm). Lower = more sensitive.
    max_muscles : int
        Cap on curves drawn per panel (largest |MA| first); all spanning muscles are
        still checked for discontinuities.

    Returns
    -------
    dict
        ``{"figure": <png path or None>, "flagged": [(dof, muscle, n_jumps), ...],
           "dofs": [<dof>, ...]}``.

    Notes
    -----
    A near-static DOF (small angle range) shows its curves as a near-vertical smear —
    expected, not a defect: the joint simply didn't move much over this window.
    """
    out_dir = out_dir or ma_dir
    os.makedirs(out_dir, exist_ok=True)
    ik, ik_deg = _read_sto(ik_mot)
    if "time" not in ik.columns:
        print(f"[moment_arm_motion] IK file has no 'time' column: {ik_mot}")
        return {"figure": None, "flagged": [], "dofs": []}

    use = []
    for stem in (dofs or DEFAULT_DOFS):
        dof = stem + side
        p = os.path.join(ma_dir, f"_MuscleAnalysis_MomentArm_{dof}.sto")
        if os.path.exists(p) and dof in ik.columns:
            use.append((dof, p))
    if not use:
        print(f"[moment_arm_motion] no MA moment-arm files + IK angles for side "
              f"{side!r} in {ma_dir}")
        return {"figure": None, "flagged": [], "dofs": []}

    ncols = 3
    nrows = int(np.ceil(len(use) / ncols))
    fig, ax = plt.subplots(nrows, ncols, figsize=(4.7 * ncols, 3.4 * nrows), squeeze=False)
    flagged = []
    for k, (dof, p) in enumerate(use):
        a = ax[k // ncols][k % ncols]
        ma, _ = _read_sto(p)
        # Joint-angle trajectory for this DOF, resampled onto the MA time base.
        ang = ik[dof].to_numpy(float)
        if ik_deg is False:                       # IK stored in radians -> degrees
            ang = np.degrees(ang)
        ang = np.interp(ma["time"].to_numpy(float), ik["time"].to_numpy(float), ang)

        muscles = [c for c in ma.columns if c != "time"]
        # Rank spanning muscles by peak |moment arm| (mm); only those above threshold.
        span = [(m, float(np.nanmax(np.abs(ma[m].to_numpy(float))) * 1000.0)) for m in muscles]
        span = sorted([(m, v) for m, v in span if v >= min_ma_mm], key=lambda x: -x[1])
        drawn = 0
        for m, _v in span:
            arr = ma[m].to_numpy(float)
            jumps = detect_discontinuities(arr, min_jump_m=min_jump_mm / 1000.0)
            if jumps:
                flagged.append((dof, m, len(jumps)))
            if drawn < max_muscles or jumps:      # always draw flagged muscles
                y = arr * 1000.0                  # mm
                ln, = a.plot(ang, y, lw=2.2 if jumps else 0.9,
                             label=m if jumps else None, zorder=4 if jumps else 2)
                if jumps:
                    a.plot(ang[jumps], y[jumps], "o", color=ln.get_color(),
                           ms=6, mec="k", mew=0.5, zorder=6)
                drawn += 1
        a.set_title(dof, fontsize=9)
        a.set_xlabel(f"{dof} angle (deg)", fontsize=8)
        a.set_ylabel("moment arm (mm)", fontsize=8)
        a.grid(alpha=0.3)
        if any(d == dof for d, _m, _n in flagged):
            a.legend(fontsize=6, loc="best")
    for k in range(len(use), nrows * ncols):
        ax[k // ncols][k % ncols].axis("off")

    fig.suptitle(title or "Moment arms over motion  (● = discontinuity)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out = os.path.join(out_dir, "moment_arm_motion_check.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)

    if flagged:
        print(f"[moment_arm_motion] {len(flagged)} muscle-DOF moment-arm discontinuit(ies) "
              f"flagged over the motion:")
        for dof, m, n in flagged:
            print(f"    {dof:20s} {m:16s} {n} jump(s)")
    else:
        print("[moment_arm_motion] no moment-arm discontinuities over the motion.")
    print(f"[moment_arm_motion] saved: {out}")
    return {"figure": out, "flagged": flagged, "dofs": [d for d, _ in use]}
