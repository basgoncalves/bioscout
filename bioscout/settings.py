"""Project settings — BUNDLED TEMPLATE (powerlifting squat study).

This is the default settings module shipped inside bioscout.
``init_project()`` copies it into a new project and ``bioscout.Project()``
falls back to it when a project has no settings.py of its own. A real
project edits its OWN copy — KEEP THIS FILE.

``__version__`` here is the settings-SCHEMA version, an INDEPENDENT series
from the bioscout package version: it is what a project pins to say which
SHAPE of settings.py it was written against, and
``check_settings_version`` compares its MAJOR.MINOR against a project's
own value. Bump it only when that shape actually changes.

Running a project copy of this file directly:

    conda activate msk311
    python settings.py                 # run the pipeline over ITERATIONS
    python settings.py --check-scaling
    python settings.py --rescale-all
    python settings.py --sessions 25_03_31 --skip cateli --reuse-models

Every switch lives in the CONTROL PANEL below. Everything after it is
configuration bioscout reads at run time, then the runner.

The reasoning that used to fill this file -- why a flag is set the way it is,
what breaks if it is not -- is in bioscout/docs/SETTINGS.md, and the file it
was extracted from is kept beside this one as settings.py.pre_streamline.
"""
import os
from pathlib import Path

# Guarded: this BUNDLED template is exec'd by bioscout DURING its own
# import, so a bare top-level import of bioscout.utils.* would be circular
# (utils.analysis is not assigned yet). A real project's own settings.py —
# loaded after bioscout is ready — takes the real imports.
try:
    from bioscout.utils.analysis import (
        Subject, build_model_config, select_subjects, sessions_from_subjects,
        discover_sessions)
    from bioscout.utils.shared import trial_type as _trial_type
except Exception:
    Subject = None
    def build_model_config(*a, **k): return {}
    def select_subjects(subs=(), *a, **k): return list(subs)
    def sessions_from_subjects(*a, **k): return {}
    def discover_sessions(*a, **k): return []
    def _trial_type(name, *a, **k): return name

__version__ = "2.0.0b1"


PROJECT_NAME    = "powerlifting_squat"
PROJECT_ROOT    = Path(__file__).resolve().parent
MODELS_DIR      = PROJECT_ROOT / "models"
SETUP_DIR       = PROJECT_ROOT / "setupFiles"
SIMULATIONS_DIR = PROJECT_ROOT / "simulations"
RESULTS_DIR     = PROJECT_ROOT / "results"
LOG_DIR         = PROJECT_ROOT / "logs"
SESSION         = "25_03_31"

CAPTURES = {
    "25_03_31": dict(
        subject="Athlete_03",
        static_trial="Static_01",
        iterations=["cateli", "lernagopal", "gpk",
                    "cateli_mri", "lernagopal_mri", "gpk_mri"],
        trials=["Squat_35kg_01", "Squat_35kg_02", "Squat_BW_01", "Squat_BW_02",
                "Walking_03", "Walking_05", "Deadlift_35kg_01", "Deadlift_35kg_02"],
        cal_trials=["Walking_03", "Squat_BW_01"],
        trial_list=["Walking_03", "Walking_05", "Squat_BW_01", "Squat_BW_02"],
        extra_trials=["Squat_35kg_02", "Squat_BW_02", "Walking_03"],
        emg_sampling_freq=2000,
        emg_bandpass_high_hz=450.0,
        grf_plate_force_sign={1: {"vx": -1}},
        emg_muscle_mapping={
            # NARROWED, and it must stay in step with session.yaml's emg_map --
            # that file outranks this one at run time (Session.trial_config), so
            # if the two drift, this dict is the one that silently does nothing.
            # gast_med drives ONLY the two gastrocnemii: it is a two-joint
            # muscle and its signal says nothing about soleus, the peroneals,
            # tibialis posterior or the toe flexors. rect_fem likewise drives
            # only rectus femoris, not sartorius and TFL.
            "EMG_Channels_EMG01_vast_lat_l":  ["vaslat_l", "vasmed_l", "vasint_l"],
            "EMG_Channels_EMG03_rect_fem_l":  ["recfem_l"],
            "EMG_Channels_EMG05_bic_fem_l":   ["bflh_l", "bfsh_l", "semimem_l", "semiten_l"],
            "EMG_Channels_EMG07_glut_l":      ["glmed1_l", "glmed2_l", "glmed3_l"],
            "EMG_Channels_EMG09_gast_med_l":  ["gasmed_l", "gaslat_l"],
            "EMG_Channels_EMG02_vast_lat_r":  ["vaslat_r", "vasmed_r", "vasint_r"],
            "EMG_Channels_EMG04_rect_fem_r":  ["recfem_r"],
            "EMG_Channels_EMG06_bic_fem_r":   ["bflh_r", "bfsh_r", "semimem_r", "semiten_r"],
            "EMG_Channels_EMG08_glut_r":      ["glmed1_r", "glmed2_r", "glmed3_r"],
            "EMG_Channels_EMG10_gast_med_r":  ["gasmed_r", "gaslat_r"],
        },
        tps_landmarks=("mri", "Athlete_03", "orientation_Katya.mrk.json"),
        tps_iterations=["cateli_mri", "lernagopal_mri", "gpk_mri"],
    ),

    "22_07_13": dict(
        subject="Athlete_06",
        static_trial="Static_01",
        iterations=["cateli", "lernagopal", "gpk"],
        trials=["Squat_70_01", "Squat_75_01", "Squat_80_01", "Squat_85_01", "Squat_90_01",
                "Deadlift_70_01", "Deadlift_75_01", "Deadlift_80_01", "Deadlift_85_01",
                "Deadlift_90_01"],
        cal_trials=["Squat_70_01", "Squat_80_01"],
        trial_list=["Squat_70_01", "Squat_90_01"],
        extra_trials=["Squat_75_01", "Squat_80_01", "Squat_85_01"],
        emg_sampling_freq=1000,
        emg_bandpass_high_hz=400.0,
        grf_plate_force_sign={},
        emg_muscle_mapping={
            "Voltage_EMG1_vast_lat_l":  ["vaslat_l", "vasmed_l", "vasint_l"],
            "Voltage_EMG3_rect_fem_l":  ["recfem_l", "sart_l", "tfl_l"],
            "Voltage_EMG5_bic_fem_l":   ["bflh_l", "bfsh_l", "semimem_l", "semiten_l"],
            "Voltage_EMG7_glut_max_l":  ["glmax1_l", "glmax2_l", "glmax3_l"],
            "Voltage_EMG9_gast_med_l":  ["fdl_l", "fhl_l", "gasmed_l", "gaslat_l", "perbrev_l", "perlong_l", "soleus_l", "tibpost_l"],
            "Voltage_EMG2_vast_lat_r":  ["vaslat_r", "vasmed_r", "vasint_r"],
            "Voltage_EMG4_rect_fem_r":  ["recfem_r", "sart_r", "tfl_r"],
            "Voltage_EMG6_bic_fem_r":   ["bflh_r", "bfsh_r", "semimem_r", "semiten_r"],
            "Voltage_EMG8_glut_max_r":  ["glmax1_r", "glmax2_r", "glmax3_r"],
            "Voltage_EMG10_gast_med_r": ["fdl_r", "fhl_r", "gasmed_r", "gaslat_r", "perbrev_r", "perlong_r", "soleus_r", "tibpost_r"],
        },
        tps_landmarks=None,
        tps_iterations=[],
    ),
}

