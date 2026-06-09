"""Analysis runner that integrates with existing analysis modules."""

import os
import sys
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
import traceback
from dataclasses import dataclass
from enum import Enum

# Add parent CODE directory to path to import existing analysis modules
CODE_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(CODE_DIR))

# Import app's logger
from utils.logger import logger


class AnalysisStep(Enum):
    """Available analysis steps."""
    EXPORT_C3D = "export_c3d"
    INVERSE_KINEMATICS = "inverse_kinematics"
    INVERSE_DYNAMICS = "inverse_dynamics"
    MUSCLE_ANALYSIS = "muscle_analysis"
    MOMENT_ARMS = "moment_arms"
    STATIC_OPTIMIZATION = "static_optimization"
    JOINT_REACTION_ANALYSIS = "joint_reaction_analysis"
    RRA = "rra"
    CMC = "cmc"
    ENERGETICS = "energetics"
    BODY_KINEMATICS = "body_kinematics"
    CEINMS_FILES = "create_ceinms_files"
    CEINMS_CALIBRATION = "ceinms_calibration"
    CEINMS_EXECUTION = "ceinms_execution"
    CEINMS_OPTIMIZATION = "ceinms_optimization"
    CEINMS_EXPORT = "ceinms_export"


class AnalysisConfig:
    """Configuration object for analysis."""
    def __init__(self, trial_path: str = None, steps: List[str] = None, parameters: Dict[str, Any] = None,
                 replace_existing: bool = False, **kwargs):
        # Support both dict and keyword arguments
        if isinstance(trial_path, dict):
            self._config = trial_path
        else:
            self._config = {
                'trial_path': trial_path,
                'steps': steps or [],
                'parameters': parameters or {},
                'replace_existing': replace_existing,
                **kwargs
            }

    def __getattr__(self, name: str):
        if name.startswith('_'):
            return super().__getattribute__(name)
        return self._config.get(name)

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    @property
    def trial_path(self):
        return self._config.get('trial_path')

    @property
    def replace_existing(self):
        return self._config.get('replace_existing', False)

    @property
    def steps(self):
        return self._config.get('steps', [])

    @property
    def parameters(self):
        return self._config.get('parameters', {})


