"""Muscle vs ID moments in the context of the task: poses, GRF and joint angles.

``static_optimisation/muscle_moments_<side>.png`` -- one figure per leg, in the
vertical task layout of :mod:`bioscout.plot.task_figure` (poses and vGRF on
top), then one row per reserved coordinate of that leg:

    stacked muscle-group moments (force x moment arm, groups/colours as in
    contributions_so.png) + reserve (hatched), summing to the ID moment (black),
    in N·m, left axis; joint angle (grey dotted, right axis)
    title: RMSE(muscles, ID) and peak |reserve|, both in % of the ID moment's
    RANGE (the numbers in muscle_moments.csv); green < 5 %, orange < 10 %, red

Trial data only: the point is to see WHEN in the task each reserve works.

    python -m bioscout.plot.muscle_moments_task <trial folder> [--sides r l]

Called after SO by ``Analyse.plot_muscle_moments`` (via
``bioscout.simulate.so_files.plot_muscle_moments``).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from bioscout.plot.task_figure import TaskStrip, read_sto

ORDER = ("hip_flexion", "hip_adduction", "hip_rotation", "knee_angle",
         "knee_adduction", "ankle_angle", "subtalar_angle", "mtp_angle")
FIG = "muscle_moments_{side}.png"

from bioscout.core.jcf_contributions import STACK_ORDER as _SO, _stack_colors
STACK_ORDER = [g for g in _SO if g not in ("Intersegmental", "Other leg (lumped)",
                                           "Reserve actuators")]
COL = _stack_colors()
HATCH = {"Reserve actuators": "///"}


class _LazyLegend(list):
    """Legend handles built when the figure asks for them (after the rows are
    drawn), so only groups that actually appear are listed."""
    def __init__(self, make):
        super().__init__()
        self._make = make

    def __iter__(self):
        if not len(self):
            self.extend(self._make())
        return super().__iter__()

    def __len__(self):
        return super().__len__() or len(self._make())


def _rmse_color(p):
    return "tab:green" if p < 5 else "darkorange" if p < 10 else "tab:red"


def _grouped_muscle_moments(trial, col, ts):
    """{stack group: moment (N·m) on ``ts``} from
    muscle_analysis/_MuscleMoments_<col>_so.sto (force x moment arm per muscle),
    grouped with the same groups/colours as contributions_so.png. None if absent."""
    from bioscout.core.jcf_contributions import stack_group
    f = Path(trial) / "muscle_analysis" / f"_MuscleMoments_{col}_so.sto"
    if not f.exists():
        return None
    mm, _ = read_sto(f)
    tm = mm["time"].to_numpy(float)
    out = {}
    for m in mm.columns:
        if m == "time":
            continue
        v = np.interp(ts, tm, mm[m].to_numpy(float))
        if not np.any(np.abs(v) > 1e-9):
            continue
        g = stack_group(m)
        out[g] = out.get(g, 0) + v
    return out


def muscle_moments(trial, sides=None, out_dir=None, log=print, strip=None):
    """Draw muscle_moments_<side>.png for ``trial`` (a 3_iterations/<it>/<trial>
    folder). Returns the list of figure paths."""
    import matplotlib.pyplot as plt
    from bioscout.simulate import so_files as sof

    trial = Path(trial).resolve()
    if trial.name == "static_optimisation":
        trial = trial.parent
    so_dir = trial / "static_optimisation"
    out_dir = Path(out_dir or so_dir)
    so, _ = read_sto(sof.pick(so_dir / sof.FORCE))
    idm, _ = read_sto(trial / "external_biomechanics" / "inverse_dynamics.sto")
    ik, deg = read_sto(trial / "external_biomechanics" / "joint_angles.mot")
    ts = so["time"].to_numpy(float)
    ti = idm["time"].to_numpy(float)
    tik = ik["time"].to_numpy(float)
    strip = strip or TaskStrip(trial, t_range=(float(ts[0]), float(ts[-1])), log=log)

    res_cols = [c for c in so.columns if c.endswith("_reserve")]
    sides = sides or sorted({c[:-len("_reserve")][-1] for c in res_cols
                             if c[:-len("_reserve")][-2:] in ("_r", "_l")})
    made = []
    for sd in sides:
        used = set()
        dofs = [d for d in ORDER if f"{d}_{sd}_reserve" in so.columns
                and f"{d}_{sd}_moment" in idm.columns]
        if not dofs:
            continue
        rows = []
        for d in dofs:
            mom = np.interp(ts, ti, idm[f"{d}_{sd}_moment"].to_numpy(float))
            res = so[f"{d}_{sd}_reserve"].to_numpy(float)
            rng = float(np.ptp(mom)) or np.nan
            rmse_pct = 100 * float(np.sqrt(np.mean(res ** 2))) / rng
            peak_pct = 100 * float(np.max(np.abs(res))) / rng
            col = f"{d}_{sd}"
            ang = (np.interp(ts, tik, ik[col].to_numpy(float)) if col in ik.columns
                   else None)
            if ang is not None and not deg:
                ang = np.degrees(ang)

            groups = _grouped_muscle_moments(trial, col, ts)
            if groups:
                used.update(groups)
                used.add("Reserve actuators")
            else:
                used.add("__lines__")

            def draw(a, mom=mom, res=res, ang=ang, groups=groups):
                if groups:
                    pos = np.zeros_like(ts)
                    neg = np.zeros_like(ts)
                    stack = [(g, groups[g]) for g in STACK_ORDER if g in groups]
                    stack.append(("Reserve actuators", res))
                    for g, v in stack:
                        p, n = np.clip(v, 0, None), np.clip(v, None, 0)
                        kw = dict(color=COL[g], lw=0, hatch=HATCH.get(g),
                                  edgecolor="white" if g in HATCH else None, zorder=2)
                        a.fill_between(ts, pos, pos + p, **kw)
                        a.fill_between(ts, neg, neg + n, **kw)
                        pos, neg = pos + p, neg + n
                        used.add(g)
                    a.plot(ts, mom, color="k", lw=1.7, zorder=3)
                else:                                   # no per-muscle file: old look
                    a.plot(ts, mom, color="k", lw=1.7, zorder=3)
                    a.plot(ts, mom - res, color="tab:blue", lw=1.1, ls="--", zorder=4)
                    a.plot(ts, res, color="tab:purple", lw=1.2, zorder=5)
                    used.add("__lines__")
                a.axhline(0, color="0.4", lw=0.5, zorder=3)
                if ang is not None:
                    a2 = a.twinx()
                    a2.plot(ts, ang, color="0.55", lw=1.0, ls=":")
                    a2.set_ylabel("angle (°)", fontsize=7, color="0.45")
                    a2.tick_params(labelsize=6, colors="0.45")

            rows.append(dict(draw=draw, ylabel="N·m", title_color=_rmse_color(rmse_pct),
                             title=f"{col}   RMSE {rmse_pct:.1f} % · peak "
                                   f"{peak_pct:.0f} % of ID range"))
        def legend():
            from matplotlib.patches import Patch
            h = [Patch(facecolor=COL[g], hatch=HATCH.get(g),
                       edgecolor="white" if g in HATCH else COL[g], label=g)
                 for g in STACK_ORDER + ["Reserve actuators"] if g in used]
            h.append(plt.Line2D([], [], color="k", lw=1.7, label="ID moment"))
            if "__lines__" in used:
                h += [plt.Line2D([], [], color="tab:blue", lw=1.1, ls="--",
                                 label="muscles (ID - reserve)"),
                      plt.Line2D([], [], color="tab:purple", lw=1.2, label="reserve")]
            h.append(plt.Line2D([], [], color="0.55", lw=1.0, ls=":",
                                label="joint angle (right axis)"))
            return h
        h = legend()
        out = strip.figure(rows, out_dir / FIG.format(side=sd), legend=h)
        made.append(out)
        if log:
            log(f"Saved muscle moments figure: {out}")
    return made


#: back-compat name (the figure used to be muscle_moments_task_<side>.png)
muscle_moments_task = muscle_moments


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trial", help="3_iterations/<iteration>/<trial> folder "
                                  "(or its static_optimisation subfolder)")
    ap.add_argument("--sides", nargs="+", choices=("r", "l"))
    a = ap.parse_args(argv)
    import matplotlib
    matplotlib.use("Agg")
    muscle_moments(a.trial, sides=a.sides)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
