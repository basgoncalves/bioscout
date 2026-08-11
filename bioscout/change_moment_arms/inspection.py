"""Check a moment-arm edit the moment it is made.

Growing a wrap surface or shifting a path point is exactly the operation that
puts a muscle path through a bone, so verification is part of producing the
model rather than a separate chore you might remember to do. This runs at the
end of every ``bioscout --change-moment-arms`` run and produces three things:

1. **A before/after overlay** per coordinate — the original curve and the
   modified one on the same axes, per muscle, with the achieved change in the
   subplot title. This is the plot the whole exercise is *about*: it shows
   whether the curve moved as a shape-preserving shift or got bent out of
   recognition.
2. **A CSV** of baseline vs modified mean and peak moment arm, so the change
   can go into a manuscript table without re-deriving it by eye.
3. **The standard ``muscle_inspect`` pass** on the modified model, which sweeps
   every default coordinate (not just the edited one — an edit about hip
   adduction also moves the same muscle's hip flexion moment arm), flags
   discontinuities, and writes the wrap-corrected ``*_modWO.osim`` alongside.

Only step 3 needs the rest of bioscout; steps 1-2 need opensim and matplotlib.
Every step degrades to a reported ``reason`` rather than an exception, because
a failed check must not invalidate a good model.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

__all__ = ["compare_sweeps", "plot_comparison", "write_summary_csv",
           "inspect_change"]

#: A muscle whose mean moment arm moved less than this is reported as unchanged
#: rather than plotted — otherwise a whole-model overlay is mostly flat lines.
_MIN_CHANGE_MM = 0.05


def compare_sweeps(before_model, after_model, coordinates, *,
                   muscles: Optional[List[str]] = None, n: int = 40) -> Dict:
    """Sweep both models and pair the curves up per coordinate and muscle.

    Returns ``{coordinate: {"deg": array, "muscles": {name: (before, after)}}}``
    with moment arms in **mm**. Only muscles present in both sweeps appear; a
    muscle that stopped spanning the coordinate after the edit is a red flag
    and is listed separately by :func:`inspect_change`.
    """
    from bioscout.muscle_inspect import moment_arms

    out: Dict[str, dict] = {}
    sw_b = moment_arms.compute_sweeps(str(before_model), coordinate_names=list(coordinates),
                                      muscle_filter=muscles, n=n)
    sw_a = moment_arms.compute_sweeps(str(after_model), coordinate_names=list(coordinates),
                                      muscle_filter=muscles, n=n)
    for c in coordinates:
        b, a = sw_b.get(c), sw_a.get(c)
        if b is None or a is None:
            continue
        pairs = {}
        for m, mab in b.moment_arms.items():
            maa = a.moment_arms.get(m)
            if maa is None:
                continue
            k = min(len(mab), len(maa))
            pairs[m] = (np.asarray(mab[:k], float) * 1000.0,
                        np.asarray(maa[:k], float) * 1000.0)
        out[c] = {"deg": np.asarray(b.angles_deg, float),
                  "muscles": pairs,
                  "lost": sorted(set(b.moment_arms) - set(a.moment_arms))}
    return out


def _changed(pairs, min_mm=_MIN_CHANGE_MM):
    """Muscles whose mean moment arm moved, biggest change first."""
    rows = []
    for m, (before, after) in pairs.items():
        d = float(np.nanmean(after) - np.nanmean(before))
        if abs(d) >= min_mm:
            rows.append((m, d))
    return [m for m, _ in sorted(rows, key=lambda r: -abs(r[1]))]


def plot_comparison(comparison, out_dir, *, title_prefix="") -> List[str]:
    """One figure per coordinate: baseline vs modified, per changed muscle.

    Grey is the model you started from, colour is the model you just wrote, so
    a glance answers the question that matters — did the curve translate, or
    did it change shape?
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for coord, data in comparison.items():
        names = _changed(data["muscles"])
        if not names:
            continue
        deg = data["deg"]
        ncol = min(4, len(names))
        nrow = int(np.ceil(len(names) / ncol))
        fig, axes = plt.subplots(nrow, ncol, figsize=(3.2 * ncol, 2.5 * nrow),
                                 squeeze=False, sharex=True)
        for ax, m in zip(axes.ravel(), names):
            before, after = data["muscles"][m]
            k = min(len(deg), len(before), len(after))
            ax.axhline(0, color="0.85", lw=0.8, zorder=0)
            ax.plot(deg[:k], before[:k], color="0.55", lw=1.4, label="original")
            ax.plot(deg[:k], after[:k], color="#0b6fa4", lw=1.6, label="modified")
            mb, ma_ = float(np.nanmean(before)), float(np.nanmean(after))
            pct = (ma_ / mb - 1.0) * 100.0 if abs(mb) > 1e-9 else float("nan")
            ax.set_title(f"{m}\n{mb:+.1f} -> {ma_:+.1f} mm ({pct:+.0f}%)",
                         fontsize=8)
            ax.tick_params(labelsize=7)
        for ax in axes.ravel()[len(names):]:
            ax.axis("off")
        for ax in axes[-1]:
            ax.set_xlabel(f"{coord} (deg)", fontsize=8)
        for row in axes:
            row[0].set_ylabel("moment arm (mm)", fontsize=8)
        axes[0][0].legend(fontsize=7, frameon=False)
        fig.suptitle(f"{title_prefix}moment arm before/after — {coord}",
                     fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        p = out_dir / f"momentarm_change_{coord}.png"
        fig.savefig(p, dpi=140)
        plt.close(fig)
        written.append(str(p))
    return written


def write_summary_csv(comparison, path) -> str:
    """Baseline vs modified mean and peak per muscle — a table you can cite."""
    import csv

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["coordinate", "muscle", "mean_before_mm", "mean_after_mm",
                    "mean_change_mm", "mean_change_pct",
                    "peak_before_mm", "peak_after_mm", "peak_change_pct"])
        for coord, data in comparison.items():
            for m, (before, after) in sorted(data["muscles"].items()):
                mb, ma_ = float(np.nanmean(before)), float(np.nanmean(after))
                pb = float(np.nanmax(np.abs(before)))
                pa = float(np.nanmax(np.abs(after)))
                w.writerow([
                    coord, m, f"{mb:.3f}", f"{ma_:.3f}", f"{ma_ - mb:+.3f}",
                    f"{(ma_ / mb - 1) * 100:+.1f}" if abs(mb) > 1e-9 else "",
                    f"{pb:.3f}", f"{pa:.3f}",
                    f"{(pa / pb - 1) * 100:+.1f}" if pb > 1e-9 else "",
                ])
    return str(path)


