# bioscout -- rules for Claude

## Engines: never mix OpenSim and pyosim
- An iteration's `engine:` in session.yaml (`opensim` | `pyosim`) decides which engine
  computes EVERY step of that iteration: scale, IK, ID, MA, SO, JRA and JRA contributions.
- Never feed one engine's results into the other's step inside an iteration (e.g. no
  pyosim JRA/contributions on OpenSim SO forces, no OpenSim step in a pyosim iteration).
- Never "speed up" or "repair" OpenSim results with pyosim, interpolation or any other
  post-processing: OpenSim output stays exactly as OpenSim produced it. Fix the inputs
  (setup/actuator files) instead.
- Comparisons between engines (e.g. 4_outputs/pyosim_vs_osim) are analysis scripts outside
  the iterations; they may read both, but never write into either iteration.
- A pyosim iteration never imports or runs OpenSim: `simulate/pyosim_backend.py` has no
  fallback (a missing step -- RRA, CMC/forward, energetics, ... -- raises NotImplementedError
  before anything is written), scaling is `model/scale/pyosim_scale.py` (plain-XML
  preparation, no ScaleTool), and Analyse helpers check `self._is_pyosim()` instead of
  loading an OpenSim model.
- An OpenSim iteration never uses pyosim (no `bioscout.pyosim` import on the OpenSim path).
- Shared helpers both engines use must be plain Python/XML (e.g. `simulate/grf_setup.py`).
- `bioscout/pyosim/` is mirrored in bioscout_web `py/pyosim/`: change both
  (`tools/sync_pyosim.py`).

## MRI2MSK
- `bioscout/model/mri2msk/` is the only copy of MRI2MSK, steps AND desktop GUI (moved from
  `Desktop/WilliOSC/MRI2MSKpy`, removed). GUI: `bioscout model mri2msk gui`.
  CLI: `bioscout model mri2msk`. Checks: `bioscout/tests/mri2msk/validate_*.py` on
  `WilliOSC/MRI2MSK/exampleParticipant` (STAPLE vs MATLAB, TPS warp vs OpenSim Creator).
