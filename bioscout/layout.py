"""bioscout.layout — the CANONICAL trial file/folder layout.

This is the single source of truth for where a trial's inputs and each pipeline
stage's outputs live (``inputs/``, ``external_biomechanics/``, ``muscle_analysis/``,
``static_optimisation/``, ``ceinms/``, ``joint_contact_forces/``).

Historically this lived as ``Inputs`` inside every project's ``settings.py`` and
``Analyse`` subclassed ``settings.Inputs``. That forced each project to carry a
copy of the layout and created a fragile settings<->utils import cycle. The layout
is now owned by the package here; a project only needs its own ``Inputs`` if it
wants to OVERRIDE the default folder layout, and ``Analyse`` falls back to this
canonical class when the project doesn't define one.

Standalone by design: this module imports only ``os`` so it can be imported very
early (before ``bioscout.utils``, which pulls scipy/opensim) without any cycle.
"""
import os


class Inputs:
    """Trial file layout — inputs separated from outputs via subfolders."""
    DIR_INPUTS = "inputs"
    DIR_EXTBIO = "external_biomechanics"   # IK + ID
    DIR_MA     = "muscle_analysis"
    DIR_SO     = "static_optimisation"
    DIR_CEINMS = "ceinms"
    DIR_JCF    = "joint_contact_forces"    # JRA (joint reaction / contact forces)

    def __init__(self, parentdir=None):
        self._parentdir = parentdir
        j = os.path.join
        I, E, M, S, C, JCF = (self.DIR_INPUTS, self.DIR_EXTBIO, self.DIR_MA,
                              self.DIR_SO, self.DIR_CEINMS, self.DIR_JCF)

        self.setup_dir = ""
        self.model_dir = ""
        self.start_time = "0.0000"
        self.end_time = "1.0000"

        # raw experimental inputs
        self.c3d       = j(I, "c3dfile.c3d")
        self.markers   = j(I, "marker_experimental.trc")
        self.markerset = j(I, "markers_FAIS.xml")
        self.grf_mot   = j(I, "grf.mot")
        self.setup_grf = j(I, "GRF.xml")
        self.emg       = j(I, "emg.mot")
        self.analog    = j(I, "analog.csv")

        # external biomechanics: IK + ID
        self.setup_ik      = j(E, "setup_IK.xml")
        self.ik            = j(E, "joint_angles.mot")
        self.model_markers = j(E, "_ik_model_marker_locations.sto")
        self.setup_id      = j(E, "setup_ID.xml")
        self.id            = j(E, "inverse_dynamics.sto")

        # muscle analysis
        self.setup_ma = j(M, "setup_MA.xml")
        self.ma       = M

        # static optimisation
        self.actuators_so   = j(S, "actuators_so.xml")
        self.setup_so       = j(S, "setup_SO.xml")
        self.so_forces      = j(S, "SO_StaticOptimization_force.sto")
        self.so_activations = j(S, "SO_StaticOptimization_activation.sto")
        self.jra_forces     = self.so_forces
        # JRA / joint contact forces (SO + CEINMS both live in joint_contact_forces/)
        self.setup_jra      = j(JCF, "setup_JRA_SO.xml")
        self.jra            = j(JCF, "Analyse_JRA_ReactionLoads_SO.sto")

        # CEINMS (trial level)
        self.emg_filtered_normalised = j(I, "emg_filtered_normalised.mot")
        self.ceinms_excitations      = self.emg_filtered_normalised
        self.ceinms_input_data       = j(C, "inputData.xml")
        self.ceinms_exe_cfg          = j(C, "ceinms_cfg.xml")
        self.ceinms_exe_setup        = j(C, "ceinms_setup.xml")
        self.ceinms_optimise_setup   = j(C, "ceinms_setup_optimise.xml")
        self.ceinms_optimise_cfg     = j(C, "ceinms_cfg_optimise.xml")
        self.ceinms_exe_dir          = j(C, "Execution")
        self.ceinms_optimisation_dir = j(C, "Optimised")
        self.setup_jra_ceinms        = j(JCF, "setup_JRA_CEINMS.xml")
        self.jra_ceinms              = j(JCF, "Analyse_JRA_ReactionLoads_CEINMS.sto")
        self.alpha = "10"
        self.beta = "1"
        self.gamma = "1000"

        # CEINMS calibration (session level, in ../ceinms_calibration/)
        C_CAL = j("..", "ceinms_calibration")
        self.ceinms_uncalibrated_model   = j(C_CAL, "subjectUncalibrated.xml")
        self.ceinms_calibrated_model     = j(C_CAL, "subjectCalibrated.xml")
        self.ceinms_calibration_cfg      = j(C_CAL, "calibrationCfg.xml")
        self.ceinms_calibration_setup    = j(C_CAL, "calibrationSetup.xml")
        self.ceinms_excitation_generator = j(C_CAL, "excitationGenerator.xml")
        self.ceinms_calibration_dir      = j(C_CAL, "calibrationOutput")

    @property
    def subfolders(self):
        return [self.DIR_INPUTS, self.DIR_EXTBIO, self.DIR_MA, self.DIR_SO,
                self.DIR_CEINMS, self.DIR_JCF]

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


# Semantic alias for the class name, mirroring the Analyse property aliases.
Layout = Inputs
