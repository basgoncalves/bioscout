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
import sys
import shutil
import datetime
import runpy

# Files a trial folder is allowed to start with — everything else is regenerated
# from these by export_c3d. (Mirrors the canonical "raw inputs only" policy.)
RAW_INPUTS = ["c3dfile.c3d"]
C3D = "c3dfile.c3d"
TRC = "marker_experimental.trc"
GRF = "grf.mot"


def _has_raw_inputs(trial_dir):
    """True if a trial has a c3d OR marker file, in the current ``inputs/``
    layout OR the legacy flat layout (files directly in the trial folder)."""
    for name in (C3D, TRC):
        if (os.path.exists(os.path.join(trial_dir, "inputs", name))
                or os.path.exists(os.path.join(trial_dir, name))):
            return True
    return False

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
                do_exbiomec=False, export_src=None,
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
                if export_src:                       # distribute loose c3d first
                    try:
                        sess.ingest_c3d(source=export_src)
                    except Exception as e:
                        log(f"  [export ingest ERROR] {subj.name}: {e}")
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

            if do_exbiomec:                          # external biomechanics only
                for tn in trials_run:
                    try:
                        t = sess.trial(tn)
                        t.run_ik(replace=replace)
                        t.run_id(replace=replace)
                        t.run_ma(replace=replace)
                        res.setdefault("exbiomec", []).append(tn)
                        log(f"  [exbiomec ok] {subj.name}/{tn}")
                    except Exception as e:
                        log(f"  [exbiomec ERROR] {subj.name}/{tn}: {e}")

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
                        # CEINMS calibration reads the calibration trial's muscle
                        # analysis (_MuscleAnalysis_Length.sto + moment arms). That
                        # trial is not necessarily in trials_run (e.g. running only
                        # Walking_02 while calibrating on Static_01), so its IK/ID/MA
                        # may never have been produced. Ensure it before calibrating.
                        try:
                            cal_names = sess._resolve_calibration_trials() or []
                        except Exception:
                            cal_names = []
                        for cn in cal_names:
                            try:
                                ct = sess.trial(cn)
                                ma_len = os.path.join(ct.path, ct.ma,
                                                      "_MuscleAnalysis_Length.sto")
                                if replace or not os.path.exists(ma_len):
                                    log(f"  [CEINMS prep] muscle analysis for "
                                        f"calibration trial {cn}")
                                    ct.run_ik(replace=replace)
                                    ct.run_id(replace=replace)
                                    ct.run_ma(replace=replace)
                            except Exception as e:
                                log(f"  [CEINMS prep ERROR] {subj.name}/{cn}: {e}")
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


def _run_session_ceinms(subj, sess, sdir, trials, calibration_trials, replace,
                        do_normalise=True):
    """Drive CEINMS for one subject/session using the tested Session/Trial verbs.

    Session-wide EMG normalisation + one calibrated model, then per-trial CEINMS
    execution. Non-destructive and full-resolution. ``calibration_trials`` may be
    None to let the Session resolve them from settings (with folder-matching and
    a squat/all fallback).

    EMG normalisation is SESSION-WIDE (per-channel max across ALL trials = MVC
    reference), so it can't be done for just a subset. With ``replace=False`` it
    is skipped only when EVERY trial already has inputs/emg_filtered_normalised.mot.
    """
    _norm_all_present = all(
        os.path.exists(os.path.join(sdir, tr, "inputs", "emg_filtered_normalised.mot"))
        for tr in trials) if trials else False
    if not do_normalise:
        print(f"  [CEINMS] EMG normalise disabled (enable_emg_normalise=False).")
    elif not replace and _norm_all_present:
        print(f"  [skip] EMG normalise: all {len(trials)} trials already normalised.")
    else:
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


