"""
Project settings — BUNDLED TEMPLATE (powerlifting squat study).

This is the default settings module shipped inside bioscout. `init_project()`
copies it into a new project, and `bioscout.Project()` falls back to it when a
project has no settings.py of its own. A real project edits its OWN copy.

Configuration lives inside classes:
  * Subjects       — model variants / subjects, AUTO-DISCOVERED from simulations/.
  * BatchSettings  — paths, trials, analysis config + batch/IK/GRF/EMG.
  * CEINMSSettings / SummarySettings / PlottingSettings / UISettings / RecordingSettings.
bioscout reads it all via ``settings.BatchSettings.X`` etc. (paths/session may
also be declared as module-level globals; bioscout falls back to those).

The trial-file LAYOUT (``inputs/``, ``external_biomechanics/`` …) is NOT declared
here — in 2.0 it is code-driven inside ``bioscout`` (Analyse). Per-trial config
(time windows, sides, CEINMS a/b/g, model names) lives in each session's
``session.yaml``.

KEEP THIS FILE — bioscout.Project()/init_project() loads it.

``__version__`` here is the settings-SCHEMA version: what a project pins to say
which shape of settings.py it was written against. ``check_settings_version``
compares its MAJOR.MINOR against a project's own value.

It is an INDEPENDENT series from the bioscout package version. The two happen
to read the same right now (both 2.0.1) because the schema last changed in the
2.0 release; do not keep them in step. Mirroring the package version here is
what made the check disagree on every patch bump — bump this only when the
shape of settings.py actually changes.
"""
import os
from pathlib import Path


# Guarded: this BUNDLED template is exec'd by bioscout.utils.settings DURING
# bioscout's own import, so a bare top-level import of bioscout.utils.* would be
# circular (utils.analysis is not assigned yet). The try/except lets it load with
# safe stubs; a real project's own settings.py (loaded after bioscout is ready)
# imports these directly without needing the guard.
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

RUN_PIPELINE = True    # run the full pipeline (IK + ID + SO + MA + CEINMS) per trial
RUN_SUMMARY  = True    # generate summary figures + metrics CSVs
RUN_SCALING  = True    # scale each subject's generic model (scale -> opt -> MVIC)
RUN_CEINMS   = True    # run CEINMS (calibration + execution) per trial

# Console/log verbosity:
#   "detailed" — everything (per-trial dumps, debug listings, tool chatter)
#   "minimal"  — section headers, [Success]/[skip]/[ERROR], and warnings only
#   "quiet"    — errors and final summary only
LOG_TYPE = "minimal"

# ---- project paths & session (GLOBAL — single source of truth) -------------
# bioscout reads these as module-level settings.<NAME> (with a BatchSettings
# fallback), so they live here rather than inside BatchSettings.
PROJECT_NAME    = "powerlifting_squat"
PROJECT_ROOT    = Path(__file__).resolve().parent
MODELS_DIR      = PROJECT_ROOT / "models"
SETUP_DIR       = PROJECT_ROOT / "setupFiles"
SIMULATIONS_DIR = PROJECT_ROOT / "simulations"
RESULTS_DIR     = PROJECT_ROOT / "results"
LOG_DIR         = PROJECT_ROOT / "logs"
SESSION         = "25_03_31"


