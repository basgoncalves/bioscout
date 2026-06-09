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
import argparse
import traceback
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from settings import BatchSettings, CEINMSSettings
from utils.model_scaler import ModelScaler
from utils.helpers import setup_logging
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
logger = setup_logging(log_dir)


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


# ---------------------------------------------------------------------------
# Main batch function
# ---------------------------------------------------------------------------
def run_batch_mode(settings_path: str) -> bool:
    try:
        if not os.path.exists(settings_path):
            logger.error(f"Settings file not found: {settings_path}")
            return False

        config = BatchSettings
        session_dir = Path(config.session_folder)

        logger.info("=" * 70)
        logger.info("Biomechanical Analysis - Batch Processing")
        logger.info(f"Session folder : {session_dir}")
        logger.info("=" * 70)

        # ------------------------------------------------------------------ #
        # DISCOVERY
        # ------------------------------------------------------------------ #
        # Only look at C3D files directly in the session folder (not in trial subdirs,
        # which may contain copies created by the export step).
        c3d_files = sorted(session_dir.glob("*.c3d"))
        if not c3d_files:
            logger.warning("No C3D files found — aborting")
            return False
        logger.info(f"Found {len(c3d_files)} C3D file(s)")

        subject_name = session_dir.name

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
                is_static = config.static_trial_name in trial.trial
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
                statics = [f for f in c3d_files if config.static_trial_name in f.stem]
                if not statics:
                    raise RuntimeError(
                        f"Static trial '{config.static_trial_name}' not found")

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
        logger.critical(f"Fatal error: {e}")
        traceback.print_exc()
        return False
    finally:
        logger.info("Batch processing finished.")


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

    d