def _run_scaling(subj, sdir, session, config, u, replace=True):
    """Scale a subject's generic model for ONE session, producing the models the
    Subject references. Three stages, matching the naming convention:

        generic  --scale-->  scaled.osim
                 --Modenese2015 muscle-opt (N_eval)-->  scaled_opt_N<N>.osim   (= model_ceinms)
                 --isometric-force x factor-->            <model_so>            (e.g. *_mvicx3.00.osim)

    The static trial is taken from ``BatchSettings.static_trials[session]`` (a
    ``{session: static_trial_name}`` map), else the Subject's ``static_trial``,
    else the first trial folder whose name starts with 'static'. Outputs go to
    ``models/<subject>/<session>/``. Returns the final model path, or None."""
    from bioscout.utils import get_openSim as _get_os; _os = _get_os()
    import shutil

    generic = subj.generic_model_path()
    if not generic or not os.path.exists(generic):
        print(f"  [scale ERROR] generic model not found for {subj.name}: "
              f"{subj.generic_model!r} -> {generic}")
        return None

    # Resolve the static trial for this session.
    smap = getattr(config, "static_trials", None) or {}
    static_name = smap.get(session) or getattr(subj, "static_trial", None)
    if not static_name:
        static_name = next((d for d in sorted(os.listdir(sdir))
                            if d.lower().startswith("static")
                            and os.path.isdir(os.path.join(sdir, d))), None)
    if not static_name:
        print(f"  [scale ERROR] no static trial for {subj.name}/{session} "
              f"(set BatchSettings.static_trials['{session}'])")
        return None
    static_dir = os.path.join(sdir, static_name)
    trc = os.path.join(static_dir, "inputs", TRC)
    if not os.path.exists(trc):
        try:
            subj.make_trial(static_dir).export_c3d()
        except Exception as e:
            print(f"  [scale] static export failed: {e}")
    if not os.path.exists(trc):
        print(f"  [scale ERROR] static TRC not found: {trc}")
        return None

    model_dir = os.path.join(str(u.MODELS_DIR), subj.name, session)
    os.makedirs(model_dir, exist_ok=True)
    final = os.path.join(model_dir, subj.model_so or f"{subj.name}.osim")
    if os.path.exists(final) and not replace:
        print(f"  [skip] scaled model already exists: {final}")
        return final

    markerset = getattr(config, "markerset", None)
    print(f"  [scale] {subj.name}/{session}: {os.path.basename(generic)} "
          f"+ static '{static_name}' -> {os.path.basename(final)}")

    # Scaling-stage toggles (per-subject; map to OpenSim ScaleTool stages).
    linear_scaling = bool(getattr(subj, "linear_scaling", True))
    marker_placer  = bool(getattr(subj, "marker_placer", False))
    prescaled      = getattr(subj, "prescaled_model", None)

    def _resolve_model(pth):
        if not pth:
            return None
        if os.path.isabs(pth) and os.path.exists(pth):
            return pth
        pd = getattr(u, "PROJECT_DIR", None) or os.getcwd()
        for base in (str(u.MODELS_DIR), os.path.join(pd, "generic models"), pd):
            cand = os.path.join(base, pth)
            if os.path.exists(cand):
                return cand
        return pth

    # 1) build the model that muscle-opt starts from. A prescaled/MRI model is
    #    already geometry-personalised → never dimensionally scale it; only the
    #    marker placer may run. Otherwise honour linear_scaling/marker_placer.
    scaled = os.path.join(model_dir, "scaled.osim")
    if prescaled:
        scale_input = _resolve_model(prescaled)
        linear_scaling = False
        print(f"  [scale] {subj.name}: prescaled model (no geometric scaling): "
              f"{os.path.basename(scale_input or prescaled)}")
    else:
        scale_input = generic
    _os.scale_model(scale_input, trc, scaled, scale_setup_output_dir=model_dir,
                    marker_set_file=markerset,
                    linear_scaling=linear_scaling, marker_placer=marker_placer)

    # 2) muscle-parameter optimisation (Modenese 2015) -> scaled_opt_N<N>.osim
    #    Reference is the generic template even for a prescaled model (preserves
    #    the template's muscle operating range in the personalised geometry).
    n_eval = int(getattr(config, "muscle_opt_neval", 10) or 10)
    opt = os.path.join(model_dir, f"scaled_opt_N{n_eval}.osim")
    _os.muscle_optimimizer_Modenese2015(scaled, save_path=opt,
                                        ref_model_path=generic, N_eval=n_eval)

    # 3) isometric-force scaling x factor -> final (named as subj.model_so)
    factor = float(getattr(config, "muscle_force_factor", 1.0) or 1.0)
    if factor and factor != 1.0:
        _os.increase_isometric_force(opt, muscleList="all", factor=factor)
        produced = opt.replace(".osim", f"_increased_{factor:.2f}.osim")
        if os.path.exists(produced) and os.path.abspath(produced) != os.path.abspath(final):
            shutil.copyfile(produced, final)
    elif os.path.abspath(opt) != os.path.abspath(final):
        shutil.copyfile(opt, final)

    print(f"  [scale OK] {subj.name}/{session} -> {final}")
    return final


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

    # Honour BatchSettings switches. ``replace_existing=False`` makes every stage
    # SKIP trials that already have their outputs (resume a partial run without
    # redoing finished trials).
    _bs = getattr(getattr(proj, "settings", None), "BatchSettings", None)
    replace   = bool(getattr(_bs, "replace_existing", replace))
    do_export = bool(getattr(_bs, "enable_c3d_export", True))
    do_norm   = bool(getattr(_bs, "enable_emg_normalise", True))
    # Per-stage switches (external biomechanics = IK + ID; SO implies muscle
    # moments + JRA). Any stage left True runs; set the rest False to stop early.
    do_ik = bool(getattr(_bs, "enable_inverse_kinematics", True))
    do_id = bool(getattr(_bs, "enable_inverse_dynamics", True))
    do_ma = bool(getattr(_bs, "enable_muscle_analysis", True))
    do_so = bool(getattr(_bs, "enable_static_optimization", True))
    # Scaling runs only when BOTH the run flag (RUN_SCALING -> `scale`) and the
    # per-project enable_scale_model switch are on.
    do_scale = bool(scale) and bool(getattr(_bs, "enable_scale_model", True))
    print(f"[pipeline] full-resolution, non-destructive run; "
          f"project={project_dir}; scale={do_scale}; ceinms={ceinms}; "
          f"replace={replace}; export_c3d={do_export}; emg_normalise={do_norm}; "
          f"IK={do_ik} ID={do_id} MA={do_ma} SO={do_so}")

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
                  and _has_raw_inputs(os.path.join(sdir, d))]
        # Honour BatchSettings.trial_list if the project restricts the run to a
        # subset (e.g. walks first). Empty/None = run every trial found on disk.
        _wanted = getattr(getattr(proj, "settings", None), "BatchSettings", None)
        _wanted = getattr(_wanted, "trial_list", None)
        if _wanted:
            trials = [t for t in trials if t in set(_wanted)]
        print(f"\n==================  {subj.name}/{session}: {len(trials)} trials  ==================")
        if not trials:
            print(f"  [skip] {subj.name}/{session}: no trials with raw inputs "
                  f"(inputs/{C3D} or inputs/{TRC}) — skipping SO + CEINMS.")
            continue

        # A subject/session runs as a CLEAR, LINEAR sequence of named stages.
        # Each stage is gated by its enable flag and skips finished work when
        # replace=False. Order matters (each stage consumes the previous output).
        def _mk(tr):
            return subj.make_trial(os.path.join(sdir, tr))

        # ---- STAGE 1 · export_c3d (raw c3d -> markers/GRF/EMG per trial) ----
        if do_export:
            print(f"\n---- export_c3d · {subj.name}/{session} ----")
            for tr in trials:
                tp = os.path.join(sdir, tr)
                if not (os.path.exists(os.path.join(tp, "inputs", C3D))
                        or os.path.exists(os.path.join(tp, C3D))):
                    continue
                if not replace and all(os.path.exists(os.path.join(tp, "inputs", f))
                                       for f in (TRC, "emg_filtered.mot")):
                    print(f"  [skip] {tr}: already exported"); continue
                try:
                    _mk(tr).export_c3d(); print(f"  [ok] {tr}")
                except Exception as e:
                    print(f"  [ERROR] export_c3d {tr}: {e}")

        # ---- STAGE 2 · run_scale_model (scale -> muscle-opt -> MVIC) --------
        if do_scale:
            print(f"\n---- run_scale_model · {subj.name}/{session} ----")
            try:
                _run_scaling(subj, sdir, session, _bs, u, replace=replace)
            except Exception as e:
                print(f"  [ERROR] scale_model: {e}")

        # ---- STAGE 3 · run_emg_normalise (session-wide MVC normalisation) ---
        if do_norm:
            _all_norm = bool(trials) and all(
                os.path.exists(os.path.join(sdir, tr, "inputs",
                               "emg_filtered_normalised.mot")) for tr in trials)
            if not replace and _all_norm:
                print(f"\n---- run_emg_normalise · [skip] all trials normalised ----")
            else:
                print(f"\n---- run_emg_normalise · {subj.name}/{session} ----")
                try:
                    sess.normalise_emg(replace=replace)
                except Exception as e:
                    print(f"  [ERROR] emg_normalise: {e}")

        # ---- STAGE 4 · run_external_biomechanics (IK + ID) ------------------
        if do_ik or do_id:
            print(f"\n---- run_external_biomechanics (IK+ID) · {subj.name} ----")
            for tr in trials:
                try:
                    t = _mk(tr)
                    if do_ik: t.run_ik(replace=replace)
                    if do_id: t.run_id(replace=replace)
                except Exception as e:
                    print(f"  [ERROR] external_biomechanics {tr}: {e}")

        # ---- STAGE 5 · run_muscle_analysis ----------------------------------
        if do_ma:
            print(f"\n---- run_muscle_analysis · {subj.name} ----")
            for tr in trials:
                try:
                    _mk(tr).run_ma(replace=replace)
                except Exception as e:
                    print(f"  [ERROR] muscle_analysis {tr}: {e}")

        # ---- STAGE 6 · run_static_optimisation (+ JRA on SO forces) ---------
        if do_so:
            print(f"\n---- run_static_optimisation (+JRA) · {subj.name} ----")
            for tr in trials:
                try:
                    t = _mk(tr)
                    t.run_so(replace=replace)
                    t.calculate_muscle_moments(forces_type="so")
                    t.run_jra(replace=replace)
                except Exception as e:
                    print(f"  [ERROR] static_optimisation {tr}: {e}")

        # ---- STAGE 7 · run_ceinms_calibration (once per session) ------------
        if ceinms:
            print(f"\n---- run_ceinms_calibration · {subj.name}/{session} ----")
            try:
                sess.calibrate(replace=replace, calibration_trials=(
                    list(calibration_trials) if calibration_trials else None))
            except Exception as e:
                print(f"  [ERROR] ceinms_calibration: {e}")

        # ---- STAGE 8 · run_ceinms (per-trial execution + JRA on CEINMS) -----
        if ceinms:
            print(f"\n---- run_ceinms (+JRA) · {subj.name} ----")
            for tr in trials:
                try:
                    t = subj.make_trial(os.path.join(sdir, tr), force_type="CEINMS")
                    t.run_ceinms_exe()
                    t.calculate_muscle_moments(forces_type="ceinms")
                    t.run_jra_ceinms(replace=replace)
                except Exception as e:
                    print(f"  [ERROR] ceinms {tr}: {e}")

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
                  and _has_raw_inputs(os.path.join(sdir, d))]
        print(f"\n====  CEINMS  {subj.name}/{session}: {len(trials)} trials  ====")
        if not trials:
            print(f"  [skip] {subj.name}/{session}: no trials with raw inputs.")
            continue
        try:
            _run_session_ceinms(subj, sess, sdir, trials, calibration_trials, replace)
        except Exception as e:
            print(f"  [CEINMS ERROR] {subj.name}: {e}")
    print("\n====  CEINMS-ONLY DONE  ====")
    return True


