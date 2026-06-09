"""
Unified Settings Module
"""

import os
from pathlib import Path

MODULE_PATH = Path(__file__).parent
LOG_DIR = MODULE_PATH / "logs"
MODELS_DIR = r'C:\Users\Basilio\ucloud\Squat_Width\Models'
SESSION_DIR = r'C:\Users\Basilio\ucloud\Squat_Width\Simulations\P05'
SETUP_DIR = r'C:\Users\Basilio\ucloud\Squat_Width\setup_files'
PROJECT_NAME = 'squatting_fais'

# ============================================================================
# BATCH SETTINGS
# ============================================================================
class BatchSettings:
    """Unified batch processing settings for motion capture session analysis."""

    # SESSION CONFIGURATION
    session_folder = SESSION_DIR
    setup_files_folder = SETUP_DIR
    generic_model = os.path.join(MODELS_DIR, 'Catelli-V4.0_pyCGM_pelvis.osim')
    markerset = os.path.join(SETUP_DIR, "markers.xml")
    static_trial_name = 'static01'
    trials_to_skip: list = []

    auto_create_dirs = True
    replace_existing = True

    # DEGREES OF FREEDOM — single canonical list used across IK, ID, MA, and CEINMS
    dof_list = [
        'hip_flexion_l', 'hip_flexion_r',
        'hip_adduction_l', 'hip_adduction_r',
        'hip_rotation_l', 'hip_rotation_r',
        'knee_angle_l', 'knee_angle_r',
        'ankle_angle_l', 'ankle_angle_r',
    ]

    # MARKER WEIGHTS for model scaling
    marker_weights = {
        'pelvis': 10.0,
        'femur_r': 1.0, 'tibia_r': 1.0, 'talus_r': 1.0, 'calcn_r': 2.0, 'toes_r': 2.0,
        'femur_l': 1.0, 'tibia_l': 1.0, 'talus_l': 1.0, 'calcn_l': 2.0, 'toes_l': 2.0,
    }

    # EMG CHANNEL → OPENSIM MUSCLE MAPPING (used for C3D export and plotting)
    emg_muscle_mapping = {
        # Left Leg
        'EMG_Channels_EMG02_L_gastro_med': ['fdl_l', 'fhl_l', 'gasmed_l', 'gaslat_l', 'perbrev_l', 'perlong_l', 'soleus_l', 'tibpost_l'],
        'EMG_Channels_EMG05_L_rect_fem':   ['recfem_l', 'sart_l', 'tfl_l'],
        'EMG_Channels_EMG06_L_vast_med':   ['vaslat_l', 'vasmed_l', 'vasint_l'],
        'EMG_Channels_EMG07_L_semitend':   ['bflh_l', 'bfsh_l', 'semimem_l', 'semiten_l'],
        'EMG_Channels_EMG08_L_glut_med':   ['glmed1_l', 'glmed2_l', 'glmed3_l'],
        # Right Leg
        'EMG_Channels_EMG10_R_gastro_med': ['fdl_r', 'fhl_r', 'gasmed_r', 'gaslat_r', 'perbrev_r', 'perlong_r', 'soleus_r', 'tibpost_r'],
        'EMG_Channels_EMG13_R_rect_fem':   ['recfem_r', 'sart_r', 'tfl_r'],
        'EMG_Channels_EMG14_R_vast_med':   ['vaslat_r', 'vasmed_r', 'vasint_r'],
        'EMG_Channels_EMG15_R_semitend':   ['bflh_r', 'bfsh_r', 'semimem_r', 'semiten_r'],
        'EMG_Channels_EMG16_R_glut_med':   ['glmed1_r', 'glmed2_r', 'glmed3_r'],
    }

    # C3D EXPORT SETTINGS
    emg_label_default = "Voltage"
    emg_lowpass_default = "500"
    emg_highpass_default = "10"
    emg_notch_default = "50"
    emg_string_list = ["EMG", "Voltage", "muscle"]
    emg_sampling_freq = 1000  # Hz — set to your actual EMG sampling rate
    right_foot_markers = ['RTOE', 'RHEE', 'RFMH', 'RSMH', 'RVMH']
    left_foot_markers = ['LTOE', 'LHEE', 'LFMH', 'LSMH', 'LVMH']

    # Coordinate axes in the exported TRC file.
    # exportC3D rotates the lab frame to the OpenSim frame, so the axes that
    # distinguish left/right (mediolateral) and vertical change depending on
    # the source system.
    #
    #   Raw Vicon/lab frame  →  OpenSim frame (after exportC3D)
    #     X = mediolateral        X = anterior-posterior
    #     Y = anterior-post.      Y = vertical
    #     Z = vertical            Z = mediolateral   ← used for foot assignment
    #
    # Change trc_lateral_axis to 'X' if your TRC is in the original lab frame.
    trc_lateral_axis  = 'Z'   # column used to tell left foot from right foot
    trc_vertical_axis = 'Y'   # column representing height
    trc_ap_axis       = 'X'   # column representing anterior-posterior direction

    # UI Layout settings
    c3d_file_col_weight = 3
    c3d_settings_col_weight = 7
    c3d_emg_channels_height = 40
    c3d_markers_height = 40

    # ANALYSIS PIPELINE - OPENSIM
    enable_c3d_export = True
    enable_scale_model = True
    enable_muscle_scaling = False
    muscle_force_factor = 3
    enable_inverse_kinematics = True
    enable_inverse_dynamics = True
    enable_static_optimization = True
    enable_muscle_analysis = False

    # session-amplitude-normalise EMG after C3D export
    enable_emg_normalise      = False

    @property
    def results_dir(self) -> Path:
        """Results directory (same as session folder)."""
        return Path(self.session_folder)