# ---- model/group templates -------------------------------------------------
# One template per distinct generic + scaled-name convention (NOT per subject).
# A registry row is auto-built for each simulations/<subject>/<session>/ folder
# and stamped with its group's template. Shared fields (model_so/model_ceinms
# names, static_trial, setup_folder) live here once. Model names use the
# canonical scaled_[opt_N<n>_]mvicx<factor>.osim convention.
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
        generic_model="GPK_generic_modWO.osim",
        model_so="scaled_opt_N10_mvicx3.00.osim", model_ceinms="scaled_opt_N10.osim",
        static_trial="Static_01", setup_folder=SETUP_DIR,
        label="Scaled (GPK)", color="red", group="generic"),
    "gpk_mri": dict(
        # Validated MRI/TPS model is the template itself (geometry AND muscle-tendon
        # params already personalised). linear_scaling off (keep MRI segment geometry),
        # marker_placer ON so markers register to the static pose (fixes IK). Muscle-opt
        # is SKIPPED — the generic's OFL/TSL are kept — so CEINMS uses the plain
        # marker-registered scaled.osim and SO uses it with isometric force x MVIC.
        generic_model="GPK/GPK_generic_modWO_tps_Athlete_03.osim",
        linear_scaling=False, marker_placer=True,
        model_so="scaled_mvicx3.00.osim", model_ceinms="scaled.osim",
        static_trial="Static_01", setup_folder=SETUP_DIR,
        label="MRI (GPK)", color="purple", group="MRI"),
    "rajagopal": dict(
        generic_model="Rajagopal2015.osim",
        model_so="Athlete_03_Rajagopal.osim", model_ceinms="Athlete_03_Rajagopal.osim",
        static_trial="Static_01", setup_folder=SETUP_DIR,
        label="Rajagopal (scaled)", color="orange", group="generic"),
    # 49-athlete backlog: add ONE default template (their shared generic) here,
    # e.g. "athlete": dict(generic_model="Rajagopal2015_FAI_os4.osim", ...), and set
    # default_group="athlete" below — then just drop their folders into simulations/.
}

# Which group each subject folder belongs to (unmapped subjects use default_group;
# None = skip). For the backlog, map new athletes here or set default_group.
SUBJECT_GROUP = {
    "Athlete_03_Cateli":     "cateli",
    "Athlete_03_Lernagopal": "lernagopal",
    "Athlete_03_GPK":        "gpk",
    "Athlete_03_GPK_MRI":    "gpk_mri",
    "Athlete_03_Rajagopal":  "rajagopal",
}


class Subjects:
    """Roster AUTO-DISCOVERED from simulations/<subject>/<session>/ for the active
    SESSION, each stamped with its GROUPS template (see above). Scales to hundreds
    of subjects/sessions with zero per-row typing — onboard the backlog by dropping
    folders into simulations/ and mapping them in SUBJECT_GROUP (or set default_group).
    (During bioscout's own import discover_sessions is a stub returning [] — the
    real roster is built when a project's own settings.py runs.)
    """
    ALL = discover_sessions(SIMULATIONS_DIR, GROUPS,
                            subject_group=SUBJECT_GROUP,
                            default_group=None,      # None = skip unmapped subjects
                            sessions=[SESSION])       # only the active session

    @classmethod
    def by_name(cls, name):
        return next((s for s in cls.ALL if getattr(s, "name", None) == name), None)

    @classmethod
    def names(cls):
        return [s.name for s in cls.ALL]