# ===========================================================================
# Session-centric runner (BioScout 2.x) — reads session.xml, loops MODEL x TRIAL.
# Additive: does NOT replace run_pipeline. v1 covers export -> IK -> ID -> MA ->
# SO(+JRA) per model; CEINMS is added in v2. Model creation (scaling) is a
# separate step — each session.xml model must already point to an existing .osim.
# ===========================================================================
def _live(msg):
    """Transient one-line status on the CONSOLE only (not the log file):
    ``[running] <msg>`` overwritten in place via carriage return."""
    try:
        sys.__stdout__.write(f"\r[running] {msg}\x1b[K")
        sys.__stdout__.flush()
    except Exception:
        pass


def _live_clear():
    try:
        sys.__stdout__.write("\r\x1b[K")
        sys.__stdout__.flush()
    except Exception:
        pass


def _quiet_opensim():
    """Reduce OpenSim's C++ logging (it bypasses the Python log filter). Keeps
    warnings/errors, drops the per-frame [info] SO/assembly chatter."""
    try:
        import opensim as _os
        _os.Logger.setLevel(_os.Logger.Level_Warn)
    except Exception:
        pass


def _c3d_for_trial(project_dir, spec, trial):
    """Locate a trial's raw .c3d: the session's own c3d folder first, else
    <project>/<c3d dir>/<subject>/<session>/<trial>.c3d. Both the numbered
    (`1_c3dfiles`) and plain (`c3dfiles`) names are accepted."""
    from bioscout.utils.session_layout import C3D_DIRS, c3d_root

    cands = []
    if spec.path:
        cands.append(os.path.join(c3d_root(spec.path), f"{trial}.c3d"))
    for name in C3D_DIRS:
        cands.append(os.path.join(project_dir, name, spec.subject,
                                  spec.session, f"{trial}.c3d"))
    return next((c for c in cands if os.path.isfile(c)), None)