# ============================================================================
# CEINMS SETTINGS
# ============================================================================
class CEINMSSettings:
    """
    All CEINMS-specific parameters in one place.
    Previously scattered across ceinms.py as TemplateParameters.
    """

    # --- Pipeline switches ---
    enable_calibration = False
    enable_execution   = True
    calibration_trial_names = ['cmj_02']  # trials used for CEINMS calibration

    # --- Calibration algorithm ---
    calibration_type             = 'hybrid'   # 'hybrid' or 'ceinms'
    tendon_type                  = 'elastic'  # 'elastic' or 'rigid'
    learning_rate                = 0.02
    max_iterations               = 1000
    early_stopping_patience      = 20
    early_stopping_min_improvement = 0.1
    num_synergies                = 4
    hybrid_calibration           = 'true'
    number_of_synergies          = 8

    # Default execution weights (overridable per trial via Analyse attributes)
    alpha = 10
    beta  = 1
    gamma = 1000

    # Search ranges for beta/gamma optimisation
    beta_min   = 1;    beta_max   = 100;  beta_delta   = 10
    gamma_min  = 1;    gamma_max  = 100;  gamma_delta  = 50

    # Grid search values used in loop optimisation
    alphas = '1 10 100'
    betas  = '1 10'
    gammas = '1 10 100 500 1000 1500 2000 3000 4000 5000'

    # Degrees of freedom included in the CEINMS model (derived from BatchSettings.dof_list,
    # excluding pelvis DOFs which have no muscle crossings)
    dof_set = ' '.join(d for d in BatchSettings.dof_list if 'pelvis' not in d)

    # --- Muscle parameter bounds (calibration) ---
    c1                   = '-0.99 -0.05'
    c2                   = '-0.95 -0.05'
    shape_factor         = '-2.999 -0.001'
    optimal_fiber_length = '0.5 3'
    tendon_slack_length  = '0.5 3'
    strength_coefficient = '0.75 3.5'

    # Target muscles ('all' or a list, e.g. ['glmax1_r', 'glmax2_r'])
    target_muscles = 'all'

    # EMG channel → OpenSim muscle mapping
    # Keys = EMG column names in the .mot file
    # Values = list of muscle names in the OpenSim model
    emg_muscle_mapping = {
        # Left leg
        'EMG_Channels_EMG01_vast_lat_l': ['vaslat_l', 'vasmed_l'],
        'EMG_Channels_EMG03_rect_fem_l': ['recfem_l', 'sart_l', 'tfl_l'],
        'EMG_Channels_EMG05_bic_fem_l':  ['bflh_l', 'bfsh_l', 'semimem_l', 'semiten_l'],
        'EMG_Channels_EMG07_glut_l':     ['glmax1_l', 'glmax2_l', 'glmax3_l'],
        'EMG_Channels_EMG09_gast_med_l': [],
        # Right leg
        'EMG_Channels_EMG02_vast_lat_r': ['vaslat_r', 'vasmed_r'],
        'EMG_Channels_EMG04_rect_fem_r': ['recfem_r', 'sart_r', 'tfl_r'],
        'EMG_Channels_EMG06_bic_fem_r':  ['bflh_r', 'bfsh_r', 'semimem_r', 'semiten_r'],
        'EMG_Channels_EMG08_glut_r':     ['glmax1_r', 'glmax2_r', 'glmax3_r'],
        'EMG_Channels_EMG10_gast_med_r': [],
    }

    # Calibration objective functions (order matters)
    objective_functions = [
        {'name': 'MomentError',  'targets': 'all', 'weight': 1},
        {'name': 'Penalty', 'targetType': 'normalisedFibreLength',
         'weight': 10,   'exponent': 2, 'range': '0.5 1.5'},
        {'name': 'Penalty', 'targetType': 'tendonStrain',
         'weight': 1000, 'exponent': 2, 'range': '0. 0.5'},
        {'name': 'ExcitationsSquared', 'weight': 1},
        {'name': 'SynergyExtraction',
         'mseWeight': 100, 'range': '0. 1.', 'rangeExponent': 2, 'rangeWeight': 1000},
    ]


