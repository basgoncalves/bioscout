"""
Project settings — powerlifting squat study.

Everything lives inside classes (no loose module-level variables or functions):
  * BatchSettings  — paths, subjects, trials, analysis config + batch/IK/GRF/EMG.
  * CEINMSSettings / SummarySettings / UISettings / RecordingSettings / Inputs.
bioscout reads it all via ``settings.BatchSettings.X`` etc.

KEEP THIS FILE — bioscout.Project()/init_project() loads it. ``__version__`` is
the settings-schema version (separate from the bioscout package version).
"""
import os
from pathlib import Path

# Guarded: this BUNDLED template is exec'd by bioscout.utils.settings DURING
# bioscout's own import, so a bare top-level import of bioscout.utils.* would be
# circular. The try/except lets it load; a real project's own settings.py
# (loaded after bioscout is ready) imports these directly without guarding.
try:
    from bioscout.utils.analysis import Subject, build_model_config, select_subjects, sessions_from_subjects
    from bioscout.utils.shared import trial_type as _trial_type
except Exception:
    Subject = None
    def build_model_config(*a, **k): return {}
    def select_subjects(subs=(), *a, **k): return list(subs)
    def sessions_from_subjects(*a, **k): return {}
    def _trial_type(name, *a, **k): return name

__version__ = "1.2.9"

# ---------------------------------------------------------------------------
# Run flags — read by `python -m bioscout -b settings.py` (bioscout.pipeline).
#   RUN_PIPELINE : rebuild inputs from c3d + IK/ID/MA/SO/JRA + CEINMS per session
#   RUN_SUMMARY  : build the results/manuscript summary (summarize_results.py)
#   RUN_SCALING  : (optional) re-scale models before the pipeline
#   RUN_CEINMS   : include the CEINMS stage in the pipeline (default True)
# ---------------------------------------------------------------------------
RUN_PIPELINE = True
RUN_SUMMARY  = True
RUN_SCALING  = False
RUN_CEINMS   = True


