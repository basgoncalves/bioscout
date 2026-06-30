#!/usr/bin/env python3
"""
BioScout — Biomechanical analysis and movement scouting for coaches and athletes.

GUI mode (default):
    python -m bioscout
    python -m bioscout --gui

Batch mode:
    python -m bioscout -b settings.py
    python -m bioscout -b /path/to/project/settings.py

Init mode (scaffold a new project):
    python -m bioscout --init /path/to/new/project
"""

import sys
import os
import re
import argparse
import traceback
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from settings import BatchSettings, CEINMSSettings
from utils.model_scaler import ModelScaler
import utils

# Ensure utils.openSim is loaded — the deferred-import block at the bottom of
# utils/__init__.py sets it, but it can silently remain None if the relative
# import fails (circular-import race).  We guarantee it here, after all
# top-level imports are complete.
if getattr(utils, 'openSim', None) is None:
    try:
        import importlib.util as _ilu
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'utils', 'openSim.py')
        _spec = _ilu.spec_from_file_location('utils.openSim', _p)
        _mod = _ilu.module_from_spec(_spec)
        sys.modules['utils.openSim'] = _mod
        _spec.loader.exec_module(_mod)
        utils.openSim = _mod
        print(f"[main] utils.openSim loaded via importlib: {_mod}", flush=True)
    except Exception as _e:
        print(f"[main] WARNING: could not load utils.openSim: {_e}", flush=True)
else:
    print(f"[main] utils.openSim already loaded: {utils.openSim}", flush=True)

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Biomechanical Analysis")
parser.add_argument('-b', '--batch', type=str, help="Path to batch settings file (batch mode)")
parser.add_argument('-g', '--gui',   action='store_true', help="Launch GUI (default when no flags given)")
parser.add_argument('--init', type=str, metavar='PROJECT_PATH',
                    help="Initialise a new project: create folder structure and copy settings template")
parser.add_argument('--add_subject', type=str, nargs='?', const='.', metavar='PROJECT_PATH',
                    help="Interactively add a subject to subjects.json in PROJECT_PATH (default: cwd)")
parser.add_argument('--install', action='store_true',
                    help="Check dependencies and install missing ones (opensim via conda, others via pip)")
parser.add_argument('--summary', nargs='?', const='', default=None, metavar='SETTINGS_OR_PROJECT',
                    help="Build kinematics/kinetics summaries. Optionally pass a settings.py "
                         "or project path; defaults to ./settings.py then the package settings.")
parser.add_argument('-overall', '--overall', dest='overall', action='store_true',
                    help="With --summary: only (re)build the overall plots/metrics in <project>/summary")
parser.add_argument('-s', '--subject', type=str, default=None, metavar='SUBJECT_ID',
                    help="With --summary: restrict to one subject (e.g. -s 012)")
parser.add_argument('-t', '--trial', type=str, default=None, metavar='TRIAL_PATH',
                    help="With --summary: build only this one trial folder (fast iteration)")
parser.add_argument('--shots', type=str, default=None, metavar='VIDEO',
                    help="Basketball shot analysis: count shots, per-shot kinematics (0-100%%), "
                         "assisted made/missed tagging, kinematics-only muscle forces")
parser.add_argument('--shooting-hand', type=str, default='right', choices=['right', 'left'],
                    help="With --shots: which hand releases the ball (default: right)")
parser.add_argument('--poses', type=str, default=None, metavar='POSES_JSON',
                    help="With --shots: precomputed {frame:{landmark:[x,y]}} JSON (skip MediaPipe). "
                         "A poses.json is written to the output folder on every run for re-tuning.")
parser.add_argument('--fps', type=float, default=None,
                    help="With --shots: override the video frame rate (e.g. 5 for 5 fps footage)")
parser.add_argument('--min-gap', type=float, default=1.5, dest='min_gap',
                    help="With --shots: minimum seconds between detected shots (default 1.5)")
parser.add_argument('--n-points', type=int, default=1000, dest='n_points',
                    help="With --shots: samples per shot for the smooth 0-100%% curves (default 1000)")
parser.add_argument('--hoop-side', type=str, default='auto', dest='hoop_side',
                    choices=['auto', 'right', 'left'],
                    help="With --shots: which side the hoop is on (ball flies toward it). Default auto")
parser.add_argument('--yolo-model', type=str, default=None, dest='yolo_model', metavar='WEIGHTS.pt',
                    help="With --shots: YOLO (ultralytics) ball+hoop model -> robust avishah3-style "
                         "shot/make detection. `pip install ultralytics` and supply a trained model.")
parser.add_argument('--hoop', type=str, default=None, metavar='CX,CY,W,H',
                    help="With --shots: rim box (pixels) for hoop-based detection without YOLO "
                         "(uses HSV ball + this hoop). E.g. --hoop 955,235,70,40")
parser.add_argument('-p', '--project', type=str, default=None, metavar='PROJECT_PATH',
                    help="With --summary: project root override (defaults to settings.PROJECT_ROOT)")
parser.add_argument('--load-report', type=str, default=None, dest='load_report',
                    metavar='FILES_OR_FOLDER',
                    help="Training-load & fatigue report from fitness-tracker exports "
                         "(.fit/.tcx/.gpx/.csv). Pass a folder, a glob, or files. "
                         "e.g. --load-report C:/zepp_exports/")