# ============================================================================
# UI SETTINGS
# ============================================================================
class UISettings:
    """User interface appearance and layout configuration."""

    FONT_SIZE_SMALL = 10
    FONT_SIZE_NORMAL = 12
    FONT_SIZE_LARGE = 14
    FONT_SIZE_TITLE = 16
    FONT_FAMILY = "Segoe UI"

    PRIMARY_COLOR = "#2E86AB"
    SECONDARY_COLOR = "#A23B72"
    ACCENT_COLOR = "#F18F01"
    BACKGROUND_COLOR = "#F4F4F4"
    TEXT_COLOR = "#1A1A1A"
    ERROR_COLOR = "#C1121F"

    PADDING_SMALL = 5
    PADDING_NORMAL = 10
    PADDING_LARGE = 15

    BUTTON_HEIGHT = 35
    FRAME_HEIGHT = 200
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800

    sidebar_weight = 1
    content_weight = 3

    # Default tab shown on launch (must match a key in main_window tab_definitions)
    DEFAULT_TAB_ON_LAUNCH = "Session Analysis"


# ============================================================================
# RECORDING SETTINGS
# ============================================================================
class RecordingSettings:
    """Configuration for video recording during motion capture sessions."""

    enabled = False
    frame_rate = 30
    resolution = "1920x1080"
    codec = "H264"
    bitrate = "5000k"

    auto_name = True
    output_format = "mp4"

    # Recording tab defaults
    OUTPUT_DIR_TEMPLATE = r'C:\Recordings'
    DEFAULT_DURATION_SECONDS = 30
    DEFAULT_VIDEO_SOURCE = "webcam"
    IP_CAMERA_ADDRESS = "http://192.168.1.100:8080/video"
    DEFAULT_OSIM_MODEL = ""


# ============================================================================
# INPUTS - TRIAL-LEVEL FILE CONFIGURATION
# ============================================================================
class Inputs:
    """Configuration for trial-level file names and relative paths."""

    def __init__(self, parentdir=None):
        """Initialize default trial inputs."""
        self._parentdir = parentdir

        # Model files
        self.setup_dir = ''
        self.model_dir = ''

        # Timing
        self.start_time = '0.0000'
        self.end_time = '1.0000'

        # Input data files
        self.c3d = 'c3dfile.c3d'
        self.emg = 'emg.mot'
        self.emg_filtered_normalised = 'emg_filtered_normalised.mot'
        self.grf_mot = 'grf.mot'
        self.markerset = 'markers.xml'
        self.markers = 'marker_experimental.trc'
        self.events = 'events.csv'

        # OpenSim setup files
        self.setup_ik = 'setup_IK.xml'
        self.setup_grf = 'GRF.xml'
        self.setup_id = 'setup_ID.xml'
        self.setup_ma = 'setup_MA.xml'
        self.actuators_so = 'actuators_so.xml'
        self.setup_so = 'setup_SO.xml'
        self.jra_forces = 'SO_StaticOptimization_force.sto'
        self.setup_jra = 'setup_JRA.xml'

        # CEINMS files
        self.ceinms_excitations = self.emg_filtered_normalised
        self.ceinms_uncalibrated_model = os.path.join('..', 'subjectUncalibrated.xml')
        self.ceinms_calibrated_model = os.path.join('..', 'subjectCalibrated.xml')
        self.ceinms_calibration_cfg = os.path.join('..', 'calibrationCfg.xml')
        self.ceinms_calibration_setup = os.path.join('..', 'calibrationSetup.xml')
        self.ceinms_input_data = 'inputData.xml'
        self.ceinms_excitation_generator = os.path.join('..', 'excitationGenerator.xml')
        self.ceinms_optimise_setup = 'ceinms_setup_optimise.xml'
        self.ceinms_optimise_cfg = 'ceinms_cfg_optimise.xml'

        # CEINMS parameters
        self.alpha = '10'
        self.beta = '1'
        self.gamma = '1000'

        # CEINMS execution files
        self.ceinms_exe_cfg = 'ceinms_cfg.xml'
        self.ceinms_exe_setup = 'ceinms_setup.xml'

        # OpenSim output files
        self.ik = 'joint_angles.mot'
        self.model_markers = '_ik_model_marker_locations.sto'
        self.id = 'inverse_dynamics.sto'
        self.ma = 'muscleAnalysis'
        self.so_forces = 'SO_StaticOptimization_force.sto'
        self.so_activations = 'SO_StaticOptimization_activation.sto'
        self.jra = 'Analyse_JRA_ReactionLoads_SO.sto'

        # CEINMS output directories
        self.ceinms_calibration_dir = os.path.join('..', 'calibrationOutput')
        self.ceinms_optimisation_dir = 'Optimised'
        self.ceinms_exe_dir = 'Execution'

        # Dynamic CEINMS output paths
        self.ceinms_muscle_forces = os.path.join(
            f'{self.ceinms_exe_dir}_a{self.alpha}_b{self.beta}_g{self.gamma}',
            'MuscleForces.sto'
        )
        self.ceinms_activations = os.path.join(
            f'{self.ceinms_exe_dir}_a{self.alpha}_b{self.beta}_g{self.gamma}',
            'Activations.sto'
        )
        self.jra_ceinms = 'Analyse_JRA_ReactionLoads_CEINMS.sto'

    def to_dict(self):
        """Return all attributes as a dictionary."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================
Config = BatchSettings
