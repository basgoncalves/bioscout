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
                    print(f"  [warn] could not remove {p}: {e}")
            t = subj.make_trial(trial_dir)
            t.export_c3d()
            _downsample_inputs(trial_dir)
            return True
        if has_trc:
            print(f"  [no-c3d] {os.path.basename(trial_dir)}: downsampling markers/grf in place")
            _downsample_inputs(trial_dir)
            return True
        return False

    for subj in proj.subjects:
        if not subj.sessions:
            continue
        session = subj.sessions[0].name
        sdir = os.path.join(sim, subj.name, session)
        if not os.path.isdir(sdir):
            print(f"[skip] {subj.name}/{session} — no folder")
            continue
        trials = [d for d in sorted(os.listdir(sdir))
                  if os.path.isdir(os.path.join(sdir, d))
                  and (os.path.exists(os.path.join(sdir, d, C3D))
                       or os.path.exists(os.path.join(sdir, d, TRC)))]
        print(f"\n==================  {subj.name}/{session}: {len(trials)} trials  ==================")

        for tr in trials:
            print(f"  [inputs] {tr}: rebuild -> downsample to N={n}")
            try:
                _rebuild_trial(subj, os.path.join(sdir, tr))
            except Exception as e:
                print(f"  [ERROR] rebuild {subj.name}/{tr}: {e}")

        for tr in trials:
            print(f"\n=== SO  {subj.name}/{tr} ===")
            try:
                t = subj.make_trial(os.path.join(sdir, tr))
                t.run_ik(replace=replace)
                t.run_id(replace=replace)
                t.run_ma(replace=replace)
                t.run_so(replace=replace)
                t.calculate_muscle_moments(forces_type="so")
                t.run_jra(replace=replace)
            except Exception as e:
                print(f"  [ERROR] SO {subj.name}/{tr}: {e}")

        if ceinms:
            print(f"\n=== CEINMS  {subj.name}/{session} ===")
            try:
                run_ceinms(proj, subj.name, session, trials, calibration_trials, replace)
            except Exception as e:
                print(f"  [CEINMS ERROR] {subj.name}: {e}")

    print("\n==================  PIPELINE DONE  ==================")
    return True


def run_ceinms_only(project_dir=None, replace=True,
                    calibration_trials=("Walking_02", "Squat_BW_01")):
    """Re-run ONLY the CEINMS stage on existing SO results (non-destructive)."""
    import bioscout
    from bioscout.tests.downsample import run_ceinms

    project_dir = project_dir or os.getcwd()
    proj = bioscout.Project(project_dir)
    sim = proj.utils.SIMULATIONS_DIR
    for subj in proj.subjects:
        if not subj.sessions:
            continue
        session = subj.sessions[0].name
        sdir = os.path.join(sim, subj.name, session)
        if not os.path.isdir(sdir):
            print(f"[skip] {subj.name}/{session} — no folder")
            continue
        trials = [d for d in sorted(os.listdir(sdir))
                  if os.path.isdir(os.path.join(sdir, d))
                  and not d.startswith("calibrationOutput")
                  and os.path.exists(os.path.join(sdir, d, "emg_filtered.mot"))]
        print(f"\n====  CEINMS  {subj.name}/{session}: {len(trials)} trials  ====")
        try:
            run_ceinms(proj, subj.name, session, trials, calibration_trials, replace)
        except Exception as e:
            print(f"  [CEINMS ERROR] {subj.name}: {e}")
    print("\n====  CEINMS-ONLY DONE  ====")
    return True


def run_summary(project_dir=None):
    """Build the project's results/manuscript summary.

    The summary is intentionally project-specific (manuscript figures, metric &
    curve CSVs), so it lives in the project as ``summarize_results.py`` and is
    executed here. Falls back to the package summary (``utils.summary``) if the
    project script is absent.
    """
    project_dir = project_dir or os.getcwd()
    script = os.path.join(project_dir, "summarize_results.py")
    if os.path.exists(script):
        print(f"[summary] running {script}")
        runpy.run_path(script, run_name="__main__")
        return True
    try:
        from bioscout.utils.summary import run_summary as _pkg_summary
        print("[summary] project summarize_results.py not found — using package summary")
        return bool(_pkg_summary())
    except Exception as e:
        print(f"[summary] no summary available: {e}")
        return False


def run_project(project_dir, settings_module):
    """Dispatcher for ``python -m bioscout -b settings.py``.

    Reads RUN_PIPELINE / RUN_SUMMARY / RUN_SCALING from the settings module and
    runs the requested stages. Returns True if everything requested succeeded.
    """
    run_pipe = bool(getattr(settings_module, "RUN_PIPELINE", False))
    run_summ = bool(getattr(settings_module, "RUN_SUMMARY", False))
    run_scale = bool(getattr(settings_module, "RUN_SCALING", False))
    run_ceinms_flag = bool(getattr(settings_module, "RUN_CEINMS", True))
    calib = _calibration_trials(settings_module)

    print("=" * 70)
    print(f"[bioscout] project run: pipeline={run_pipe} summary={run_summ} "
          f"scaling={run_scale} ceinms={run_ceinms_flag}")
    print("=" * 70)

    ok = True
    if run_pipe:
        ok = run_pipeline(project_dir, scale=run_scale, ceinms=run_ceinms_flag,
                          calibration_trials=calib) and ok
    if run_summ:
        ok = run_summary(project_dir) and ok
    if not run_pipe and not run_summ:
        print("[bioscout] nothing to do — set RUN_PIPELINE and/or RUN_SUMMARY "
              "in settings.py.")
    return ok