class BatchSettings:
    """All project + batch-analysis configuration."""

    # ---- session & trials ------------------------------------------------
    # Paths + SESSION are module-level globals above (single source of truth);
    # bioscout resolves them via settings.<NAME>. Referenced unqualified below.
    # Full set: ["Squat_35kg_01","Squat_35kg_02","Squat_BW_01","Squat_BW_02",
    #            "Walking_02","Walking_03"]
    SESSION      = SESSION
    trial_list   = ["Walking_02", "Walking_03", "Squat_BW_01", "Squat_BW_02"]
    TRIAL_TYPE_PATTERN = r"(.+?)_(\d+)$"

    # ---- subjects --------------------------------------------------------
    # Subject metadata lives in the `Subjects` registry above; edit it there.
    # Choose which to process with RUN_/SKIP_ (names or indices).
    ALL_SUBJECTS = Subjects.ALL
    RUN_SUBJECTS  = None      # 'all' or None/[] = all; e.g. ["Athlete_03_GPK"] or [2, 3]
    SKIP_SUBJECTS = []        # e.g. ["Athlete_03_Cateli"] or [0]

    SUBJECTS         = select_subjects(ALL_SUBJECTS, RUN_SUBJECTS, SKIP_SUBJECTS)
    SUBJECTS_BY_NAME = {s.name: s for s in SUBJECTS}
    model_config     = build_model_config(SUBJECTS, force_types=("SO", "CEINMS"))
    MODEL_FILES      = {s.name: s.model_ceinms for s in SUBJECTS}
    SETUP_FOLDERS    = {s.name: s.setup_folder for s in SUBJECTS}
    # session map {path: static_trial} — Project also derives this at runtime.
    sessions         = sessions_from_subjects(SUBJECTS, SIMULATIONS_DIR)

    # ---- analysis / comparison config ------------------------------------
    # NOTE: the DOFs to PLOT / SUMMARISE now live in SummarySettings.dofs.
    # The single processing DOF set (IK / ID / CEINMS, bilateral) is dof_list below.
    MODELS_TO_FLIP_KNEE = ["Lernagopal", "GPK"]
    CONTRASTS = {
        "generic_vs_mri": ["Scaled (GPK)", "MRI (GPK)"],
        "so_vs_ceinms":   ["Scaled (GPK)", "Scaled (GPK) - CEINMS"],
        "across_models":  ["Scaled (Cateli)", "Scaled (Lernagopal)", "Scaled (GPK)"],
    }
    # Both legs defined; the muscle-group plot filters by the trial's `side`
    # (walking -> one leg, squat -> both).
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

    # Time-normalise (downsample) exported inputs/results to this many frames.
    # 0 = native sampling. ~100 is near-lossless for kinematics/moments.
    normalise_inputs = 100

    # ---- batch / IK / GRF / EMG processing -------------------------------
    # NOTE: generic_model moved onto each Subject (Subject.generic_model).
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
    # knee_adduction_l/r included for models with a free frontal-plane knee
    # coordinate (e.g. Lerner/GPK-MRI knee). create_ceinms_model() auto-drops any
    # DOF the model lacks, and any DOF no muscle spans (|moment arm| < 1e-6), so
    # models without it (or with it locked) are unaffected.
    marker_weights = {
        "pelvis": 10.0,
        "femur_r": 1.0, "tibia_r": 1.0, "talus_r": 1.0, "calcn_r": 2.0, "toes_r": 2.0,
        "femur_l": 1.0, "tibia_l": 1.0, "talus_l": 1.0, "calcn_l": 2.0, "toes_l": 2.0,
    }
    # Markers excluded from IK entirely (belt / noise markers). Their IK task is
    # disabled so they don't pull the fit. Matched case-insensitively.
    markers_to_skip = ["BL", "BR"]
    # session.yaml is the single source of truth for per-trial config; do NOT
    # write per-trial trial_settings.xml scratch files. Set True to restore them.
    write_trial_settings_xml = False
    # Quiet OpenSim's C++ [info]/[warning] spam (missing display-geometry meshes,
    # etc.) by raising its log level. "off" hides everything; "error" keeps errors;
    # None / "warning" shows them again.
    opensim_log_level = "off"
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
    # Per-plate force-sign correction for individually mis-wired plates.
    # {plate_id: {axis: sign}}. Plate 1's anterior-posterior (vx) force is
    # inverted in the raw C3D, so flip it back:
    grf_plate_force_sign = {1: {"vx": -1}}
    # A force plate whose CoP sits farther than this (mm) from BOTH foot-marker
    # centroids is treated as NOT acting on a foot (e.g. a loaded barbell resting on a
    # plate during a deadlift) and is EXCLUDED from GRF.xml. None/0 disables the check.
    grf_max_cop_foot_dist_mm = 300.0

    # EMG linear-envelope filtering (applied during export). Lower the envelope
    # low-pass for a smoother envelope (4-6 Hz suits walking/squat; raise for fast
    # tasks). emg_bandpass_high_hz=None -> auto 0.9*Nyquist.
    emg_bandpass_low_hz     = 20.0
    emg_bandpass_high_hz    = 450.0   # standard sEMG band
    emg_envelope_lowpass_hz = 6.0
    emg_bandpass_order      = 4
    emg_envelope_order      = 4
    c3d_file_col_weight = 3
    c3d_settings_col_weight = 7
    c3d_emg_channels_height = 40
    c3d_markers_height = 40

    auto_create_dirs = True
    replace_existing = True
    enable_c3d_export = True
    enable_scale_model = True
    enable_muscle_scaling = False
    muscle_force_factor = 3        # isometric-force x factor -> model_so (*_mvicx3.00)
    muscle_opt_neval = 10          # Modenese muscle-opt sampling -> scaled_opt_N10.osim
    # Static trial to scale FROM, per session (name of the trial folder / c3d stem).
    static_trials = {"25_03_31": "Static_01"}
    enable_inverse_kinematics = True
    enable_inverse_dynamics = True
    enable_static_optimization = True
    enable_muscle_analysis = True
    enable_emg_normalise = True
    # Per-trial end-of-run validation (muscle-length/strength sweeps + literature
    # overlay). Slow, silent step that dominates wall time. Off for fast/preview
    # runs; turn on when you want the QC figures (see bioscout.muscle_inspect).
    enable_trial_validation = False

    # Model constraint-assembly tolerance used when loading models for IK/ID/MA/SO/JRA.
    # Coupled-knee models (GPK/Lernagopal patella couplers) miss OpenSim's ultra-tight
    # default and print "Unable to achieve required assembly error tolerance"; a loose
    # value is physically negligible for moments/JCF and silences it.
    assembly_accuracy = 1e-6

    # Literature JCF overlay styling on the JRA |resultant| panels.
    literature_band_alpha = 0.18   # shaded band opacity (0-1)
    literature_line_alpha = 0.60   # dashed reference-line opacity (0-1)
    literature_line_width = 1.8    # dashed reference-line width

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
    def JRA_COLUMNS(model_name, side="r"):
        """Joint-reaction (contact-force) column names per model (knee differs)
        and per leg. ``side`` = 'r'/'l' (accepts 'right'/'left')."""
        name = (model_name or "").lower()   # case-insensitive: folder names are lowercase
        s = "l" if str(side).lower().startswith("l") else "r"
        hip = [f"hip_{s}_on_femur_{s}_in_femur_{s}_f{a}" for a in "xyz"]
        ankle = [f"ankle_{s}_on_talus_{s}_in_talus_{s}_f{a}" for a in "xyz"]
        # Lerner knee: gpk / gpk_mri / lernagopal (the MRI GPK_generic_modWO_tps
        # model ALSO uses the Lerner sagittal-articulation knee). cateli / rajagopal
        # use the standard walker_knee.
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
    """Configuration for the results summary (bioscout.summarize_results())."""

    # ---- what to summarise -----------------------------------------------
    # DOFs to PLOT / SUMMARISE. The full processing DOF set (IK/ID/CEINMS,
    # bilateral) is BatchSettings.dof_list. Both legs (right=blue, left=red —
    # merged onto the same column by plot_kin_mom_summary) plus the pelvis DOFs.
    dofs         = ["pelvis_tilt", "pelvis_list", "pelvis_rotation",
                    "hip_flexion_r", "hip_adduction_r", "hip_rotation_r",
                    "knee_angle_r", "knee_adduction_r", "ankle_angle_r",
                    "hip_flexion_l", "hip_adduction_l", "hip_rotation_l",
                    "knee_angle_l", "knee_adduction_l", "ankle_angle_l"]
    dofs_moments = [d + "_moment" for d in dofs]
    # Default leg in per-trial summary plots (kinematics_moments.png):
    # "both" | "r" | "l".
    analysis_leg = "both"
    # Reference model (name or label) that others are compared against (RMSE/R2).
    reference_model = "Athlete_03_Cateli"
    algorithms      = ["SO", "CEINMS"]
    # Extra trials to include on top of BatchSettings.trial_list (if present on disk).
    extra_trials    = ["Squat_35kg_02", "Squat_BW_02", "Walking_03"]
    npts            = 101            # time-normalisation points for every curve
    joints          = ["hip", "knee", "ankle"]

    # ---- output ----------------------------------------------------------
    output_subdir   = ""             # under PROJECT_ROOT; figures go in <subdir>/figures
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


