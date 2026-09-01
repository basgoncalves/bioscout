"""Compare SEVERAL models against each other and against the literature.

    python -m bioscout.muscle_inspect compare-models \\
        --models a.osim b.osim c.osim --out report/

Everything else in this package inspects ONE model and writes one folder next
to it. That is the wrong shape for the question people actually ask -- "is this
model better than the one we published?" -- which needs every curve on the same
axes, scored against the same studies, in one place.

WHAT IT WRITES

    discontinuity.csv                 model x muscle x coordinate, flagged or not
    moment_arm_curves.csv             long format: coordinate, model, muscle,
                                      angle_deg, moment_arm_mm, source
    validation_rmse.csv               model x muscle x study: rmse_cm, pct_within_sd
    fig01_<coord>_vs_literature.png   one coordinate, in detail
    fig02_moment_arms_all_coordinates.png   every coordinate, models overlaid
    fig03_validate_<coord>.png        per moment DOF: panels of muscle x study

BOTH HALVES, ON PURPOSE
    The discontinuity screen and the literature comparison answer different
    questions and disagree usefully. A path can be perfectly smooth and 20 mm
    from every published curve, or sit inside the SD band and still step 6 mm
    between two frames. Reporting one without the other is how a model gets
    called "validated" on the half that happened to pass.

SIGNS AND UNITS
    The corpus is SIGNED and in CENTIMETRES, using the models' own convention.
    Curves are plotted signed with a zero line, because a moment arm crossing
    zero is a muscle reversing its action -- the single most important thing a
    plot of this kind can show, and invisible if magnitudes are used.
"""
from __future__ import annotations

import csv
import os
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                  # noqa: E402

from .logutil import LOG                                         # noqa: E402
from .paths import resolve_literature_csv                        # noqa: E402
# muscle_length_validation, NOT validation.py. `validate_against_literature`
# calls it "up-to-date loader/colours/knee-flip" and it is the difference
# between a right and a wrong figure:
#   * its `_sweep_moment_arm` applies `canonical_flip` to BOTH the angle axis
#     and the moment-arm sign, so a knee-flexion-POSITIVE model (Catelli,
#     Rajagopal) is drawn in the same frame as a knee-flexion-NEGATIVE one
#     (GPK, Lernagopal) and as the literature. Without it those two families
#     are mirror images of each other and nobody can read the panel.
#   * its SIGN carries `knee_angle: -1.0, ankle_angle: -1.0` (OpenSim reports a
#     flexor/plantarflexor moment arm as negative). validation.py has every
#     entry at 1.0 and no ankle key at all, which is why the first version of
#     this module drew the ankle upside down against the literature.
from .muscle_length_validation import (DOF_ORDER, MUSCLE_MAP,     # noqa: E402
                                       SIGN, _sweep_fibre, _sweep_moment_arm,
                                       grid_overlays, load_literature,
                                       study_color)

#: Colour-blind-safe; index by position so any number of models works.
MODEL_COLORS = ["#0072B2", "#D55E00", "#2a9d5c", "#785EF0", "#CC79A7",
                "#E69F00", "#56B4E9", "#000000"]

#: Same 12 as moment_arms.DEFAULT_COORDINATES — both limbs.
_DEFAULT_COORDS = ["hip_flexion_r", "hip_adduction_r", "hip_rotation_r",
                   "knee_angle_r", "ankle_angle_r", "subtalar_angle_r",
                   "hip_flexion_l", "hip_adduction_l", "hip_rotation_l",
                   "knee_angle_l", "ankle_angle_l", "subtalar_angle_l"]