class BatchSettings:
    """All project + batch-analysis configuration."""

    # ---- paths -----------------------------------------------------------
    PROJECT_ROOT    = Path(__file__).resolve().parent
    PROJECT_NAME    = "powerlifting_squat"
    MODELS_DIR      = PROJECT_ROOT / "models"
    SETUP_DIR       = PROJECT_ROOT / "setupFiles"
    SIMULATIONS_DIR = PROJECT_ROOT / "simulations"
    LOG_DIR         = PROJECT_ROOT / "logs"

    # ---- session & trials ------------------------------------------------
    SESSION      = "25_03_31"
    session_list = [SESSION]
    trial_list   = ["Walking_02", "Squat_BW_01", "Squat_35kg_01"]
    TRIAL_TYPE_PATTERN = r"(.+?)_(\d+)$"

    # ---- subjects --------------------------------------------------------
    # Curated metadata; choose which to process with RUN_/SKIP_ (names or indices).
    ALL_SUBJECTS = [] if Subject is None else [
        Subject("Athlete_03_Cateli",     label="Scaled (Cateli)",     session=SESSION,
                model_so="scaled_opt_N10_increased_3.00.osim", model_ceinms="scaled_opt_N10.osim",
                setup_folder="Purzel",     color="green",  group="generic"),
        Subject("Athlete_03_Lernagopal", label="Scaled (Lernagopal)", session=SESSION,
                model_so="scaled_89_opt_N10_increased_3.00.osim", model_ceinms="scaled_89_opt_N10.osim",
                setup_folder="Lernagopal", color="blue",   group="generic"),
        Subject("Athlete_03_GPK",        label="Scaled (GPK)",        session=SESSION,
                model_so="scaled_increased_3.00.osim", model_ceinms="scaled.osim",
                setup_folder="GPK",        color="red",    group="generic"),
        Subject("Athlete_03_GPK_MRI",    label="MRI (GPK)",           session=SESSION,
                model_so="GPK_MRI_scaled_increased_3.00.osim", model_ceinms="GPK_MRI_scaled.osim",
                setup_folder="GPK",        color="purple", group="MRI"),
    ]
    RUN_SUBJECTS  = None      # None/[] = all; e.g. ["Athlete_03_GPK"] or [2, 3]
    SKIP_SUBJECTS = []        # e.g. ["Athlete_03_Cateli"] or [0]

    SUBJECTS         = select_subjects(ALL_SUBJECTS, RUN_SUBJECTS, SKIP_SUBJECTS)
    SUBJECTS_BY_NAME = {s.name: s for s in SUBJECTS}
    model_config     = build_model_config(SUBJECTS, force_types=("SO", "CEINMS"))
    MODEL_FILES      = {s.name: s.model_ceinms for s in SUBJECTS}
    SETUP_FOLDERS    = {s.name: s.setup_folder for s in SUBJECTS}
    # session map {path: static_trial} — Project also derives this at runtime.
    sessions         = sessions_from_subjects(SUBJECTS, SIMULATIONS_DIR)

    # ---- analysis / comparison config ------------------------------------
    DOFS = ["hip_flexion_r", "hip_adduction_r", "hip_rotation_r",
            "knee_angle_r", "knee_adduction_r", "ankle_angle_r"]
    DOFS_MOMENTS = [d + "_moment" for d in DOFS]
    MODELS_TO_FLIP_KNEE = ["Lernagopal", "GPK"]
    CONTRASTS = {
        "generic_vs_mri": ["Scaled (GPK)", "MRI (GPK)"],
        "so_vs_ceinms":   ["Scaled (GPK)", "Scaled (GPK) - CEINMS"],
        "across_models":  ["Scaled (Cateli)", "Scaled (Lernagopal)", "Scaled (GPK)"],
    }
    MUSCLE_GROUPS = {
        "R Gluteus maximus":  ["glmax1_r", "glmax2_r", "glmax3_r"],
        "R Gluteus medius":   ["glmed1_r", "glmed2_r", "glmed3_r"],
        "R Gluteus minimus":  ["glmin1_r", "glmin2_r", "glmin3_r"],
        "R Adductor Magnus":  ["addmagDist_r", "addmagIsch_r", "addmagMid_r", "addmagProx_r"],
        "R Biceps Femoris":   ["bflh_r", "bfsh_r"],
        "R Semimembranosus":  ["semimem_r"],
        "R Semitendinosus":   ["semiten_r"],
        "R Rectus Femoris":   ["recfem_r"],
        "R Vasti":            ["vasint_r", "vaslat_r", "vasmed_r"],
        "R Triceps Surae":    ["soleus_r", "gaslat_r", "gasmed_r"],
    }

    # Time-normalise (downsample) exported inputs/results to this many frames.
    # 0 = native sampling. ~100 is near-lossless for kinematics/moments.
    normalise_inputs = 100

    # ---- batch / IK / GRF / EMG processing -------------------------------
    setup_files_folder = SETUP_DIR
    generic_model = os.path.join(MODELS_DIR, "Rajagopal2015_FAI_os4.osim")
    markerset = os.path.join(SETUP_DIR, "markers_FAIS.xml")
    trials_to_skip: list = []
    trials_to_run:  list = []
    auto_create_dirs = True
    replace_existing = True
    dof_list = [
        "hip_flexion_l", "hip_flexion_r", "hip_adduction_l", "hip_adduction_r",
        "hip_rotation_l", "hip_rotation_r", "knee_angle_l", "knee_angle_r",
        "ankle_angle_l", "ankle_angle_r",
    ]
    marker_weights = {
        "pelvis": 10.0,
        "femur_r": 1.0, "tibia_r": 1.0, "talus_r": 1.0, "calcn_r": 2.0, "toes_r": 2.0,
        "femur_l": 1.0, "tibia_l": 1.0, "talus_l": 1.0, "calcn_l": 2.0, "toes_l": 2.0,
    }
    emg_muscle_mapping = {
        "EMG_Channels_EMG02_L_gastro_med": ["fdl_l", "fhl_l", "gasmed_l", "gaslat_l", "perbrev_l", "perlong_l", "soleus_l", "tibpost_l"],
        "EMG_Channels_EMG05_L_rect_fem":   ["recfem_l", "sart_l", "tfl_l"],
        "EMG_Channels_EMG06_L_vast_med":   ["vaslat_l", "vasmed_l", "vasint_l"],
        "EMG_Channels_EMG07_L_semitend":   ["bflh_l", "bfsh_l", "semimem_l", "semiten_l"],
        "EMG_Channels_EMG08_L_glut_med":   ["glmed1_l", "glmed2_l", "glmed3_l"],
        "EMG_Channels_EMG10_R_gastro_med": ["fdl_r", "fhl_r", "gasmed_r", "gaslat_r", "perbrev_r", "perlong_r", "soleus_r", "tibpost_r"],
        "EMG_Channels_EMG13_R_rect_fem":   ["recfem_r", "sart_r", "tfl_r"],
        "EMG_Channels_EMG14_R_vast_med":   ["vaslat_r", "vasmed_r", "vasint_r"],
        "EMG_Channels_EMG15_R_semitend":   ["bflh_r", "bfsh_r", "semimem_r", "semiten_r"],
        "EMG_Channels_EMG16_R_glut_med":   ["glmed1_r", "glmed2_r", "glmed3_r"],
    }
    emg_label_default = "Voltage"
    emg_lowpass_default = "500"
    emg_highpass_default = "10"
    emg_notch_default = "50"
    emg_string_list = ["EMG", "Voltage", "muscle"]
    emg_sampling_freq = 1000
    right_foot_markers = ["RTOE", "RHEE", "RFMH", "RSMH", "RVMH"]
    left_foot_markers = ["LTOE", "LHEE", "LFMH", "LSMH", "LVMH"]
    trc_lateral_axis  = "Z"
    trc_vertical_axis = "Y"
    trc_ap_axis       = "X"
    grf_axis_map = {"x": ("x", 1.0), "y": ("z", 1.0), "z": ("y", -1.0)}
    grf_cop_scale_to_m = 0.001
    grf_moment_scale   = 0.001
    grf_moment_sign    = -1.0
    c3d_file_col_weight = 3
    c3d_settings_col_weight = 7
    c3d_emg_channels_height = 40
    c3d_markers_height = 40
    enable_c3d_export = True
    enable_scale_model = True
    enable_muscle_scaling = False
    muscle_force_factor = 3
    enable_inverse_kinematics = True
    enable_inverse_dynamics = True
    enable_static_optimization = True
    enable_muscle_analysis = True
    enable_emg_normalise = True

    # ---- helpers (as static methods, not loose functions) ----------------
    @staticmethod
    def trial_type(trial_name):
        """'Squat_35kg_02' -> 'Squat_35kg' (groups reps of a task)."""
        return _trial_type(trial_name, BatchSettings.TRIAL_TYPE_PATTERN)

    @staticmethod
    def model_for(subject, force_type="SO"):
        s = BatchSettings.SUBJECTS_BY_NAME.get(subject)
        return s.model_for(force_type) if s else None

    @staticmethod
    def JRA_COLUMNS(model_name):
        """Joint-reaction (contact-force) column names per model (knee differs)."""
        name = model_name or ""
        hip = ["hip_r_on_femur_r_in_femur_r_fx", "hip_r_on_femur_r_in_femur_r_fy", "hip_r_on_femur_r_in_femur_r_fz"]
        ankle = ["ankle_r_on_talus_r_in_talus_r_fx", "ankle_r_on_talus_r_in_talus_r_fy", "ankle_r_on_talus_r_in_talus_r_fz"]
        if "Lernagopal" in name or "MRI" in name:   # both use the Lerner knee joint
            knee = ["Lerner_knee_r_on_sagittal_articulation_frame_r_in_sagittal_articulation_frame_r_fx",
                    "Lerner_knee_r_on_sagittal_articulation_frame_r_in_sagittal_articulation_frame_r_fy",
                    "Lerner_knee_r_on_sagittal_articulation_frame_r_in_sagittal_articulation_frame_r_fz"]
        else:
            knee = ["walker_knee_r_on_tibia_r_in_tibia_r_fx", "walker_knee_r_on_tibia_r_in_tibia_r_fy", "walker_knee_r_on_tibia_r_in_tibia_r_fz"]
        return {"hip": hip, "knee": knee, "ankle": ankle}

    @property
    def results_dir(self):
        return Path(next(iter(self.sessions))) if self.sessions else Path(".")