class PlottingSettings:
    """Central colours / line styles / sizes for RESULT figures (not the GUI —
    that's UISettings). Keyed by DATA SOURCE so different quantities never share
    a colour: EMG grey, muscle moment orange, ID black, CEINMS blue, SO red.
    Read by bioscout via ``utils.plot_style('<source>')``; anything omitted falls
    back to the package defaults (utils.DEFAULT_PLOT_STYLE).

    COLOURS ARE PLAIN (R, G, B) IN 0-255 (hex '#2E86AB', a named 'tab:blue', or
    0-1 tuples also work — bioscout auto-detects).
    """
    dpi        = 200
    font_size  = 10
    fig_scale  = 1.0                 # multiply default figure sizes by this
    scale_per_subplot = (2, 3)       # (row_mult, col_mult) multipliers by subplot count

    sources = {                       # (R, G, B) 0-255
        "inverse_dynamics":    {"color": (0,   0,   0),   "ls": "-", "lw": 2.0},   # black
        "ceinms":              {"color": (31,  119, 180), "ls": "-", "lw": 1.8},   # blue
        "static_optimisation": {"color": (214, 39,  40),  "ls": "-", "lw": 1.8},   # red
        "emg":                 {"color": (128, 128, 128), "ls": "-", "lw": 1.5},   # grey
        "activation":          {"color": (89,  89,  89),  "ls": "-", "lw": 1.2},   # dark grey
        "muscle_force":        {"color": (214, 39,  40),  "ls": "-", "lw": 1.2},   # red
    }
    # Any source not listed above falls back to utils.DEFAULT_PLOT_STYLE.


