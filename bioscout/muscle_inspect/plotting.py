"""Plot moment-arm / muscle-length sweeps, before vs after correction.

No OpenSim dependency -- operates on the CoordinateSweep objects from
moment_arms.compute_sweeps. Optionally overlays literature moment-arm bands
(cm->mm) on the moment-arm grids.
"""
from __future__ import annotations

import math
import os
from typing import Optional

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .discontinuity import detect_discontinuities  # noqa: E402


def _grid(n: int):
    cols = int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / cols))
    return rows, cols


def _series(sweep, quantity: str, muscle: str):
    return (sweep.moment_arms if quantity == "moment_arm" else sweep.lengths)[muscle]


def plot_coordinate(coord_name, before, after, quantity="moment_arm", outdir=".",
                    mark_discontinuities=True, literature=None):
    """Plot one figure (grid of muscles) for a single coordinate. Returns file path.

    `literature` (moment_arm only): {muscle: [(label, color, ang_deg, mean_mm, sd_mm)]}.
    """
    if before is None and after is None:
        return None
    ref = after if after is not None else before
    muscles = sorted(ref.moment_arms.keys())
    if not muscles:
        return None
    lit = literature or {}

    rows, cols = _grid(len(muscles))
    fig, axes = plt.subplots(rows, cols, figsize=(3.2 * cols, 2.4 * rows), squeeze=False)
    ylabel = "Moment arm (mm)" if quantity == "moment_arm" else "Length (mm)"
    xlabel = f"{coord_name} (deg)" if ref.unit == "rad" else f"{coord_name} (m)"
    scale = 1000.0

    for idx, muscle in enumerate(muscles):
        ax = axes[idx // cols][idx % cols]
        # literature bands (moment arm only)
        if quantity == "moment_arm" and muscle in lit:
            for label, color, ang, mean_mm, sd_mm in lit[muscle]:
                ax.plot(ang, mean_mm, color=color, lw=1.3, label=label, zorder=0)
                if np.any(np.asarray(sd_mm) > 0):
                    ax.fill_between(ang, mean_mm - sd_mm, mean_mm + sd_mm,
                                    color=color, alpha=0.2, zorder=0)
        if before is not None and muscle in before.moment_arms:
            y0 = _series(before, quantity, muscle) * scale
            ax.plot(before.angles_deg, y0, color="#bbbbbb", lw=1.4, label="before", zorder=1)
        if after is not None and muscle in after.moment_arms:
            y1 = _series(after, quantity, muscle) * scale
            ax.plot(after.angles_deg, y1, color="#1f77b4", lw=1.6,
                    linestyle="--", dashes=(5, 3), label="after", zorder=2)
            if mark_discontinuities:
                for j in detect_discontinuities(_series(after, quantity, muscle)):
                    ax.plot(after.angles_deg[j], y1[j], "rx", ms=7, zorder=3)
        if mark_discontinuities and before is not None and muscle in before.moment_arms:
            for j in detect_discontinuities(_series(before, quantity, muscle)):
                ax.plot(before.angles_deg[j], _series(before, quantity, muscle)[j] * scale,
                        "o", mfc="none", mec="#d62728", ms=8, zorder=2)
        ax.set_title(muscle, fontsize=8)
        ax.tick_params(labelsize=7)
        ax.grid(True, alpha=0.25)

    for idx in range(len(muscles), rows * cols):
        axes[idx // cols][idx % cols].axis("off")

    # combined legend across all axes (dedup by label)
    handles, labels = [], []
    for row_ax in axes:
        for ax in row_ax:
            for h, l in zip(*ax.get_legend_handles_labels()):
                if l not in labels:
                    handles.append(h); labels.append(l)
    if handles:
        fig.legend(handles, labels, loc="upper right", fontsize=8)
    title = ylabel.split(" (")[0]
    extra = "; coloured=literature" if (quantity == "moment_arm" and lit) else ""
    fig.suptitle(f"{title} vs {coord_name}  (grey=before, blue=after; red=discontinuity{extra})",
                 fontsize=11)
    fig.supxlabel(xlabel, fontsize=10)
    fig.supylabel(ylabel, fontsize=10)
    fig.tight_layout(rect=[0.01, 0.01, 1, 0.97])

    os.makedirs(outdir, exist_ok=True)
    tag = "momentarm" if quantity == "moment_arm" else "length"
    path = os.path.join(outdir, f"{tag}_{coord_name}.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_comparison(before_sweeps, after_sweeps, outdir=".",
                    quantities=("moment_arm", "length"), mark_discontinuities=True,
                    literature=None):
    """Plot every coordinate present in either sweep dict. Returns saved file paths.

    `literature`: {coordinate_name: {muscle: [(label, color, ang, mean_mm, sd_mm)]}}.
    """
    coords = sorted(set(before_sweeps) | set(after_sweeps))
    lit = literature or {}
    saved = []
    for c in coords:
        for q in quantities:
            p = plot_coordinate(c, before_sweeps.get(c), after_sweeps.get(c),
                                quantity=q, outdir=outdir,
                                mark_discontinuities=mark_discontinuities,
                                literature=lit.get(c) if q == "moment_arm" else None)
            if p:
                saved.append(p)
    return saved