def inspect_change(before_model, after_model, coordinates, *, n: int = 40,
                   full: bool = True, plots: bool = True, log=print) -> dict:
    """Verify and document a moment-arm edit. Never raises.

    ``full`` also runs the standard ``muscle_inspect`` pass on the modified
    model. That is the slower half (it sweeps every default coordinate, not
    just the ones edited) and the more thorough one: an edit made about hip
    adduction also moves that muscle's hip flexion and knee moment arms, and
    those are where an unnoticed discontinuity would sit.
    """
    before_model, after_model = Path(before_model), Path(after_model)
    coordinates = list(coordinates)
    info = {"ok": False, "figures": [], "csv": None, "discontinuous": [],
            "lost": [], "out_dir": None, "full": None, "reason": None}

    from bioscout.muscle_inspect.paths import validation_dir
    out_dir = Path(validation_dir(after_model, kind="moment_arm_change"))
    info["out_dir"] = str(out_dir)

    try:
        comp = compare_sweeps(before_model, after_model, coordinates, n=n)
    except Exception as exc:
        info["reason"] = (f"could not sweep for comparison "
                          f"({type(exc).__name__}: {exc}) — needs opensim")
        return info

    info["lost"] = sorted({m for d in comp.values() for m in d["lost"]})
    n_changed = sum(len(_changed(d["muscles"])) for d in comp.values())

    if plots:
        try:
            info["figures"] = plot_comparison(
                comp, out_dir, title_prefix=f"{after_model.stem}  ")
        except Exception as exc:
            log(f"[ma] comparison plots failed: {type(exc).__name__}: {exc}")
    try:
        info["csv"] = write_summary_csv(
            comp, out_dir / f"moment_arm_change_{after_model.stem}.csv")
    except Exception as exc:
        log(f"[ma] summary csv failed: {type(exc).__name__}: {exc}")

    # -- discontinuities on the edited coordinates ------------------------
    try:
        from .core import check_model
        chk = check_model(after_model, coordinates=coordinates, n=n)
        info["discontinuous"] = chk["discontinuous"]
    except Exception as exc:
        log(f"[ma] discontinuity check failed: {type(exc).__name__}: {exc}")

    log(f"[ma] inspect: {n_changed} muscle-coordinate curve(s) moved; "
        f"{len(info['figures'])} figure(s) in "
        f"{'/'.join(out_dir.parts[-3:])}")
    if info["csv"]:
        log(f"[ma] inspect: {Path(info['csv']).name}")
    if info["lost"]:
        log(f"[ma] inspect: WARNING these muscles no longer span the coordinate "
            f"after the edit: {', '.join(info['lost'])}")
    if info["discontinuous"]:
        log(f"[ma] inspect: WARNING discontinuous: "
            f"{', '.join(info['discontinuous'])}")
    else:
        log("[ma] inspect: no discontinuity on the edited coordinates.")

    # -- the full pass ----------------------------------------------------
    if full:
        log("[ma] inspect: running the full muscle_inspect pass on the modified "
            "model (all default coordinates) ...")
        cwd = os.getcwd()
        try:
            from bioscout.tps_personalise.bioscout_adapter import inspect_model
            info["full"] = inspect_model(after_model, make_plots=plots)
        except Exception as exc:
            info["full"] = {"ok": False,
                            "reason": f"{type(exc).__name__}: {exc}"}
        finally:
            os.chdir(cwd)
        f = info["full"] or {}
        if f.get("ok"):
            log(f"[ma] inspect: full pass wrote {Path(f['figures']).name}/ "
                f"and {Path(f['corrected']).name}")
        else:
            log(f"[ma] inspect: full pass did not run — {f.get('reason')}")

    info["ok"] = True
    return info
