"""
settings_teaching.py — batch settings for the BD2II teaching dataset.

A thin override of settings.py: inherits everything (DOFs, marker weights, EMG
mappings, CEINMS config, etc.) and only changes the session list, the model /
setup-file locations, and which pipeline steps run.

Run with:
    python -m msk_modelling_python -b msk_modelling_python/settings_teaching.py
"""

from pathlib import Path
from settings import (
    BatchSettings as _BaseBatch,
    CEINMSSettings as _BaseCEINMS,
    PlayerConfig,
    build_sessions,
)

# Root of the teaching MoCap data — the only hardcoded path in this file.
_ROOT = Path(r'C:\Git\research_documents\Uvienna\Teaching\BD2II - Biomechanical Motion Analysis in Practice\2026S\MoCap')

# Players in the teaching dataset
_PLAYERS = {
    'P01': PlayerConfig(group='student'),
    'P02': PlayerConfig(group='student'),
}

# Derived paths
_SIMULATIONS_DIR = _ROOT
_MODELS_DIR      = _ROOT / 'Models'
_SETUP_DIR       = _ROOT / 'setup_files'
LOG_DIR          = _ROOT / 'logs'


class BatchSettings(_BaseBatch):
    """Teaching-run batch settings (only export / scale / IK / ID)."""

    # Sessions derived from the player registry above
    sessions = build_sessions(_PLAYERS, _SIMULATIONS_DIR)

    # Model + setup files for this dataset
    generic_model      = str(_MODELS_DIR / 'Catelli-V4.0_pyCGM.osim')
    setup_files_folder = str(_SETUP_DIR)
    markerset          = str(_SETUP_DIR / 'markers.xml')

    # Pipeline steps — run ONLY export, scale, IK and ID
    enable_c3d_export          = True
    enable_scale_model         = True
    enable_muscle_scaling      = False
    enable_inverse_kinematics  = True
    enable_inverse_dynamics    = True
    enable_static_optimization = False
    enable_muscle_analysis     = False
    enable_emg_normalise       = False

    # MARKER WEIGHTS for model scaling
    marker_weights = {
        'pelvis': 2.0,
        'femur_r': 2.0, 'tibia_r': 1.0, 'talus_r': 1.0, 'calcn_r': 2.0, 'toes_r': 2.0,
        'femur_l': 2.0, 'tibia_l': 1.0, 'talus_l': 1.0, 'calcn_l': 2.0, 'toes_l': 2.0,
    }


class CEINMSSettings(_BaseCEINMS):
    """CEINMS disabled for the teaching run."""
    enable_calibration = False
    enable_execution   = False