class UISettings:
    """Desktop-app (GUI) look & feel."""
    FONT_SIZE_SMALL = 20; FONT_SIZE_NORMAL = 24; FONT_SIZE_LARGE = 28; FONT_SIZE_TITLE = 32
    FONT_FAMILY = "Segoe UI"
    PRIMARY_COLOR = "#2E86AB"; SECONDARY_COLOR = "#A23B72"; ACCENT_COLOR = "#F18F01"
    BACKGROUND_COLOR = "#F4F4F4"; TEXT_COLOR = "#1A1A1A"; ERROR_COLOR = "#C1121F"
    PADDING_SMALL = 5; PADDING_NORMAL = 10; PADDING_LARGE = 15
    BUTTON_HEIGHT = 35; FRAME_HEIGHT = 200; WINDOW_WIDTH = 1200; WINDOW_HEIGHT = 800
    sidebar_weight = 1; content_weight = 3
    DEFAULT_TAB_ON_LAUNCH = "Session Analysis"


class RecordingSettings:
    """Video capture / recording defaults (experimental)."""
    enabled = False
    frame_rate = 30
    resolution = "1920x1080"
    codec = "H264"
    bitrate = "5000k"
    auto_name = True
    output_format = "mp4"
    OUTPUT_DIR_TEMPLATE = str(PROJECT_ROOT / "recordings")
    DEFAULT_DURATION_SECONDS = 5
    DEFAULT_VIDEO_SOURCE = "webcam"
    IP_CAMERA_ADDRESS = "http://192.168.1.100:8080/video"
    DEFAULT_OSIM_MODEL = "GPK_generic"
    DEFAULT_VIDEO_ANALYSIS_MODEL = "GPK_generic"
    DEFAULT_POSE_MAX_DELTA_PX = 50


Config = BatchSettings