class CEINMSSettings:
    enable_calibration = True
    enable_execution   = True
    calibration_trial_names = ["Walking_02", "Squat_BW_01"]
    calibration_type = "hybrid"
    tendon_type = "elastic"
    learning_rate = 0.02
    max_iterations = 1000
    early_stopping_patience = 20
    early_stopping_min_improvement = 0.1
    num_synergies = 4
    hybrid_calibration = "true"
    number_of_synergies = 8
    alpha = 10
    beta  = 1
    gamma = 1000
    beta_min = 1;  beta_max = 100;  beta_delta = 10
    gamma_min = 1; gamma_max = 100; gamma_delta = 50
    alphas = "1 10 100"
    betas  = "1 10"
    gammas = "1 10 100 500 1000 1500 2000 3000 4000 5000"
    dof_set = " ".join(d for d in BatchSettings.dof_list if "pelvis" not in d)
    c1 = "-0.99 -0.05"
    c2 = "-0.95 -0.05"
    shape_factor = "-2.999 -0.001"
    optimal_fiber_length = "0.5 3"
    tendon_slack_length = "0.5 3"
    strength_coefficient = "0.75 3.5"
    target_muscles = "all"
    emg_muscle_mapping = BatchSettings.emg_muscle_mapping
    objective_functions = [
        {"name": "MomentError", "targets": "all", "weight": 1},
        {"name": "Penalty", "targetType": "normalisedFibreLength", "weight": 10, "exponent": 2, "range": "0.5 1.5"},
        {"name": "Penalty", "targetType": "tendonStrain", "weight": 1000, "exponent": 2, "range": "0. 0.5"},
        {"name": "ExcitationsSquared", "weight": 1},
        {"name": "SynergyExtraction", "mseWeight": 100, "range": "0. 1.", "rangeExponent": 2, "rangeWeight": 1000},
    ]


