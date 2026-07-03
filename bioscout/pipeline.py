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
RAW_INPUTS = ["c3dfile.c3d"]
C3D = "c3dfile.c3d"
TRC = "marker_experimental.trc"
GRF = "grf.mot"

# Raw C3D files for a session live in <session>/c3d/ (one per trial). This folder
# is source data, so reset must never delete it.
C3D_DIRNAME = "c3d"


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
    # subfoldered layout: keep the whole inputs/ folder + the trial manifest
    "inputs", "trial_settings.xml",
    # flat layout (pre-migration): keep the individual raw input files too
    "c3dfile.c3d", "marker_experimental.trc", "grf.mot",
    "GRF.xml", "emg.mot", "analog.csv",
}
# Session-level files KEPT on reset: none. All CEINMS calibration files now live
# in the session's ceinms_calibration/ folder (a non-trial dir that is removed and
# regenerated), so nothing at the session root needs preserving.
SESSION_KEEP = set()


def _is_trial_dir(path):
    """A trial folder holds raw motion inputs — flat (c3d/markers at root) OR the
    subfoldered layout (an inputs/ folder or a trial_settings.xml manifest)."""
    return (os.path.exists(os.path.join(path, C3D))
            or os.path.exists(os.path.join(path, TRC))
            or os.path.isdir(os.path.join(path, "inputs"))
            or os.path.exists(os.path.join(path, "trial_settings.xml")))


