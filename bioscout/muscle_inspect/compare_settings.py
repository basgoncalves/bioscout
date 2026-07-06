"""compare_settings.py

Run the moment-arm inspection pipeline across RANGES of each setting -- one
setting at a time, others held at baseline -- and write figures into per-setting
subfolders, so you can see how each setting affects DISCONTINUITY DETECTION (and,
for fix settings, whether the jumps actually get removed).

Edit CONFIG_BASE (baseline) and SETTINGS_TO_TRY (the ranges), then run:
    python compare_settings.py

Output layout (under CONFIG_BASE["out"]):
    <setting>/<setting>=<value>/          per-value figures (red x = detected)
    <setting>/_summary_<quantity>_<coord>.png   ALL values OVERLAID per coordinate
    <setting>/_muscles_flagged.png        # flagged muscles vs the setting's value
    _overview.txt                         text summary incl. RMSD% vs the original

RMSD% = root-mean-square difference between this iteration's curves and the
ORIGINAL (baseline before) curves, as a % of each curve's range, averaged over
muscles. ~0 means the iteration barely changed the model; large means big edits.
(Detection settings don't change the curves, so their RMSD% is 0; 'n' changes
the sample count so it's reported as n/a.)

COST: detection settings (min_jump_mm, k_d2, k_local, k_global) are CHEAP -- they
reuse one baseline sweep. 'n' re-sweeps per value. Fix settings
(max_displacement_mm, margin_base_mm, margin_frac, n_pose) run a full fix +
re-sweep per value, so keep those ranges short. Subset `coords` to go faster.
"""
from __future__ import annotations

import math
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .logutil import setup_logging, timed, LOG  # noqa: E402
from . import moment_arms, radius_reduce  # noqa: E402
from .discontinuity import detect_discontinuities  # noqa: E402


# =====================================================================
#  BASELINE  --  every run uses these except the one setting being varied
# =====================================================================
CONFIG_BASE = {
    "model": "scaled.osim",
    "out":   "compare_settings",
    # Subset coords to keep this fast; None = full lower-limb set.
    "coords": ["hip_adduction_l", "knee_angle_l"],
    "muscle_filter": None,
    "n": 80,
    # fix knobs
    "max_displacement_mm": 5.0,
    "margin_base_mm": 2.0,
    "margin_frac": 0.5,
    "max_penetration_mm": 5.0,
    "n_pose": 30,
    "rr_n": 40,
    "radius_reduction": True,
    # detection knobs
    "min_jump_mm": 1.0,
    "k_d2": 7.0,
    "k_local": 3.0,
    "k_global": 8.0,
}

# =====================================================================
#  RANGES TO TRY  --  one setting at a time; comment out any you don't want
# =====================================================================
SETTINGS_TO_TRY = {
    # --- detection (cheap: reuse one baseline sweep) ---
    "min_jump_mm": [0.1, 0.25, 0.5, 1.0, 2.0],
    "k_global":    [2.0, 4.0, 6.0, 8.0, 12.0],
    "k_d2":        [3.0, 5.0, 7.0, 10.0],
    "k_local":     [1.5, 2.0, 3.0, 5.0],
    # --- sweep resolution (re-sweep per value) ---
    "n":           [40, 80, 160],
    # --- fix settings (re-fix + re-sweep per value: slower) ---
    "max_displacement_mm": [5.0, 10.0, 20.0],
    "margin_base_mm":      [1.0, 2.0, 5.0],
    "n_pose":              [20, 40],
}

DETECTION_ONLY = {"min_jump_mm", "k_d2", "k_local", "k_global"}
RESWEEP = {"n"}
# anything else in SETTINGS_TO_TRY is treated as a fix setting


# --------------------------------------------------------------------- helpers
def _detect_kwargs(cfg) -> dict:
    return dict(min_jump_m=cfg["min_jump_mm"] / 1000.0, k_d2=cfg["k_d2"],
                k_local=cfg["k_local"], k_global=cfg["k_global"])


def _count_flagged(sweeps, dk):
    """(#muscles flagged, #total flagged points) across both quantities."""
    muscles, pts = set(), 0
    for sw in sweeps.values():
        for series in (sw.moment_arms, sw.lengths):
            for m, arr in series.items():
                idx = detect_discontinuities(arr, **dk)
                if idx:
                    muscles.add(m)
                    pts += len(idx)
    return len(muscles), pts


