#!/usr/bin/env python3
"""
Biomechanical Analysis — entry point

GUI mode (default):
    python msk_modelling_python
    python msk_modelling_python --gui

Batch mode:
    python msk_modelling_python -b settings.py
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
    """Return True if this trial matches any entry in BatchSettings.trials_to_skip."""
    skip_list = getattr(config, 'trials_to_skip', []) or []
    return any(s in trial_name for s in skip_list)


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


def run_batch_mode(settings_path: str) -> bool:
    """Run the pipeline for one session or for every session inside a folder."""
    # Load the settings module specified by -b (e.g. settings_teaching.py).
    _load_settings_from_path(settings_path)

    config = BatchSettings
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
        try:
            ok = _run_one_session(session_dir, config, session_dir.name,
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
                _run_step(trial, "C3D export", "export_c3d")
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
                    _run_step(trial, "Inverse Kinematics", "run_ik")

                if config.enable_inverse_dynamics:
                    _run_step(trial, "Inverse Dynamics", "run_id")

                if getattr(config, 'enable_static_optimization', False):
                    _run_step(trial, "Static Optimization", "run_so")

                if getattr(config, 'enable_muscle_analysis', False):
                    _run_step(trial, "Muscle Analysis", "run_ma")


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
        gui_main()
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


def _is_video_batch_settings(settings_path: str) -> bool:
    """Return True if the settings file looks like a video batch config (has 'videos' key)."""
    import json
    try:
        cfg = json.loads(Path(settings_path).read_text())
        return "videos" in cfg
    except Exception:
        return False


def main() -> int:
    if args.batch:
        if _is_video_batch_settings(args.batch):
            return 0 if run_video_batch_mode(args.batch) else 1
        return 0 if run_batch_mode(args.batch) else 1
    # GUI mode: explicit --gui flag, or no arguments at all
    return run_gui_mode()


if __name__ == '__main__':
    sys.exit(main())