if __name__ == "__main__":
    # =====================================================================
    # SINGLE-SESSION RUNNER
    #       conda activate <your env>
    #       python settings.py
    #
    # settings.py is the ONLY project file you edit/run. Everything above this
    # block is configuration; everything below is the run. It needs bioscout
    # installed in the env and the session data under
    #       simulations/<subject>/<SESSION>/3_iterations/<iteration>/<trial>/
    #
    # Per-iteration recipe (generic model, time windows, CEINMS a/b/g, labels,
    # colours) lives in that session's session.yaml — not here.
    #
    # A study running several captures should lift ITERATIONS / TRIALS /
    # STATIC_TRIAL / CAL_TRIALS into a CAPTURES = {session: {...}} dict at the
    # top of the file and index it with SESSION, so changing SESSION switches
    # the model list, the trial list and the calibration trials together. Doing
    # it by hand is how one athlete's trial names end up running against
    # another's data.
    # =====================================================================
    import glob
    from bioscout import Session

    # =====================================================================
    # 1. WHAT TO RUN — turn exactly one on (TPS may be combined with the batch)
    # =====================================================================
    RUN_TPS_PERSONALISE     = False  # (re)build the MRI/TPS-personalised models
    RUN_SESSION_ITERATIONS  = True   # run the pipeline over ITERATIONS below
    RUN_SINGLE_ITERATION    = False  # one iteration, for debugging
    RUN_PRUNE_LEGACY_INPUTS = False  # drop pre-YAML per-iteration inputs/ folders

    # =====================================================================
    # 2. PIPELINE CONFIG — used by RUN_SESSION_ITERATIONS
    #
    # Generic stage switches: they apply to whichever models ITERATIONS names,
    # MRI or not. Scaling and analysis are separate stages because scaling
    # invalidates everything downstream of it.
    # =====================================================================
    ITERATIONS   = ["gpk", "cateli"]
    TRIALS       = list(BatchSettings.trial_list)   # or e.g. ["Squat_35kg_01"]
    STATIC_TRIAL = "Static_01"
    REPLACE      = True   # overwrite existing outputs (False = skip finished work)

    # ---- stage switches -------------------------------------------------
    # A FULL first run of a session needs every one of these True, in this
    # order. Set the earlier ones False to resume part-way.
    DO_EXPORT   = True    # c3d -> markers/GRF/EMG in 2_experimental/ + EMG normalise
    EXPORT_SRC  = None    # None = <session>/1_c3dfiles
    DO_SCALE    = True    # generic + static -> scaled.osim (per iteration)
    MUSCLE_OPT  = True    # DO_SCALE: Modenese2015 muscle-opt -> scaled_opt_N<n>.osim
                          # (False = marker-register only; use for MRI models whose
                          #  muscle-tendon params are already personalised)
    DO_EXBIOMEC = True    # IK -> ID
    DO_MA       = True    # Muscle Analysis (lengths + moment arms)
    DO_SO       = True    # Static Optimisation -> muscle moments -> JRA
    DO_CEINMS   = True    # CEINMS execution -> muscle forces -> JRA
    CALIBRATE   = True    # True = calibrate first (needed once per NEW model);
                          # False = reuse ceinms_calibration/subjectCalibrated.xml
    # bioscout reads CEINMSSettings.calibration_trial_names and, when nothing
    # matches, falls back to "every trial with squat in the name" — a
    # plausible-looking calibration on the wrong trials. session.yaml's
    # `calibration_trials` key is documentation only; bioscout does not read it.
    CAL_TRIALS  = None    # e.g. ["Squat_35kg_01"]  (None = settings default)

    DO_PLOTS    = True    # per-trial figures inside each trial folder
    FIGURES     = ["kin_mom", "jra"]        # {"kin_mom", "summary", "jra"}
    DO_SUMMARY  = True    # cross-model overlays -> results/<session>/

    # =====================================================================
    # 3. TPS / MRI PERSONALISATION CONFIG — used by RUN_TPS_PERSONALISE
    #
    # Which iterations to warp, and the landmark file to warp them onto.
    # Writes "<generic stem>_tps_<subject>.osim" beside each generic — the
    # filename the *_mri iterations in session.yaml expect. Re-run whenever the
    # landmarks or bioscout's TPS code change.
    # =====================================================================
    TPS_ITERATIONS = []          # e.g. ["gpk_mri", "cateli_mri"]
    # Sweep the warped model's moment arms afterwards and save the plots. Also
    # writes a wrap-corrected "<model>_modWO.osim" beside it as an EXTRA to
    # compare against — the personalised model itself is left untouched and
    # session.yaml keeps pointing at it. Needs opensim; adds a few minutes per
    # model, so turn it off for a quick rebuild.
    TPS_INSPECT = True
    # Per subject. Hard-coding one subject's landmarks would warp another
    # subject's model onto the wrong bones without a word of complaint.
    TPS_LANDMARKS = None         # e.g. os.path.join(PROJECT_ROOT, "mri", "<subject>", "landmarks.mrk.json")

    # =====================================================================
    # 4. HOUSEKEEPING CONFIG — used by RUN_PRUNE_LEGACY_INPUTS
    #
    # Drops the pre-YAML per-iteration inputs/ folders (each model used to keep
    # its own copy of the raw c3d/markers/GRF/EMG). Only removes a folder when
    # the shared 2_experimental/ export for that trial exists, so it can never
    # delete the last copy. Set PRUNE_ARCHIVE = None to delete outright.
    # =====================================================================
    PRUNE_DRY_RUN = True
    PRUNE_ARCHIVE = os.path.join("_to_delete", "legacy_inputs")

    # =====================================================================
    # THE RUN
    # =====================================================================
    # Report what is enabled. With every switch off this script used to print
    # nothing at all and return to the prompt — indistinguishable from a crash.
    _switches = {
        "RUN_TPS_PERSONALISE":     RUN_TPS_PERSONALISE,
        "RUN_SESSION_ITERATIONS":  RUN_SESSION_ITERATIONS,
        "RUN_SINGLE_ITERATION":    RUN_SINGLE_ITERATION,
        "RUN_PRUNE_LEGACY_INPUTS": RUN_PRUNE_LEGACY_INPUTS,
    }
    _on = [k for k, v in _switches.items() if v]
    print(f"[settings] bioscout {__import__('bioscout').__version__} | "
          f"settings schema {__version__}")
    if not _on:
        print("[settings] nothing to do — every run switch is False:")
        for k in _switches:
            print(f"             {k} = False")
        print("[settings] set ONE of them to True and re-run `python settings.py`.")
        exit(1)
    print(f"[settings] enabled: {', '.join(_on)}")

    _hits = glob.glob(os.path.join(str(SIMULATIONS_DIR), "*", SESSION, "session.yaml"))
    if not _hits:
        # An older fallback pointed at a hard-coded subject regardless of
        # SESSION, so a typo in SESSION silently ran the wrong one. Fail instead.
        exit(f"[settings] no simulations/*/{SESSION}/session.yaml found. "
             f"Check SESSION (= {SESSION!r}) and that the session folder exists.")
    if len(_hits) > 1:
        exit(f"[settings] {len(_hits)} sessions match {SESSION!r}: "
             f"{', '.join(os.path.dirname(h) for h in _hits)}. Session names must "
             f"be unique across subjects.")
    SESSION_PATH = os.path.dirname(_hits[0])
    print(f"[settings] session: {SESSION_PATH}")

    # ---- housekeeping ---------------------------------------------------
    if RUN_PRUNE_LEGACY_INPUTS:
        s = Session.open(SESSION_PATH)
        s.prune_legacy_inputs(dry_run=PRUNE_DRY_RUN, archive_dir=PRUNE_ARCHIVE)
        if PRUNE_DRY_RUN:
            print("[settings] dry run only — set PRUNE_DRY_RUN = False to apply.")
        exit()

    # ---- build the MRI/TPS models ---------------------------------------
    if RUN_TPS_PERSONALISE:
        if not TPS_LANDMARKS:
            exit("[settings] TPS_LANDMARKS is None — nothing to warp onto.")
        from bioscout.tps_personalise import personalise_iteration
        for name in TPS_ITERATIONS:
            # A *_mri iteration's `generic` already NAMES the *_tps_*.osim file,
            # so warp its non-MRI sibling: "cateli_mri" -> "cateli".
            source = name[:-4] if name.endswith("_mri") else name
            print(f"[settings] TPS personalise {source} -> {name}")
            personalise_iteration(SESSION_PATH, source, mri_landmarks=TPS_LANDMARKS,
                                  inspect=TPS_INSPECT)
        print("[settings] TPS models rebuilt.")
        # Rebuilding a model without re-running it leaves that iteration's
        # results describing the OLD model, with nothing marking them stale.
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

    # ---- one iteration, for debugging -----------------------------------
    if RUN_SINGLE_ITERATION:
        s = Session.open(SESSION_PATH)
        it = s.iteration(ITERATIONS[0])
        print(f"[settings] --- single: {ITERATIONS[0]} ---")
        it.run(trials=TRIALS, do_exbiomec=DO_EXBIOMEC, do_so=DO_SO,
               do_muscle_analysis=DO_MA, do_ceinms=DO_CEINMS, calibrate=CALIBRATE,
               calibration_trials=CAL_TRIALS, replace=REPLACE)
        it.plot_summary(trials=TRIALS, figures=FIGURES)
        exit()

    # ---- the batch ------------------------------------------------------
    if not RUN_SESSION_ITERATIONS:
        print("[settings] done (RUN_SESSION_ITERATIONS is False — batch skipped).")
        exit()

    s = Session.open(SESSION_PATH)
    print(s, "-> iterations on disk:", s.iterations)

    # ---- 1. EXPORT: model-INDEPENDENT, run ONCE for the whole session ----
    # markers/GRF/EMG live in 2_experimental/<trial>/ and are shared by every
    # iteration, so exporting per-iteration just repeats identical work. This
    # also runs the session-wide EMG normalisation the CEINMS excitations come
    # from (the session-max reference spans every trial).
    #
    # TRIALS must be named explicitly on a FIRST run: Iteration._trial_names()
    # only sees trials whose folder already exists, so it returns [] until the
    # c3d have been ingested. EXPORT_SRC must be ABSOLUTE — ingest_c3d globs
    # relative to the process cwd and defaults to the session root, not
    # 1_c3dfiles.
    if DO_EXPORT:
        from bioscout.utils.session_layout import c3d_root
        _src = EXPORT_SRC or os.path.abspath(c3d_root(SESSION_PATH))
        # The STATIC trial must be exported too, and it is deliberately NOT in
        # TRIALS (TRIALS is the analysis list; session.yaml marks the static one
        # `type: static`, and bioscout excludes it from _trial_names()). Scaling
        # reads 2_experimental/<static>/marker_experimental.trc, so leaving it
        # out of the export gives no scaled model and every later stage fails.
        EXPORT_TRIALS = ([STATIC_TRIAL] if STATIC_TRIAL not in TRIALS else []) + TRIALS
        print(f"[settings] export {len(EXPORT_TRIALS)} trials "
              f"(incl. static '{STATIC_TRIAL}') from {_src}")
        s.export(trials=EXPORT_TRIALS, export_src=_src, replace=REPLACE)

    # ---- 2..5. per iteration: scale -> IK/ID -> MA -> SO -> CEINMS -------
    for name in ITERATIONS:
        if name not in s.iterations:
            print(f"[skip] {name}: not present in this session")
            continue
        it = s.iteration(name)
        print(f"[settings] --- {name} ---")
        if DO_SCALE:
            # static_trial is passed explicitly: scale_model's default is the
            # literal "Static_01" and it does NOT read session.yaml's
            # `static_trial` key.
            _model = it.scale_model(static_trial=STATIC_TRIAL,
                                    muscle_opt=MUSCLE_OPT, replace=REPLACE)
            # scale_model returns None on failure. Without this guard IK, MA, SO
            # and CEINMS all run anyway and fail per-trial, burying the one line
            # that said why in hundreds of downstream errors.
            if not _model:
                print(f"[settings] [ERROR] {name}: scaling produced no model — "
                      f"skipping IK/ID/MA/SO/CEINMS for this iteration. Fix the "
                      f"cause above before re-running.")
                continue
        if DO_EXBIOMEC or DO_MA or DO_SO or DO_CEINMS:
            it.run(trials=TRIALS,
                   do_exbiomec=DO_EXBIOMEC, do_so=DO_SO,
                   do_muscle_analysis=DO_MA,
                   do_ceinms=DO_CEINMS, calibrate=CALIBRATE,
                   calibration_trials=CAL_TRIALS, replace=REPLACE)
        if DO_PLOTS:
            it.plot_summary(trials=TRIALS, figures=FIGURES)

    if DO_SUMMARY:
        s.summarise(trials=TRIALS)      # -> results/<subject>/<session>/summary_*.png
    print(f"[settings] done: {', '.join(ITERATIONS)}")