parser.add_argument('--load-out', type=str, default=None, dest='load_out', metavar='PDF',
                    help="With --load-report: output PDF path (default: load_report.pdf)")
parser.add_argument('--hr-max', type=float, default=None, dest='hr_max',
                    help="With --load-report: athlete max heart rate (else 220-age)")
parser.add_argument('--hr-rest', type=float, default=None, dest='hr_rest',
                    help="With --load-report: athlete resting heart rate (default 60)")
parser.add_argument('--age', type=int, default=None, dest='age',
                    help="With --load-report: athlete age (for HRmax fallback)")
parser.add_argument('--sex', type=str, default='M', choices=['M', 'F'], dest='sex',
                    help="With --load-report: athlete sex (Banister TRIMP constant)")
parser.add_argument('--zepp-pull', action='store_true', dest='zepp_pull',
                    help="Pull workouts straight from your Zepp/Huami cloud account "
                         "(needs a captured apptoken in the credentials file), then "
                         "build the load report.")
parser.add_argument('--strava-pull', action='store_true', dest='strava_pull',
                    help="Pull activities from Strava (Zepp→Strava sync), then build "
                         "the load report. Needs Strava creds in the credentials file.")
parser.add_argument('--creds', type=str, default=None, dest='creds', metavar='JSON',
                    help="Path to the cloud credentials JSON "
                         "(default ~/.bioscout/load_credentials.json)")
args = parser.parse_args()

log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)
# Use the single application logger (AppLogger). It writes one timestamped file
# per run — app_*.log for GUI, batch_*.log for batch (-b/--batch) — so we no
# longer create an empty second log via helpers.setup_logging.
from utils.logger import logger

