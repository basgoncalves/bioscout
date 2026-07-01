"""
bioscout.pipeline — project-level orchestration driven by settings flags.

This folds the old per-project driver scripts (redo_pipeline.py, run_pipeline.py,
redo_ceinms.py, summarize_results.py) into the package so a project is run with a
single command::

    python -m bioscout -b settings.py

The settings module controls what runs via module-level flags::

    RUN_PIPELINE = True   # rebuild inputs from c3d + IK/ID/MA/SO/JRA + CEINMS
    RUN_SUMMARY  = True   # build the results/manuscript summary
    RUN_SCALING  = False  # (optional) re-scale models before the pipeline

``run_project`` reads those flags and calls the steps below. Everything operates
on a ``bioscout.Project`` rooted at the settings file's folder.
"""
import os
import shutil
import datetime
import runpy

# Files a trial folder is allowed to start with — everything else is regenerated
# from these by export_c3d. (Mirrors the canonical "raw inputs only" policy.)
RAW_INPUTS = ["c3dfile.c3d", "events.csv"]
C3D = "c3dfile.c3d"
TRC = "marker_experimental.trc"
GRF = "grf.mot"


def _calibration_trials(settings_module, default=("Walking_02", "Squat_BW_01")):
    """Resolve CEINMS calibration trials from settings, with a safe default."""
    cs = getattr(settings_module, "CEINMSSettings", None)
    names = getattr(cs, "calibration_trial_names", None)
    if names:
        return tuple(names)
    bs = getattr(settings_module, "BatchSettings", None)
    names = getattr(bs, "calibration_trials", None)
    return tuple(names) if names else tuple(default)


# ---------------------------------------------------------------------------
# Reset a project's simulations back to inputs-only (with timestamped backup).
# ---------------------------------------------------------------------------

# Per-trial files KEPT on reset: raw experimental inputs + the per-trial config
# the pipeline reads. Everything else in a trial folder is a generated output.
TRIAL_KEEP = {
    "c3dfile.c3d", "events.csv", "marker_experimental.trc", "grf.mot",
    "GRF.xml", "emg.mot", "analog.csv", "trial_settings.xml",
}
# Session-level files KEPT on reset: CEINMS calibration *inputs*. Calibration
# *outputs* (subjectCalibrated*, calibrationOutput*/, *_parameters.png,
# *_vs_uncalibrated.png) and any other non-trial sub-folders are removed.
SESSION_KEEP = {
    "subjectUncalibrated.xml", "calibrationCfg.xml", "calibrationSetup.xml",
    "excitationGenerator.xml",
}


def _is_trial_dir(path):
    """A trial folder holds raw motion inputs (a c3d or experimental markers)."""
    return (os.path.exists(os.path.join(path, C3D))
            or os.path.exists(os.path.join(path, TRC)))