def run_sessions(project_dir=None, replace=None, models=None, trials=None,
                 subjects=None):
    """Run analysis for every ``session.xml`` — layout B: ONE model per session
    folder, FLAT trial folders (no per-model subdir).

    For each ``simulations/<folder>/<session>/session.xml`` this imports each
    trial's raw c3d from the session's ``<c3d_source>`` into ``<trial>/inputs/``,
    exports it (markers/GRF/EMG), then runs export->IK->ID->MA->SO(+JRA) into the
    trial folder. The raw ``.c3d`` is NOT kept in ``inputs/``. ``subject`` / model
    are metadata on the session (stats group by ``subject``). ``Analyse`` unchanged.

    Filters: ``subjects`` (athlete) / ``models`` (model name) / ``trials``; each
    defaults to the matching ``BatchSettings`` value."""
    import bioscout
    import shutil
    from bioscout.utils.session import discover_session_specs

    # Absolute: Analyse chdir()s into the trial folder, so model/setup/source
    # paths must be absolute or they resolve relative to the wrong directory.
    project_dir = os.path.abspath(project_dir or os.getcwd())
    proj = bioscout.Project(project_dir)
    u = proj.utils
    _quiet_opensim()          # hush OpenSim's per-frame C++ chatter (bypasses tee)
    sim = str(u.SIMULATIONS_DIR)
    _stg = getattr(proj, "settings", None)
    bs = getattr(_stg, "BatchSettings", None)

    if replace is None:
        replace = bool(getattr(bs, "replace_existing", True))
    do_export = bool(getattr(bs, "enable_c3d_export", True))
    do_ik = bool(getattr(bs, "enable_inverse_kinematics", True))
    do_id = bool(getattr(bs, "enable_inverse_dynamics", True))
    do_ma = bool(getattr(bs, "enable_muscle_analysis", True))
    do_so = bool(getattr(bs, "enable_static_optimization", True))
    do_ceinms = bool(getattr(_stg, "RUN_CEINMS", True))

    def _norm(v):  # 'all'/None -> None (no filter); str -> [str]; list -> list
        if v is None:
            return None
        if isinstance(v, str):
            return None if v.strip().lower() == "all" else [v]
        return list(v) or None

    want_subjects = _norm(subjects if subjects is not None else getattr(bs, "RUN_SUBJECTS", "all"))
    want_models = _norm(models if models is not None else getattr(bs, "RUN_MODELS", "all"))
    want_trials = _norm(trials if trials is not None else (getattr(bs, "trial_list", None) or None))

    specs = [s for s in discover_session_specs(sim) if s.models]   # need a model
    if want_subjects:
        specs = [s for s in specs if s.subject in set(want_subjects)]
    if want_models:
        specs = [s for s in specs if s.models[0].name in set(want_models)]
    print(f"[run_sessions] {len(specs)} session(s); replace={replace}; "
          f"IK={do_ik} ID={do_id} MA={do_ma} SO={do_so} CEINMS={do_ceinms}")

    _ok = _err = 0
    for spec in specs:
        sdir = spec.path
        model = spec.models[0]
        abs_model = model.model if os.path.isabs(model.model) \
            else os.path.join(project_dir, model.model)
        if not os.path.isfile(abs_model):
            print(f"  [ERROR] {spec.subject}/{model.name}: model not found -> {abs_model}")
            continue
        setup_dir = (spec.setup_folder if (spec.setup_folder and os.path.isabs(spec.setup_folder))
                     else os.path.join(project_dir, spec.setup_folder or "setupFiles"))
        csrc = spec.c3d_source
        csrc = (csrc if (csrc and os.path.isabs(csrc))
                else (os.path.join(project_dir, csrc) if csrc else None))
        trs = list(spec.trials.keys())
        if want_trials:
            trs = [t for t in trs if t in set(want_trials)]
        print(f"\n==================  {spec.subject} / {model.name} / {spec.session}: "
              f"{len(trs)} trial(s)  ==================")

        for tr in trs:
            work = os.path.join(sdir, tr)               # FLAT trial folder
            print(f"  {tr}")
            t = None
            failed = False

            def _stage(name, enabled, fn):
                # Print every stage so the log shows the full sequence; 'skip' for
                # disabled/upstream-failed stages. Live [running] status on console.
                nonlocal failed
                if not enabled:
                    print(f"    {name:16s} skip"); return
                if failed:
                    print(f"    {name:16s} skip (upstream failed)"); return
                _live(f"{model.name}/{tr}: {name}")
                try:
                    fn(); _live_clear(); print(f"    {name:16s} ok")
                except Exception as e:
                    _live_clear(); print(f"    {name:16s} ERROR: {e}"); failed = True

            # Model scaling is a standalone step (not run by the analysis pipeline).
            print(f"    {'run_scale_model':16s} skip (standalone)")

            def _export():
                nonlocal t
                os.makedirs(os.path.join(work, "inputs"), exist_ok=True)
                src = (os.path.join(csrc, f"{tr}.c3d") if csrc
                       else _c3d_for_trial(project_dir, spec, tr))
                if not (src and os.path.isfile(src)):
                    raise FileNotFoundError("no c3d in source")
                shutil.copy2(src, os.path.join(work, "inputs", C3D))
                t = u.Analyse(work)
                t.update_trial_attribute("model_dir", abs_model)
                t.update_trial_attribute("setup_dir", setup_dir)
                if spec.body_mass is not None:
                    t.update_trial_attribute("body_mass", spec.body_mass)
                t.export_c3d()
                try:
                    os.remove(os.path.join(work, "inputs", C3D))   # don't keep raw c3d
                except OSError:
                    pass
                tw = (spec.trials.get(tr) or {}).get("time_range")
                if tw:
                    t.update_trial_attribute("time_range", list(tw)); t.time_range = list(tw)

            _stage("export_c3d", do_export, _export)
            if t is None and not failed:      # export disabled -> attach to existing folder
                t = u.Analyse(work)
                t.update_trial_attribute("model_dir", abs_model)
                t.update_trial_attribute("setup_dir", setup_dir)

            def _so():
                t.run_so(replace=replace)
                t.calculate_muscle_moments(forces_type="so")
                t.run_jra(replace=replace)

            _stage("IK", do_ik, lambda: t.run_ik(replace=replace))
            _stage("ID", do_id, lambda: t.run_id(replace=replace))
            _stage("MA", do_ma, lambda: t.run_ma(replace=replace))
            _stage("SO+JRA", do_so, _so)
            if failed:
                _err += 1
            else:
                _ok += 1

        # ---- CEINMS (session-level): normalise EMG -> calibrate -> per-trial
        # execution + CEINMS moments + JRA. Reuses the tested _run_session_ceinms
        # via a folder-scoped Subject/Session; the session's model_ceinms is used.
        if do_ceinms and trs:
            try:
                from bioscout.utils.analysis import Subject as _Subject
                folder = os.path.basename(os.path.dirname(sdir))   # e.g. Athlete_03_Cateli
                sname = os.path.basename(sdir)                     # e.g. 25_03_31
                _ceinms_model = model.model_ceinms or model.model
                _subj = _Subject(name=folder, session=sname,
                                 model_so=os.path.basename(model.model),
                                 model_ceinms=os.path.basename(_ceinms_model),
                                 setup_folder=setup_dir)
                _sess = _subj.get_session(sname)
                print(f"\n----  run_ceinms  {spec.subject} / {model.name}  ----")
                # Session-level: normalise EMG across trials, then calibrate on the
                # run trials that have muscle-analysis data (exclude static/quiet).
                cal = [t for t in trs if "static" not in t.lower()] or list(trs)
                _sess.normalise_emg(replace=replace)
                _sess.calibrate(replace=replace, calibration_trials=cal)
                # Per trial: execution + CEINMS moments + JRA on the SAME object,
                # so run_ceinms_exe sets jra_forces_ceinms before it's read.
                for tr in trs:
                    try:
                        tt = _subj.make_trial(os.path.join(sdir, tr), force_type="CEINMS")
                        tt.run_ceinms_exe()
                        tt.calculate_muscle_moments(forces_type="ceinms")
                        tt.run_jra_ceinms(replace=replace)
                        print(f"  [ok] {tr}  (CEINMS+JRA)")
                        _ok += 1
                    except Exception as e:
                        print(f"  [ERROR] {tr} CEINMS: {e}")
                        _err += 1
            except Exception as e:
                print(f"  [ERROR] {spec.subject}/{model.name} CEINMS: {e}")
                _err += 1

    print(f"\n==================  SESSIONS DONE — {_ok} ok, {_err} error(s)  ==================")
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