class SummarySettings:
    combine_legs = True
    left_color = "tab:red"
    right_color = "tab:blue"
    rows = ["angle", "emg", "moment", "moment_arms", "muscle_forces", "activations", "energetics"]
    joint_marker_patterns = {
        "hip":   ["ASI", "PSI", "SACR", "THI"],
        "knee":  ["THI", "FC", "TIB", "KNE"],
        "ankle": ["TIB", "MAL", "ANK", "HEE", "MT"],
    }
    joint_muscles = {}


class UISettings:
    FONT_SIZE_SMALL = 20; FONT_SIZE_NORMAL = 24; FONT_SIZE_LARGE = 28; FONT_SIZE_TITLE = 32
    FONT_FAMILY = "Segoe UI"
    PRIMARY_COLOR = "#2E86AB"; SECONDARY_COLOR = "#A23B72"; ACCENT_COLOR = "#F18F01"
    BACKGROUND_COLOR = "#F4F4F4"; TEXT_COLOR = "#1A1A1A"; ERROR_COLOR = "#C1121F"
    PADDING_SMALL = 5; PADDING_NORMAL = 10; PADDING_LARGE = 15
    BUTTON_HEIGHT = 35; FRAME_HEIGHT = 200; WINDOW_WIDTH = 1200; WINDOW_HEIGHT = 800
    sidebar_weight = 1; content_weight = 3
    DEFAULT_TAB_ON_LAUNCH = "Session Analysis"