if SESSION not in CAPTURES:
    raise SystemExit(
        f"settings.py: SESSION = {SESSION!r} has no entry in CAPTURES. "
        f"Known: {', '.join(sorted(CAPTURES))}. Add one rather than letting the "
        f"other capture's EMG map and plate signs be used silently.")
CAPTURE = CAPTURES[SESSION]

# ============================================================================
#  CONTROL PANEL — every switch this project has, in one place.
#  What each one means: bioscout/docs/SETTINGS.md
# ============================================================================
# -- read by bioscout itself (must stay module-level) ------------------------
RUN_PIPELINE = True
RUN_SUMMARY  = False
RUN_SCALING  = True
RUN_CEINMS   = True
LOG_TYPE = "minimal"
# -- the single-session runner (python settings.py) --------------------------
RUN_TPS_PERSONALISE     = False
RUN_SESSION_ITERATIONS  = True
RUN_SINGLE_ITERATION    = False
RUN_PRUNE_LEGACY_INPUTS = False
# -- what to run over --------------------------------------------------------
ITERATIONS   = list(CAPTURE["iterations"])
TRIALS       = list(CAPTURE["trials"])
STATIC_TRIAL = CAPTURE["static_trial"]
CAL_TRIALS  = list(CAPTURE["cal_trials"])
REPLACE      = True
# -- stages, in pipeline order -----------------------------------------------
#
#  SET FOR THE a1 b1 g30 CEINMS RE-RUN (2026-08-10). Only the CEINMS execution
#  weights changed, so only CEINMS and what depends on it is rebuilt:
#
#    scaling / IK / ID / MA / SO  are inputs to CEINMS, not outputs of it, and
#    nothing about them changed -- re-running them would burn hours to write
#    byte-identical files. They are already on disk and were NOT backed up.
#
#    CALIBRATE = False is deliberate, and is the switch to check first if the
#    results look wrong. The calibrated model depends on the CALIBRATION
#    objective (see CEINMSSettings.objective_functions) and on the excitation
#    generator -- NOT on alpha/beta/gamma, which are execution-only weights.
#    The generators on disk were rebuilt on 2026-08-08 with the narrowed EMG
#    map already in force: 26 prescribed excitations, soleus correctly absent.
#    So they are current. Set this True only if the EMG map, the calibration
#    trials or the calibration objective change.
#
#  To go back to a full rebuild: DO_SCALE / DO_MA / DO_SO / CALIBRATE = True.
DO_EXPORT   = False
EXPORT_SRC  = None
# Movement detection: classify every exported trial from its markers/GRF and
# write session_auto_detection.yaml + movement_detection/ beside the session.
# Runs straight after export because that is when the .trc and grf.mot it reads
# first exist, and because a wrong trial type in session.yaml is cheapest to
# catch before it has been carried through IK, ID, SO and CEINMS.
DO_DETECT   = False
# True = also correct session.yaml's trial types from the detection (the old
# file is kept as session.yaml.pre_detection). Leave False to only write
# session_auto_detection.yaml and review it by hand first.
DETECT_WRITE_YAML = False
DO_SCALE    = False
MUSCLE_OPT  = None
DO_EXBIOMEC = False
DO_MA       = False
DO_SO       = False
DO_CEINMS   = True
CALIBRATE   = False
DO_PLOTS    = True
FIGURES     = ["kin_mom", "jra"]
DO_SUMMARY  = True
# -- TPS / MRI personalisation -----------------------------------------------
TPS_ITERATIONS = list(CAPTURE["tps_iterations"])
TPS_INSPECT = True
TPS_LANDMARKS = (os.path.join(PROJECT_ROOT, *CAPTURE["tps_landmarks"])
                 if CAPTURE["tps_landmarks"] else None)
# -- legacy-input pruning ----------------------------------------------------
PRUNE_DRY_RUN = False
PRUNE_ARCHIVE = os.path.join("_to_delete", "legacy_inputs")