# In batch mode redirect logs to the project's LOG_DIR (PROJECT_ROOT/logs)
# so analysis logs don't accumulate inside the app install directory.
if args.batch:
    try:
        from settings import LOG_DIR as _PROJECT_LOG_DIR
        logger.set_project_log_dir(_PROJECT_LOG_DIR)
    except Exception as _log_err:
        logger.warning(f"Could not redirect to project log dir: {_log_err}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _trial_subdir(c3d_path: Path) -> str:
    """Return the trial subdirectory (a folder named after the trial stem)."""
    name = c3d_path.stem
    parent = c3d_path.parent
    subdir = parent if parent.name == name else parent / name
    return str(subdir)


def _run_step(trial: 'utils.Analyse', step_name: str, method_name: str) -> bool:
    """Call trial.<method_name>() and log the outcome. Returns True on success."""
    logger.info(f"    {step_name}...")
    try:
        getattr(trial, method_name)()
        logger.info(f"    [OK] {step_name}")
        return True
    except Exception as e:
        logger.error(f"    [ERROR] {step_name}: {e}")
        logger.debug(traceback.format_exc())
        return False


def _should_skip(trial_name: str, config) -> bool:
    """Return True if this trial should be skipped.

    Logic (both lists are optional / can be left empty):
      - If ``trials_to_run`` is non-empty, only trials whose name contains
        at least one entry are processed; everything else is skipped.
      - If ``trials_to_skip`` is non-empty, any trial whose name contains
        at least one entry is skipped (applied after the whitelist check).
    Static trials are never affected here — callers guard them separately.
    """
    run_list  = getattr(config, 'trials_to_run',  []) or []
    skip_list = getattr(config, 'trials_to_skip', []) or []

    # Whitelist: if populated, trial must match at least one entry
    if run_list and not any(s in trial_name for s in run_list):
        return True

    # Blacklist
    if any(s in trial_name for s in skip_list):
        return True

    return False


def _trc_is_valid(trc_path: str):
    """Return (True, 'ok') if the TRC has ≥1 marker and ≥1 frame, else (False, reason)."""
    if not os.path.exists(trc_path):
        return False, f"file not found: {trc_path}"
    try:
        with open(trc_path, 'r') as fh:
            lines = fh.readlines()
        if len(lines) < 3:
            return False, "file has fewer than 3 lines"
        # Line 3 (index 2): DataRate CameraRate NumFrames NumMarkers Units ...
        vals = lines[2].strip().split('\t')
        num_frames  = int(float(vals[2]))
        num_markers = int(float(vals[3]))
        if num_markers == 0:
            return False, f"NumMarkers=0 in TRC header"
        if num_frames == 0:
            return False, f"NumFrames=0 in TRC header"
        return True, "ok"
    except Exception as exc:
        return False, f"could not parse TRC header: {exc}"


def _validate_step_inputs(trial: 'utils.Analyse', step: str) -> tuple:
    """Check that all required input files exist and are valid for *step*.

    Returns (is_valid: bool, issues: list[str]).

    Steps checked: 'IK', 'ID', 'SO', 'MA'.
    """
    issues = []
    trc_abs  = os.path.join(trial.path, trial.markers) if not os.path.isabs(trial.markers) else trial.markers
    grf_abs  = os.path.join(trial.path, trial.grf_mot) if not os.path.isabs(trial.grf_mot) else trial.grf_mot
    ik_abs   = os.path.join(trial.path, trial.ik)      if not os.path.isabs(trial.ik)      else trial.ik
    id_abs   = os.path.join(trial.path, trial.id)      if not os.path.isabs(trial.id)      else trial.id

    if step == 'IK':
        ok, reason = _trc_is_valid(trc_abs)
        if not ok:
            issues.append(f"marker TRC invalid — {reason}")

    elif step == 'ID':
        if not os.path.exists(ik_abs):
            issues.append(f"IK output missing: {ik_abs}")
        if not os.path.exists(grf_abs):
            issues.append(f"GRF .mot missing: {grf_abs}")

    elif step == 'SO':
        if not os.path.exists(ik_abs):
            issues.append(f"IK output missing (needed by SO): {ik_abs}")
        if not os.path.exists(id_abs):
            issues.append(f"ID output missing (needed by SO): {id_abs}")

    elif step == 'MA':
        if not os.path.exists(ik_abs):
            issues.append(f"IK output missing (needed by MA): {ik_abs}")

    return len(issues) == 0, issues


def _norm(s: str) -> str:
    """Lowercase and strip non-alphanumerics so 'Static_01' == 'static01'."""
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def _is_static(trial_stem: str, static_name: Optional[str]) -> bool:
    """
    Tolerant static-trial match. Handles naming variants like 'static01',
    'static_01', 'Static_01' by normalising both sides.

    - If static_name is given, matches stems whose normalised form contains it.
    - If static_name is None/empty, matches any stem that starts with 'static'.
    """
    stem_n = _norm(trial_stem)
    if static_name:
        return _norm(static_name) in stem_n
    return stem_n.startswith('static')


def _resolve_static_name(session_dir: Path, requested: Optional[str]) -> Optional[str]:
    """
    Return the actual static trial stem found in a session, or the requested
    name if no C3D match is found (so downstream errors are still clear).
    """
    c3d = sorted(session_dir.glob('*.c3d'))
    for f in c3d:
        if _is_static(f.stem, requested):
            return f.stem
    return requested


# ---------------------------------------------------------------------------
# Main batch function
# ---------------------------------------------------------------------------
def _discover_sessions(config) -> list:
    """
    Resolve sessions to process as a list of (session_dir, static_name) from
    config.sessions — the single source of truth.

    config.sessions may be:
      • a dict {session_path: static_trial_name}   (static_name None = auto-detect)
      • a list/tuple [session_path, ...]           (static auto-detected each)

    Static matching is tolerant (case/underscores ignored). When static_name is
    None, any trial whose name starts with 'static' (static01 / static_01 /
    Static_01) is used.
    """
    sessions = getattr(config, "sessions", None)
    if not sessions:
        return []
    if isinstance(sessions, dict):
        return [(Path(p), sn or None) for p, sn in sessions.items()]
    # plain list/tuple of session paths
    return [(Path(p), None) for p in sessions]


def _load_settings_from_path(settings_path: str):
    """Load BatchSettings / CEINMSSettings from an arbitrary settings .py file.

    Lets `-b path/to/settings_xyz.py` actually use that file (e.g.
    settings_teaching.py) instead of always the default settings.py. Falls back
    to the already-imported defaults if the path is missing or lacks the classes.
    """
    global BatchSettings, CEINMSSettings
    try:
        p = Path(settings_path)
        if not (p.suffix == '.py' and p.is_file()):
            # Try resolving relative to the package directory.
            alt = Path(__file__).parent / p.name
            if alt.is_file():
                p = alt
            else:
                logger.warning(
                    f"Settings file '{settings_path}' not found; using default "
                    f"settings.py.")
                return
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location('_batch_settings_module', str(p))
        mod = _ilu.module_from_spec(spec)
        sys.modules['_batch_settings_module'] = mod
        spec.loader.exec_module(mod)
        if hasattr(mod, 'BatchSettings'):
            BatchSettings = mod.BatchSettings
        if hasattr(mod, 'CEINMSSettings'):
            CEINMSSettings = mod.CEINMSSettings
        # Propagate into the `settings` module so other modules that read
        # `settings.BatchSettings` (e.g. utils/openSim.py for marker weights)
        # use the loaded config, not the default settings.py.
        try:
            import settings as _settings_mod
            if hasattr(mod, 'BatchSettings'):
                _settings_mod.BatchSettings = mod.BatchSettings
            if hasattr(mod, 'CEINMSSettings'):
                _settings_mod.CEINMSSettings = mod.CEINMSSettings
        except Exception as _pe:
            logger.warning(f"Could not propagate settings to 'settings' module: {_pe}")
        logger.info(f"Loaded batch settings from: {p}")
    except Exception as e:
        logger.warning(f"Could not load settings from '{settings_path}': {e}; "
                       f"using default settings.py.")


def _load_settings_module(settings_path: str):
    """Import an arbitrary settings .py file and return the module object.

    Used to read project-level flags (RUN_PIPELINE / RUN_SUMMARY / RUN_SCALING)
    that live at module scope (outside the BatchSettings class). Returns None if
    the file can't be loaded.
    """
    try:
        p = Path(settings_path)
        if not (p.suffix == '.py' and p.is_file()):
            alt = Path(__file__).parent / p.name
            if not alt.is_file():
                return None
            p = alt
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location('_project_settings_flags', str(p))
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        logger.warning(f"Could not read project flags from '{settings_path}': {e}")
        return None


def run_batch_mode(settings_path: str) -> bool:
    """Run the pipeline for one session or for every session inside a folder."""
    # Load the settings module specified by -b (e.g. settings_teaching.py).
    _load_settings_from_path(settings_path)

    config = BatchSettings

    # ------------------------------------------------------------------ #
    # PRE-FLIGHT: OpenSim must be importable, otherwise every OpenSim step
    # (C3D export, IK, ID, SO, energetics) fails one-by-one and floods the
    # log. Fail fast here with an actionable message instead.
    # ------------------------------------------------------------------ #
    if getattr(utils, 'openSim', None) is None:
        try:
            import opensim  # noqa: F401
        except Exception as _osim_err:
            logger.error("=" * 70)
            logger.error("OpenSim is not available in this Python environment.")
            logger.error(f"   import opensim -> {type(_osim_err).__name__}: {_osim_err}")
            logger.error("")
            logger.error("Every OpenSim step would fail, so the batch is aborting.")
            logger.error("Fix: install OpenSim into the SAME environment that runs")
            logger.error("BioScout, then re-run. With Python 3.11:")
            logger.error("     pip install opensim")
            logger.error("   or (any version):")
            logger.error("     conda install -c opensim-org opensim -y")
            logger.error("Verify with:  python -c \"import opensim; print(opensim.__version__)\"")
            logger.error(f"Interpreter in use: {sys.executable}")
            logger.error("=" * 70)
            return False

    sessions = _discover_sessions(config)
    if not sessions:
        logger.error(
            "No sessions to process. Add entries to SESSIONS in settings.py "
            "(a dict of {session_folder: static_trial_name}).")
        return False

    logger.info("=" * 70)
    logger.info("Biomechanical Analysis - Batch Processing")
    logger.info(f"Sessions to process : {len(sessions)}")
    for s, static_name in sessions:
        resolved = _resolve_static_name(s, static_name)
        logger.info(f"   • {s}   (static: {resolved or '??? not found'})")
    logger.info("=" * 70)

    all_ok = True
    for i, (session_dir, static_name) in enumerate(sessions, 1):
        resolved_static = _resolve_static_name(session_dir, static_name)
        logger.info("")
        logger.info("#" * 70)
        logger.info(f"# SESSION {i}/{len(sessions)} : {session_dir.name}")
        logger.info("#" * 70)
        # Derive subject name: for Simulations/PID/session structure the subject
        # is the parent dir (PID); for flat Simulations/PID structure it is the
        # dir itself.  We prefer the parent when it isn't the filesystem root.
        _subject_name = (session_dir.parent.name
                         if session_dir.parent != session_dir.parent.parent
                         else session_dir.name)
        try:
            ok = _run_one_session(session_dir, config, _subject_name,
                                  resolved_static)
            all_ok = all_ok and ok
        except Exception as e:
            logger.critical(f"Session {session_dir.name} crashed: {e}")
            logger.debug(traceback.format_exc())
            all_ok = False

    logger.info("=" * 70)
    logger.info(f"[OK] ALL SESSIONS FINISHED ({len(sessions)} processed)"
                if all_ok else "[WARN] Batch finished with some failures")
    logger.info("=" * 70)
    logger.info("Batch processing finished.")
    return all_ok


def _run_one_session(session_dir: Path, config, subject_name: str,
                     static_name: Optional[str] = None) -> bool:
    """Run the full pipeline for a single session folder.

    static_name is this session's static-trial stem (already resolved); falls
    back to config.static_trial_name when None.
    """
    if static_name is None:
        static_name = getattr(config, "static_trial_name", None)
    try:
        logger.info(f"Session folder : {session_dir}")
        logger.info(f"Static trial   : {static_name or '(auto: starts with static)'}")

        # ------------------------------------------------------------------ #
        # DISCOVERY
        # ------------------------------------------------------------------ #
        # Only look at C3D files directly in the session folder (not in trial subdirs,
        # which may contain copies created by the export step).
        c3d_files = sorted(session_dir.glob("*.c3d"))
        if not c3d_files:
            logger.warning(f"No C3D files found in {session_dir} — skipping")
            return False
        logger.info(f"Found {len(c3d_files)} C3D file(s)")

        # ------------------------------------------------------------------ #
        # PHASE 1: C3D EXPORT  (all trials — must happen before scaling)
        # ------------------------------------------------------------------ #
        # Build trial objects early so we can reuse them in later phases
        trial_objects: list = []
        for c3d_file in c3d_files:
            trial_subdir = _trial_subdir(c3d_file)
            os.makedirs(trial_subdir, exist_ok=True)
            trial = utils.Analyse(trial_subdir)
            trial.c3d = str(c3d_file.resolve())
            trial_objects.append(trial)

        if config.enable_c3d_export:
            logger.info("=" * 70)
            logger.info("C3D EXPORT  (all trials)")
            logger.info("=" * 70)
            for trial in trial_objects:
                is_static = _is_static(trial.trial, static_name)
                if _should_skip(trial.trial, config) and not is_static:
                    logger.info(f"  Skipping {trial.trial} (in trials_to_skip)")
                    continue
                logger.info(f"  {trial.trial}")
                ok = _run_step(trial, "C3D export", "export_c3d")
                # After export, refresh time_range from the newly created TRC so that
                # IK/ID setup files get the correct time window (settings XML was
                # written before the TRC existed, so time_range was 'None').
                if ok:
                    os.chdir(trial.path)
                    new_tr = trial.get_time_range()
                    if new_tr:
                        trial.time_range = new_tr
                        trial.update_trial_attribute('time_range', new_tr)
                        logger.info(f"    time_range updated: {float(new_tr[0]):.4f} – {float(new_tr[1]):.4f} s")
                # Static trial only needs TRC for scaling — skip EMG processing
                if not is_static:
                    _run_step(trial, "EMG filter", "run_emg_filter")

        # ------------------------------------------------------------------ #
        # PHASE 2: MODEL SCALING  (once per session, uses static TRC)
        # ------------------------------------------------------------------ #
        active_model = os.path.join(
            os.path.dirname(config.generic_model), f"{subject_name}.osim")
        if not os.path.exists(active_model):
            active_model = config.generic_model

        if config.enable_scale_model:
            logger.info("-" * 70)
            logger.info("MODEL SCALING")
            logger.info("-" * 70)
            try:
                statics = [f for f in c3d_files if _is_static(f.stem, static_name)]
                if not statics:
                    raise RuntimeError(
                        f"Static trial '{static_name or 'static*'}' not found "
                        f"in {session_dir}")

                static_subdir = _trial_subdir(statics[0])
                trc_file = os.path.join(static_subdir, "marker_experimental.trc")
                if not os.path.isfile(trc_file):
                    raise RuntimeError(f"Static TRC not found: {trc_file}")

                scaler = ModelScaler(
                    template_model_path=config.generic_model,
                    trc_file=trc_file,
                    destination_dir=static_subdir,
                    output_model_dir=os.path.dirname(config.generic_model),
                )
                scaler.output_model_filename = f"{subject_name}.osim"
                active_model, _ = scaler.run_scale(
                    marker_weights=getattr(config, 'marker_weights', None),
                    markerset_path=config.markerset,
                )
                logger.info(f"[OK] Scaled model: {active_model}")
            except Exception as e:
                logger.error(f"[CRITICAL] Model scaling failed: {e}")
                raise

        # Set scaled model on all trial objects now that it's known, and persist to
        # each trial's settings XML so that load_settings() inside run_ik/run_id/etc.
        # picks up the correct path rather than the stale default.
        for trial in trial_objects:
            trial.update_trial_attribute('model_dir', active_model)

        # ------------------------------------------------------------------ #
        # PHASE 3: PER-TRIAL ANALYSIS  — IK, ID, SO, MA
        # ------------------------------------------------------------------ #
        logger.info("=" * 70)
        logger.info("PER-TRIAL ANALYSIS")
        logger.info("=" * 70)

        for trial in trial_objects:
            trial_name = trial.trial
            logger.info("-" * 70)
            logger.info(f"Trial: {trial_name}")
            logger.info("-" * 70)

            if _should_skip(trial_name, config):
                logger.info(f"  Skipping (in trials_to_skip)")
                continue

            try:

                if config.enable_inverse_kinematics:
                    _ok, _issues = _validate_step_inputs(trial, 'IK')
                    if _ok:
                        _run_step(trial, "Inverse Kinematics", "run_ik")
                    else:
                        logger.warning(f"  [SKIP] IK — inputs invalid: {'; '.join(_issues)}")

                if config.enable_inverse_dynamics:
                    _ok, _issues = _validate_step_inputs(trial, 'ID')
                    if _ok:
                        _run_step(trial, "Inverse Dynamics", "run_id")
                    else:
                        logger.warning(f"  [SKIP] ID — inputs invalid: {'; '.join(_issues)}")

                if getattr(config, 'enable_static_optimization', False):
                    _ok, _issues = _validate_step_inputs(trial, 'SO')
                    if _ok:
                        _run_step(trial, "Static Optimization", "run_so")
                    else:
                        logger.warning(f"  [SKIP] SO — inputs invalid: {'; '.join(_issues)}")

                if getattr(config, 'enable_muscle_analysis', False):
                    _ok, _issues = _validate_step_inputs(trial, 'MA')
                    if _ok:
                        _run_step(trial, "Muscle Analysis", "run_ma")
                    else:
                        logger.warning(f"  [SKIP] MA — inputs invalid: {'; '.join(_issues)}")

                if getattr(config, 'enable_energetics', False):
                    # Energetics (metabolic cost) needs the IK kinematics and,
                    # ideally, the Static Optimization activations.
                    _ik_abs     = os.path.join(trial.path, trial.ik)
                    _so_act_abs = os.path.join(trial.path, trial.so_activations)
                    if not os.path.exists(_ik_abs):
                        logger.warning(
                            f"  [SKIP] Energetics — IK output missing: {_ik_abs}")
                    else:
                        if not os.path.exists(_so_act_abs):
                            logger.warning(
                                f"  [WARN] Energetics — SO activations missing "
                                f"({_so_act_abs}); using default activation")
                        _run_step(trial, "Energetics (Metabolic Cost)",
                                  "run_energetics")


            except Exception as e:
                logger.error(f"Trial {trial_name} failed: {e}")
                logger.debug(traceback.format_exc())
                continue

        # ------------------------------------------------------------------ #
        # EMG SESSION AMPLITUDE NORMALISATION  (divide by session max)
        # ------------------------------------------------------------------ #
        if getattr(config, 'enable_emg_normalise', False) and trial_objects:
            logger.info('Session EMG amplitude normalisation (session-max scaling)...')
            try:
                utils.normalise_emg_across_session(trial_objects)
                logger.info('[OK] EMG normalised across session')
            except Exception as e:
                logger.error(f'[ERROR] EMG session normalisation: {e}')

        # ------------------------------------------------------------------ #
        # CEINMS INPUT DATA  (second pass — after EMG normalisation)
        # ------------------------------------------------------------------ #
        if (getattr(CEINMSSettings, 'enable_calibration', False) or
                getattr(CEINMSSettings, 'enable_execution', False)) and trial_objects:
            logger.info('Building CEINMS input data (post-EMG normalisation)...')
            for trial in trial_objects:
                if _should_skip(trial.trial, config):
                    continue
                _run_step(trial, 'CEINMS input data', 'create_ceinms_input_data')

        # ------------------------------------------------------------------ #
        # CEINMS CALIBRATION  (session-level — once after all trials)
        # ------------------------------------------------------------------ #
        if getattr(CEINMSSettings, 'enable_calibration', False) and trial_objects:
            logger.info("=" * 70)
            logger.info("CEINMS CALIBRATION  (session-level)")
            logger.info("=" * 70)
            # run_ceinms_calibration discovers sibling trial inputs automatically
            _run_step(trial_objects[0], "CEINMS Calibration", "run_ceinms_calibration")

        # ------------------------------------------------------------------ #
        # CEINMS EXECUTION  (per-trial — needs calibrated model from above)
        # ------------------------------------------------------------------ #
        if getattr(CEINMSSettings, 'enable_execution', False):
            logger.info("=" * 70)
            logger.info("CEINMS EXECUTION  (per-trial)")
            logger.info("=" * 70)
            for trial in trial_objects:
                if _should_skip(trial.trial, config):
                    logger.info(f"    Skipping {trial.trial} (in trials_to_skip)")
                    continue
                _run_step(trial, "CEINMS Execution", "run_ceinms_exe")

        logger.info("=" * 70)
        logger.info("[OK] PIPELINE COMPLETED")
        logger.info("=" * 70)
        return True

    except Exception as e:
        logger.critical(f"Fatal error in session {subject_name}: {e}")
        traceback.print_exc()
        return False
    finally:
        logger.info(f"Session {subject_name} finished.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def run_gui_mode() -> int:
    import traceback as _tb
    _app_log = None
    _app_log = None
    try:
        from utils.logger import logger as _app_log
    except Exception:
        pass

    def _log(msg: str) -> None:
        print(msg, flush=True)
        if _app_log:
            _app_log.info(msg)

    def _err(msg: str) -> None:
        print(msg, flush=True)
        if _app_log:
            _app_log.error(msg)

    _log("[GUI] Importing main_window...")
    try:
        from gui.main_window import main as gui_main
    except BaseException as e:
        _err(f"[GUI] Import failed ({type(e).__name__}): {e}")
        _err(_tb.format_exc())
        return 1
    _log("[GUI] Starting GUI...")
    try:
        gui_main(fullscreen=True)
    except SystemExit as e:
        _err(f"[GUI] sys.exit() called with code={e.code}")
        return 1
    except BaseException as e:
        _err(f"[GUI] Crashed ({type(e).__name__}): {e}")
        _err(_tb.format_exc())
        return 1
    _log("[GUI] GUI closed normally.")
    return 0


def run_video_batch_mode(settings_path: str) -> bool:
    """
    Run video analysis batch from a JSON settings file.

    Settings file format (JSON):
    {
        "videos": ["path/to/video1.mp4", "path/to/video2.mp4"],
              "model": "full_body",
        "detect_interval": 1,
        "output_dir": "path/to/output"
    }
    """
    import json
    import subprocess

    settings_file = Path(settings_path)
    if not settings_file.exists():
        logger.error(f"Settings file not found: {settings_path}")
        return False

    try:
        cfg = json.loads(settings_file.read_text())
    except Exception as e:
        logger.error(f"Failed to parse settings file: {e}")
        return False

    videos = cfg.get("videos", [])
    if not videos:
        logger.error("No videos listed in settings file.")
        return False

    model = cfg.get("model", "full_body")
    detect_interval = int(cfg.get("detect_interval", 1))
    output_dir = cfg.get("output_dir", None)

    analyzer = Path(__file__).parent / "record" / "video_analyzer.py"
    if not analyzer.exists():
        logger.error(f"video_analyzer.py not found at {analyzer}")
        return False

    logger.info("=" * 70)
    logger.info("Video Analysis — Batch Mode")
    logger.info(f"Settings : {settings_path}")
    logger.info(f"Videos   : {len(videos)}")
    logger.info(f"Model    : {model}")
    logger.info(f"Interval : {detect_interval}")
    if output_dir:
        logger.info(f"Output   : {output_dir}")
    logger.info("=" * 70)

    all_ok = True
    for i, video in enumerate(videos, 1):
        video_path = Path(video)
        logger.info(f"[{i}/{len(videos)}] {video_path.name}")

        cmd = [
            sys.executable, str(analyzer),
            "--video", str(video),
            "--model", model,
            "--detect-interval", str(detect_interval),
        ]
        if output_dir:
            cmd += ["--output-dir", str(output_dir)]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            for line in proc.stdout:
                logger.info("  " + line.rstrip())
            proc.wait()
            if proc.returncode == 0:
                logger.info(f"  [OK] {video_path.name}")
            else:
                logger.error(f"  [FAILED] {video_path.name} (exit {proc.returncode})")
                all_ok = False
        except Exception as e:
            logger.error(f"  [ERROR] {video_path.name}: {e}")
            all_ok = False

    logger.info("=" * 70)
    logger.info("[OK] Video batch finished." if all_ok else "[WARN] Some videos failed.")
    logger.info("=" * 70)
    return all_ok


def run_init_mode(project_path: str) -> int:
    """Initialise a new BioScout project at *project_path*.

    Actions
    -------
    1. Create standard subdirectories (simulations/, Models/, setup_files/, logs/).
    2. Copy bundled setup_files templates (XML) into <project>/setup_files/ —
       skips files that already exist so re-running is safe.
    3. Copy the package settings.py template to <project_path>/settings.py,
       updating PROJECT_ROOT to the given path (skipped if already exists).
    4. If simulations/ already contains participant sub-folders, compare them
       against SUBJECTS in the existing settings.py and warn about mismatches.
    """
    import shutil
    import re as _re

    project = Path(project_path).resolve()
    print(f"\n{'='*60}")
    print(f"BioScout — Initialising project at: {project}")
    print(f"{'='*60}")

    # ---------------------------------------------------------------------- #
    # 1. Create standard folder structure
    # ---------------------------------------------------------------------- #
    standard_dirs = ['simulations', 'Models', 'setup_files', 'logs']
    for d in standard_dirs:
        target = project / d
        if not target.exists():
            target.mkdir(parents=True)
            print(f"  [created]  {target}")
        else:
            print(f"  [exists]   {target}")

    # ---------------------------------------------------------------------- #
    # 2. Copy bundled templates (setup_files and models)
    # ---------------------------------------------------------------------- #
    def _copy_template_dir(src: Path, dst: Path, extensions: tuple) -> tuple:
        """Copy files matching *extensions* from src → dst, skipping existing.
        Returns (copied_count, skipped_count).
        """
        if not src.exists():
            return 0, 0
        copied, skipped = 0, 0
        for item in sorted(src.rglob('*')):
            if item.is_file() and (not extensions or item.suffix in extensions):
                rel = item.relative_to(src)
                target = dst / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    skipped += 1
                else:
                    shutil.copy2(item, target)
                    copied += 1
        return copied, skipped

    for tmpl_name, dst_name, exts in [
        ('setup_files', 'setup_files', ('.xml', '.txt')),
        ('models',      'Models',      ()),       # () = copy all (includes Geometry/ meshes)
    ]:
        src_dir = Path(__file__).parent / tmpl_name
        dst_dir = project / dst_name
        c, s = _copy_template_dir(src_dir, dst_dir, exts)
        label = f"  [{dst_name}]"
        if c:
            print(f"\n{label} {c} file(s) copied to {dst_dir}")
        if s:
            print(f"{label} {s} file(s) already existed — not overwritten")
        if not c and not s:
            print(f"\n{label} No bundled templates found at {src_dir}")

    # ---------------------------------------------------------------------- #
    # 3. Copy settings template
    # ---------------------------------------------------------------------- #
    settings_dest = project / 'settings.py'
    settings_src  = Path(__file__).parent / 'settings.py'

    if settings_dest.exists():
        print(f"\n  [skip] settings.py already exists — not overwriting.")
        print(f"         Edit it directly: {settings_dest}")
    else:
        if settings_src.exists():
            content = settings_src.read_text(encoding='utf-8')
            # Replace PROJECT_ROOT with the actual project path (forward slashes
            # work on all platforms; raw string keeps backslashes on Windows).
            # Use a lambda replacement so re never interprets the path string
            # as a regex escape sequence (e.g. \U on Windows would raise
            # re.PatternError in Python 3.12+).
            path_str = str(project).replace('\\', '/')
            repl = f"PROJECT_ROOT    = Path(r'{path_str}')"
            content = _re.sub(
                r"PROJECT_ROOT\s*=\s*.*",
                lambda _: repl,
                content,
                count=1,
            )
            settings_dest.write_text(content, encoding='utf-8')
            print(f"\n  [created]  {settings_dest}")
            print(f"  ⚠  Edit SUBJECTS and generic_model / markerset paths before running --batch.")
        else:
            print(f"\n  [warn] Package settings.py template not found at {settings_src}.")

    # ---------------------------------------------------------------------- #
    # 3. Check existing simulations against SUBJECTS in settings.py
    # ---------------------------------------------------------------------- #
    sims_dir = project / 'simulations'
    if sims_dir.exists():
        sim_folders = sorted(
            d.name for d in sims_dir.iterdir() if d.is_dir()
        )

        if sim_folders:
            # Try to load SUBJECTS from the settings file
            subjects_in_settings: Optional[set] = None
            try:
                import importlib.util as _ilu
                _spec = _ilu.spec_from_file_location('_init_settings', str(settings_dest))
                _mod  = _ilu.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                if hasattr(_mod, 'SUBJECTS'):
                    subjects_in_settings = set(_mod.SUBJECTS.keys())
            except Exception as _e:
                print(f"\n  [warn] Could not parse SUBJECTS from settings.py: {_e}")

            print(f"\n  Simulation folders found  : {sim_folders}")

            if subjects_in_settings is not None:
                print(f"  SUBJECTS in settings.py    : {sorted(subjects_in_settings)}")
                missing_from_settings = set(sim_folders) - subjects_in_settings
                missing_from_disk     = subjects_in_settings - set(sim_folders)

                if missing_from_settings:
                    print(f"\n  ⚠  WARNING: these folders exist in simulations/ but are NOT in SUBJECTS:")
                    for m in sorted(missing_from_settings):
                        print(f"       {m}")
                if missing_from_disk:
                    print(f"\n  ⚠  WARNING: these SUBJECTS entries have no folder in simulations/:")
                    for m in sorted(missing_from_disk):
                        print(f"       {m}")
                if not missing_from_settings and not missing_from_disk:
                    print(f"\n  ✓  simulations/ folders match SUBJECTS in settings.py.")
            else:
                print(f"\n  [info] Add these folder names to SUBJECTS in settings.py:")
                for f in sim_folders:
                    print(f"           '{f}': SubjectConfig(group=''),")

    print(f"\n{'='*60}")
    print(f"Project ready. Next steps:")
    print(f"  1. Edit {settings_dest}")
    print(f"     — set SUBJECTS, generic_model, markerset")
    print(f"  2. cd {project}")
    print(f"  3. python -m bioscout -b settings.py")
    print(f"{'='*60}\n")
    return 0


def _is_video_batch_settings(settings_path: str) -> bool:
    """Return True if the settings file looks like a video batch config (has 'videos' key)."""
    import json
    try:
        cfg = json.loads(Path(settings_path).read_text())
        return "videos" in cfg
    except Exception:
        return False


def run_add_subject_mode(project_path: str) -> int:
    """Interactively add a subject to subjects.json in *project_path*."""
    from utils.subject_registry import SubjectRegistry, prompt_add_subject
    root = Path(project_path).resolve()
    if not root.is_dir():
        print(f"[error] Project path does not exist: {root}")
        return 1
    registry = SubjectRegistry(root)
    existing = registry.all_ids()
    if existing:
        print(f"  {len(existing)} subject(s) already registered: {', '.join(existing)}")
    pid = prompt_add_subject(registry)
    return 0 if pid else 1


def run_load_report_mode(inputs=None) -> int:
    """Build a training-load & fatigue PDF report.

    Sources can be combined: local files/folder (``inputs``), the Zepp cloud
    (``--zepp-pull``), and/or Strava (``--strava-pull``).
    """
    from load_tracking import LoadTracker, AthleteProfile, load_credentials, pull_into_tracker
    athlete = AthleteProfile(
        name="Athlete", age=args.age, sex=args.sex,
        hr_max=args.hr_max, hr_rest=args.hr_rest,
    )
    tracker = LoadTracker(athlete=athlete)
    total = 0

    if inputs:
        n = tracker.add_files(inputs)
        print(f"[load-report] Loaded {n} session(s) from files.")
        total += n

    if args.zepp_pull or args.strava_pull:
        creds = load_credentials(args.creds)
        if not creds:
            cpath = args.creds or "~/.bioscout/load_credentials.json"
            print(f"[load-report] No credentials found at {cpath}. "
                  "See bioscout/load_tracking/README.md for the format.")
            return 1
        res = pull_into_tracker(tracker, creds,
                                zepp=args.zepp_pull, strava=args.strava_pull)
        if res["zepp"]:
            print(f"[load-report] Pulled {res['zepp']} session(s) from Zepp.")
        if res["strava"]:
            print(f"[load-report] Pulled {res['strava']} session(s) from Strava.")
        for err in res["errors"]:
            print(f"[load-report] {err}")
        total += res["zepp"] + res["strava"]

    if total == 0:
        print("[load-report] No sessions loaded. Expected .fit/.tcx/.gpx/.csv files, "
              "or a valid --zepp-pull / --strava-pull credentials file.")
        return 1

    tracker.compute()
    print(tracker.summary_text())
    out = args.load_out or "load_report.pdf"
    tracker.report(out)
    print(f"\n[load-report] PDF written: {out}")
    return 0


def main() -> int:
    if args.install:
        from utils.dependency_installer import install_missing
        return 0 if install_missing(interactive=True) else 1
    if args.add_subject is not None:
        return run_add_subject_mode(args.add_subject)
    if args.shots:
        from bioscout.load_tracking.shot_analysis import analyze_video
        _model = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'models', 'kinematics_only_model.pkl')
        _hoop = None
        if args.hoop:
            try:
                _hoop = tuple(float(v) for v in args.hoop.split(','))
                assert len(_hoop) == 4
            except Exception:
                print("[shots] --hoop must be CX,CY,W,H (e.g. 955,235,70,40); ignoring")
                _hoop = None
        analyze_video(args.shots, shooting_hand=args.shooting_hand,
                      poses=args.poses, fps=args.fps,
                      min_gap_s=args.min_gap, n_points=args.n_points,
                      hoop_side=args.hoop_side, yolo_model=args.yolo_model, hoop=_hoop,
                      model_path=_model if os.path.exists(_model) else None)
  