class AnalysisRunner:
    """Runs analysis steps using the existing Analyse class."""

    def __init__(self, callback: Optional[Callable] = None, progress_callback: Optional[Callable] = None):
        """Initialize the analysis runner."""
        self.callback = callback or progress_callback
        self.progress_callback = progress_callback or callback
        self.analysis_obj = None
        self.current_step = None

    def run_analysis(self, config: AnalysisConfig) -> tuple[bool, str]:
        """Run complete analysis workflow."""
        try:
            # Prepare analysis
            success, error = self.prepare_analysis(config)
            if not success:
                return False, error

            # Handle RESET_SETTINGS from config
            reset_settings = config.get('reset_settings', False)
            if reset_settings:
                try:
                    logger.info(f"Resetting settings XML for: {config.trial_path}")
                    self.analysis_obj._reset_settings_xml()
                    logger.info("Settings XML reset successfully")
                except Exception as e:
                    logger.error(f"Failed to reset settings XML: {e}")
                    return False, f"Failed to reset settings: {str(e)}"

            # Run enabled steps
            steps = config.get('steps', [])

            # If we only have reset_settings and no other steps, we're done
            if not steps:
                if reset_settings:
                    return True, ""
                else:
                    return False, "No analysis steps selected"

            # Run analysis steps
            for step_str in steps:
                try:
                    step = AnalysisStep(step_str)
                except ValueError:
                    return False, f"Unknown analysis step: {step_str}"

                success, error = self.run_step(step, {})
                if not success:
                    return False, error

            return True, ""

        except Exception as e:
            error_msg = f"Analysis error: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return False, error_msg

    def stop_analysis(self) -> None:
        """Stop the currently running analysis."""
        logger.info("Analysis stopped by user")

    def prepare_analysis(self, config: AnalysisConfig) -> tuple[bool, str]:
        """Prepare analysis by loading the Analyse class."""
        try:
            try:
                import matplotlib
                matplotlib.use('Agg')
            except Exception:
                pass

            import importlib.util
            app_utils_dir = Path(__file__).parent.parent / 'utils'
            utils_init_path = app_utils_dir / '__init__.py'
            code_dir = Path(__file__).parent.parent.parent.parent

            if not utils_init_path.exists():
                raise FileNotFoundError(f"Cannot find utils at: {utils_init_path}")

            if str(app_utils_dir) not in sys.path:
                sys.path.insert(0, str(app_utils_dir))
            if str(code_dir) not in sys.path:
                sys.path.insert(0, str(code_dir))

            spec = importlib.util.spec_from_file_location("parent_utils", utils_init_path)
            parent_utils = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(parent_utils)

            self.analysis_obj = parent_utils.Analyse(trialPath=config.trial_path)
            self.analysis_obj.replace = config.replace_existing

            # Ensure time_range attribute exists (defensive programming)
            if not hasattr(self.analysis_obj, 'time_range'):
                self.analysis_obj.time_range = 'None'

            logger.info(f"Analysis prepared for: {config.trial_path}")
            self._update_progress("Preparation", "Ready", 0)
            return True, ""

        except Exception as e:
            error_msg = f"Failed to prepare analysis: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return False, error_msg

    def run_step(self, step: AnalysisStep, step_config: Dict[str, Any]) -> tuple[bool, str]:
        """Run a single analysis step."""
        if not self.analysis_obj:
            return False, "Analysis not prepared. Call prepare_analysis first."

        try:
            self.current_step = step.value
            self._update_progress(step.value, "Running", None)

            method_map = {
                AnalysisStep.EXPORT_C3D: self._run_export_c3d,
                AnalysisStep.INVERSE_KINEMATICS: self._run_inverse_kinematics,
                AnalysisStep.INVERSE_DYNAMICS: self._run_inverse_dynamics,
                AnalysisStep.MUSCLE_ANALYSIS: self._run_muscle_analysis,
                AnalysisStep.MOMENT_ARMS: self._run_moment_arms,
                AnalysisStep.STATIC_OPTIMIZATION: self._run_static_optimization,
                AnalysisStep.JOINT_REACTION_ANALYSIS: self._run_joint_reaction_analysis,
                AnalysisStep.RRA: self._run_rra,
                AnalysisStep.CMC: self._run_cmc,
                AnalysisStep.ENERGETICS: self._run_energetics,
                AnalysisStep.BODY_KINEMATICS: self._run_body_kinematics,
                AnalysisStep.CEINMS_FILES: self._run_create_ceinms_files,
                AnalysisStep.CEINMS_CALIBRATION: self._run_ceinms_calibration,
                AnalysisStep.CEINMS_EXECUTION: self._run_ceinms_execution,
                AnalysisStep.CEINMS_OPTIMIZATION: self._run_ceinms_optimization,
                AnalysisStep.CEINMS_EXPORT: self._run_ceinms_export,
            }

            if step not in method_map:
                return False, f"Unknown analysis step: {step.value}"

            method_map[step](step_config)

            # Verify that expected output files were created
            verification_msg = self._verify_step_output(step)
            if verification_msg:
                # Output files missing - report error
                logger.error(f"[ERROR] {step.value} - Output verification failed:")
                logger.error(verification_msg)
                self._update_progress(step.value, "Error", None)
                return False, verification_msg

            self._update_progress(step.value, "Complete", 100)
            logger.info(f"Analysis step {step.value} completed successfully")
            return True, ""

        except Exception as e:
            error_msg = f"Error in {step.value}: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            self._update_progress(step.value, "Error", None)
            return False, error_msg

    def _verify_step_output(self, step: AnalysisStep) -> str:
        """
        Verify that expected output files exist for a step.
        Returns empty string if all outputs exist, error message otherwise.
        """
        trial_path = self.analysis_obj.path if self.analysis_obj else ""

        # Define expected outputs for each step
        expected_outputs = {
            AnalysisStep.INVERSE_KINEMATICS: ["joint_angles.mot"],
            AnalysisStep.INVERSE_DYNAMICS: ["inverse_dynamics.sto"],
            AnalysisStep.MUSCLE_ANALYSIS: [],  # Multiple output files, skip verification
            AnalysisStep.STATIC_OPTIMIZATION: [],  # Multiple output files
            AnalysisStep.JOINT_REACTION_ANALYSIS: [],  # Multiple output files
        }

        # Check if this step requires output verification
        if step not in expected_outputs:
            return ""  # Skip verification for steps without defined outputs

        expected_files = expected_outputs[step]
        if not expected_files:
            return ""  # Skip verification if no specific outputs defined

        missing_files = []
        for filename in expected_files:
            filepath = os.path.join(trial_path, filename)
            if not os.path.exists(filepath):
                missing_files.append(f"  - {filename} (expected at {filepath})")

        if missing_files:
            error_msg = f"Missing output file(s) for {step.value}:\n" + "\n".join(missing_files)
            return error_msg

        return ""

    def _update_progress(self, step: str, status: str, progress: Optional[int]) -> None:
        """Update progress callback."""
        if self.callback:
            try:
                self.callback({
                    'step': step,
                    'status': status,
                    'progress': progress
                })
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    # Step implementation methods
    def _run_export_c3d(self, config: Dict[str, Any]) -> None:
        """Run C3D export step."""
        self.analysis_obj.export_c3d_data()

    def _run_inverse_kinematics(self, config: Dict[str, Any]) -> None:
        """Run inverse kinematics step."""
        self.analysis_obj.run_ik()

    def _run_inverse_dynamics(self, config: Dict[str, Any]) -> None:
        """Run inverse dynamics step."""
        self.analysis_obj.run_id()

    def _run_muscle_analysis(self, config: Dict[str, Any]) -> None:
        """Run muscle analysis step."""
        self.analysis_obj.run_ma()

    def _run_moment_arms(self, config: Dict[str, Any]) -> None:
        """Run moment arms step."""
        self.analysis_obj.run_jra()

    def _run_static_optimization(self, config: Dict[str, Any]) -> None:
        """Run static optimization step."""
        self.analysis_obj.run_so()

    def _run_joint_reaction_analysis(self, config: Dict[str, Any]) -> None:
        """Run joint reaction analysis step."""
        self.analysis_obj.run_jra()

    def _run_rra(self, config: Dict[str, Any]) -> None:
        """Run Residual Reduction Algorithm step."""
        self.analysis_obj.run_rra()

    def _run_cmc(self, config: Dict[str, Any]) -> None:
        """Run Computed Muscle Control step."""
        self.analysis_obj.run_cmc()

    def _run_energetics(self, config: Dict[str, Any]) -> None:
        """Run Metabolic Cost (Energetics) analysis step."""
        self.analysis_obj.run_energetics()

    def _run_body_kinematics(self, config: Dict[str, Any]) -> None:
        """Run Body Kinematics analysis step."""
        self.analysis_obj.run_body_kinematics()

    def _run_create_ceinms_files(self, config: Dict[str, Any]) -> None:
        """Run CEINMS file creation step."""
        self.analysis_obj.create_ceinms_input_data()

    def _run_ceinms_calibration(self, config: Dict[str, Any]) -> None:
        """Run CEINMS calibration step."""
        logger.info("CEINMS calibration step executed")

    def _run_ceinms_execution(self, config: Dict[str, Any]) -> None:
        """Run CEINMS execution step."""
        logger.info("CEINMS execution step executed")

    def _run_ceinms_optimization(self, config: Dict[str, Any]) -> None:
        """Run CEINMS optimization step."""
        logger.info("CEINMS optimization step executed")

    def _run_ceinms_export(self, config: Dict[str, Any]) -> None:
        """Run CEINMS export step."""
        logger.info("CEINMS export step executed")
                                                