GROUPS = {
    "cateli": dict(
        generic_model="Catelli_high_hip_Flexion_V4.0/Catelli-V4.0_PowerliftingMarkers.osim",
        model_so="scaled_opt_N10_mvicx3.00.osim", model_ceinms="scaled_opt_N10.osim",
        static_trial="Static_01", setup_folder=SETUP_DIR,
        label="Scaled (Cateli)", color="green", group="generic"),
    "lernagopal": dict(
        generic_model="Lernagopal/Lernagopal_41_OUF_PowerlifitingMarkers.osim",
        model_so="scaled_89_opt_N10_mvicx3.00.osim", model_ceinms="scaled_89_opt_N10.osim",
        static_trial="Static_01", setup_folder=SETUP_DIR,
        label="Scaled (Lernagopal)", color="blue", group="generic"),
    "gpk": dict(
        generic_model="GPK/GPK_v3.osim",
        model_so="scaled_mvicx3.00.osim", model_ceinms="scaled.osim",
        static_trial="Static_01", setup_folder=SETUP_DIR,
        label="Scaled (GPK)", color="red", group="generic"),
    "gpk_mri": dict(
        generic_model="GPK/GPK_v3_tps_Athlete_03.osim",
        linear_scaling=False, marker_placer=True,
        model_so="scaled_mvicx3.00.osim", model_ceinms="scaled.osim",
        static_trial="Static_01", setup_folder=SETUP_DIR,
        label="MRI (GPK)", color="purple", group="MRI"),
    "cateli_mri": dict(
        generic_model="Catelli_high_hip_Flexion_V4.0/Catelli-V4.0_PowerliftingMarkers_tps_Athlete_03.osim",
        linear_scaling=False, marker_placer=True,
        model_so="scaled_mvicx3.00.osim", model_ceinms="scaled.osim",
        static_trial="Static_01", setup_folder=SETUP_DIR,
        label="MRI (Cateli)", color="darkgreen", group="MRI"),
    "lernagopal_mri": dict(
        generic_model="Lernagopal/Lernagopal_41_OUF_PowerlifitingMarkers_tps_Athlete_03.osim",
        linear_scaling=False, marker_placer=True,
        model_so="scaled_mvicx3.00.osim", model_ceinms="scaled.osim",
        static_trial="Static_01", setup_folder=SETUP_DIR,
        label="MRI (Lernagopal)", color="navy", group="MRI"),
}

SUBJECT_GROUP = {
    "Athlete_03_Cateli":     "cateli",
    "Athlete_03_Lernagopal": "lernagopal",
    "Athlete_03_GPK":        "gpk",
    "Athlete_03_GPK_MRI":    "gpk_mri",
    "Athlete_03_Cateli_MRI":      "cateli_mri",
    "Athlete_03_Lernagopal_MRI":  "lernagopal_mri",
}

class Subjects:
    """Roster AUTO-DISCOVERED from simulations/<subject>/<session>/ for the active
    SESSION, each stamped with its GROUPS template (see above). Scales to hundreds
    of subjects/sessions with zero per-row typing — onboard the backlog by dropping
    folders into simulations/ and mapping them in SUBJECT_GROUP (or set default_group).
    """
    ALL = discover_sessions(SIMULATIONS_DIR, GROUPS,
                            subject_group=SUBJECT_GROUP,
                            default_group=None,
                            sessions=[SESSION])

    @classmethod
    def by_name(cls, name):
        return next((s for s in cls.ALL if s.name == name), None)

    @classmethod
    def names(cls):
        return [s.name for s in cls.ALL]