class RecordingSettings:
    enabled = False
    frame_rate = 30
    resolution = "1920x1080"
    codec = "H264"
    bitrate = "5000k"
    auto_name = True
    output_format = "mp4"
    OUTPUT_DIR_TEMPLATE = str(BatchSettings.PROJECT_ROOT / "recordings")
    DEFAULT_DURATION_SECONDS = 5
    DEFAULT_VIDEO_SOURCE = "webcam"
    IP_CAMERA_ADDRESS = "http://192.168.1.100:8080/video"
    DEFAULT_OSIM_MODEL = "GPK_generic"
    DEFAULT_VIDEO_ANALYSIS_MODEL = "GPK_generic"
    DEFAULT_POSE_MAX_DELTA_PX = 50


class Inputs:
    def __init__(self, parentdir=None):
        self._parentdir = parentdir
        self.setup_dir = ""
        self.model_dir = ""
        self.start_time = "0.0000"
        self.end_time = "1.0000"
        self.c3d = "c3dfile.c3d"
        self.emg = "emg.mot"
        self.emg_filtered_normalised = "emg_filtered_normalised.mot"
        self.grf_mot = "grf.mot"
        self.markerset = "markers_FAIS.xml"
        self.markers = "marker_experimental.trc"
        self.events = "events.csv"
        self.setup_ik = "setup_IK.xml"
        self.setup_grf = "GRF.xml"
        self.setup_id = "setup_ID.xml"
        self.setup_ma = "setup_MA.xml"
        self.actuators_so = "actuators_so.xml"
        self.setup_so = "setup_SO.xml"
        self.jra_forces = "SO_StaticOptimization_force.sto"
        self.setup_jra = "setup_JRA.xml"
        self.ceinms_excitations = self.emg_filtered_normalised
        self.ceinms_uncalibrated_model = os.path.join("..", "subjectUncalibrated.xml")
        self.ceinms_calibrated_model = os.path.join("..", "subjectCalibrated.xml")
        self.ceinms_calibration_cfg = os.path.join("..", "calibrationCfg.xml")
        self.ceinms_calibration_setup = os.path.join("..", "calibrationSetup.xml")
        self.ceinms_input_data = "inputData.xml"
        self.ceinms_excitation_generator = os.path.join("..", "excitationGenerator.xml")
        self.ceinms_optimise_setup = "ceinms_setup_optimise.xml"
        self.ceinms_optimise_cfg = "ceinms_cfg_optimise.xml"
        self.alpha = "10"
        self.beta = "1"
        self.gamma = "1000"
        self.ceinms_exe_cfg = "ceinms_cfg.xml"
        self.ceinms_exe_setup = "ceinms_setup.xml"
        self.ik = "joint_angles.mot"
        self.model_markers = "_ik_model_marker_locations.sto"
        self.id = "inverse_dynamics.sto"
        self.ma = "muscleAnalysis"
        self.so_forces = "SO_StaticOptimization_force.sto"
        self.so_activations = "SO_StaticOptimization_activation.sto"
        self.jra = "Analyse_JRA_ReactionLoads_SO.sto"
        self.ceinms_calibration_dir = os.path.join("..", "calibrationOutput")
        self.ceinms_optimisation_dir = "Optimised"
        self.ceinms_exe_dir = "Execution"
        self.ceinms_muscle_forces = os.path.join(f"{self.ceinms_exe_dir}_a{self.alpha}_b{self.beta}_g{self.gamma}", "MuscleForces.sto")
        self.ceinms_activations = os.path.join(f"{self.ceinms_exe_dir}_a{self.alpha}_b{self.beta}_g{self.gamma}", "Activations.sto")
        self.jra_ceinms = "Analyse_JRA_ReactionLoads_CEINMS.sto"

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


Config = BatchSettings
