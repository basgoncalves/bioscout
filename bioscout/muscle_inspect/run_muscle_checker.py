"""run_muscle_checker.py  --  motion-driven muscle-path checker (matches MATLAB muscleChecker)

Inputs: an OpenSim model + one or more kinematics (.mot) files.
Edit the CONFIG block, then run:

    python run_muscle_checker.py

Outputs:
  - corrected model  <model_dir>/<model>_modWO.osim      (next to the ORIGINAL model)
  - log              <model_dir>/<model>_modWO_log.txt    (next to the ORIGINAL model)
  - figures          <model_dir>/muscle_inspect_<model>/
"""
from __future__ import annotations

import logging
import os
import sys
import time

# =====================================================================
#  CONFIG  --  edit these; no command line needed
# =====================================================================
CONFIG = {
    "model":  "scaled.osim",
    "motion": "joint_angles.mot",          # a path, or a list of .mot paths
    "out":    None,                        # None = muscle_inspect_<model> next to the model

    # analysis settings (MATLAB defaults if left as None)
    "coordinate_names": None,              # None = MATLAB default 12 lower-limb coords
    "muscle_filter":    None,              # None = MATLAB default 21 muscles
    "filter_frequency": 6.0,               # low-pass the kinematics (Hz); 0 = off
    "max_iterations":   3,
    "min_jump_mm":      1.0,

    "make_plots": True,
    "verbose":    False,
    "opensim_warnings": False,
}
# =====================================================================


def main():
    here = os.getcwd()
    c = dict(CONFIG)

    from .logutil import setup_logging, fmt_hms, add_file_handler
    from . import muscle_checker as mc

    log = setup_logging(level=logging.DEBUG if c["verbose"] else logging.INFO,
                        quiet_opensim=not c["opensim_warnings"])

    def _abs(p):
        return p if os.path.isabs(p) else os.path.join(here, p)

    model = _abs(c["model"])
    motions = c["motion"] if isinstance(c["motion"], list) else [c["motion"]]
    motions = [_abs(m) for m in motions]
    for p in [model] + motions:
        if not os.path.isfile(p):
            sys.exit(f"Not found: {p}")

    model_dir = os.path.dirname(model)
    base = os.path.splitext(os.path.basename(model))[0]
    out = c["out"] or os.path.join(model_dir, f"muscle_inspect_{base}")
    if not os.path.isabs(out):
        out = _abs(out)
    os.makedirs(out, exist_ok=True)
    add_file_handler(os.path.join(out, "run_log.txt"), log)
    log.info("run log -> %s", os.path.join(out, "run_log.txt"))

    dk = dict(min_jump_m=c["min_jump_mm"] / 1000.0)
    t0 = time.perf_counter()

    # BEFORE lengths (for plotting), per motion
    before = {}
    if c["make_plots"]:
        for mot in motions:
            tvec, names, L = mc.compute_lengths(
                model, mot, c["coordinate_names"], c["muscle_filter"], c["filter_frequency"])
            before[mot] = (tvec, names, L)

    # run the correction pipeline -> corrected model + log written NEXT TO the original model
    log.info("=" * 64)
    log.info("Muscle-path correction: model=%s, %d motion(s)", os.path.basename(model), len(motions))
    log.info("=" * 64)
    success, corrected, log_path = mc.check_and_fix_muscle_paths(
        model, motions,
        coordinate_names=c["coordinate_names"], muscle_filter=c["muscle_filter"],
        filter_freq=c["filter_frequency"], max_iterations=c["max_iterations"],
        min_jump_mm=c["min_jump_mm"], out_dir=model_dir, verbose=c["verbose"])

    # AFTER lengths + plots
    if c["make_plots"]:
        for mot in motions:
            tvec, names, La = mc.compute_lengths(
                corrected, mot, c["coordinate_names"], c["muscle_filter"], c["filter_frequency"])
            _, bnames, Lb = before[mot]
            tag = os.path.splitext(os.path.basename(mot))[0]
            p = mc.plot_length_waveforms(tvec, names, Lb if bnames == names else None,
                                         La, out, tag, dk=dk)
            log.info("saved %s", p)

    log.info("-" * 64)
    log.info("success=%s", success)
    log.info("corrected model (next to original): %s", corrected)
    log.info("log: %s", log_path)
    log.info("figures: %s", out)
    log.info("total time: %s", fmt_hms(time.perf_counter() - t0))


if __name__ == "__main__":
    main()