class BatchSettings:
    """All project + batch-analysis configuration."""

    trial_list   = list(CAPTURE["trial_list"])
    TRIAL_TYPE_PATTERN = r"(.+?)_(\d+)$"

    ALL_SUBJECTS = Subjects.ALL

    RUN_SUBJECTS  = 'all'
    SKIP_SUBJECTS = []

    SUBJECTS         = select_subjects(ALL_SUBJECTS, RUN_SUBJECTS, SKIP_SUBJECTS)
    SUBJECTS_BY_NAME = {s.name: s for s in SUBJECTS}
    model_config     = build_model_config(SUBJECTS, force_types=("SO", "CEINMS"))
    MODEL_FILES      = {s.name: s.model_ceinms for s in SUBJECTS}
    SETUP_FOLDERS    = {s.name: s.setup_folder for s in SUBJECTS}
    sessions         = sessions_from_subjects(SUBJECTS, SIMULATIONS_DIR)

    MODELS_TO_FLIP_KNEE = ["Lernagopal", "GPK"]
    CONTRASTS = {
        "generic_vs_mri": ["Scaled (GPK)", "MRI (GPK)"],
        "generic_vs_mri_all": [
            "Scaled (Cateli)", "MRI (Cateli)",
            "Scaled (Lernagopal)", "MRI (Lernagopal)",
            "Scaled (GPK)", "MRI (GPK)",
        ],
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
        "L Gluteus maximus":  ["glmax1_l", "glmax2_l", "glmax3_l"],
        "L Gluteus medius":   ["glmed1_l", "glmed2_l", "glmed3_l"],
        "L Gluteus minimus":  ["glmin1_l", "glmin2_l", "glmin3_l"],
        "L Adductor Magnus":  ["addmagDist_l", "addmagIsch_l", "addmagMid_l", "addmagProx_l"],
        "L Biceps Femoris":   ["bflh_l", "bfsh_l"],
        "L Semimembranosus":  ["semimem_l"],
        "L Semitendinosus":   ["semiten_l"],
        "L Rectus Femoris":   ["recfem_l"],
        "L Vasti":            ["vasint_l", "vaslat_l", "vasmed_l"],
        "L Triceps Surae":    ["soleus_l", "gaslat_l", "gasmed_l"],
    }

    normalise_inputs = 100

    setup_files_folder = SETUP_DIR
    markerset = os.path.join(SETUP_DIR, "markers_powerlifter.xml")
    trials_to_skip: list = []
    trials_to_run:  list = []

    dof_list = [
        "hip_flexion_l", "hip_flexion_r", "hip_adduction_l", "hip_adduction_r",
        "hip_rotation_l", "hip_rotation_r", "knee_angle_l", "knee_angle_r",
        "knee_adduction_l", "knee_adduction_r",
        "ankle_angle_l", "ankle_angle_r",
    ]
    marker_weights = {
        "pelvis": 10.0,
        "femur_r": 1.0, "tibia_r": 1.0, "talus_r": 1.0, "calcn_r": 2.0, "toes_r": 2.0,
        "femur_l": 1.0, "tibia_l": 1.0, "talus_l": 1.0, "calcn_l": 2.0, "toes_l": 2.0,
    }
    markers_to_skip = ["BL", "BR"]
    write_trial_settings_xml = False
    opensim_log_level = "off"
    emg_muscle_mapping = dict(CAPTURE["emg_muscle_mapping"])
    emg_label_default = "Voltage"
    emg_lowpass_default = "500"
    emg_highpass_default = "10"
    emg_notch_default = "50"
    emg_string_list = ["EMG", "Voltage", "muscle"]
    emg_sampling_freq = CAPTURE["emg_sampling_freq"]
    right_foot_markers = ["RTOE", "RHEE", "RFMH", "RSMH", "RVMH"]
    left_foot_markers = ["LTOE", "LHEE", "LFMH", "LSMH", "LVMH"]
    # Markers on the barbell. They are skipped for IK (markers_to_skip above —
    # the bar is not a body segment) but the movement detector reads them: they
    # are the only thing that separates a deadlift from a squat, since the
    # pelvis does the same descend-bottom-rise in both, and they carry the bar
    # path, ROM and mean concentric velocity for every lift.
    bar_markers = ["BL", "BR"]
    trc_lateral_axis  = "Z"
    trc_vertical_axis = "Y"
    trc_ap_axis       = "X"
    grf_axis_map = {"x": ("x", 1.0), "y": ("z", 1.0), "z": ("y", -1.0)}
    grf_cop_scale_to_m = 0.001
    grf_moment_scale   = 0.001
    grf_moment_sign    = -1.0
    grf_plate_force_sign = dict(CAPTURE["grf_plate_force_sign"])

    emg_bandpass_low_hz    = 20.0
    emg_bandpass_high_hz   = CAPTURE["emg_bandpass_high_hz"]
    emg_envelope_lowpass_hz = 3.0
    emg_bandpass_order     = 4
    emg_envelope_order     = 4
    c3d_file_col_weight = 3
    c3d_settings_col_weight = 7
    c3d_emg_channels_height = 40
    c3d_markers_height = 40

    auto_create_dirs = True
    replace_existing = True
    enable_c3d_export = True
    enable_scale_model = True
    enable_muscle_scaling = False
    muscle_force_factor = 3
    muscle_opt_neval = 10
    # Coordinates the Modenese muscle optimiser must not build a grid axis for.
    # A model that leaves secondary DOFs unlocked (knee_adduction +-20 deg,
    # subtalar_angle +-30 deg in GPK_v3) pays for them: the sampling grid is
    # N**nDOF, so each extra axis multiplies the cost by N. On Athlete_06 those
    # two pushed the hamstrings/quads to 5 spanned coordinates (1024 poses,
    # 177 s each) and the gastrocnemii to 6 (capped to 729, 113 s each) --
    # 13 muscles for 34 of the run's 39 minutes, for millimetre moment arms.
    muscle_opt_skip_coords = ["knee_adduction", "subtalar_angle"]
    # A coordinate counts as spanned only above this moment arm (m). The
    # default 0.1 mm is below any real geometry and lets noise add an axis.
    muscle_opt_ma_tol = 0.001
    static_trials = {k: v["static_trial"] for k, v in CAPTURES.items()}
    enable_inverse_kinematics = True
    enable_inverse_dynamics = True
    enable_static_optimization = True
    enable_muscle_analysis = True
    enable_emg_normalise = True
    enable_trial_validation = False

    assembly_accuracy = 1e-6

    literature_band_alpha = 0.18
    literature_line_alpha = 0.60
    literature_line_width = 1.8

    @staticmethod
    def trial_type(trial_name):
        """'Squat_35kg_02' -> 'Squat_35kg' (groups reps of a task)."""
        return _trial_type(trial_name, BatchSettings.TRIAL_TYPE_PATTERN)

    @staticmethod
    def model_for(subject, force_type="SO"):
        s = BatchSettings.SUBJECTS_BY_NAME.get(subject)
        return s.model_for(force_type) if s else None

    @staticmethod
    def JRA_COLUMNS(model_name, side="r"):
        """Joint-reaction (contact-force) column names per model (knee differs)
        and per leg. ``side`` = 'r'/'l' (accepts 'right'/'left')."""
        name = (model_name or "").lower()
        s = "l" if str(side).lower().startswith("l") else "r"
        hip = [f"hip_{s}_on_femur_{s}_in_femur_{s}_f{a}" for a in "xyz"]
        ankle = [f"ankle_{s}_on_talus_{s}_in_talus_{s}_f{a}" for a in "xyz"]
        if any(k in name for k in ("lernagopal", "lerner", "gpk")):
            knee = [f"Lerner_knee_{s}_on_sagittal_articulation_frame_{s}_in_sagittal_articulation_frame_{s}_f{a}"
                    for a in "xyz"]
        else:
            knee = [f"walker_knee_{s}_on_tibia_{s}_in_tibia_{s}_f{a}" for a in "xyz"]
        return {"hip": hip, "knee": knee, "ankle": ankle}

    @property
    def results_dir(self):
        return Path(next(iter(self.sessions))) if self.sessions else Path(".")