def _rmsd_vs_before(before_base, used):
    """(mean RMSD%, max RMSD%) of `used` vs baseline, over comparable series.

    Returns (None, None) if nothing is comparable (e.g. different sample count).
    """
    vals = []
    for cname, sw in used.items():
        if cname not in before_base:
            continue
        b = before_base[cname]
        for quantity in ("moment_arms", "lengths"):
            ua = getattr(sw, quantity)
            ba = getattr(b, quantity)
            for m, arr in ua.items():
                if m not in ba:
                    continue
                o = ba[m]
                if np.shape(o) != np.shape(arr):
                    continue
                rng = np.nanmax(o) - np.nanmin(o)
                if not np.isfinite(rng) or rng <= 0:
                    continue
                rmsd = np.sqrt(np.nanmean((arr - o) ** 2))
                vals.append(100.0 * rmsd / rng)
    if not vals:
        return None, None
    return float(np.mean(vals)), float(np.max(vals))


def _grid(n):
    cols = int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / cols))
    return rows, cols


def _series_of(sw, quantity):
    return sw.moment_arms if quantity == "moment_arm" else sw.lengths


def _render(sweeps, outdir, quantity, dk):
    """Per-value figure: each muscle curve with red x at detected jumps."""
    os.makedirs(outdir, exist_ok=True)
    for cname, sw in sweeps.items():
        series = _series_of(sw, quantity)
        muscles = sorted(series)
        if not muscles:
            continue
        rows, cols = _grid(len(muscles))
        fig, axes = plt.subplots(rows, cols, figsize=(3.2 * cols, 2.4 * rows), squeeze=False)
        for i, m in enumerate(muscles):
            ax = axes[i // cols][i % cols]
            y = series[m] * 1000.0
            ax.plot(sw.angles_deg, y, color="#1f77b4", lw=1.4)
            for j in detect_discontinuities(series[m], **dk):
                ax.plot(sw.angles_deg[j], y[j], "rx", ms=7)
            ax.set_title(m, fontsize=8)
            ax.tick_params(labelsize=7)
            ax.grid(True, alpha=0.25)
        for i in range(len(muscles), rows * cols):
            axes[i // cols][i % cols].axis("off")
        ylab = "Moment arm (mm)" if quantity == "moment_arm" else "Length (mm)"
        fig.suptitle(f"{ylab.split(' (')[0]} vs {cname}  (red x = detected discontinuity)",
                     fontsize=11)
        fig.supxlabel(f"{cname} (deg)")
        fig.supylabel(ylab)
        fig.tight_layout(rect=[0.01, 0.01, 1, 0.97])
        tag = "momentarm" if quantity == "moment_arm" else "length"
        fig.savefig(os.path.join(outdir, f"{tag}_{cname}.png"), dpi=110)
        plt.close(fig)


def _overlay(runs, sdir, quantity):
    """One figure per coordinate overlaying ALL values (curve + markers per value)."""
    coords = []
    for _, sw, _ in runs:
        for c in sw:
            if c not in coords:
                coords.append(c)
    colors = plt.cm.viridis(np.linspace(0, 1, max(len(runs), 1)))
    tag = "momentarm" if quantity == "moment_arm" else "length"
    ylab = "Moment arm (mm)" if quantity == "moment_arm" else "Length (mm)"

    for cname in coords:
        muscles = set()
        for _, sw, _ in runs:
            if cname in sw:
                muscles |= set(_series_of(sw[cname], quantity).keys())
        muscles = sorted(muscles)
        if not muscles:
            continue
        rows, cols = _grid(len(muscles))
        fig, axes = plt.subplots(rows, cols, figsize=(3.2 * cols, 2.4 * rows), squeeze=False)
        for i, m in enumerate(muscles):
            ax = axes[i // cols][i % cols]
            for (label, sw, dk), col in zip(runs, colors):
                if cname not in sw:
                    continue
                series = _series_of(sw[cname], quantity)
                if m not in series:
                    continue
                y = series[m] * 1000.0
                ax.plot(sw[cname].angles_deg, y, color=col, lw=1.1, label=label)
                for j in detect_discontinuities(series[m], **dk):
                    ax.plot(sw[cname].angles_deg[j], y[j], "x", color=col, ms=6)
            ax.set_title(m, fontsize=8)
            ax.tick_params(labelsize=7)
            ax.grid(True, alpha=0.25)
        for i in range(len(muscles), rows * cols):
            axes[i // cols][i % cols].axis("off")
        h, l = axes[0][0].get_legend_handles_labels()
        if h:
            fig.legend(h, l, loc="upper right", fontsize=8)
        fig.suptitle(f"{ylab.split(' (')[0]} vs {cname}  (all values overlaid; x = detected)",
                     fontsize=11)
        fig.supxlabel(f"{cname} (deg)")
        fig.supylabel(ylab)
        fig.tight_layout(rect=[0.01, 0.01, 1, 0.97])
        fig.savefig(os.path.join(sdir, f"_summary_{tag}_{cname}.png"), dpi=120)
        plt.close(fig)


def _muscles_flagged_plot(sdir, setting, xs, ys, is_fix):
    try:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot([str(x) for x in xs], ys, "o-")
        ax.set_xlabel(setting)
        ax.set_ylabel("muscles still discontinuous after fix" if is_fix
                      else "muscles flagged as discontinuous")
        ax.set_title(f"Effect of {setting}")
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(sdir, "_muscles_flagged.png"), dpi=120)
        plt.close(fig)
    except Exception as exc:  # pragma: no cover
        LOG.warning("muscles_flagged plot failed for %s: %s", setting, exc)


# --------------------------------------------------------------------- main
def main():
    log = setup_logging()
    here = os.getcwd()
    base = dict(CONFIG_BASE)
    model = base["model"] if os.path.isabs(base["model"]) else os.path.join(here, base["model"])
    root = base["out"] if os.path.isabs(base["out"]) else os.path.join(here, base["out"])
    os.makedirs(root, exist_ok=True)
    overview = ["setting               value   flagged_muscles  points   rmsd%_mean  rmsd%_max"]

    with timed("baseline before-sweeps"):
        before_base = moment_arms.compute_sweeps(
            model, coordinate_names=base["coords"],
            muscle_filter=base["muscle_filter"], n=base["n"])

    for setting, values in SETTINGS_TO_TRY.items():
        is_fix = setting not in (DETECTION_ONLY | RESWEEP)
        sdir = os.path.join(root, setting)
        os.makedirs(sdir, exist_ok=True)
        log.info("=" * 64)
        log.info("SETTING %s over %s%s", setting, values, "  (fix: slow)" if is_fix else "")
        log.info("=" * 64)
        xs, ys, runs = [], [], []

        for v in values:
            cfg = dict(base)
            cfg[setting] = v
            label = f"{setting}={v}"
            vdir = os.path.join(sdir, label.replace(".", "p"))
            os.makedirs(vdir, exist_ok=True)
            dk = _detect_kwargs(cfg)

            if setting in DETECTION_ONLY:
                used = before_base
                _render(used, vdir, "moment_arm", dk)
                _render(used, vdir, "length", dk)
                nm, npts = _count_flagged(used, dk)

            elif setting in RESWEEP:
                with timed(f"sweep n={v}"):
                    used = moment_arms.compute_sweeps(
                        model, coordinate_names=base["coords"],
                        muscle_filter=base["muscle_filter"], n=v)
                _render(used, vdir, "moment_arm", dk)
                _render(used, vdir, "length", dk)
                nm, npts = _count_flagged(used, dk)

            else:  # fix setting: run the fix, re-sweep, plot before/after
                from . import plotting
                corrected = os.path.join(vdir, "model_modWO.osim")
                suspects = moment_arms.discontinuous_muscles(before_base, **dk)
                with timed(f"fix {label}"):
                    radius_reduce.fix_with_radius_reduction(
                        model, corrected, muscle_filter=base["muscle_filter"],
                        max_penetration_mm=cfg["max_penetration_mm"],
                        max_displacement_mm=cfg["max_displacement_mm"],
                        margin_base_m=cfg["margin_base_mm"] / 1000.0,
                        margin_frac=cfg["margin_frac"], cross_body=True,
                        coordinate_names=base["coords"], suspect_muscles=suspects,
                        n_pose=cfg["n_pose"], radius_reduction=cfg["radius_reduction"],
                        detect_kwargs=dk, rr_n=cfg["rr_n"])
                with timed(f"after-sweep {label}"):
                    used = moment_arms.compute_sweeps(
                        corrected, coordinate_names=base["coords"],
                        muscle_filter=base["muscle_filter"], n=base["n"])
                plotting.plot_comparison(before_base, used, outdir=vdir)
                nm, npts = _count_flagged(used, dk)  # remaining after the fix

            rmsd_mean, rmsd_max = _rmsd_vs_before(before_base, used)
            rm = "n/a" if rmsd_mean is None else f"{rmsd_mean:8.3f}"
            rx = "n/a" if rmsd_max is None else f"{rmsd_max:8.3f}"
            xs.append(v)
            ys.append(nm)
            runs.append((label, used, dk))
            log.info("  %-22s -> %d muscles flagged (%d points)  rmsd%%: mean=%s max=%s",
                     label, nm, npts, rm, rx)
            overview.append(f"{setting:20s} {str(v):>7}  {nm:>15}  {npts:>6}  "
                            f"{rm:>10}  {rx:>9}")

        _overlay(runs, sdir, "moment_arm")
        _overlay(runs, sdir, "length")
        _muscles_flagged_plot(sdir, setting, xs, ys, is_fix)

    with open(os.path.join(root, "_overview.txt"), "w") as f:
        f.write("\n".join(overview) + "\n")
    log.info("Done. Results in %s", root)


if __name__ == "__main__":
    main()
