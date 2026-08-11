"""Adjust the moment arms of an OpenSim model, plot before/after, and validate vs literature.

EDIT THE `CONFIG` BLOCK BELOW, then run:

    python run_moment_arm_inspection.py

Outputs (all under <model_dir>/validation/<model>/):
  - corrected model  <model_dir>/<model>_modWO.osim   (next to the ORIGINAL model)
  - momentarm_<coord>.png / length_<coord>.png  before vs after grids
        (literature bands overlaid on hip-flexion moment-arm panels where available)
  - validation_moment_arms.png + validation_rmse.csv   full literature comparison

Coordinate-SWEEP (motion-free) tool. For motion-driven checking against a .mot,
use run_muscle_checker.py.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

# =====================================================================
#  CONFIG
# =====================================================================
CONFIG = {
    "model": "scaled.osim",
    "out":   None,                     # None = validation/<model>/ next to the model

    "coords": None,                    # None = default lower-limb set
    "muscle_filter": None,
    "n": 80,

    "max_displacement_mm": 5.0,
    "margin_base_mm":      2.0,
    "margin_frac":         0.5,
    "max_penetration_mm":  5.0,
    "n_pose":              30,
    "min_jump_mm":         1.0,
    "radius_reduction":    True,
    "rr_n":                40,

    # literature validation
    "validate":        True,
    "literature_csv":  "validation/literature_moment_arms.csv",
    "val_side":        "_r",

    "cross_body":  True,
    "make_plots":  True,
    "force_after": False,
    "verbose":     False,
    "opensim_warnings": False,
}
# =====================================================================


def _build_parser():
    c = CONFIG
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", default=c["model"])
    p.add_argument("--out", default=c["out"])
    p.add_argument("--coords", nargs="*", default=c["coords"])
    p.add_argument("--muscle-filter", nargs="*", default=c["muscle_filter"])
    p.add_argument("--n", type=int, default=c["n"])
    p.add_argument("--max-penetration-mm", type=float, default=c["max_penetration_mm"])
    p.add_argument("--max-displacement-mm", type=float, default=c["max_displacement_mm"])
    p.add_argument("--margin-base-mm", type=float, default=c["margin_base_mm"])
    p.add_argument("--margin-frac", type=float, default=c["margin_frac"])
    p.add_argument("--min-jump-mm", type=float, default=c["min_jump_mm"])
    p.add_argument("--n-pose", type=int, default=c["n_pose"])
    p.add_argument("--rr-n", type=int, default=c["rr_n"])
    p.add_argument("--literature-csv", default=c["literature_csv"])
    p.add_argument("--val-side", default=c["val_side"])
    p.add_argument("--no-radius-reduction", dest="radius_reduction", action="store_false", default=c["radius_reduction"])
    p.add_argument("--no-validate", dest="validate", action="store_false", default=c["validate"])
    p.add_argument("--no-plots", dest="make_plots", action="store_false", default=c["make_plots"])
    p.add_argument("--no-cross-body", dest="cross_body", action="store_false", default=c["cross_body"])
    p.add_argument("--force-after", action="store_true", default=c["force_after"])
    p.add_argument("--verbose", action="store_true", default=c["verbose"])
    p.add_argument("--opensim-warnings", action="store_true", default=c["opensim_warnings"])
    return p


def main(argv=None):
    here = os.getcwd()
    args = _build_parser().parse_args(argv)

    from .logutil import setup_logging, fmt_hms, add_file_handler
    from . import moment_arms, plotting, radius_reduce
    from . import muscle_length_validation as validation  # up-to-date loader/colours/knee-flip

    log = setup_logging(level=logging.DEBUG if args.verbose else logging.INFO,
                        quiet_opensim=not args.opensim_warnings)

    model = args.model if os.path.isabs(args.model) else os.path.join(here, args.model)
    if not os.path.isfile(model):
        sys.exit(f"Model not found: {model}")
    model_dir = os.path.dirname(model)
    base = os.path.splitext(os.path.basename(model))[0]
    corrected = os.path.join(model_dir, f"{base}_modWO.osim")
    from .paths import validation_dir
    out = validation_dir(model, out=args.out, base=base)
    os.makedirs(out, exist_ok=True)
    add_file_handler(os.path.join(out, "run_log.txt"), log)
    log.info("run log -> %s", os.path.join(out, "run_log.txt"))
    from .paths import resolve_literature_csv
    # prefer the CSV passed on the command line; fall back to the bundled copy
    csv_path = resolve_literature_csv(args.literature_csv)

    min_jump_m = args.min_jump_mm / 1000.0
    timings = {}
    t_start = time.perf_counter()

    # -- STEP 1: before --
    before = {}
    if args.make_plots:
        log.info("=" * 64); log.info("STEP 1  Moment arms BEFORE correction"); log.info("=" * 64)
        t = time.perf_counter()
        before = moment_arms.compute_sweeps(model, coordinate_names=args.coords,
                                            muscle_filter=args.muscle_filter, n=args.n)
        timings["before sweeps"] = time.perf_counter() - t

    # -- STEP 2: fix --
    log.info("=" * 64); log.info("STEP 2  Fixing path points + wrap surfaces"); log.info("=" * 64)
    suspects = moment_arms.discontinuous_muscles(before, min_jump_m=min_jump_m) if before else None
    if suspects is not None:
        log.info("%d muscles show a discontinuity: %s", len(suspects), ", ".join(sorted(suspects)) or "(none)")
    t = time.perf_counter()
    fix = radius_reduce.fix_with_radius_reduction(
        model, corrected, muscle_filter=args.muscle_filter,
        max_penetration_mm=args.max_penetration_mm, max_displacement_mm=args.max_displacement_mm,
        margin_base_m=args.margin_base_mm / 1000.0, margin_frac=args.margin_frac,
        cross_body=args.cross_body, coordinate_names=args.coords, suspect_muscles=suspects,
        n_pose=args.n_pose, radius_reduction=args.radius_reduction,
        detect_kwargs=dict(min_jump_m=min_jump_m), rr_n=args.rr_n)
    timings["fix model"] = time.perf_counter() - t
    log.info("corrected model saved next to original: %s", corrected)

    if not args.make_plots:
        log.info("Done (plots skipped). %s", fix.summary)
        _print_timings(log, timings, t_start)
        return

    # -- STEP 3: after --
    n_applied = len(fix.projections) + len(getattr(fix, "radius_reductions", []))
    if n_applied == 0 and not args.force_after:
        log.info("STEP 3  No corrections applied -> reusing BEFORE curves")
        after = before
    else:
        log.info("STEP 3  Moment arms AFTER correction (%d edits)", n_applied)
        t = time.perf_counter()
        after = moment_arms.compute_sweeps(corrected, coordinate_names=args.coords,
                                           muscle_filter=args.muscle_filter, n=args.n)
        timings["after sweeps"] = time.perf_counter() - t

    # -- literature overlays for the grids (hip-flexion 1:1 muscles) --
    overlays = None
    if args.validate:
        lit = validation.load_literature(csv_path)
        if lit:
            overlays = {}
            for coord, sw in (after or before).items():
                ov = validation.grid_overlays(lit, coord, list(sw.moment_arms.keys()))
                if ov:
                    overlays[coord] = ov

    # -- STEP 4: plots --
    log.info("=" * 64); log.info("STEP 4  Saving comparison plots"); log.info("=" * 64)
    t = time.perf_counter()
    saved = plotting.plot_comparison(before, after, outdir=out, literature=overlays)
    timings["plots"] = time.perf_counter() - t
    for p in saved:
        log.info("saved %s", p)

    # -- STEP 5: full literature validation figure --
    if args.validate:
        log.info("=" * 64); log.info("STEP 5  Literature validation"); log.info("=" * 64)
        t = time.perf_counter()
        vp = validation.run_validation(corrected, csv_path, out, side=args.val_side, n=60)
        timings["validation"] = time.perf_counter() - t
        if vp:
            log.info("saved %s", vp)

    log.info("-" * 64)
    log.info("SUMMARY: %s", fix.summary)
    log.info("Corrected model: %s", corrected)
    log.info("Figures: %s", out)
    _print_timings(log, timings, t_start)


def _print_timings(log, timings, t_start):
    from .logutil import fmt_hms
    log.info("-" * 64); log.info("TIMING")
    for label, secs in timings.items():
        log.info("  %-16s %8s", label, fmt_hms(secs))
    log.info("  %-16s %8s", "TOTAL", fmt_hms(time.perf_counter() - t_start))


if __name__ == "__main__":
    main()