def reset_simulations(project_dir=None, backup=True, dry_run=False,
                      trial_keep=None, session_keep=None,
                      extra_backup=("results", os.path.join("manuscript", "figures")),
                      verbose=True):
    """Back up and reset a project's simulations tree to inputs-only.

    For each ``simulations/<subject>/<session>``:
      * every trial folder is reduced to ``trial_keep`` (raw inputs + trial
        settings); all generated outputs — IK/ID/MA/SO/JRA results, ``setup_*.xml``,
        ``MuscleAnalysis/``, ``Execution*/``, plots, filtered EMG, ... — are deleted;
      * session-level CEINMS *inputs* (``session_keep``) are kept; calibration
        *outputs* (``subjectCalibrated*``, ``*_parameters.png``, ``*_vs_uncalibrated.png``)
        and any non-trial sub-folder (``calibrationOutput*``, old run backups) are deleted.

    Before deleting anything, ``simulations/`` and every existing path in
    ``extra_backup`` (project-relative, e.g. ``results/`` and ``manuscript/figures/``)
    are copied to timestamped siblings ``<name>_backup_<YYYYmmdd_HHMMSS>`` that all
    share one timestamp. Use ``dry_run=True`` to preview without touching disk.

    Returns a dict: ``{"timestamp", "backups": [...], "trials_reset", "removed"}``.
    """
    import bioscout
    project_dir = os.path.abspath(project_dir or os.getcwd())
    proj = bioscout.Project(project_dir)
    sim = proj.utils.SIMULATIONS_DIR or os.path.join(project_dir, "simulations")
    tkeep = set(trial_keep) if trial_keep is not None else set(TRIAL_KEEP)
    skeep = set(session_keep) if session_keep is not None else set(SESSION_KEEP)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log = print if verbose else (lambda *a, **k: None)

    if not os.path.isdir(sim):
        raise FileNotFoundError(f"no simulations folder at {sim}")
    info = {"timestamp": ts, "backups": [], "trials_reset": 0, "removed": 0}

    # ---- 1. backups (shared timestamp) ----
    if backup and not dry_run:
        dst = f"{sim}_backup_{ts}"
        log(f"[reset] backup {sim} -> {dst}  (can take a while)")
        shutil.copytree(sim, dst); info["backups"].append(dst)
        for rel in extra_backup:
            src = os.path.join(project_dir, rel)
            if os.path.isdir(src):
                d = os.path.join(os.path.dirname(src),
                                 f"{os.path.basename(src)}_backup_{ts}")
                log(f"[reset] backup {src} -> {d}")
                shutil.copytree(src, d); info["backups"].append(d)
        log("[reset] backups done")
    elif backup:
        log(f"[reset] (dry-run) would back up {sim} + {list(extra_backup)} with ts={ts}")

    def _remove(path):
        info["removed"] += 1
        if dry_run:
            log(f"    would remove {os.path.relpath(path, sim)}")
            return
        try:
            shutil.rmtree(path) if os.path.isdir(path) else os.remove(path)
        except Exception as e:
            log(f"    [warn] could not remove {path}: {e}")

    # ---- 2. walk subjects / sessions and strip to inputs ----
    for subject in sorted(os.listdir(sim)):
        sub_dir = os.path.join(sim, subject)
        if not os.path.isdir(sub_dir):
            continue
        for session in sorted(os.listdir(sub_dir)):
            sess_dir = os.path.join(sub_dir, session)
            if not os.path.isdir(sess_dir):
                continue
            for entry in sorted(os.listdir(sess_dir)):
                p = os.path.join(sess_dir, entry)
                if os.path.isdir(p):
                    if _is_trial_dir(p):
                        kept = 0
                        for item in sorted(os.listdir(p)):
                            if item in tkeep:
                                kept += 1
                            else:
                                _remove(os.path.join(p, item))
                        info["trials_reset"] += 1
                        log(f"[reset] trial {subject}/{session}/{entry}: kept {kept} input(s)")
                    else:
                        log(f"[reset] remove non-trial dir {subject}/{session}/{entry}")
                        _remove(p)
                elif entry not in skeep:
                    _remove(p)

    log(f"[reset] {'DRY-RUN ' if dry_run else ''}done (ts={ts}): "
        f"{info['trials_reset']} trials reset, {info['removed']} item(s) "
        f"{'to remove' if dry_run else 'removed'}; backups: {info['backups']}")
    return info


def run_pipeline(project_dir=None, scale=False, ceinms=True, replace=True,
                 calibration_trials=("Walking_02", "Squat_BW_01"),
                 backup=True, normalise_inputs=None):
    """Clean re-run of the whole pipeline from raw inputs only.

    For every subject/session/trial: strip the trial to {c3d, events},
    export_c3d (regenerates markers/grf/emg/trial_settings), downsample
    markers+grf to ``normalise_inputs`` frames, then run IK -> ID -> MA -> SO ->
    muscle moments -> JRA, and finally CEINMS per session (normalise EMG +
    calibrate + execute). Model scaling is intentionally NOT performed (existing
    scaled models are reused); pass ``scale=True`` only once that is wired up.

    Trials with no c3d but an existing .trc (template/MRI subjects) just get
    their markers/grf downsampled in place.
    """
    import bioscout
    from bioscout.tests.downsample import resample_trc, resample_sto, run_ceinms

    project_dir = project_dir or os.getcwd()
    proj = bioscout.Project(project_dir)
    u = proj.utils
    sim = u.SIMULATIONS_DIR
    bs = u.settings.BatchSettings
    n = int(normalise_inputs if normalise_inputs is not None
            else getattr(bs, "normalise_inputs", 0)) or 101
    print(f"[pipeline] downsample markers+grf to N={n} frames (EMG native); "
          f"project={project_dir}; scale={scale}; ceinms={ceinms}")

    if scale:
        print("[pipeline] NOTE: scale=True requested, but project pipeline reuses "
              "existing scaled models — skipping scaling.")

    if backup:
        dst = os.path.join(project_dir,
                           f"simulations_backup_{datetime.datetime.now():%Y%m%d_%H%M%S}")
        print(f"[backup] copying simulations -> {dst}  (this can take a while)")
        shutil.copytree(sim, dst)
        print("[backup] done")

    def _downsample_inputs(trial_dir):
        trc = os.path.join(trial_dir, TRC)
        grf = os.path.join(trial_dir, GRF)
        if os.path.exists(trc):
            resample_trc(trc, trc, n)
        if os.path.exists(grf):
            resample_sto(grf, grf, n)

    def _rebuild_trial(subj, trial_dir):
        has_c3d = os.path.exists(os.path.join(trial_dir, C3D))
        has_trc = os.path.exists(os.path.join(trial_dir, TRC))
        if has_c3d:
            for item in os.listdir(trial_dir):
                if item in RAW_INPUTS:
                    continue
                p = os.path.join(trial_dir, item)
                try:
                    shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
                except Exception as e:
                