def reset_simulations(project_dir=None, backup=True, dry_run=False,
                      subjects=None, session=None, trials=None,
                      trial_keep=None, session_keep=None, raw_inputs=False,
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

    Pass ``subjects`` (name or list), ``session`` (name or list) and/or ``trials``
    (name or list) to scope the reset to just those; the backup is then limited to
    the selected subtree too. When ``trials`` is given, only matching trial folders
    are reset — non-trial dirs and session-level files in that session are left
    untouched. With no scope, every subject/session is reset and the whole tree is
    backed up.

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

    # Optional scoping: restrict the reset (and backup) to specific subject(s) /
    # session(s). None = every subject / every session.
    subj_filter = ({subjects} if isinstance(subjects, str)
                   else set(subjects) if subjects else None)
    sess_filter = ({session} if isinstance(session, str)
                   else set(session) if session else None)
    trial_filter = ({trials} if isinstance(trials, str)
                    else set(trials) if trials else None)
    scoped = (subj_filter is not None or sess_filter is not None
              or trial_filter is not None)

    # ---- 1. backups (shared timestamp) ----
    if backup and not dry_run:
        dst = f"{sim}_backup_{ts}"
        if scoped:
            # Back up only the selected subject/session subtree(s), preserving the
            # simulations/<subject>/<session> layout so a restore is a plain copy.
            n = 0
            for subject in sorted(os.listdir(sim)):
                if subj_filter is not None and subject not in subj_filter:
                    continue
                sub_dir = os.path.join(sim, subject)
                if not os.path.isdir(sub_dir):
                    continue
                for sess_name in sorted(os.listdir(sub_dir)):
                    if sess_filter is not None and sess_name not in sess_filter:
                        continue
                    s = os.path.join(sub_dir, sess_name)
                    if not os.path.isdir(s):
                        continue
                    if trial_filter is not None:
                        # Back up only the selected trial folder(s).
                        for tname in sorted(os.listdir(s)):
                            if tname not in trial_filter:
                                continue
                            tsrc = os.path.join(s, tname)
                            if not os.path.isdir(tsrc):
                                continue
                            d = os.path.join(dst, subject, sess_name, tname)
                            log(f"[reset] backup {subject}/{sess_name}/{tname} -> "
                                f"{os.path.relpath(d, project_dir)}")
                            shutil.copytree(tsrc, d); n += 1
                    else:
                        d = os.path.join(dst, subject, sess_name)
                        log(f"[reset] backup {subject}/{sess_name} -> {os.path.relpath(d, project_dir)}")
                        shutil.copytree(s, d); n += 1
            if n:
                info["backups"].append(dst)
        else:
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
        log(f"[reset] (dry-run) would back up "
            f"{'selected subject/session' if scoped else sim} with ts={ts}")

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
        if subj_filter is not None and subject not in subj_filter:
            continue
        sub_dir = os.path.join(sim, subject)
        if not os.path.isdir(sub_dir):
            continue
        for sess_name in sorted(os.listdir(sub_dir)):
            if sess_filter is not None and sess_name not in sess_filter:
                continue
            sess_dir = os.path.join(sub_dir, sess_name)
            if not os.path.isdir(sess_dir):
                continue
            for entry in sorted(os.listdir(sess_dir)):
                p = os.path.join(sess_dir, entry)
                if os.path.isdir(p):
                    if _is_trial_dir(p):
                        if trial_filter is not None and entry not in trial_filter:
                            continue
                        # Subfoldered trial (has inputs/): keep ONLY inputs/ +
                        # trial_settings.xml, so stale root-level files (e.g. a
                        # leftover flat emg_ceinms.mot / grf.mot) are stripped.
                        # Flat trial (no inputs/): fall back to keeping the raw
                        # input files so un-migrated raw data isn't deleted.
                        # An explicit trial_keep=... always overrides.
                        if trial_keep is not None:
                            tkeep_eff = tkeep
                        elif os.path.isdir(os.path.join(p, "inputs")):
                            tkeep_eff = {"inputs", "trial_settings.xml"}
                        else:
                            tkeep_eff = tkeep
                        kept = 0
                        for item in sorted(os.listdir(p)):
                            if item in tkeep_eff:
                                kept += 1
                            else:
                                _remove(os.path.join(p, item))
                        # raw_inputs: additionally prune inside inputs/ down to just
                        # the raw C3D (RAW_INPUTS), so only c3dfile.c3d + trial_settings.xml
                        # remain. Derived files (markers/grf/emg/GRF.xml/plots) are
                        # regenerated on the next --export run.
                        if raw_inputs:
                            _inp = os.path.join(p, "inputs")
                            if os.path.isdir(_inp):
                                for item in sorted(os.listdir(_inp)):
                                    if item not in RAW_INPUTS:
                                        _remove(os.path.join(_inp, item))
                        info["trials_reset"] += 1
                        log(f"[reset] trial {subject}/{sess_name}/{entry}: kept {kept} input(s)"
                            f"{' (raw c3d only)' if raw_inputs else ''}")
                    else:
                        # The raw-C3D folder (<session>/c3d/) holds source data and
                        # is never removed by reset.
                        if entry == C3D_DIRNAME:
                            continue
                        # When scoped to specific trials, leave non-trial dirs alone.
                        if trial_filter is not None:
                            continue
                        log(f"[reset] remove non-trial dir {subject}/{sess_name}/{entry}")
                        _remove(p)
                elif entry not in skeep:
                    # When scoped to specific trials, leave session-level files alone.
                    if trial_filter is not None:
                        continue
                    _remove(p)

    log(f"[reset] {'DRY-RUN ' if dry_run else ''}done (ts={ts}): "
        f"{info['trials_reset']} trials reset, {info['removed']} item(s) "
        f"{'to remove' if dry_run else 'removed'}; backups: {info['backups']}")
    return info


def run_subject(project_dir=None, subject=None, sessions=None, trials=None,
                replace=False, do_so=True, do_ceinms=True, export=False,
                extra_trials=(), reset=False, verbose=True):
    """Run the FULL analysis pipeline for one (or every) subject.

    For each selected ``subject`` → ``session`` → trial::

        IK -> ID -> MA -> SO -> muscle moments -> JRA          (SO stage)

    then the session-level CEINMS stage::

        prepare_ceinms (EMG normalise + calibrate) -> per-trial run_ceinms_exe
        -> muscle moments -> JRA (CEINMS)

    Assumes each trial already holds its (clean) inputs — this does NOT re-export
    from c3d and does NOT downsample. This is the packaged replacement for the
    old per-project ``run_subject.py`` script.

    Parameters
    ----------
    project_dir : str
        Project root (contains ``settings.py`` and ``simulations/``). Default cwd.
    subject : str | list | None
        Subject name(s) to run. ``None`` = every subject in ``settings.SUBJECTS``.
    sessions : str | list | None
        Restrict to these session folder name(s). ``None`` = all of a subject's sessions.
    trials : str | list | None
        Restrict to these trial name(s). ``None`` = ``BatchSettings.trial_list``
        (+ ``extra_trials``). Names given here that aren't in the default list are
        still attempted.
    replace : bool
        ``False`` (default) skips trials/stages whose outputs already exist (resume);
        ``True`` recomputes and overwrites everything.
    do_so, do_ceinms : bool
        Toggle the SO stage / the CEINMS stage.
    reset : bool
        ``True`` first strips the trials that are about to run back to inputs-only
        (keeps ``inputs/`` + ``trial_settings.xml``, with a timestamped backup) via
        :func:`reset_simulations`, scoped to the same subject/session/trials. Combine
        with ``export=True`` to also regenerate markers/GRF/EMG from the c3d.

    Returns a dict ``{subject: {session: {"so": [...], "ceinms": [...]}}}`` summarising
    which trials succeeded per stage.
    """
    import bioscout
    import glob as _glob
    project_dir = os.path.abspath(project_dir or os.getcwd())
    proj = bioscout.Project(project_dir)
    log = print if verbose else (lambda *a, **k: None)
    skip_done = not replace

    def _as_set(x):
        if x is None:
            return None
        return {x} if isinstance(x, str) else set(x)

    sess_filter = _as_set(sessions)
    trial_filter = _as_set(trials)
    subj_filter = _as_set(subject)

    all_subj = list(proj.subjects)
    if subj_filter is not None:
        subs = [s for s in all_subj if s.name in subj_filter]
        missing = subj_filter - {s.name for s in subs}
        if missing:
            raise ValueError(f"subject(s) {sorted(missing)} not found; "
                             f"have {[s.name for s in all_subj]}")
    else:
        subs = all_subj

    bs = proj.settings.BatchSettings
    base_trials = list(getattr(bs, "trial_list", []) or [])
    sim = getattr(proj.utils, "SIMULATIONS_DIR", None) or os.path.join(project_dir, "simulations")
    results = {}

    # Optional: strip the trials we're about to run back to inputs-only first
    # (timestamped backup made inside reset_simulations). Scoped to exactly the
    # subject/session/trials this run targets, so nothing else is touched. When
    # no trials were named, reset the default trial_list (+ extras) — i.e. the
    # same set the run below will process.
    if reset:
        reset_trials = (sorted(trial_filter) if trial_filter is not None
                        else (base_trials + [t for t in extra_trials
                                             if t not in base_trials]))
        reset_simulations(
            project_dir=project_dir,
            subjects=(sorted(subj_filter) if subj_filter is not None else None),
            session=(sorted(sess_filter) if sess_filter is not None else None),
            trials=(reset_trials or None),
            verbose=verbose)

    def _so_done(td):
        return os.path.exists(os.path.join(td, "Analyse_JRA_ReactionLoads_SO.sto"))

    def _ceinms_done(td):
        return (bool(_glob.glob(os.path.join(td, "Execution_a*", "MuscleForces.sto")))
                and os.path.exists(os.path.join(td, "Analyse_JRA_ReactionLoads_CEINMS.sto")))

    for subj in subs:
        results[subj.name] = {}
        for sess in subj.sessions:
            if sess_filter is not None and sess.name not in sess_filter:
                continue
            # Resolve the trials to run for this session.
            trials_run = list(base_trials) + [t for t in extra_trials if t not in base_trials]
            if trial_filter is not None:
                trials_run = [t for t in trials_run if t in trial_filter]
                for t in trial_filter:                    # allow explicitly-named extras
                    if t not in trials_run:
                        trials_run.append(t)
            res = {"so": [], "ceinms": [], "export": []}
            results[subj.name][sess.name] = res
            log(f"\n=== {subj.name} / {sess.name}  trials={trials_run}  "
                f"replace={replace} (skip_done={skip_done}) export={export} ===")

            # Optional: (re)generate inputs from c3d (markers/GRF/EMG + trial
            # settings), refresh the time window, and filter EMG — mirrors the
            # batch pipeline's export phase. Do this for ALL selected trials first
            # so the session-level EMG normalisation below sees fresh envelopes.
            if export:
                for tn in trials_run:
                    try:
                        t = sess.trial(tn)
                        t.export_c3d()
                        os.chdir(t.path)
                        _tr = t.get_time_range()
                        if _tr:
                            t.time_range = _tr
                            t.update_trial_attribute('time_range', _tr)
                        try:
                            t.run_emg_filter()
                        except Exception as _ee:
                            log(f"  [export] EMG filter warn {subj.name}/{tn}: {_ee}")
                        res["export"].append(tn)
                        log(f"  [export ok] {subj.name}/{tn}")
                    except Exception as e:
                        log(f"  [export ERROR] {subj.name}/{tn}: {e}")

            if do_so:
                for tn in trials_run:
                    try:
                        t = sess.trial(tn)
                        if skip_done and _so_done(t.path):
                            log(f"  [skip] {tn}: SO already done")
                            res["so"].append(tn)
                            continue
                        t.run_ik(replace=replace)
                        t.run_id(replace=replace)
                        t.run_ma(replace=replace)
                        t.run_so(replace=replace)
                        t.calculate_muscle_moments(forces_type="so")
                        t.run_jra(replace=replace)
                        res["so"].append(tn)
                        log(f"  [SO ok] {subj.name}/{tn}")
                    except Exception as e:
                        log(f"  [SO ERROR] {subj.name}/{tn}: {e}")

            if do_ceinms:
                try:
                    calibrated = os.path.join(sim, subj.name, sess.name, "ceinms_calibration", "subjectCalibrated.xml")
                    if skip_done and os.path.exists(calibrated):
                        log("  [skip] CEINMS calibration already done")
                    else:
                        sess.prepare_ceinms(replace=replace)
                    for tn in trials_run:
                        try:
                            t = sess.trial(tn, force_type="CEINMS")
                            if skip_done and _ceinms_done(t.path):
                                log(f"  [skip] {tn}: CEINMS already done")
                                res["ceinms"].append(tn)
                                continue
                            t.run_ceinms_exe()
                            t.calculate_muscle_moments(forces_type="ceinms")
                            t.run_jra_ceinms(replace=replace)
                            res["ceinms"].append(tn)
                            log(f"  [CEINMS ok] {subj.name}/{tn}")
                        except Exception as e:
                            log(f"  [CEINMS ERROR] {subj.name}/{tn}: {e}")
                except Exception as e:
                    log(f"  [CEINMS calibration ERROR] {subj.name}: {e}")

    log(f"\n[run_subject] done: "
        + "; ".join(f"{s}/{ss}: SO={len(r['so'])} CEINMS={len(r['ceinms'])}"
                    for s, sd in results.items() for ss, r in sd.items()))
    return results


def _run_session_ceinms(subj, sess, sdir, trials, calibration_trials, replace):
    """Drive CEINMS for one subject/session using the tested Session/Trial verbs.

    Session-wide EMG normalisation + one calibrated model, then per-trial CEINMS
    execution. Non-destructive and full-resolution. ``calibration_trials`` may be
    None to let the Session resolve them from settings (with folder-matching and
    a squat/all fallback).
    """
    try:
        sess.normalise_emg(replace=replace)
    except Exception as e:
        print(f"  [CEINMS] EMG normalise failed for {subj.name}/{sess.name}: {e}")
    cal = list(calibration_trials) if calibration_trials else None
    try:
        sess.calibrate(replace=replace, calibration_trials=cal)
    except Exception as e:
        print(f"  [CEINMS] calibration failed for {subj.name}/{sess.name}: {e}")
        return
    for tr in trials:
        print(f"  [CEINMS exe] {subj.name}/{tr}")
        try:
            t = subj.make_trial(os.path.join(sdir, tr))
            t.update_trial_attribute("replace", replace)
            t.run_ceinms_exe()
        except Exception as e:
            print(f"  [CEINMS ERROR] {subj.name}/{tr}: {e}")


def run_pipeline(project_dir=None, scale=False, ceinms=True, replace=True,
                 calibration_trials=("Walking_02", "Squat_BW_01"),
                 backup=True, normalise_inputs=None):
    """Full-resolution, non-destructive run of the whole pipeline.

    For every subject/session/trial: export_c3d (regenerates markers/grf/emg/
    trial_settings from the C3D at native sampling — no downsampling and no
    destructive strip), then run IK -> ID -> MA -> SO -> muscle moments -> JRA,
    and finally CEINMS per session (normalise EMG + calibrate + execute). Model
    scaling is intentionally NOT performed (existing scaled models are reused);
    pass ``scale=True`` only once that is wired up.

    Trials with no c3d but an existing .trc (template/MRI subjects) are analysed
    from their existing markers/grf as-is. ``backup`` and ``normalise_inputs``
    are accepted for backwards compatibility but no longer used.
    """
    import bioscout

    project_dir = project_dir or os.getcwd()
    proj = bioscout.Project(project_dir)
    u = proj.utils
    sim = u.SIMULATIONS_DIR
    print(f"[pipeline] full-resolution, non-destructive run; "
          f"project={project_dir}; scale={scale}; ceinms={ceinms}")

    if scale:
        print("[pipeline] NOTE: scale=True requested, but project pipeline reuses "
              "existing scaled models — skipping scaling.")

    for subj in proj.subjects:
        if not subj.sessions:
            continue
        sess = subj.sessions[0]
        session = sess.name
        sdir = os.path.join(sim, subj.name, session)
        if not os.path.isdir(sdir):
            print(f"[skip] {subj.name}/{session} — no folder")
            continue
        trials = [d for d in sorted(os.listdir(sdir))
                  if os.path.isdir(os.path.join(sdir, d))
                  and (os.path.exists(os.path.join(sdir, d, C3D))
                       or os.path.exists(os.path.join(sdir, d, TRC)))]
        print(f"\n==================  {subj.name}/{session}: {len(trials)} trials  ==================")

        # Regenerate trial inputs from the C3D at full resolution (no downsample,
        # no destructive strip). Trials with no C3D (template/MRI) keep their .trc.
        for tr in trials:
            tp = os.path.join(sdir, tr)
            if os.path.exists(os.path.join(tp, C3D)):
                print(f"  [inputs] {tr}: export c3d (full resolution)")
                try:
                    subj.make_trial(tp).export_c3d()
                except Exception as e:
                    print(f"  [ERROR] export_c3d {subj.name}/{tr}: {e}")

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
                _run_session_ceinms(subj, sess, sdir, trials, calibration_trials, replace)
            except Exception as e:
                print(f"  [CEINMS ERROR] {subj.name}: {e}")

    print("\n==================  PIPELINE DONE  ==================")
    return True


def run_ceinms_only(project_dir=None, replace=True,
                    calibration_trials=("Walking_02", "Squat_BW_01")):
    """Re-run ONLY the CEINMS stage on existing SO results (non-destructive)."""
    import bioscout

    project_dir = project_dir or os.getcwd()
    proj = bioscout.Project(project_dir)
    sim = proj.utils.SIMULATIONS_DIR
    for subj in proj.subjects:
        if not subj.sessions:
            continue
        sess = subj.sessions[0]
        session = sess.name
        sdir = os.path.join(sim, subj.name, session)
        if not os.path.isdir(sdir):
            print(f"[skip] {subj.name}/{session} — no folder")
            continue
        trials = [d for d in sorted(os.listdir(sdir))
                  if os.path.isdir(os.path.join(sdir, d))
                  and not d.startswith("calibrationOutput")
                  and (os.path.exists(os.path.join(sdir, d, C3D))
                       or os.path.exists(os.path.join(sdir, d, TRC)))]
        print(f"\n====  CEINMS  {subj.name}/{session}: {len(trials)} trials  ====")
        try:
            _run_session_ceinms(subj, sess, sdir, trials, calibration_trials, replace)
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