class CEINMSSettings:
    enable_calibration = True
    enable_execution   = True
    calibration_trial_names = list(CAPTURE["cal_trials"])
    calibration_type = "hybrid"
    tendon_type = "elastic"
    learning_rate = 0.02
    max_iterations = 1000
    early_stopping_patience = 20
    early_stopping_min_improvement = 0.1
    num_synergies = 4
    hybrid_calibration = "true"
    number_of_synergies = 8
    # -- EXECUTION weights, F_obj = a*E_trackMOM + b*E_sumEXC + g*E_trackEMG
    #    (Sartori et al. 2014 Eq. 1; beta is the EFFORT penalty, gamma the
    #    EMG-tracking weight -- they were read the wrong way round before t19).
    #
    #    Was a10 b1 g1000, i.e. gamma/alpha = 100. t19 swept 288 cells over
    #    Walking_03 and Squat_35kg_01 and settled three things:
    #
    #      * alpha is only a SCALE. (a, b, g) == (1, b/a, g/a), and the solver
    #        honours that to a median of 0.02 % wherever beta > 0. So alpha is
    #        pinned at 1 and only the ratios are real.
    #      * the L-curve KNEE is not usable here. Re-run inside five different
    #        gamma windows it comes out at exactly one tenth of whatever the
    #        top of the window was -- it finds the corner of a box you sized,
    #        not one the data put there.
    #      * a window-free criterion does work: the largest gamma whose
    #        moment-tracking error is still within 10 % of the best that beta
    #        reaches. That gives gamma = 30 for BOTH trials at beta = 1, and it
    #        removes 68-76 % of the EMG discrepancy. CEINMSoptimise, searching
    #        on its own, chose 54 (walking) and 10 (squat) -- 30 sits between
    #        them; Sartori tuned 5-15 for walking.
    #
    #    session.yaml's `ceinms:` block OUTRANKS these three at run time. Both
    #    are set to the same values; change them together.
    alpha = 1
    beta  = 1
    gamma = 30
    beta_min = 1;  beta_max = 100;  beta_delta = 10
    gamma_min = 1; gamma_max = 100; gamma_delta = 50
    alphas = "1 10 100"
    betas  = "1 10"
    gammas = "1 10 100 500 1000 1500 2000 3000 4000 5000"
    # The DOFs CEINMS calibrates and executes over. Derived from dof_list by
    # default; pinned explicitly here because knee_adduction was dropped (t23)
    # -- it is a secondary DOF whose moment the muscles cannot track, and
    # leaving it in spends calibration effort on noise. Keep this a literal:
    # a derived list changes silently when dof_list does.
    dof_set = ("hip_flexion_l hip_flexion_r hip_adduction_l hip_adduction_r "
               "hip_rotation_l hip_rotation_r knee_angle_l knee_angle_r "
               "ankle_angle_l ankle_angle_r")
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

    dofs         = ["pelvis_tilt", "pelvis_list", "pelvis_rotation",
                    "hip_flexion_r", "hip_adduction_r", "hip_rotation_r",
                    "knee_angle_r", "knee_adduction_r", "ankle_angle_r",
                    "hip_flexion_l", "hip_adduction_l", "hip_rotation_l",
                    "knee_angle_l", "knee_adduction_l", "ankle_angle_l"]

    dofs_moments = [d + "_moment" for d in dofs]
    analysis_leg = "both"
    reference_model = "Athlete_03_Cateli"
    algorithms      = ["SO", "CEINMS"]
    extra_trials    = list(CAPTURE["extra_trials"])
    npts            = 101
    joints          = ["hip", "knee", "ankle"]

    output_subdir   = ""
    style           = "minimal"
    dpi             = 200
    export_csv      = True

    figures = {
        "marker_errors":   True,
        "kin_mom":         True,
        "moment_arms":     True,
        "muscle_dynamics": True,
        "jrf":             True,
        "poster":          True,
    }
    emg_background   = True
    annotate_stats   = True

    hypothesis = ("Bone geometry (MRI) DECREASES muscle & joint forces; "
                  "measured coordination (CEINMS) INCREASES muscle & joint forces.")

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

class PlottingSettings:
    """Central colours / line styles / sizes for RESULT figures (not the GUI —
    that's UISettings). Keyed by DATA SOURCE so different quantities never share
    a colour: EMG grey, muscle moment orange, ID black, CEINMS blue, SO red,
    literature green. Read by bioscout via ``utils.plot_style('<source>')``;
    anything omitted falls back to the package defaults (utils.DEFAULT_PLOT_STYLE).

    Each source maps to {'color', 'ls' (line style), 'lw' (line width)}.

    COLOURS ARE PLAIN (R, G, B) IN 0-255 — pick any colour and paste the RGB here.
    Colour picker:  https://share.google/Va9O7umqecaS1dthG
    (Hex '#2E86AB', a named colour 'tab:blue', or 0-1 tuples also work — bioscout
    auto-detects 0-255 vs 0-1.)
    """
    dpi        = 200
    font_size  = 10
    fig_scale  = 1.0

    scale_per_subplot = (2, 3)

    sources = {
        "inverse_dynamics":    {"color": (0,   0,   0),   "ls": "-",  "lw": 2.0},
        "ceinms":              {"color": (31,  119, 180), "ls": "-",  "lw": 1.8},
        "static_optimisation": {"color": (214, 39,  40),  "ls": "-",  "lw": 1.8},
        "emg":                 {"color": (128, 128, 128), "ls": "-",  "lw": 1.5},
        "activation":          {"color": (89,  89,  89),  "ls": "-",  "lw": 1.2},
        "muscle_force":        {"color": (214, 39,  40),  "ls": "-",  "lw": 1.2},
    }

class UISettings:
    """Desktop-app (GUI) look & feel."""
    FONT_SIZE_SMALL = 20
    FONT_SIZE_NORMAL = 24
    FONT_SIZE_LARGE = 28
    FONT_SIZE_TITLE = 32
    FONT_FAMILY = 'Segoe UI'
    PRIMARY_COLOR = '#2E86AB'
    SECONDARY_COLOR = '#A23B72'
    ACCENT_COLOR = '#F18F01'
    BACKGROUND_COLOR = '#F4F4F4'
    TEXT_COLOR = '#1A1A1A'
    ERROR_COLOR = '#C1121F'
    PADDING_SMALL = 5
    PADDING_NORMAL = 10
    PADDING_LARGE = 15
    BUTTON_HEIGHT = 35
    FRAME_HEIGHT = 200
    WINDOW_WIDTH = 1200
    WINDOW_HEIGHT = 800
    sidebar_weight = 1
    content_weight = 3
    DEFAULT_TAB_ON_LAUNCH = 'Session Analysis'

class RecordingSettings:
    """Video capture / recording defaults (experimental)."""
    enabled = False
    frame_rate = 30
    resolution = '1920x1080'
    codec = 'H264'
    bitrate = '5000k'
    auto_name = True
    output_format = 'mp4'
    OUTPUT_DIR_TEMPLATE = 'recordings'
    DEFAULT_DURATION_SECONDS = 5
    DEFAULT_VIDEO_SOURCE = 'webcam'
    IP_CAMERA_ADDRESS = 'http://192.168.1.100:8080/video'
    DEFAULT_OSIM_MODEL = 'GPK_generic'
    DEFAULT_VIDEO_ANALYSIS_MODEL = 'GPK_generic'
    DEFAULT_POSE_MAX_DELTA_PX = 50

def run_catelli_marker_placer_ik_id_ma_so_ceinms():
    from bioscout import Session, Iteration

    s  = Session.open(os.path.join("simulations", "Athlete_03", "25_03_31"))
    it = s.iteration("cateli")

    it.run(trials=["Walking_03","Squat_BW_01","Squat_BW_02"],
       do_exbiomec=False,
       do_muscle_analsysis=True,
       do_so=True,
       do_ceinms=True,
       calibrate=True,
       calibration_trials=["Walking_03", "Squat_BW_01"],
       replace=True)

