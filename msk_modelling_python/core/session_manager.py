"""
Session Manager - Handles session-level operations and trial discovery.
Version: 1.0.0
"""

import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import json


class TrialValidator:
    """Validates trial folders for required input files."""

    # Required files for different analysis types
    BASIC_REQUIREMENTS = {
        'c3d': 'c3dfile.c3d',
        'markers': 'marker_experimental.trc',
        'grf': 'grf.mot',
    }

    CEINMS_REQUIREMENTS = {
        'c3d': 'c3dfile.c3d',
        'markers': 'marker_experimental.trc',
        'grf': 'grf.mot',
        'grf_xml': 'GRF.xml',
        'model': 'scaled_*.osim',  # Pattern match for scaled model
    }

    EMG_REQUIREMENTS = {
        'emg_filtered': 'EMG_filtered_normalised*.sto',
    }

    @staticmethod
    def has_file(trial_dir: Path, filename: str, session_dir: Path = None) -> bool:
        """Check if a file exists in trial directory or session root (supports glob patterns)."""
        if '*' in filename:
            # Pattern matching
            import glob
            pattern = os.path.join(str(trial_dir), filename)
            return len(glob.glob(pattern)) > 0
        else:
            # Check trial folder first
            if (trial_dir / filename).exists():
                return True

            # For C3D files, also check session root with trial name
            if filename == 'c3dfile.c3d' and session_dir:
                trial_name = trial_dir.name
                c3d_file = session_dir / f"{trial_name}.c3d"
                if c3d_file.exists():
                    return True

            return False

    @staticmethod
    def validate_trial(trial_dir: Path, requirements: Dict[str, str], session_dir: Path = None) -> Dict[str, bool]:
        """Validate if trial has all required files."""
        results = {}
        for req_name, filename in requirements.items():
            results[req_name] = TrialValidator.has_file(trial_dir, filename, session_dir)
        return results

    @staticmethod
    def is_valid_trial(trial_dir: Path, session_dir: Path = None) -> bool:
        """Check if folder is a valid trial (has C3D or TRC file)."""
        # Check for TRC file in trial folder
        if TrialValidator.has_file(trial_dir, 'marker_experimental.trc', session_dir):
            return True

        # Check for C3D file in session root with trial name
        if session_dir:
            trial_name = trial_dir.name
            c3d_file = session_dir / f"{trial_name}.c3d"
            if c3d_file.exists():
                return True

        # Check for C3D file in trial folder (backward compatibility)
        return TrialValidator.has_file(trial_dir, 'c3dfile.c3d', session_dir)

    @staticmethod
    def get_trial_status(trial_dir: Path, session_dir: Path = None) -> Dict[str, any]:
        """Get complete validation status for a trial."""
        trial_name = trial_dir.name
        basic_valid = TrialValidator.validate_trial(trial_dir, TrialValidator.BASIC_REQUIREMENTS, session_dir)
        ceinms_valid = TrialValidator.validate_trial(trial_dir, TrialValidator.CEINMS_REQUIREMENTS, session_dir)
        emg_valid = TrialValidator.validate_trial(trial_dir, TrialValidator.EMG_REQUIREMENTS, session_dir)

        basic_complete = all(basic_valid.values())
        ceinms_complete = all(ceinms_valid.values())
        emg_complete = all(emg_valid.values())

        return {
            'name': trial_name,
            'path': str(trial_dir),
            'is_valid_trial': TrialValidator.is_valid_trial(trial_dir, session_dir),
            'basic_complete': basic_complete,
            'ceinms_complete': ceinms_complete,
            'emg_complete': emg_complete,
            'basic_files': basic_valid,
            'ceinms_files': ceinms_valid,
            'emg_files': emg_valid,
            'status_color': 'green' if ceinms_complete else 'red',
        }


class SessionManager:
    """Manages session-level operations and trial discovery."""

    VERSION = "1.0.0"

    def __init__(self, session_path: Optional[str] = None):
        """Initialize session manager."""
        self.session_path = Path(session_path) if session_path else None
        self.trials = []
        self.session_name = self.session_path.name if self.session_path else None

    def discover_trials(self) -> List[Path]:
        """Discover all trial folders in session (containing C3D or TRC files)."""
        if not self.session_path or not self.session_path.exists():
            return []

        trials = []
        for item in sorted(self.session_path.iterdir()):
            if item.is_dir() and TrialValidator.is_valid_trial(item, self.session_path):
                trials.append(item)

        self.trials = trials
        return trials

    def get_trial_list(self) -> List[Dict]:
        """Get list of trials with their status information."""
        if not self.trials:
            self.discover_trials()

        trial_list = []
        for trial_path in self.trials:
            status = TrialValidator.get_trial_status(trial_path, self.session_path)
            trial_list.append(status)

        return trial_list

    def get_trial_by_name(self, trial_name: str) -> Optional[Path]:
        """Get trial path by name."""
        if not self.trials:
            self.discover_trials()

        for trial_path in self.trials:
            if trial_path.name == trial_name:
                return trial_path
        return None

    def validate_for_analysis(self, trial_name: str) -> Tuple[bool, str]:
        """Validate if trial is ready for analysis."""
        trial_path = self.get_trial_by_name(trial_name)
        if not trial_path:
            return False, f"Trial '{trial_name}' not found"

        status = TrialValidator.get_trial_status(trial_path, self.session_path)
        if status['basic_complete']:
            return True, "Trial ready for analysis"
        else:
            missing = [k for k, v in status['basic_files'].items() if not v]
            return False, f"Trial missing required files: {', '.join(missing)}"

    def validate_for_ceinms(self, trial_name: str) -> Tuple[bool, str]:
        """Validate if trial is ready for CEINMS calibration."""
        trial_path = self.get_trial_by_name(trial_name)
        if not trial_path:
            return False, f"Trial '{trial_name}' not found"

        status = TrialValidator.get_trial_status(trial_path, self.session_path)
        if status['ceinms_complete']:
            return True, "Trial ready for CEINMS calibration"
        else:
            missing = [k for k, v in status['ceinms_files'].items() if not v]
            return False, f"Trial missing CEINMS files: {', '.join(missing)}"

    def get_session_summary(self) -> Dict:
        """Get summary of session with trial statuses."""
        trials = self.get_trial_list()
        ready_for_analysis = sum(1 for t in trials if t['basic_complete'])
        ready_for_ceinms = sum(1 for t in trials if t['ceinms_complete'])

        return {
            'session_name': self.session_name,
            'session_path': str(self.session_path),
            'total_trials': len(trials),
            'ready_for_analysis': ready_for_analysis,
            'ready_for_ceinms': ready_for_ceinms,
            'trials': trials,
        }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        session_path = sys.argv[1]
        manager = SessionManager(session_path)
        summary = manager.get_session_summary()
        print(json.dumps(summary, indent=2))
