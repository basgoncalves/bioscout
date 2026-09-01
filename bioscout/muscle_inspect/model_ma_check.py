"""Moment-arm discontinuity check straight from a MODEL and a motion.

Unlike ``moment_arm_motion`` (which QCs already-solved MuscleAnalysis ``.sto``
files), this drives the ``.osim`` through the trial's joint angles with OpenSim
and computes the moment arms itself — so a model can be checked BEFORE any
pipeline stage is run, e.g. right after scaling or after a wrap edit.

The figure is one fig06-style column: one row per muscle group about its
primary coordinate (hip -> knee -> ankle), moment arms in cm over the task
cycle, every member muscle drawn, discontinuities marked with an X. Pass
``dofs=[...]`` instead to inspect coordinates directly — each row then shows
every muscle spanning that DOF.

    from bioscout.muscle_inspect.model_ma_check import check_ma_discontinuities
    check_ma_discontinuities("scaled.osim", "joint_angles.mot")

    python -m bioscout.muscle_inspect.model_ma_check scaled.osim joint_angles.mot
    python -m bioscout.muscle_inspect.model_ma_check scaled.osim ik.mot \
        --dofs hip_flexion_r knee_angle_r --out qc/

Found the 2026-08 defect this was written for: linearly scaled pelvis wrap
cylinders make psoas/iliacus flicker 24-31 mm twice per walking cycle.
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .discontinuity import detect_discontinuities
from .moment_arm_motion import _read_sto

#: fig06's rows: (label, member muscle stems, primary coordinate stem).
DEFAULT_GROUPS = [
    ("Gluteus maximus", ["glmax1", "glmax2", "glmax3"], "hip_flexion"),
    ("Iliopsoas", ["iliacus", "psoas"], "hip_flexion"),
    ("Gluteus med+min", ["glmed1", "glmed2", "glmed3",
                         "glmin1", "glmin2", "glmin3"], "hip_adduction"),
    ("Rectus femoris", ["recfem"], "hip_flexion"),
    ("Hamstrings", ["bflh", "bfsh", "semimem", "semiten"], "knee_angle"),
    ("Vasti", ["vasint", "vaslat", "vasmed"], "knee_angle"),
    ("Triceps surae", ["soleus", "gaslat", "gasmed"], "ankle_angle"),
]
#: OpenSim reports flexor / plantarflexor arms negative; flip into fig06's frame.
SIGN = {"knee_angle": -1.0, "ankle_angle": -1.0}
DOFLAB = {"hip_flexion": "hip flexion", "hip_adduction": "hip adduction",
          "hip_rotation": "hip rotation", "knee_angle": "knee flexion",
          "ankle_angle": "ankle dorsiflexion", "subtalar_angle": "inversion"}


def _moment_arms(model_path, motion, pairs, stride=1):
    """{(muscle, dof): mm array} for every requested (muscle, dof) pair."""
    import opensim as osim
    model = osim.Model(model_path)
    state = model.initSystem()
    coords = model.getCoordinateSet()
    present = {coords.get(i).getName() for i in range(coords.getSize())}
    mus = {}
    for m, _ in pairs:
        if m not in mus:
            try:
                mus[m] = model.getMuscles().get(m)
            except Exception:
                mus[m] = None
    pairs = [(m, d) for m, d in pairs if mus[m] is not None and d in present]
    cols = [c for c in motion.columns if c != "time" and c in present]
    rows = range(0, len(motion), stride)
    out = {p: np.full(len(list(rows)), np.nan) for p in pairs}
    for j, k in enumerate(range(0, len(motion), stride)):
        for c in cols:
            if not coords.get(c).getLocked(state):
                coords.get(c).setValue(
                    state, np.deg2rad(float(motion[c].values[k])), False)
        model.assemble(state)
        model.realizePosition(state)
        for m, d in pairs:
            try:
                out[(m, d)][j] = mus[m].computeMomentArm(
                    state, coords.get(d)) * 1000.0
            except Exception:
                pass
    return out


def check_ma_discontinuities(model, motion, out_dir=None, side="_r",
                             groups=None, dofs=None, min_jump_mm=1.0,
                             step_mm=2.0, min_ma_mm=5.0, stride=1, title=None):
    """One-column fig06-style discontinuity check of ``model`` over ``motion``.

    Parameters
    ----------
    model : str            ``.osim`` file.
    motion : str           IK ``joint_angles.mot`` (degrees).
    out_dir : str          where the png + csv go (default: next to the model).
    side : str             ``"_r"`` or ``"_l"``, appended to stems.
    groups : list          ``(label, [muscle stems], dof stem)`` rows
                           (default: the fig06 muscle groups).
    dofs : list[str]       inspect these coordinates instead of groups — each
                           row shows every muscle spanning the DOF
                           (peak |MA| >= ``min_ma_mm``).
    min_jump_mm : float    ``detect_discontinuities`` sensitivity.
    step_mm : float        also flag any frame-to-frame change above this.
    stride : int           evaluate every Nth frame (speed).

    Returns ``{"figure": png, "table": csv, "flagged": DataFrame}``.
    """
    ik, ik_deg = _read_sto(motion)
    if ik_deg is False:
        for c in ik.columns:
            if c != "time":
                ik[c] = np.degrees(ik[c])
    out_dir = out_dir or os.path.dirname(os.path.abspath(model))
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(model))[0]

    if dofs:                                     # row per coordinate
        allm = _all_muscle_names(model, side)
        rows = [(DOFLAB.get(d.removesuffix(side), d), allm, d) for d in dofs]
        rows = [(lab, ms, d if d.endswith(("_r", "_l")) else d + side)
                for lab, ms, d in rows]
    else:                                        # fig06 groups
        rows = [(lab, [m + side for m in ms], dof + side)
                for lab, ms, dof in (groups or DEFAULT_GROUPS)]

    pairs = sorted({(m, d) for _, ms, d in rows for m in ms})
    ma = _moment_arms(model, ik, pairs, stride=stride)

    recs, flagged_pairs = [], {}
    for (m, d), v in ma.items():
        ok = np.isfinite(v)
        if not ok.any():
            continue
        dv = np.abs(np.diff(v[ok]))
        jumps = detect_discontinuities(v / 1000.0, min_jump_m=min_jump_mm / 1000.0)
        n_flag = len(jumps) + int((dv > step_mm).sum() > 0 and not jumps)
        if jumps or (dv.size and dv.max() > step_mm):
            flagged_pairs[(m, d)] = jumps
        recs.append(dict(muscle=m, coordinate=d,
                         max_step_mm=round(float(dv.max()), 2) if dv.size else 0.0,
                         n_steps_over=int((dv > step_mm).sum()),
                         n_jumps=len(jumps),
                         peak_ma_mm=round(float(np.nanmax(np.abs(v))), 1),
                         flagged=bool(n_flag)))
    table = pd.DataFrame(recs).sort_values(["flagged", "max_step_mm"],
                                           ascending=False)

    nr = len(rows)
    fig, axes = plt.subplots(nr, 1, figsize=(5.2, 1.9 * nr),
                             sharex=True, squeeze=False)
    for ri, (lab, ms, d) in enumerate(rows):
        ax = axes[ri][0]
        sgn = SIGN.get(d[:-2] if d.endswith(("_r", "_l")) else d, 1.0)
        for m in ms:
            v = ma.get((m, d))
            if v is None or not np.isfinite(v).any():
                continue
            if dofs and np.nanmax(np.abs(v)) < min_ma_mm:
                continue
            x = np.linspace(0.0, 100.0, len(v))
            bad = (m, d) in flagged_pairs
            ln, = ax.plot(x, sgn * v / 10.0, lw=2.0 if bad else 1.1,
                          zorder=4 if bad else 2, label=m if (bad or dofs) else None)
            if bad:
                j = flagged_pairs[(m, d)]
                if not j:                        # step_mm-only flag
                    j = list(np.where(np.abs(np.diff(v)) > step_mm)[0] + 1)
                ax.plot(x[j], sgn * v[j] / 10.0, "x", color=ln.get_color(),
                        ms=8, mew=2, zorder=6)
        ax.set_ylabel(f"{lab}\n{DOFLAB.get(d[:-2], d)} (cm)", fontsize=8)
        ax.grid(alpha=0.25)
        ax.spines[["top", "right"]].set_visible(False)
        if any(k[1] == d and k[0] in ms for k in flagged_pairs) or dofs:
            ax.legend(fontsize=6, loc="best", frameon=False)
    axes[-1][0].set_xlabel("task cycle (%)", fontsize=9)
    nbad = len(flagged_pairs)
    fig.suptitle(title or f"{stem} — moment-arm discontinuity check\n"
                 f"{'✗ ' + str(nbad) + ' muscle(s) flagged' if nbad else 'clean'}"
                 f"  (X = jump, thresholds {min_jump_mm}/{step_mm} mm)",
                 fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    png = os.path.join(out_dir, f"{stem}_ma_discontinuity_check.png")
    csv = os.path.join(out_dir, f"{stem}_ma_discontinuity_check.csv")
    fig.savefig(png, dpi=150)
    plt.close(fig)
    table.to_csv(csv, index=False)

    bad = table[table.flagged]
    if len(bad):
        print(f"[model_ma_check] {len(bad)} muscle-DOF pair(s) flagged:")
        for _, r in bad.iterrows():
            print(f"    {r.muscle:14s} {r.coordinate:16s} "
                  f"max step {r.max_step_mm:6.2f} mm, {r.n_jumps} jump(s)")
    else:
        print("[model_ma_check] clean — no moment-arm discontinuities.")
    print(f"[model_ma_check] saved: {png}")
    return {"figure": png, "table": csv, "flagged": bad}


def _all_muscle_names(model_path, side):
    import opensim as osim
    mset = osim.Model(model_path).getMuscles()
    return [mset.get(i).getName() for i in range(mset.getSize())
            if mset.get(i).getName().endswith(side)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("model")
    ap.add_argument("motion", help="IK joint_angles.mot")
    ap.add_argument("--out", default=None)
    ap.add_argument("--side", default="_r", choices=["_r", "_l"])
    ap.add_argument("--dofs", nargs="*", default=None,
                    help="coordinates instead of muscle groups")
    ap.add_argument("--min-jump-mm", type=float, default=1.0)
    ap.add_argument("--step-mm", type=float, default=2.0)
    ap.add_argument("--stride", type=int, default=1)
    a = ap.parse_args(argv)
    r = check_ma_discontinuities(a.model, a.motion, out_dir=a.out, side=a.side,
                                 dofs=a.dofs, min_jump_mm=a.min_jump_mm,
                                 step_mm=a.step_mm, stride=a.stride)
    return 1 if len(r["flagged"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