def run_deadlifts_export_to_ceinms_jrf():
    """From scratch: the two 35 kg deadlifts through the CEINMS pipeline for the
    cateli and GPK models —
        ingest c3d -> export (markers/GRF/EMG) -> session EMG normalise
        -> IK -> ID -> MA -> CEINMS execution -> CEINMS moments -> CEINMS JRA.
    NO CEINMS calibration: reuses each iteration's existing
    ceinms_calibration/subjectCalibrated.xml.
    """
    import os
    from bioscout import Session

    SESSION_DIR = os.path.join("simulations", "Athlete_03", "25_03_31")
    from bioscout.utils.session_layout import c3d_root
    C3D_SRC     = c3d_root(SESSION_DIR)
    TRIALS      = ["Walking_10", "Walking_05", "Walking_06", "Walking_07", "Walking_08", "Walking_09"]
    TRIALS      = ["Deadlift_35kg_01"]
    ITERATIONS  = ["gpk"]

    s = Session.open(os.path.join("simulations", "Athlete_03", "25_03_31"))

    for name in ITERATIONS:
        it = s.iteration(name)
        it.run(trials=TRIALS,
            export=False,
            do_exbiomec=False, do_muscle_analsysis=False,
            do_so=False, do_ceinms=True, calibrate=False, replace=True)