#: One hue per model FAMILY, matching the manuscript's figures exactly
#: (results.py PlotSettings.Effects.generic_color). A reader who has just seen
#: Figure 6 should not have to re-learn the colours to read the supplement.
#: Matched as a lowercased SUBSTRING of the file stem, so GPK_v3, GPK_v4_016 and
#: GPK_v4_016_tps_Athlete_03 are all "the GPK model" and share one colour.
FAMILY_COLOR = {"catelli": "#009E73",      # bluish green
                "cateli": "#009E73",       # the spelling session.yaml uses
                "lernagopal": "#0072B2",   # blue
                "gpk": "#D55E00"}          # vermillion

#: Variants WITHIN a family differ only by line style. Solid is the plain
#: generic and dashed is its TPS/MRI warp -- the same convention the manuscript
#: uses for every generic-vs-MRI pair -- because sorting puts non-TPS first.
VARIANT_LS = ["-", "--", ":", "-.", (0, (3, 1, 1, 1))]


def _family(label):
    """The family a model file stem belongs to, or None."""
    s = str(label).lower()
    for k in FAMILY_COLOR:
        if k in s:
            return k
    return None


def model_styles(labels):
    """{label: (colour, linestyle)} — one hue per family, style within it.

    A family the map does not know (Hagen, say) keeps the old behaviour: a
    colour off MODEL_COLORS, solid. The named families' hues are removed from
    that pool first, so an unnamed model can never come out the same green as
    Catelli in one figure and something else in the next.
    """
    # "#2a9d5c" is dropped as well as the family hues themselves: it is a
    # second green, and an unnamed model in Catelli's green is worse than an
    # unnamed model in purple.
    taken = {str(c).lower() for c in FAMILY_COLOR.values()} | {"#2a9d5c"}
    spare = [c for c in MODEL_COLORS if str(c).lower() not in taken] or MODEL_COLORS
    # non-TPS first inside a family, so plain gets "-" and the warp gets "--"
    order = sorted(labels, key=lambda l: ("_tps_" in str(l).lower(), str(l)))
    out, seen, k = {}, {}, 0
    for lab in order:
        fam = _family(lab)
        if fam is None:
            out[lab] = (spare[k % len(spare)], "-")
            k += 1
            continue
        i = seen.get(fam, 0)
        seen[fam] = i + 1
        out[lab] = (FAMILY_COLOR[fam], VARIANT_LS[i % len(VARIANT_LS)])
    return out


def _label(path):
    return os.path.splitext(os.path.basename(path))[0]


# ---------------------------------------------------------------- discontinuity
def screen_discontinuity(models, coords=None, n=80, out_dir=None, detect=None):
    """{label: set(flagged muscles)} plus a csv. The original screen, per model.

    `detect` is forwarded to `detect_discontinuities` (min_jump_m, k_d2,
    k_local, k_global, win). Exposed because the default 1 mm floor is a
    judgement about what counts as a jump, not a constant of nature -- a
    generic and a scaled model do not deserve the same threshold.
    """
    from .moment_arms import compute_sweeps, discontinuous_muscles
    rows = [("model", "coordinate", "muscle", "flagged")]
    flagged = {}
    for path in models:
        lab = _label(path)
        sweeps = compute_sweeps(path, coordinate_names=coords, n=n)
        bad = discontinuous_muscles(sweeps, **(detect or {}))
        flagged[lab] = bad
        for cname, sw in sweeps.items():
            for mus in sw.moment_arms:
                rows.append((lab, cname, mus, int(mus in bad)))
        LOG.info("%-28s %d discontinuous: %s", lab, len(bad),
                 ", ".join(sorted(bad)) or "none")
    if out_dir:
        with open(os.path.join(out_dir, "discontinuity.csv"), "w", newline="") as fh:
            csv.writer(fh).writerows(rows)
    return flagged


