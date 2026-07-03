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


# The canonical trial layout now lives in bioscout.layout (a standalone module
# with no heavy deps), so it is the single source of truth and importing it is
# cycle-free. Re-exported here for back-compat: existing code and projects that
# reference ``settings.Inputs`` keep working unchanged. A project only needs to
# define its own ``Inputs`` if it wants to OVERRIDE the default folder layout.
from bioscout.layout import Inputs, Layout   # noqa: F401


# Guarded: this BUNDLED template is exec'd by bioscout.utils.settings DURING
# bioscout's own import, so a bare top-level import of bioscout.utils.* would be
# circular (utils.settings is not assigned yet). The try/except lets it load; a
# real project's own settings.py (loaded after bioscout is ready) imports these
# directly without needing the guard.
try:
    from bioscout.utils.analysis import Subject, build_model_config, select_subjects, sessions_from_subjects
    from bioscout.utils.shared import trial_type as _trial_type
except Exception:
    Subject = None
    def build_model_config(*a, **k): return {}
    def select_subjects(subs=(), *a, **k): return list(subs)
    def sessions_from_subjects(*a, **k): return {}
    def _trial_type(name, *a, **k): return name

__version__ = "1.2.10"

RUN_PIPELINE = True    # run the full pipeline (IK + ID + SO + MA + CEINMS) for each trial
RUN_SUMMARY  = True    # generate summary figures + metrics CSVs
RUN_SCALING  = False   # reuse existing scaled models (no re-scaling)
RUN_CEINMS   = True    # run CEINMS (calibration + execution) for each trial

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
    # SESSION is just the default session-folder name applied to each Subject
    # below (so you don't repeat the date on every one). The dict the pipeline
    # actually runs is `sessions` (built from SUBJECTS further down).
    SESSION      = "25_03_31"
    trial_list   = ["Walking_02", "Squat_BW_01", "Squat_35kg_01"]
    TRIAL_TYPE_PATTERN = r"(.+?)_(\d+)$"

    # ---- subjects --------------------------------------------------------
    # Curated metadata; choose which to process with RUN_/SKIP_ (names or indices).
    # `[] if Subject is None` keeps the guarded template exec (above) from failing.
    ALL_SUBJECTS = [] if Subject is None else [
        Subject("Athlete_03_Cateli",     label="Scaled (Cateli)",     session=SESSION,
                model_so="scaled_opt_N10_muscles_copied.00.osim", model_ceinms="scaled_opt_N10.osim",
                setup_folder="Purzel",     color="green",  group="generic"),
        Subject("Athlete_03_Lernagopal", label="Scaled (Lernagopal)", session=SESSION,
                model_so="scaled_89_opt_N10_mvicx3.00.osim", model_ceinms="scaled_89_opt_N10.osim",
                setup_folder="Lernagopal", color="blue",   group="generic"),
        Subject("Athlete_03_GPK",        label="Scaled (GPK)",        session=SESSION,
                model_so="scaled_mvicx3.00.osim", model_ceinms="scaled.osim",
                setup_folder="GPK",        color="red",    group="generic"),
        Subject("Athlete_03_GPK_MRI",    label="MRI (GPK)",           session=SESSION,
                model_so="GPK_MRI_scaled_mvicx3.00.osim", model_ceinms="GPK_MRI_scaled.osim",
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

    # ---- literature JCF overlay styling (plot_jra_comparison resultant) ---
    # Literature contact-force curves drawn on the |resultant| panels. Sources
    # with a variance band render as a shaded band; sources with only a mean
    # curve render as a dashed reference line. Tune readability here.
    literature_band_alpha = 0.18   # opacity of the shaded uncertainty band (0-1)
    literature_line_alpha = 0.60   # opacity of the dashed reference lines (0-1)
    literature_line_width = 1.8    # width of the dashed reference lines

    # Time-normalise (downsample) exported inputs/results to this many frames.
    # 0 = native sampling. ~100 is near-lossless for kinematics/moments.
    normalise_inputs = 100

    # ---- batch / IK / GRF / EMG processing -------------------------------
    setup_files_folder = SETUP_DIR
    generic_model = os.path.join(MODELS_DIR, "Rajagopal2015_FAI_os4.osim")
    markerset = os.path.join(SETUP_DIR, "markers_FAIS.xml")
    trials_to_skip: list = []
    trials_to_run:  list = []

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
    # Keys MUST match the EMG column names exported to emg.mot from the C3D
    # (channels EMG01-12 were labelled at capture; EMG13-16 came through unnamed
    # and are unused). Muscle groupings preserved from the original design.
    emg_muscle_mapping = {
        # left
        "EMG_Channels_EMG01_vast_lat_l":  ["vaslat_l", "vasmed_l", "vasint_l"],
        "EMG_Channels_EMG03_rect_fem_l":  ["recfem_l", "sart_l", "tfl_l"],
        "EMG_Channels_EMG05_bic_fem_l":   ["bflh_l", "bfsh_l", "semimem_l", "semiten_l"],
        "EMG_Channels_EMG07_glut_l":      ["glmed1_l", "glmed2_l", "glmed3_l"],
        "EMG_Channels_EMG09_gast_med_l":  ["fdl_l", "fhl_l", "gasmed_l", "gaslat_l", "perbrev_l", "perlong_l", "soleus_l", "tibpost_l"],
        # right
        "EMG_Channels_EMG02_vast_lat_r":  ["vaslat_r", "vasmed_r", "vasint_r"],
        "EMG_Channels_EMG04_rect_fem_r":  ["recfem_r", "sart_r", "tfl_r"],
        "EMG_Channels_EMG06_bic_fem_r":   ["bflh_r", "bfsh_r", "semimem_r", "semiten_r"],
        "EMG_Channels_EMG08_glut_r":      ["glmed1_r", "glmed2_r", "glmed3_r"],
        "EMG_Channels_EMG10_gast_med_r":  ["fdl_r", "fhl_r", "gasmed_r", "gaslat_r", "perbrev_r", "perlong_r", "soleus_r", "tibpost_r"],
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

    auto_create_dirs = True
    replace_existing = True
    enable_c3d_export = True
    enable_scale_model = True
    enable_muscle_scaling = False
    muscle_force_factor = 20
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
    calibration_trial_names = ["Walking_02"]
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
    """Configuration for the results summary (bioscout.summarize_results())."""

    # ---- what to summarise -----------------------------------------------
    # Reference model (name or label) that others are compared against (RMSE/R2).
    reference_model = "Athlete_03_Cateli"
    algorithms      = ["SO", "CEINMS"]
    # Extra trials to include on top of BatchSettings.trial_list (if present on disk).
    extra_trials    = ["Squat_35kg_02", "Squat_BW_02", "Walking_03"]
    npts            = 101            # time-normalisation points for every curve
    joints          = ["hip", "knee", "ankle"]

    # ---- output ----------------------------------------------------------
    output_subdir   = "manuscript"   # under PROJECT_ROOT; figures go in <subdir>/figures
    style           = "minimal"      # "minimal" | "poster" | "journal"
    dpi             = 200
    export_csv      = True           # write metrics_long.csv + metrics_wide.csv for JASP

    # ---- which figures to build ------------------------------------------
    figures = {
        "marker_errors":   True,
        "kin_mom":         True,   # 02 — kinematics + moments (+ R2/RMSE text boxes)
        "moment_arms":     True,   # 02b
        "muscle_dynamics": True,   # 04 — activations(+EMG bg)/lengths/forces + EMG R2/RMSE
        "jrf":             True,   # 05b — joint reaction force components
        "poster":          True,   # 05 — catchy summary + hypothesis verdict
    }
    emg_background   = True         # draw EMG as a grey filled background on activations
    annotate_stats   = True         # R2/RMSE text boxes on kin/mom + muscle figures

    # ---- hypothesis (stated, and answered from the data in the poster) ---
    hypothesis = ("Bone geometry (MRI) DECREASES muscle & joint forces; "
                  "measured coordination (CEINMS) INCREASES muscle & joint forces.")

    # ---- styling ---------------------------------------------------------
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


Config = BatchSettings