if __name__ == "__main__":
    # Headless backend ONLY when run as a script. At import time bioscout
    # may be driving the GUI, whose canvases need TkAgg.
    import matplotlib
    matplotlib.use("Agg")

    import os, glob, sys
    from bioscout import Session, Iteration

    RUN_CHECK_SCALING       = "--check-scaling" in sys.argv
    RUN_RESCALE_ALL         = "--rescale-all"   in sys.argv

    def _argvals(flag):
        """Values after ``flag`` until the next --option. Accepts commas."""
        if flag not in sys.argv:
            return None
        out = []
        for a in sys.argv[sys.argv.index(flag) + 1:]:
            if a.startswith("--"):
                break
            out += [x for x in a.replace(",", " ").split() if x]
        return out or None

    ONLY_SESSIONS = _argvals("--sessions")
    SKIP_ITERS    = set(_argvals("--skip") or [])
    REUSE_MODELS  = "--reuse-models" in sys.argv
    if RUN_CHECK_SCALING or RUN_RESCALE_ALL:
        RUN_SESSION_ITERATIONS = False

    _switches = {
        "RUN_TPS_PERSONALISE":     RUN_TPS_PERSONALISE,
        "RUN_SESSION_ITERATIONS":  RUN_SESSION_ITERATIONS,
        "RUN_SINGLE_ITERATION":    RUN_SINGLE_ITERATION,
        "RUN_PRUNE_LEGACY_INPUTS": RUN_PRUNE_LEGACY_INPUTS,
        "RUN_CHECK_SCALING":       RUN_CHECK_SCALING,
        "RUN_RESCALE_ALL":         RUN_RESCALE_ALL,
    }
    _on = [k for k, v in _switches.items() if v]
    print(f"[settings] bioscout {__import__('bioscout').__version__} | "
          f"settings {__version__}")
    if not _on:
        print("[settings] nothing to do — every run switch is False:")
        for k in _switches:
            print(f"             {k} = False")
        print("[settings] set ONE of them to True and re-run `python settings.py`.")
        exit(1)
    print(f"[settings] enabled: {', '.join(_on)}")

    RESCALE_PLAN = [
        ("25_03_31", ["cateli", "lernagopal", "gpk"],   True),
        ("25_03_31", ["gpk_mri"],                       True),
        ("25_03_31", ["cateli_mri", "lernagopal_mri"],  True),
        ("22_07_13", ["cateli", "lernagopal", "gpk"],   True),
        ("25_03_31", ["gpk_optimised"],                 False),
    ]

    if RUN_CHECK_SCALING or RUN_RESCALE_ALL:
        import time as _time
        from bioscout.utils import scale_measurements as _sm
        from bioscout.utils.session import experimental_dir as _expdir

        def _session_path(sess):
            hits = glob.glob(os.path.join(str(SIMULATIONS_DIR), "*", sess, "session.yaml"))
            if len(hits) != 1:
                exit(f"[rescale] expected exactly one simulations/*/{sess}/session.yaml, "
                     f"found {len(hits)}")
            return os.path.dirname(hits[0])

        if RUN_CHECK_SCALING:
            from bioscout.utils import get_openSim as _get_os; _os = _get_os()
            _scratch = os.path.join(str(LOG_DIR), "_scale_check")
            for sess, names, _ in RESCALE_PLAN:
                sp = _session_path(sess)
                cap = CAPTURES[sess]
                st = cap["static_trial"]
                trc = os.path.join(_expdir(sp, st), "marker_experimental.trc")
                grf = os.path.join(_expdir(sp, st), "grf.mot")
                print(f"\n===== {cap['subject']} / {sess} =====")
                if not os.path.exists(trc):
                    print(f"[check] MISSING static TRC: {trc} — export the static "
                          f"trial first, nothing can be scaled without it.")
                    continue
                s_ = Session.open(sp)
                _measured = _sm.mass_from_static_grf(grf)
                _typed = s_._cfg.get("body_mass")
                print(f"[check] session.yaml body_mass: {_typed} kg"
                      + (f"  ->  using {_measured:.2f} kg from the plates"
                         if _measured else "  (no usable static GRF)"))
                for n in names:
                    if n not in s_.iterations:
                        print(f"[check] {n}: not in this session — skipping")
                        continue
                    _it = s_.iteration(n)
                    mks = _it._resolve_model_file(s_._cfg.get("markerset"), "markerset")
                    itcfg = (s_._cfg.get("iterations") or {}).get(n) or {}
                    gen = _it._resolve_model_file(itcfg.get("generic"), "generic")
                    if not gen or not os.path.exists(gen):
                        print(f"[check] {n}: generic not found ({itcfg.get('generic')!r})")
                        continue
                    if not bool(itcfg.get("linear_scaling", True)):
                        print(f"--- {n}  (linear_scaling=false — geometry is already "
                              f"personalised, so there are no scale factors to check; "
                              f"the run will apply the measured mass only) ---")
                        continue
                    outdir = os.path.join(_scratch, sess, n)
                    os.makedirs(outdir, exist_ok=True)
                    print(f"--- {n}  ({os.path.basename(gen)}) ---")
                    try:
                        _os.scale_model(gen, trc, os.path.join(outdir, "scaled.osim"),
                                        scale_setup_output_dir=outdir,
                                        mass=(_measured or _typed),
                                        marker_set_file=mks,
                                        linear_scaling=True, marker_placer=False)
                    except Exception as e:
                        print(f"[check] {n}: {type(e).__name__}: {e}")
            print(f"\n[check] scale stage only — no analysis was run and no iteration "
                  f"folder was touched.\n[check] per-body factors: "
                  f"{os.path.join(_scratch, '<session>', '<iteration>', 'scale_factors.xml')}"
                  f"\n[check] If the factors look right, run: "
                  f"python settings.py --rescale-all")
            exit()

        _t0 = _time.time()
        _done, _failed, _skipped = [], [], []
        _plan = [(sess, names, ds) for sess, names, ds in RESCALE_PLAN
                 if not ONLY_SESSIONS or sess in ONLY_SESSIONS]
        if not _plan:
            exit(f"[rescale] --sessions {ONLY_SESSIONS} matched nothing in RESCALE_PLAN.")
        if ONLY_SESSIONS:
            print(f"[rescale] sessions restricted to: {', '.join(ONLY_SESSIONS)}")
        if SKIP_ITERS:
            print(f"[rescale] skipping iterations: {', '.join(sorted(SKIP_ITERS))}")
        if REUSE_MODELS:
            print("[rescale] --reuse-models: existing scaled/muscle-optimised models "
                  "are kept; only the analysis is rebuilt.")
        for sess, names, do_scale in _plan:
            sp = _session_path(sess)
            cap = CAPTURES[sess]
            trials = list(cap["trials"])
            cals = list(cap["cal_trials"])
            _extra = [t for t in cals if t not in trials]
            if _extra:
                print(f"[rescale] adding calibration trials to the analysis list: "
                      f"{', '.join(_extra)}")
                trials += _extra
            s_ = Session.open(sp)
            print(f"\n########## {cap['subject']} / {sess} — {len(names)} iterations "
                  f"over {len(trials)} trials ##########")
            for n in names:
                if n not in s_.iterations:
                    print(f"[rescale] {n}: not in this session — skipping")
                    continue
                if n in SKIP_ITERS:
                    print(f"[rescale] {n}: --skip")
                    _skipped.append(f"{cap['subject']}/{sess}/{n}")
                    continue
                tag = f"{cap['subject']}/{sess}/{n}"
                print(f"\n===== {tag} =====")
                try:
                    it_ = s_.iteration(n)
                    if do_scale:
                        _icfg = (s_._cfg.get("iterations") or {}).get(n) or {}
                        _mopt = _icfg.get("muscle_opt")
                        if _mopt is None:
                            _mopt = "opt_N" in str(_icfg.get("ceinms_model") or "")
                        print(f"[rescale] {tag}: muscle_opt={bool(_mopt)} "
                              f"(ceinms_model={_icfg.get('ceinms_model')!r})")
                        m = it_.scale_model(static_trial=cap["static_trial"],
                                            muscle_opt=bool(_mopt),
                                            replace=not REUSE_MODELS)
                        if not m:
                            print(f"[rescale] [ERROR] {tag}: no model produced — "
                                  f"skipping the analysis for this iteration.")
                            _failed.append(f"{tag} (scaling)")
                            continue
                    it_.run(trials=trials,
                            do_exbiomec=True, do_muscle_analysis=True,
                            do_so=True, do_ceinms=True,
                            calibrate=True, calibration_trials=cals,
                            replace=True)
                    _done.append(tag)
                except Exception as e:
                    print(f"[rescale] [ERROR] {tag}: {type(e).__name__}: {e}")
                    _failed.append(f"{tag} ({type(e).__name__})")
            try:
                s_.summarise(trials=trials)
            except Exception as e:
                print(f"[rescale] [WARNING] summary for {sess} failed: {e}")

        _h = (_time.time() - _t0) / 3600.0
        print(f"\n[rescale] finished in {_h:.1f} h")
        print(f"[rescale] completed ({len(_done)}): {', '.join(_done) or 'none'}")
        if _skipped:
            print(f"[rescale] skipped ({len(_skipped)}): {', '.join(_skipped)}")
        if _failed:
            print(f"[rescale] FAILED ({len(_failed)}): {', '.join(_failed)}")
            print("[rescale] Re-run just those by trimming RESCALE_PLAN.")
        print("[rescale] Next: rebuild gpk_ma / gpk_optimised from the NEW gpk "
              "models (`bioscout --change-moment-arms`) — the copies on disk carry "
              "the old unscaled geometry.")
        print("[rescale] Then: python results.py --subject Athlete_03 --session 25_03_31")
        exit()

    _hits = glob.glob(os.path.join(str(SIMULATIONS_DIR), "*", SESSION, "session.yaml"))
    if not _hits:
        exit(f"[settings] no simulations/*/{SESSION}/session.yaml found. "
             f"Check SESSION (= {SESSION!r}) and that the session folder exists.")
    if len(_hits) > 1:
        exit(f"[settings] {len(_hits)} sessions match {SESSION!r}: "
             f"{', '.join(os.path.dirname(h) for h in _hits)}. Session names must "
             f"be unique across subjects.")
    SESSION_PATH = os.path.dirname(_hits[0])
    print(f"[settings] session: {SESSION_PATH}  (subject {CAPTURE['subject']})")

    if RUN_PRUNE_LEGACY_INPUTS:
        s = Session.open(SESSION_PATH)
        if not hasattr(s, "prune_legacy_inputs"):
            exit("[settings] this bioscout has no prune_legacy_inputs() — needs "
                 ">= 2.0.3. Reinstall with: pip install -e C:/Git/bioscout")
        s.prune_legacy_inputs(dry_run=PRUNE_DRY_RUN, archive_dir=PRUNE_ARCHIVE)
        if PRUNE_DRY_RUN:
            print("[settings] dry run only — set PRUNE_DRY_RUN = False to apply.")
        exit()

    if RUN_TPS_PERSONALISE:
        if not TPS_LANDMARKS:
            exit(f"[settings] {SESSION} has no MRI landmark set in CAPTURES "
                 f"(tps_landmarks=None) — nothing to warp onto. See mri/README.md.")
        from bioscout.tps_personalise import personalise_iteration
        for name in TPS_ITERATIONS:
            source = name[:-4] if name.endswith("_mri") else name
            print(f"[settings] TPS personalise {source} -> {name}")
            personalise_iteration(SESSION_PATH, source, mri_landmarks=TPS_LANDMARKS,
                                  inspect=TPS_INSPECT)
        print("[settings] TPS models rebuilt.")
        _stale = [n for n in TPS_ITERATIONS
                  if not (RUN_SESSION_ITERATIONS and n in ITERATIONS)]
        if _stale:
            print(f"[settings] WARNING: rebuilt but NOT re-run: {', '.join(_stale)}")
            print( "[settings]          their results still come from the previous")
            print( "[settings]          model. Add them to ITERATIONS.")
        if not RUN_SESSION_ITERATIONS:
            print("[settings] next: RUN_SESSION_ITERATIONS = True")
            exit()
        print("[settings] continuing into the pipeline...")

    if RUN_SINGLE_ITERATION:
        s = Session.open(SESSION_PATH)
        it = s.iteration(ITERATIONS[0])
        print(f"[settings] --- single: {ITERATIONS[0]} ---")
        it.run(trials=TRIALS, do_exbiomec=DO_EXBIOMEC, do_so=DO_SO, do_muscle_analysis=DO_MA,
               do_ceinms=DO_CEINMS, calibrate=CALIBRATE,
               calibration_trials=CAL_TRIALS, replace=REPLACE)
        it.plot_summary(trials=TRIALS, figures=FIGURES)
        exit()

    if not RUN_SESSION_ITERATIONS:
        print("[settings] done (RUN_SESSION_ITERATIONS is False — batch skipped).")
        exit()

    s = Session.open(SESSION_PATH)
    print(s, "-> iterations on disk:", s.iterations)

    if DO_EXPORT:
        from bioscout.utils.session_layout import c3d_root
        _src = EXPORT_SRC or os.path.abspath(c3d_root(SESSION_PATH))
        EXPORT_TRIALS = ([STATIC_TRIAL] if STATIC_TRIAL not in TRIALS else []) + TRIALS
        print(f"[settings] export {len(EXPORT_TRIALS)} trials "
              f"(incl. static '{STATIC_TRIAL}') from {_src}")
        s.export(trials=EXPORT_TRIALS, export_src=_src, replace=REPLACE)

    if DO_DETECT:
        # Same code path as `bioscout --classifier <session>`, so the pipeline
        # and the command line can never disagree about what a trial is.
        from bioscout.movement_detector import classify_session
        classify_session(SESSION_PATH, settings=BatchSettings,
                         write_session_yaml=DETECT_WRITE_YAML)

    for name in ITERATIONS:
        if name not in s.iterations:
            print(f"[skip] {name}: not present in this session")
            continue
        it = s.iteration(name)
        print(f"[settings] --- {name} ---")
        if DO_SCALE:
            _icfg = (s._cfg.get("iterations") or {}).get(name) or {}
            _mopt = MUSCLE_OPT
            if _mopt is None:
                _mopt = _icfg.get("muscle_opt")
            if _mopt is None:
                _mopt = "opt_N" in str(_icfg.get("ceinms_model") or "")
            print(f"[settings] {name}: muscle_opt={bool(_mopt)} "
                  f"(ceinms_model={_icfg.get('ceinms_model')})")
            _model = it.scale_model(static_trial=STATIC_TRIAL,
                                    muscle_opt=bool(_mopt), replace=REPLACE)
            if not _model:
                print(f"[settings] [ERROR] {name}: scaling produced no model — "
                      f"skipping IK/ID/MA/SO/CEINMS for this iteration. Fix the "
                      f"cause above before re-running.")
                continue
            _sc = os.path.join(SESSION_PATH, "3_iterations", name, "scaled.osim")
            if os.path.exists(_sc):
                import re as _re
                _names = _re.findall(
                    r'<(?:Coordinate|Point|Torque)Actuator name="([^"]+)"',
                    open(_sc, encoding="utf-8", errors="replace").read())
                _nr = sum(1 for _n in _names if _n.endswith("_reserve"))
                _nd = sum(1 for _n in _names
                          if _n in ("FX", "FY", "FZ", "MX", "MY", "MZ"))
                print(f"[settings] {name}: scaled.osim carries {_nr} reserve + "
                      f"{_nd} residual actuator(s)")
                if _nr < 10 or _nd < 6:
                    raise SystemExit(
                        f"[settings] [ABORT] ScaleTool dropped the reserve "
                        f"actuators ({_nr} reserve, {_nd} residual in {_sc}).\n"
                        f"Add them at the scaled-model stage instead of in the "
                        f"generic:\n"
                        f"    from bioscout.model_edit import apply\n"
                        f"    apply(\"reserves\", \"{_sc}\")")
        if DO_EXBIOMEC or DO_MA or DO_SO or DO_CEINMS:
            it.run(trials=TRIALS,
                   do_exbiomec=DO_EXBIOMEC, do_so=DO_SO,
                   do_muscle_analysis=DO_MA,
                   do_ceinms=DO_CEINMS, calibrate=CALIBRATE,
                   calibration_trials=CAL_TRIALS, replace=REPLACE)
        if DO_PLOTS:
            it.plot_summary(trials=TRIALS, figures=FIGURES)

    if DO_SUMMARY:
        s.summarise(trials=TRIALS)
    print(f"[settings] done: {', '.join(ITERATIONS)}")
    print(f"[settings] manuscript figures: "
          f"`python results.py --subject {CAPTURE['subject']} --session {SESSION}`")