# ---------------------------------------------------------------- literature
def _model_curves(models, lit, side, n):
    """{(muscle, mdof, xdof): {label: (deg, ma_cm)}} for every model."""
    from .moment_arms import MomentArmModel
    out = defaultdict(dict)
    for path in models:
        lab = _label(path)
        mam = MomentArmModel(path)
        present = {mam.coord_set.get(i).getName()
                   for i in range(mam.coord_set.getSize())}
        have = set(mam.all_muscle_names())
        for (muscle, mdof, xdof), studies in lit.items():
            x_coord, m_coord = xdof + side, mdof + side
            comps = [m + side for m in MUSCLE_MAP.get(muscle, [muscle])
                     if (m + side) in have]
            if x_coord not in present or m_coord not in present or not comps:
                continue
            angs = [a for st in studies.values() for (a, _, _) in st]
            deg, ma_m = _sweep_moment_arm(mam, x_coord, m_coord, comps,
                                          min(angs), max(angs), n)
            out[(muscle, mdof, xdof)][lab] = (deg, SIGN.get(mdof, 1.0) * ma_m * 100.0)
    return out


def _score(deg, ma_cm, pts):
    """(rmse_cm, fraction inside mean +- SD) over the study's own angles."""
    a = np.array([p[0] for p in pts], float)
    m = np.array([p[1] for p in pts], float)
    s = np.array([p[2] for p in pts], float)
    ok = (a >= np.nanmin(deg)) & (a <= np.nanmax(deg))
    if not ok.any():
        return None, None, 0
    v = np.interp(a[ok], deg, ma_cm)
    err = v - m[ok]
    within = np.abs(err) <= np.maximum(s[ok], 1e-9)
    return float(np.sqrt(np.mean(err ** 2))), float(within.mean()), int(ok.sum())


def _lit_band(ax, studies):
    """Literature as a shaded mean+-SD band per study, not dots.

    A study is a POPULATION, and a band says so; markers with error bars read
    as measurements at those exact angles and invite the eye to compare a model
    curve to five points rather than to a range.
    """
    import numpy as np
    for study, pts in sorted(studies.items()):
        a = np.array([p[0] for p in pts], float)
        m = np.array([p[1] for p in pts], float)
        sd = np.array([p[2] for p in pts], float)
        col = study_color(study)
        lab = study.split("[")[0].strip()
        if np.any(sd > 0):
            ax.fill_between(a, m - sd, m + sd, color=col, alpha=.20,
                            lw=0, zorder=2, label=lab)
            ax.plot(a, m, "-", color=col, lw=1.2, alpha=.9, zorder=3)
        else:
            ax.plot(a, m, "-", color=col, lw=1.6, alpha=.9, zorder=3, label=lab)


def _panel(ax, studies, curves, style):
    """`style` is the {label: (colour, linestyle)} map from model_styles().

    It is computed ONCE per report and passed in, not derived per panel: a
    per-panel map would renumber whenever a muscle happened to be missing from
    one model, and the same model would change colour between panels.
    """
    ax.axhline(0, color="0.2", lw=.8, zorder=1)
    _lit_band(ax, studies)
    for lab, (deg, ma) in sorted(curves.items()):
        col, ls = style.get(lab, (MODEL_COLORS[0], "-"))
        ax.plot(deg, ma, ls=ls, lw=2.0, color=col, label=lab, zorder=4)
    ax.grid(True, alpha=.3)
    ax.tick_params(labelsize=7)


# ------------------------------------------------- every muscle, per coordinate
def _grids(models, out_dir, coords, n, dpi, lit, kind="moment_arm"):
    """`momentarm_<coord>.png` / `fibrelength_<coord>.png` — ALL muscles.

    The literature figures only show the handful of muscles a study measured.
    This is the other half, and the one `muscle_inspect inspect` produces for a
    single model: every muscle that spans the coordinate, one panel each, all
    models overlaid. It is how you see that a muscle nobody has ever measured
    disagrees between two models.

    `canonical_flip` is applied here too. Without it a knee-flexion-positive
    model and a knee-flexion-negative one are mirror images and the grid is
    unreadable — the same bug that put the ankle upside down against the
    literature.
    """
    from .moment_arms import MomentArmModel, canonical_flip
    import numpy as np
    written = []
    per_model = {}
    for path in models:
        lab = _label(path)
        mam = MomentArmModel(path)
        present = {mam.coord_set.get(i).getName()
                   for i in range(mam.coord_set.getSize())}
        cs = [c for c in (coords or _DEFAULT_COORDS) if c in present]
        got = {}
        for cname in cs:
            names = mam.find_spanning_muscles(cname, mam.all_muscle_names())
            if not names:
                continue
            sw = mam.sweep(cname, names, n=n)
            xf = canonical_flip(mam.coord_set.get(cname))
            mf = xf if kind == "moment_arm" else 1.0
            series = sw.moment_arms if kind == "moment_arm" else sw.lengths
            got[cname] = (np.asarray(sw.angles_deg) * xf,
                          {m: np.asarray(v) * 1000.0 * mf for m, v in series.items()})
        per_model[lab] = got

    sty = model_styles(list(per_model))
    allc = sorted({c for g in per_model.values() for c in g})
    for cname in allc:
        muscles = sorted({m for g in per_model.values()
                          for m in g.get(cname, (None, {}))[1]})
        if not muscles:
            continue
        bands = grid_overlays(lit, cname, muscles) if kind == "moment_arm" else {}
        ncol = min(6, len(muscles))
        nrow = int(np.ceil(len(muscles) / ncol))
        fig, axes = plt.subplots(nrow, ncol, figsize=(2.7 * ncol, 2.1 * nrow),
                                 squeeze=False, sharex=True)
        for i, mus in enumerate(muscles):
            ax = axes[i // ncol][i % ncol]
            ax.axhline(0, color="0.2", lw=.7, zorder=1)
            for k, (lab, g) in enumerate(sorted(per_model.items())):
                if cname not in g or mus not in g[cname][1]:
                    continue
                x, ser = g[cname]
                col, ls = sty.get(lab, (MODEL_COLORS[k % len(MODEL_COLORS)], "-"))
                ax.plot(x, ser[mus], ls=ls, lw=1.5, zorder=4, color=col,
                        label=lab if i == 0 else None)
            for (blab, bcol, bang, bmean, bsd) in bands.get(mus, []):
                bang = np.asarray(bang, float)
                bmean = np.asarray(bmean, float); bsd = np.asarray(bsd, float)
                ax.fill_between(bang, bmean - bsd, bmean + bsd, color=bcol,
                                alpha=.20, lw=0, zorder=2,
                                label=blab if i == 0 else None)
            ax.set_title(mus, fontsize=7.5)
            ax.tick_params(labelsize=6)
            ax.grid(True, alpha=.25)
            if i % ncol == 0:
                ax.set_ylabel("MA (mm)" if kind == "moment_arm"
                              else "fibre length (mm)", fontsize=7)
        for j in range(len(muscles), nrow * ncol):
            axes[j // ncol][j % ncol].axis("off")
        h, l = axes[0][0].get_legend_handles_labels()
        fig.legend(h, l, loc="upper left", frameon=False, fontsize=7.5, ncol=4,
                   bbox_to_anchor=(0.005, 0.998))
        what = "moment arms" if kind == "moment_arm" else "fibre lengths"
        fig.suptitle(f"{cname} — {what}, {len(muscles)} muscle(s), "
                     f"{len(per_model)} model(s)", fontsize=10)
        fig.tight_layout(rect=(0, 0, 1, 0.95))
        stem = "momentarm" if kind == "moment_arm" else "fibrelength"
        fp = os.path.join(out_dir, f"{stem}_{cname}.png")
        fig.savefig(fp, dpi=dpi); plt.close(fig)
        written.append(os.path.basename(fp))
    return written


def compare_models(models, out_dir, literature_csv=None, side="_r", n=60,
                   coords=None, focus="knee_angle", discontinuity=True,
                   detect=None, dpi=110, grids=True, fibre=True):
    """The whole report. Returns the list of files written."""
    os.makedirs(out_dir, exist_ok=True)
    models = [os.path.abspath(m) for m in models]
    labels = [_label(m) for m in models]
    if len(set(labels)) != len(labels):
        raise ValueError(f"model file stems must be unique, got {labels}")
    written = []

    if discontinuity:
        screen_discontinuity(models, coords=coords, n=n, out_dir=out_dir,
                             detect=detect)
        written.append("discontinuity.csv")

    lit = load_literature(resolve_literature_csv(literature_csv))
    if not lit:
        LOG.warning("no literature rows — figures skipped")
        return written
    curves = _model_curves(models, lit, side, n)
    STY = model_styles(labels)   # once, for every figure below

    # ---- long-format curves + scores
    crows = [("coordinate", "model", "muscle", "angle_deg", "moment_arm_mm", "source")]
    srows = [("model", "muscle", "moment_dof", "x_dof", "study",
              "rmse_cm", "pct_within_sd", "n_points")]
    for (muscle, mdof, xdof), per in curves.items():
        for lab, (deg, ma) in per.items():
            for d, v in zip(deg, ma):
                crows.append((mdof, lab, muscle, f"{d:.3f}", f"{v * 10:.4f}", "model"))
            for study, pts in lit[(muscle, mdof, xdof)].items():
                r, w, k = _score(deg, ma, pts)
                if k:
                    srows.append((lab, muscle, mdof, xdof, study,
                                  f"{r:.4f}", f"{w:.3f}", k))
    for name, rows in (("moment_arm_curves.csv", crows),
                       ("validation_rmse.csv", srows)):
        with open(os.path.join(out_dir, name), "w", newline="") as fh:
            csv.writer(fh).writerows(rows)
        written.append(name)

    by_mdof = defaultdict(list)
    for key in curves:
        by_mdof[key[1]].append(key)
    order = ([d for d in DOF_ORDER if d in by_mdof]
             + sorted(d for d in by_mdof if d not in DOF_ORDER))

    # ---- fig03: one figure per moment DOF
    for mdof in order:
        panels = sorted(by_mdof[mdof], key=lambda k: (k[2], k[0]))
        ncol = min(4, len(panels))
        nrow = int(np.ceil(len(panels) / ncol))
        fig, axes = plt.subplots(nrow, ncol, figsize=(4.0 * ncol, 3.1 * nrow),
                                 squeeze=False)
        for i, key in enumerate(panels):
            ax = axes[i // ncol][i % ncol]
            _panel(ax, lit[key], curves[key], STY)
            ax.set_title(key[0], fontsize=9)
            ax.set_xlabel(f"{key[2]} (deg)", fontsize=8)
            if i % ncol == 0:
                ax.set_ylabel(f"{mdof} MA (cm)", fontsize=9)
        for j in range(len(panels), nrow * ncol):
            axes[j // ncol][j % ncol].axis("off")
        h, l = axes[0][0].get_legend_handles_labels()
        fig.legend(h, l, loc="upper left", frameon=False, fontsize=8, ncol=2,
                   bbox_to_anchor=(0.005, 0.995))
        fig.suptitle(f"{mdof} moment arms — {len(models)} models vs literature",
                     fontsize=11)
        fig.tight_layout(rect=(0, 0, 1, 0.93))
        p = os.path.join(out_dir, f"fig03_validate_{mdof}.png")
        fig.savefig(p, dpi=dpi); plt.close(fig)
        written.append(os.path.basename(p))

    # ---- fig02: every coordinate on one page
    allk = [k for d in order for k in sorted(by_mdof[d])]
    ncol = min(4, len(allk)) or 1
    nrow = int(np.ceil(len(allk) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.8 * ncol, 2.9 * nrow),
                             squeeze=False)
    for i, key in enumerate(allk):
        ax = axes[i // ncol][i % ncol]
        _panel(ax, lit[key], curves[key], STY)
        ax.set_title(f"{key[0]} — {key[1]}", fontsize=8)
    for j in range(len(allk), nrow * ncol):
        axes[j // ncol][j % ncol].axis("off")
    h, l = axes[0][0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper left", frameon=False, fontsize=8, ncol=3,
               bbox_to_anchor=(0.005, 0.995))
    fig.suptitle("Moment arms, every coordinate", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    p = os.path.join(out_dir, "fig02_moment_arms_all_coordinates.png")
    fig.savefig(p, dpi=dpi); plt.close(fig)
    written.append(os.path.basename(p))

    # ---- fig01: one coordinate, large
    fk = [k for k in curves if k[1] == focus]
    if fk:
        ncol = min(3, len(fk))
        nrow = int(np.ceil(len(fk) / ncol))
        fig, axes = plt.subplots(nrow, ncol, figsize=(5.0 * ncol, 3.8 * nrow),
                                 squeeze=False)
        for i, key in enumerate(sorted(fk)):
            ax = axes[i // ncol][i % ncol]
            _panel(ax, lit[key], curves[key], STY)
            ax.set_title(key[0], fontsize=10)
            ax.set_xlabel(f"{key[2]} (deg)", fontsize=9)
            if i % ncol == 0:
                ax.set_ylabel(f"{focus} MA (cm)", fontsize=10)
        for j in range(len(fk), nrow * ncol):
            axes[j // ncol][j % ncol].axis("off")
        h, l = axes[0][0].get_legend_handles_labels()
        fig.legend(h, l, loc="upper left", frameon=False, fontsize=9, ncol=2,
                   bbox_to_anchor=(0.005, 0.995))
        fig.suptitle(f"{focus} moment arm vs literature", fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, 0.92))
        p = os.path.join(out_dir, f"fig01_{focus}_vs_literature.png")
        fig.savefig(p, dpi=dpi); plt.close(fig)
        written.append(os.path.basename(p))

    if grids:
        written += _grids(models, out_dir, coords, n, dpi, lit, "moment_arm")
    if fibre:
        written += _grids(models, out_dir, coords, n, dpi, lit, "fibre_length")

    LOG.info("wrote %d file(s) to %s", len(written), out_dir)
    return written


def main(argv=None):
    import argparse
    import logging
    from .logutil import setup_logging
    p = argparse.ArgumentParser(prog="muscle_inspect compare-models",
                                description=__doc__.splitlines()[0])
    p.add_argument("--models", nargs="+", required=True)
    p.add_argument("--out", default="model_comparison")
    p.add_argument("--literature-csv", default=None)
    p.add_argument("--side", default="_r")
    p.add_argument("-n", type=int, default=60)
    p.add_argument("--coords", nargs="*", default=None)
    p.add_argument("--focus", default="knee_angle",
                   help="moment DOF for the detailed fig01")
    p.add_argument("--no-discontinuity", dest="discontinuity",
                   action="store_false", default=True)
    p.add_argument("--min-jump-mm", type=float, default=None,
                   help="discontinuity floor (default 1.0 mm)")
    p.add_argument("--dpi", type=int, default=110)
    p.add_argument("--no-grids", dest="grids", action="store_false", default=True,
                   help="skip the all-muscle momentarm_<coord> grids")
    p.add_argument("--no-fibre", dest="fibre", action="store_false", default=True,
                   help="skip the fibre-length grids")
    a = p.parse_args(argv)
    setup_logging(logging.INFO)
    detect = ({"min_jump_m": a.min_jump_mm / 1000.0}
              if a.min_jump_mm is not None else None)
    for f in compare_models(a.models, a.out, literature_csv=a.literature_csv,
                            side=a.side, n=a.n, coords=a.coords,
                            focus=a.focus, discontinuity=a.discontinuity,
                            detect=detect, dpi=a.dpi, grids=a.grids,
                            fibre=a.fibre):
        print("  ", f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
