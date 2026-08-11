"""
Integration smoke test: a tiny synthetic ("ghost") knee through the real
OpenSim + CEINMS pipeline (the suite's only OpenSim/CEINMS coverage).

A 1-DOF knee (flexion/extension) with two flexors and two extensors is built,
fed a short synthetic extension->flexion movement plus EMG at a set activation
level, and run through the actual pipeline so regressions in the OpenSim/CEINMS
path get caught:

  * TestKneeModelBuild        — build the model, reload, check structure.
  * TestKneeOpenSim           — MuscleAnalysis + StaticOptimization + InverseDynamics
                                run and produce finite outputs.
  * TestKneeCEINMSWiring      — bioscout's CEINMS XML builders wire model muscles
                                to EMG channels + DOFs (no CEINMS binary needed).
  * TestKneeCEINMSCalibration — full CEINMS calibration (needs ceinms-nn-calibrate.exe):
                                build uncalibrated subject -> excitation generator ->
                                input data -> calibration cfg/setup -> calibrate,
                                asserting a calibrated subject XML is produced.

All tests build up ONE shared ghost session under
``bioscout/tests/_results/simulations/<Subject>/<session>/`` in the ITERATIVE
layout — the exact shape a real session has today (e.g. Athlete_03/25_03_31)::

    KneeGhost/ghost_session/
        session.yaml            <- scaffold_session_yaml(), then the ghost map
        1_c3dfiles/             <- placeholder captures the scaffold reads
        2_experimental/         <- model-independent exports (empty here)
        3_iterations/
            ghost/              <- ONE model iteration
                knee.osim
                ExtFlex_01/     <- MuscleAnalysis/, joint_angles.mot,
                ExtFlex_02/        emg.mot, inverse_dynamics.sto
                ceinms_calibration/
        logs/

The fixture is built THROUGH bioscout's own session tools — ``scaffold_session_yaml``
and the ``session_layout`` resolvers — not by joining folder names by hand. That
is deliberate: it makes this test the only coverage that session CREATION
produces a session the rest of the pipeline can actually open, and it means a
layout change cannot pass here while breaking real projects.

``ceinms_calibration/`` sits INSIDE the iteration, not at the session root: the
calibrated subject is a property of one model variant (cateli/gpk/lernagopal
each have their own), so a session-level folder would be a lie about what the
calibration belongs to.

The full run log is saved to ``bioscout/tests/_results/test_run.log``.
(``bioscout/tests/_results/`` is already in .gitignore.)

Everything self-skips when OpenSim (and, for calibration, the CEINMS binary)
isn't available, so the lightweight suite is never broken.

----------------------------------------------------------------------------
Test settings — edit these to change the synthetic task.
----------------------------------------------------------------------------
"""
import os
import sys
import types
import shutil
import stat
import unittest

import numpy as np

# ---- editable test configuration ------------------------------------------
N_FRAMES        = 100      # frames in the synthetic movement (max 100)
DURATION_S      = 1.0      # movement duration (s)
FLEX_MIN_DEG    = 5.0      # knee angle at start/end of the half-cycle
FLEX_MAX_DEG    = 70.0     # peak knee flexion
ACTIVATION_PCT  = 30.0     # synthetic EMG/activation level (% of max), 0–100
FMAX_N          = 600.0    # max isometric force per muscle (N)
CALIB_MAX_ITER  = 50       # CEINMS calibration iterations (small = fast test)
CALIB_SYNERGIES = 2        # CEINMS synergies during calibration
N_CALIB_TASKS   = 2        # number of calibration tasks (trials) in the session
WITH_BONE_GEOMETRY = True  # attach simple bone geometry to femur/tibia
EXEC_ALPHA      = 1        # CEINMS execution hybrid weights (EMG vs tracking)
EXEC_BETA       = 1
EXEC_GAMMA      = 1
CEINMS_TIME_MARGIN_S = 0.05  # inset the CEINMS time window inside the data range
# ---------------------------------------------------------------------------

N_FRAMES = min(int(N_FRAMES), 100)
# CEINMS time window, inset inside [0, DURATION_S]. OpenSim's InverseDynamicsTool
# can emit a final time stamp a hair short of DURATION_S (e.g. 0.999998), so a
# full-range [0, DURATION_S] window makes CEINMS *execution* reject the run with
# "externalTorques does not cover the CEINMS time range". Insetting guarantees
# every input (EMG, Lmt, moment arms, ID) covers the requested window.
CEINMS_T0 = 0.0 + CEINMS_TIME_MARGIN_S
CEINMS_T1 = DURATION_S - CEINMS_TIME_MARGIN_S
MUSCLES = ["ext_med", "ext_lat", "flx_med", "flx_lat"]   # 2 extensors, 2 flexors
DOF = "knee_angle"
EMG_CHANNELS = ["EMG_ext", "EMG_flx"]
EMG_MAP = {"EMG_ext": ["ext_med", "ext_lat"], "EMG_flx": ["flx_med", "flx_lat"]}

# Ghost session laid out exactly like a real bioscout `simulations/` session:
#   _results/simulations/<SUBJECT>/<SESSION>/3_iterations/<ITERATION>/<Trial>/...
RESULTS_ROOT  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_results")
SIM_ROOT      = os.path.join(RESULTS_ROOT, "simulations")
SUBJECT_NAME  = "KneeGhost"           # one ghost subject
SESSION_NAME  = "ghost_session"       # one session holding all trials
ITERATION_NAME = "ghost"              # the one model iteration in the session
CEINMS_CALIB_DIR = "ceinms_calibration"  # per-ITERATION CEINMS files live here
GHOST_BODY_MASS = 75.0                # session.yaml needs one; nothing normalises to it
MA_FOLDER     = "MuscleAnalysis"   # match real-session MA folder name
IK_MOT        = "joint_angles.mot" # match real-session IK output name
ID_STO        = "inverse_dynamics.sto"
EMG_MOT       = "emg.mot"

GHOST_SESSION = os.path.join(SIM_ROOT, SUBJECT_NAME, SESSION_NAME)


def _ghost_iter():
    """The iteration folder, resolved through bioscout rather than joined here.

    A function and not a constant: ``iteration_path`` answers from what is on
    disk (it supports the old flat layout too), so it must be asked AFTER
    setUpModule has built the skeleton, not at import time.
    """
    from bioscout.utils.session_layout import iteration_path
    return iteration_path(GHOST_SESSION, ITERATION_NAME)


def _has_opensim() -> bool:
    try:
        import opensim  # noqa: F401
        return True
    except Exception:
        return False


HAS_OSIM = _has_opensim()


def _has_ceinms_calibration() -> bool:
    try:
        from bioscout import utils
        exe = getattr(utils, "CEINMS_CALIBRATION_EXE", None)
        return bool(exe) and os.path.exists(exe)
    except Exception:
        return False


def _has_ceinms_exe() -> bool:
    try:
        from bioscout import utils
        exe = getattr(utils, "CEINMS_EXE", None)
        return bool(exe) and os.path.exists(exe)
    except Exception:
        return False


def _has_ceinms_optimise() -> bool:
    try:
        from bioscout import utils
        exe = getattr(utils, "CEINMS_OPTIMISE_EXE", None)
        return bool(exe) and os.path.exists(exe)
    except Exception:
        return False


def _use_headless_matplotlib():
    """Force a non-interactive backend so plotting tests never open windows."""
    try:
        import matplotlib
        matplotlib.use("Agg", force=True)
    except Exception:
        pass


def _wipe(path):
    """Delete *path* and make sure it is gone.

    ``shutil.rmtree(..., ignore_errors=True)`` is the obvious call and the wrong
    one here: files copied out of a read-only source carry the read-only bit,
    and on Windows that makes the unlink fail. With errors ignored the wipe
    reports nothing and the NEXT run builds its new-layout session on top of the
    old one — a fixture that is half old layout, half new, and passes. So clear
    the read-only bit and retry, then assert.
    """
    def _retry(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass

    if os.path.exists(path):
        shutil.rmtree(path, onerror=_retry)
    assert not os.path.exists(path), (
        f"could not remove {path} — a stale fixture would be silently reused. "
        "Close anything holding a file open in it (Explorer, an editor) and "
        "re-run.")


def build_ghost_session():
    """Create ONE fresh ghost session in the ITERATIVE layout, using bioscout's
    own session tools so this test covers session CREATION as well as the
    pipeline that runs inside it.

    Returns the path to the iteration folder. Steps:

    1. the folder skeleton, from the ``session_layout`` resolvers (they pick
       the numbered names for a session that does not exist yet);
    2. placeholder ``.c3d`` files — ``scaffold_session_yaml`` takes the trial
       list from the c3d FILENAMES, which is the real contract, and there is no
       synthetic c3d writer here. They stay empty; nothing reads their bytes.
       ``Static_01`` is included because a real session always has one and the
       scaffold warns when it is missing (the ghost pipeline never scales, so
       it is never opened);
    3. ``scaffold_session_yaml`` itself;
    4. the ghost EMG map written over whatever the scaffold inherited. The
       scaffold walks UP for the nearest ``settings.py`` to pick up lab
       constants, and from inside the installed package that finds bioscout's
       own bundled template — a real project's powerlifting EMG map, which
       names muscles this 4-muscle knee does not have.
    """
    from bioscout.utils.session_layout import (
        c3d_root, experimental_root, iterations_root, iteration_path,
        is_numbered_layout)
    from bioscout.utils.session import (
        scaffold_session_yaml, read_session_yaml, write_session_yaml)

    _wipe(SIM_ROOT)
    os.makedirs(GHOST_SESSION, exist_ok=True)

    c3d = c3d_root(GHOST_SESSION, create=True)
    experimental_root(GHOST_SESSION, create=True)
    iterations_root(GHOST_SESSION, create=True)
    os.makedirs(os.path.join(GHOST_SESSION, "logs"), exist_ok=True)
    assert is_numbered_layout(GHOST_SESSION), \
        "session_layout did not create the numbered layout for a new session"

    trials = [f"ExtFlex_{i + 1:02d}" for i in range(N_CALIB_TASKS)]
    for name in ["Static_01"] + trials:
        open(os.path.join(c3d, name + ".c3d"), "wb").close()

    scaffold_session_yaml(GHOST_SESSION, body_mass=GHOST_BODY_MASS,
                          static_trial="Static_01", overwrite=True)

    spec = read_session_yaml(os.path.join(GHOST_SESSION, "session.yaml"))
    spec.emg_muscle_mapping = {k: list(v) for k, v in EMG_MAP.items()}
    # Absolute paths to the bundled setup files came in with the lab constants.
    # They are correct for the machine that ran the scaffold and wrong for every
    # other one, and the ghost model has no markers to scale — drop them so the
    # fixture is the same on disk everywhere.
    spec.setup_folder = None
    spec.markerset = None
    spec.ceinms = {"alpha": str(EXEC_ALPHA), "beta": str(EXEC_BETA),
                   "gamma": str(EXEC_GAMMA)}
    spec.calibration_trials = list(trials)
    write_session_yaml(spec, os.path.join(GHOST_SESSION, "session.yaml"))

    it = iteration_path(GHOST_SESSION, ITERATION_NAME)
    os.makedirs(it, exist_ok=True)
    return it


def setUpModule():
    build_ghost_session()


def _model_path():
    """The iteration's model. A model IS the iteration — that is why it lives
    in the iteration folder and not at the session root."""
    return os.path.join(_ghost_iter(), "knee.osim")


def _ensure_model():
    """Build the iteration model once; reuse it across tests (tests stay
    independent — each builds it if missing)."""
    mp = _model_path()
    if not os.path.exists(mp):
        os.makedirs(_ghost_iter(), exist_ok=True)
        build_knee_model(mp)
    return mp


def _calib_dir():
    """Per-iteration CEINMS folder: <iteration>/ceinms_calibration/."""
    d = os.path.join(_ghost_iter(), CEINMS_CALIB_DIR)
    os.makedirs(d, exist_ok=True)
    return d


def build_trial(model_path, session_dir, trial_name, lo=FLEX_MIN_DEG,
                hi=FLEX_MAX_DEG, activation=ACTIVATION_PCT / 100.0):
    """Create one trial folder in real-session format under *session_dir* (an
    ITERATION folder): ``<iteration>/<trial_name>/`` with joint_angles.mot,
    emg.mot, a MuscleAnalysis/ folder and inverse_dynamics.sto.
    Returns (trial_dir, ik_mot, emg, ma_dir, id_sto)."""
    trial = os.path.join(session_dir, trial_name)
    os.makedirs(trial, exist_ok=True)
    ik = write_motion(os.path.join(trial, IK_MOT), lo=lo, hi=hi)
    emg = write_emg(os.path.join(trial, EMG_MOT), activation=activation)
    ma = os.path.join(trial, MA_FOLDER); os.makedirs(ma, exist_ok=True)
    run_muscle_analysis_and_so(model_path, ik, ma)
    idf = run_inverse_dynamics(model_path, ik, trial, fname=ID_STO)
    return trial, ik, emg, ma, idf


# --------------------------------------------------------------------------- #
# synthetic "ghost" model + data
# --------------------------------------------------------------------------- #
def build_knee_model(path, fmax=FMAX_N):
    """Minimal 1-DOF knee .osim: femur welded to ground, tibia on a pin joint,
    two anterior (extensor) and two posterior (flexor) Thelen muscles."""
    import opensim as osim
    m = osim.Model()
    m.setName("knee_ghost")
    m.setGravity(osim.Vec3(0, -9.81, 0))

    femur = osim.Body("femur", 1.0, osim.Vec3(0, 0.2, 0),
                      osim.Inertia(0.01, 0.01, 0.01, 0, 0, 0))
    tibia = osim.Body("tibia", 1.5, osim.Vec3(0, -0.2, 0),
                      osim.Inertia(0.02, 0.02, 0.02, 0, 0, 0))
    m.addBody(femur)
    m.addBody(tibia)

    ground = m.getGround()
    weld = osim.WeldJoint("hip_weld", ground, osim.Vec3(0, 0.8, 0), osim.Vec3(0),
                          femur, osim.Vec3(0, 0.4, 0), osim.Vec3(0))
    m.addJoint(weld)
    knee = osim.PinJoint("knee", femur, osim.Vec3(0, 0, 0), osim.Vec3(0),
                         tibia, osim.Vec3(0, 0, 0), osim.Vec3(0))
    coord = knee.updCoordinate()
    coord.setName(DOF)
    coord.setRangeMin(-0.2)
    coord.setRangeMax(2.2)
    m.addJoint(knee)

    def add_muscle(name, fem_pt, tib_pt):
        mus = osim.Thelen2003Muscle(name, fmax, 0.10, 0.15, 0.0)
        mus.addNewPathPoint(f"{name}_o", femur, osim.Vec3(*fem_pt))
        mus.addNewPathPoint(f"{name}_i", tibia, osim.Vec3(*tib_pt))
        m.addForce(mus)

    add_muscle("ext_med", (0.04, 0.20, 0.02), (0.04, -0.06, 0.02))
    add_muscle("ext_lat", (0.04, 0.20, -0.02), (0.04, -0.06, -0.02))
    add_muscle("flx_med", (-0.04, 0.20, 0.02), (-0.04, -0.06, 0.02))
    add_muscle("flx_lat", (-0.04, 0.20, -0.02), (-0.04, -0.06, -0.02))

    if WITH_BONE_GEOMETRY:
        # Simple bone geometry: a cylinder along each segment so the model has
        # visualizable "bones". Self-contained OpenSim primitives (no external
        # .vtp mesh files needed). Placed on offset frames so each cylinder
        # spans between its joints (femur: hip->knee, tibia: knee->shank).
        _add_bone(m, femur, center_y=0.20, length=0.40, radius=0.030,
                  color=(0.92, 0.90, 0.80))
        _add_bone(m, tibia, center_y=-0.20, length=0.40, radius=0.025,
                  color=(0.92, 0.90, 0.80))

    m.finalizeConnections()
    m.printToXML(path)
    return path


def _add_bone(model, body, center_y, length, radius, color):
    """Attach a cylinder 'bone' to *body*, centred at local y=*center_y*."""
    import opensim as osim
    frame = osim.PhysicalOffsetFrame(
        f"{body.getName()}_bone_offset", body,
        osim.Transform(osim.Vec3(0.0, center_y, 0.0)))
    body.addComponent(frame)
    cyl = osim.Cylinder(radius, length / 2.0)   # (radius, half-height) along Y
    cyl.setColor(osim.Vec3(*color))
    frame.attachGeometry(cyl)


def write_motion(path, n=N_FRAMES, t0=0.0, t1=DURATION_S,
                 lo=FLEX_MIN_DEG, hi=FLEX_MAX_DEG):
    """Synthetic knee extension->flexion->extension half-cycle (.mot, degrees)."""
    t = np.linspace(t0, t1, n)
    ang = lo + (hi - lo) * 0.5 * (1 - np.cos(2 * np.pi * (t - t0) / (t1 - t0)))
    with open(path, "w") as f:
        f.write("knee_motion\n")
        f.write(f"version=1\nnRows={n}\nnColumns=2\ninDegrees=yes\nendheader\n")
        f.write(f"time\t{DOF}\n")
        for ti, ai in zip(t, ang):
            f.write(f"{ti:.6f}\t{ai:.6f}\n")
    return path


def write_emg(path, n=N_FRAMES, t0=0.0, t1=DURATION_S, activation=ACTIVATION_PCT / 100.0):
    """Synthetic [0,1] EMG envelopes for the ext/flx channels, reciprocal,
    peaking at *activation* (the configured % activation)."""
    activation = float(np.clip(activation, 0.0, 1.0))
    t = np.linspace(t0, t1, n)
    ph = 2 * np.pi * (t - t0) / (t1 - t0)
    ext = activation * 0.5 * (1 + np.sin(ph))
    flx = activation * 0.5 * (1 + np.cos(ph))
    cols = ["time"] + EMG_CHANNELS
    with open(path, "w") as f:
        f.write("emg\n")
        f.write(f"version=1\nnRows={n}\nnColumns={len(cols)}\ninDegrees=no\nendheader\n")
        f.write("\t".join(cols) + "\n")
        for ti, a, b in zip(t, ext, flx):
            f.write(f"{ti:.6f}\t{a:.6f}\t{b:.6f}\n")
    return path


def run_muscle_analysis_and_so(model_path, mot_path, out_dir, t0=0.0, t1=DURATION_S):
    """OpenSim MuscleAnalysis + StaticOptimization via AnalyzeTool.

    Empty tool name -> output files are ``_MuscleAnalysis_*`` /
    ``_StaticOptimization_*`` (what CEINMS / create_input_data expect)."""
    import opensim as osim
    tool = osim.AnalyzeTool()
    tool.setName("")
    tool.setModelFilename(model_path)
    tool.setResultsDir(out_dir)
    tool.setInitialTime(t0)
    tool.setFinalTime(t1)
    tool.setCoordinatesFileName(mot_path)
    tool.setLowpassCutoffFrequency(-1)
    aset = tool.getAnalysisSet()
    ma = osim.MuscleAnalysis(); ma.setStartTime(t0); ma.setEndTime(t1)
    aset.cloneAndAppend(ma)
    so = osim.StaticOptimization(); so.setStartTime(t0); so.setEndTime(t1)
    aset.cloneAndAppend(so)
    setup = os.path.join(out_dir, "setup_analyze.xml")
    tool.printToXML(setup)
    osim.AnalyzeTool(setup).run()
    return out_dir


def run_inverse_dynamics(model_path, mot_path, out_dir, fname="inverse_dynamics.sto",
                         t0=0.0, t1=DURATION_S):
    """OpenSim InverseDynamics -> generalized forces (knee_angle_moment)."""
    import opensim as osim
    idt = osim.InverseDynamicsTool()
    idt.setModelFileName(model_path)
    idt.setCoordinatesFileName(mot_path)
    idt.setStartTime(t0)
    idt.setEndTime(t1)
    idt.setLowpassCutoffFrequency(6.0)
    idt.setResultsDir(out_dir)
    idt.setOutputGenForceFileName(fname)
    idt.run()
    return os.path.join(out_dir, fname)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _read_sto(path):
    import io
    import pandas as pd
    with open(path, errors="replace") as f:
        lines = f.readlines()
    h = next((i for i, l in enumerate(lines) if l.strip().lower() == "endheader"), None)
    skip = h + 1 if h is not None else 0
    return pd.read_csv(io.StringIO("".join(lines[skip:])), sep=r"\s+")


def _find(out_dir, suffix):
    for f in sorted(os.listdir(out_dir)):
        if f.endswith(suffix):
            return os.path.join(out_dir, f)
    return None


def _resolve_ceinms():
    """Return the live CEINMS helper module (the binary ``ceinms/`` package can
    shadow ``ceinms.py``, leaving the package attribute as a None placeholder)."""
    import importlib
    import bioscout  # noqa: F401
    from bioscout import utils
    cand = getattr(utils, "ceinms", None)
    if cand is not None and hasattr(cand, "create_excitation_generator"):
        return cand
    for name in ("bioscout.utils.ceinms", "ceinms"):
        try:
            m = importlib.import_module(name)
            if hasattr(m, "create_excitation_generator"):
                return m
        except Exception:
            pass
    m = sys.modules.get("ceinms")
    if m is not None and hasattr(m, "create_excitation_generator"):
        return m
    raise unittest.SkipTest("CEINMS helper module not importable")


def _stub_settings():
    """A minimal `settings` module the CEINMS helpers read via sys.modules."""
    bs = types.SimpleNamespace(
        dof_list=[DOF],
        emg_muscle_mapping=EMG_MAP,
        MUSCLE_GROUPS={"extensors": MUSCLES[:2], "flexors": MUSCLES[2:]},
    )
    cs = types.SimpleNamespace(
        # NB: no ExcitationsSquared objective — every ghost muscle maps to an EMG
        # channel, so there are 0 synthesised muscles and that term evaluates to
        # nan, which poisons the total loss and stops the optimiser improving.
        objective_functions=[
            {"name": "MomentError", "targets": "all", "weight": 1},
            {"name": "Penalty", "targetType": "normalisedFibreLength",
             "weight": 10, "exponent": 2, "range": "0.5 1.5"},
            {"name": "Penalty", "targetType": "tendonStrain",
             "weight": 1000, "exponent": 2, "range": "0. 0.5"},
        ],
        target_muscles=list(MUSCLES),
        num_synergies=CALIB_SYNERGIES,
        max_iterations=CALIB_MAX_ITER,
        learning_rate=0.02,
        # small beta/gamma sweep for the CEINMS optimise step (keeps it fast)
        beta_min=1, beta_max=2, beta_delta=1,
        gamma_min=1, gamma_max=2, gamma_delta=1,
    )

    class _Inputs:
        ceinms_input_data = "inputData.xml"

    mod = types.ModuleType("settings")
    mod.BatchSettings = bs
    mod.CEINMSSettings = cs
    mod.Inputs = _Inputs
    return mod


def build_session_task(ceinms, model_path, session_dir, task_name,
                       lo=FLEX_MIN_DEG, hi=FLEX_MAX_DEG,
                       activation=ACTIVATION_PCT / 100.0):
    """Build one calibration task (trial) in real-session format and write its
    ``inputData.xml``. Assumes a `settings` context is active (create_input_data
    reads it). Returns the inputData.xml path relative to the session dir."""
    trial, ik, emg, ma, idf = build_trial(model_path, session_dir, task_name,
                                           lo=lo, hi=hi, activation=activation)
    ceinms.create_input_data(MAFolder=ma, excitationsFile=emg, motionFile=ik,
                             externalTorquesFile=idf, externalLoadsFile=ik,
                             startStopTime=(CEINMS_T0, CEINMS_T1))
    return os.path.join(task_name, "inputData.xml")


class _settings_context:
    """Install a stub `settings` in sys.modules for the duration of a test."""
    def __enter__(self):
        self._saved = sys.modules.get("settings")
        sys.modules["settings"] = _stub_settings()
        return sys.modules["settings"]

    def __exit__(self, *exc):
        if self._saved is not None:
            sys.modules["settings"] = self._saved
        else:
            sys.modules.pop("settings", None)
        return False


# --------------------------------------------------------------------------- #
# tests
# --------------------------------------------------------------------------- #
class TestGhostSessionLayout(unittest.TestCase):
    """The session the other tests run inside is a VALID session.

    No OpenSim, so this runs everywhere — which is the point: it is the only
    coverage that bioscout's session-creation tools produce a session that
    bioscout's session-reading tools can open. The pipeline tests below all
    skip on a machine without OpenSim, and used to take this with them.
    """
    def test_numbered_layout(self):
        from bioscout.utils.session_layout import (
            is_numbered_layout, c3d_root, experimental_root, iterations_root)
        self.assertTrue(is_numbered_layout(GHOST_SESSION))
        self.assertEqual(os.path.basename(c3d_root(GHOST_SESSION)), "1_c3dfiles")
        self.assertEqual(os.path.basename(experimental_root(GHOST_SESSION)),
                         "2_experimental")
        self.assertEqual(os.path.basename(iterations_root(GHOST_SESSION)),
                         "3_iterations")

    def test_iteration_is_under_iterations_root(self):
        it = _ghost_iter()
        self.assertTrue(os.path.isdir(it))
        self.assertEqual(
            os.path.normpath(os.path.dirname(it)),
            os.path.normpath(os.path.join(GHOST_SESSION, "3_iterations")),
            "the iteration must live under 3_iterations/, not at the session root")

    def test_session_yaml_round_trips(self):
        from bioscout.utils.session import read_session_yaml
        spec = read_session_yaml(os.path.join(GHOST_SESSION, "session.yaml"))
        self.assertEqual(spec.subject, SUBJECT_NAME)
        self.assertEqual(spec.session, SESSION_NAME)
        self.assertEqual(spec.body_mass, GHOST_BODY_MASS)
        self.assertEqual(spec.static_trial, "Static_01")
        # the ghost map, not the powerlifting one the scaffold inherits
        self.assertEqual(spec.emg_map_for(), EMG_MAP)
        # machine-specific paths must not be baked into the fixture
        self.assertIsNone(spec.markerset)
        self.assertIsNone(spec.setup_folder)

    def test_session_opens_and_sees_the_iteration(self):
        from bioscout import Session
        s = Session.open(GHOST_SESSION)
        self.assertIn(ITERATION_NAME, list(s.iterations))


@unittest.skipUnless(HAS_OSIM, "OpenSim not importable")
class TestKneeModelBuild(unittest.TestCase):
    def test_build_and_reload(self):
        import opensim as osim
        mp = build_knee_model(_model_path())   # model at the session root
        self.assertTrue(os.path.exists(mp))
        m = osim.Model(mp); m.initSystem()
        self.assertEqual(m.getMuscles().getSize(), 4)
        names = {m.getMuscles().get(i).getName() for i in range(4)}
        self.assertEqual(names, set(MUSCLES))
        self.assertGreaterEqual(m.getCoordinateSet().getIndex(DOF), 0)
        if WITH_BONE_GEOMETRY:
            self.assertIn("Cylinder", open(mp).read(),
                          "bone geometry not written to the model")


@unittest.skipUnless(HAS_OSIM, "OpenSim not importable")
class TestKneeOpenSim(unittest.TestCase):
    def test_ma_so_id(self):
        import pandas as pd
        mp = _ensure_model()
        trial, ik, emg, ma, idf = build_trial(mp, _ghost_iter(), "ExtFlex_01")

        length = _find(ma, "_MuscleAnalysis_Length.sto")
        marm = _find(ma, f"_MuscleAnalysis_MomentArm_{DOF}.sto")
        force = _find(ma, "_StaticOptimization_force.sto")
        self.assertIsNotNone(length, "MuscleAnalysis Length not produced")
        self.assertIsNotNone(marm, "MuscleAnalysis MomentArm not produced")
        self.assertIsNotNone(force, "StaticOptimization force not produced")
        self.assertTrue(os.path.exists(idf), "InverseDynamics output not produced")

        df = _read_sto(force)
        mcols = [c for c in df.columns if c != "time"]
        self.assertGreaterEqual(len(mcols), 4)
        vals = df[mcols].apply(pd.to_numeric, errors="coerce").values
        self.assertTrue(np.isfinite(vals).any(), "all SO forces NaN")
        self.assertGreater(np.nanmax(vals), 0.0, "no positive muscle force")
        # ID produced a knee moment column
        idd = _read_sto(idf)
        self.assertTrue(any("knee" in c.lower() for c in idd.columns))


@unittest.skipUnless(HAS_OSIM, "OpenSim not importable")
class TestKneeCEINMSWiring(unittest.TestCase):
    """bioscout's CEINMS XML builders — no CEINMS binary required. Guards the
    settings-mapping / shadowing class of bug fixed this cycle."""
    def test_excitation_generator_and_input_data(self):
        ceinms = _resolve_ceinms()
        mp = _ensure_model()
        trial, ik, emg, ma, idf = build_trial(mp, _ghost_iter(), "ExtFlex_01")

        with _settings_context():
            eg = os.path.join(_calib_dir(), "excitationGenerator.xml")
            ceinms.create_excitation_generator(osim_model_path=mp, emg_path=emg, save_path=eg)
            self.assertTrue(os.path.exists(eg))
            txt = open(eg).read()
            for mus in MUSCLES:
                self.assertIn(mus, txt, f"muscle {mus} missing from excitation generator")
            for ch in EMG_CHANNELS:
                self.assertIn(ch, txt, f"channel {ch} missing from excitation generator")

            ceinms.create_input_data(MAFolder=ma, excitationsFile=emg, motionFile=ik,
                                     externalTorquesFile=idf, externalLoadsFile=ik,
                                     startStopTime=(CEINMS_T0, CEINMS_T1))
        idp = os.path.join(trial, "inputData.xml")   # written next to the MA folder
        self.assertTrue(os.path.exists(idp), "inputData.xml not produced")
        itxt = open(idp).read()
        self.assertIn(f"_MuscleAnalysis_MomentArm_{DOF}.sto", itxt)
        self.assertIn("_MuscleAnalysis_Length.sto", itxt)


def ghost_calibrate(ceinms, force=False):
    """Build the ghost session trials and run CEINMS calibration, mirroring the
    pipeline. Session-level CEINMS files go under ``ceinms_calibration/``; the
    per-task trials stay at the session root. Returns a dict of paths + trial
    names. If a calibrated subject already exists it is reused (force=True to
    always recalibrate)."""
    mp = _ensure_model()
    calib = _calib_dir()
    n_tasks = max(1, int(N_CALIB_TASKS))
    task_specs = [
        (FLEX_MIN_DEG, FLEX_MAX_DEG, ACTIVATION_PCT / 100.0),
        (FLEX_MIN_DEG, FLEX_MAX_DEG * 0.8, ACTIVATION_PCT / 100.0 * 0.7),
    ]
    paths = dict(
        model=mp, calib=calib,
        uncal=os.path.join(calib, "subjectUncalibrated.xml"),
        eg=os.path.join(calib, "excitationGenerator.xml"),
        cfg=os.path.join(calib, "calibrationCfg.xml"),
        setup=os.path.join(calib, "calibrationSetup.xml"),
        calibrated=os.path.join(calib, "subjectCalibrated.xml"),
        trials=[f"ExtFlex_{i + 1:02d}" for i in range(n_tasks)],
    )
    if not force and os.path.exists(paths["calibrated"]) and os.path.exists(paths["eg"]):
        return paths   # reuse a calibration already produced this run

    with _settings_context():
        ceinms.create_ceinms_model(osimModelPath=mp, outputCEINMSModelPath=paths["uncal"],
                                   DOFs=[DOF])
        input_rels, first_emg = [], None
        for i, name in enumerate(paths["trials"]):
            lo, hi, act = task_specs[i % len(task_specs)]
            build_session_task(ceinms, mp, _ghost_iter(), name, lo=lo, hi=hi, activation=act)
            # cfg/setup live in ceinms_calibration/, so trial inputData is referenced
            # relative to that folder (../<trial>/inputData.xml).
            input_abs = os.path.join(_ghost_iter(), name, "inputData.xml")
            input_rels.append(os.path.relpath(input_abs, calib))
            if first_emg is None:
                first_emg = os.path.join(_ghost_iter(), name, EMG_MOT)

        ceinms.create_excitation_generator(osim_model_path=mp, emg_path=first_emg,
                                           save_path=paths["eg"])
        ceinms.create_calibrationCfg(osimModelPath=mp, inputPaths=input_rels,
                                     outputPath=paths["cfg"])
        ceinms.create_calibrationSetupXML(
            uncalibratedCEINMSModelPath=paths["uncal"], excitationGeneratorFile=paths["eg"],
            calibrationCfgPath=paths["cfg"], outputSubjectFile=paths["calibrated"],
            outputDirectory=os.path.join(calib, "calibrationOutput"), setupXMLPath=paths["setup"])

        # Run calibration binary (suppress the XML auto-open inside calibrate()).
        _orig = getattr(os, "startfile", None)
        if _orig is not None:
            os.startfile = lambda *a, **k: None  # type: ignore[attr-defined]
        cwd = os.getcwd()
        try:
            ceinms.calibrate(setupXML_path=os.path.abspath(paths["setup"]))
        finally:
            os.chdir(cwd)
            if _orig is not None:
                os.startfile = _orig  # type: ignore[attr-defined]
    return paths


def ghost_execute(ceinms, trial_name, calibrated, eg):
    """Run CEINMS execution for one trial using the calibrated subject. Per-trial
    CEINMS files stay at the trial root (ceinms_cfg.xml, ceinms_setup.xml,
    Execution_*/). Returns the execution output directory."""
    from bioscout import utils
    import xml.etree.ElementTree as ET
    trial = os.path.join(_ghost_iter(), trial_name)
    exe_cfg = os.path.join(trial, "ceinms_cfg.xml")
    exe_setup = os.path.join(trial, "ceinms_setup.xml")
    out_dir = f"Execution_a{EXEC_ALPHA}_b{EXEC_BETA}_g{EXEC_GAMMA}"

    with _settings_context():
        ceinms.create_ceinms_cfg(ceinmsModelPath=calibrated, alpha=EXEC_ALPHA,
                                 beta=EXEC_BETA, gamma=EXEC_GAMMA, dofSet=DOF,
                                 excitationGeneratorFilePath=eg, outputPath=exe_cfg)
        root = ET.Element("ceinms")
        ET.SubElement(root, "subjectFile").text = os.path.relpath(calibrated, trial)
        ET.SubElement(root, "inputDataFile").text = "inputData.xml"
        ET.SubElement(root, "executionFile").text = os.path.relpath(exe_cfg, trial)
        ET.SubElement(root, "excitationGeneratorFile").text = os.path.relpath(eg, trial)
        ET.SubElement(root, "outputDirectory").text = out_dir
        utils.save_pretty_xml(ET.ElementTree(root), exe_setup)

        cwd = os.getcwd()
        try:
            ceinms.executable(setupXML_path=os.path.abspath(exe_setup))
        finally:
            os.chdir(cwd)
    return os.path.join(trial, out_dir)


def ghost_optimise(ceinms, trial_name, calibrated, eg):
    """Run the CEINMS optimise step (beta/gamma sweep) for one trial, reusing the
    execution cfg as the parameter template. Returns the optimisation output
    directory (or None if it produced nothing)."""
    from bioscout import utils
    trial = os.path.join(_ghost_iter(), trial_name)
    exe_cfg = os.path.join(trial, "ceinms_cfg.xml")       # template (from ghost_execute)
    opt_cfg = os.path.join(trial, "ceinms_optimise_cfg.xml")
    opt_setup = os.path.join(trial, "ceinms_optimise_setup.xml")
    out_dir = os.path.join(trial, "Optimisation")
    with _settings_context():
        ceinms.create_optimise_setupFiles(
            ceinmsModelPath=calibrated,
            inputDataFile=os.path.join(trial, "inputData.xml"),
            calibrationCfgPath=opt_cfg,
            excitationGeneratorFilePath=eg,
            outputDirectory=out_dir,
            setupXMLPath=opt_setup,
            templateCfgXMLPath=exe_cfg)
        cwd = os.getcwd()
        try:
            ceinms.optimise(setupXML_path=os.path.abspath(opt_setup))
        finally:
            os.chdir(cwd)
    return out_dir if os.path.isdir(out_dir) and os.listdir(out_dir) else None


def _knee_jra_cols(jra_df):
    if jra_df is None:
        return []
    return [c for c in jra_df.columns
            if "knee" in c.lower() and c.lower().rstrip().endswith(("fx", "fy", "fz"))][:3]


def build_and_render_trial_summary(trial_name, exec_dir, opt_dir=None):
    """For one trial: run SO + CEINMS JointReaction, render the full 5-row trial
    summary (Analyse.plot_summary layout) to <trial>/summary_plot.png. If
    *opt_dir* (a CEINMS-optimise output dir) is given and contains results, its
    forces/activations/fibre lengths + a JRA are overlaid as a third series.
    Returns (save_path, jra_so_file, jra_ceinms_file, jra_force_cols)."""
    trial = os.path.join(_ghost_iter(), trial_name)
    ma = os.path.join(trial, MA_FOLDER)
    ik_mot = os.path.join(trial, IK_MOT)
    so_force_f = _find(ma, "_StaticOptimization_force.sto")
    ceinms_force_f = os.path.join(exec_dir, "MuscleForces.sto")

    # minimal JointReaction for SO and CEINMS muscle forces (populates row 5);
    # reaction-loads .sto are written directly into the trial folder.
    jra_so_f = run_joint_reaction(_model_path(), ik_mot, so_force_f, trial, "JRA_SO")
    jra_ceinms_f = run_joint_reaction(_model_path(), ik_mot, ceinms_force_f, trial, "JRA_CEINMS")
    jra_so = _read_sto(jra_so_f) if jra_so_f else None
    jra_ceinms = _read_sto(jra_ceinms_f) if jra_ceinms_f else None
    jra_cols = _knee_jra_cols(jra_so)

    # optional CEINMS-optimise series
    opt_forces = opt_act = opt_fibre = opt_jra = None
    opt_jra_cols = []
    if opt_dir:
        opt_force_f = os.path.join(opt_dir, "MuscleForces.sto")
        if os.path.exists(opt_force_f):
            opt_forces = _read_sto(opt_force_f)
            opt_jra_f = run_joint_reaction(_model_path(), ik_mot, opt_force_f, trial, "JRA_OPT")
            if opt_jra_f:
                opt_jra = _read_sto(opt_jra_f)
                opt_jra_cols = _knee_jra_cols(opt_jra)
        if os.path.exists(os.path.join(opt_dir, "Activations.sto")):
            opt_act = _read_sto(os.path.join(opt_dir, "Activations.sto"))
        if os.path.exists(os.path.join(opt_dir, "NormFibreLengths.sto")):
            opt_fibre = _read_sto(os.path.join(opt_dir, "NormFibreLengths.sto"))

    save = os.path.join(trial, "summary_plot.png")
    render_trial_summary(
        save, dof=DOF, muscles=MUSCLES, emg_map=EMG_MAP,
        ik=_read_sto(ik_mot), idm=_read_sto(os.path.join(trial, ID_STO)),
        emg=_read_sto(os.path.join(trial, EMG_MOT)),
        so_forces=_read_sto(so_force_f), ceinms_forces=_read_sto(ceinms_force_f),
        so_act=_read_sto(_find(ma, "_StaticOptimization_activation.sto")),
        ceinms_act=_read_sto(os.path.join(exec_dir, "Activations.sto")),
        marm=_read_sto(_find(ma, f"_MuscleAnalysis_MomentArm_{DOF}.sto")),
        fibre_so=_read_sto(_find(ma, "_MuscleAnalysis_NormalizedFiberLength.sto")),
        fibre_ceinms=_read_sto(os.path.join(exec_dir, "NormFibreLengths.sto")),
        jra_so=jra_so, jra_ceinms=jra_ceinms, jra_cols=jra_cols,
        abg=(EXEC_ALPHA, EXEC_BETA, EXEC_GAMMA),
        opt_forces=opt_forces, opt_act=opt_act, opt_fibre=opt_fibre,
        opt_jra=opt_jra, opt_jra_cols=opt_jra_cols)
    return save, jra_so_f, jra_ceinms_f, jra_cols


def run_joint_reaction(model_path, mot_path, forces_sto, out_dir, name):
    """Minimal OpenSim JointReaction (no external loads) that applies *forces_sto*
    (the SO or CEINMS muscle forces) and returns the reaction-loads .sto path.
    This is the GRF-free core of openSim.run_jra, enough to populate the JRA row
    of the trial summary on the ghost."""
    import opensim as osim
    os.makedirs(out_dir, exist_ok=True)
    tool = osim.AnalyzeTool()
    tool.setName(name)
    tool.setModelFilename(model_path)
    tool.setResultsDir(out_dir)
    tool.setInitialTime(CEINMS_T0); tool.setFinalTime(CEINMS_T1)
    tool.setCoordinatesFileName(mot_path)
    tool.setLowpassCutoffFrequency(-1)
    jr = osim.JointReaction()
    jr.setName("JointReaction")
    jr.setStartTime(CEINMS_T0); jr.setEndTime(CEINMS_T1)
    jr.setForcesFileName(os.path.abspath(forces_sto))
    a_in, a_on, a_j = osim.ArrayStr(), osim.ArrayStr(), osim.ArrayStr()
    a_in.set(0, "child"); a_on.set(0, "child"); a_j.set(0, "all")
    jr.setInFrame(a_in); jr.setOnBody(a_on); jr.setJointNames(a_j)
    tool.getAnalysisSet().cloneAndAppend(jr)
    setup = os.path.join(out_dir, f"setup_{name}.xml")
    tool.printToXML(setup)
    osim.AnalyzeTool(setup).run()
    # name-prefixed so SO and CEINMS JRA can coexist in the same trial folder
    for fn in sorted(os.listdir(out_dir)):
        if fn.startswith(name) and fn.endswith("ReactionLoads.sto"):
            return os.path.join(out_dir, fn)
    return _find(out_dir, "ReactionLoads.sto")


def _time_normalise(df, n=101):
    """Resample a DataFrame onto n points over its own time range, with a 0-100%
    time axis. Mirrors analysis._u.time_normalise_df so signals of different
    lengths (e.g. CEINMS cropped to the [0.05,0.95] window vs full-length SO/MA)
    align before being multiplied/compared."""
    import numpy as _np
    import pandas as _pd
    if df is None or "time" not in df.columns or len(df) < 2:
        return df
    t = df["time"].values
    tnew = _np.linspace(t.min(), t.max(), n)
    out = {"time": _np.linspace(0, 100, n)}
    for c in df.columns:
        if c == "time":
            continue
        try:
            out[c] = _np.interp(tnew, t, df[c].values)
        except Exception:
            pass
    return _pd.DataFrame(out)


def render_trial_summary(save_path, *, dof, muscles, emg_map, ik, idm, emg,
                         so_forces, ceinms_forces, so_act, ceinms_act, marm,
                         fibre_so, fibre_ceinms, jra_so, jra_ceinms, jra_cols,
                         abg=(EXEC_ALPHA, EXEC_BETA, EXEC_GAMMA),
                         opt_forces=None, opt_act=None, opt_fibre=None,
                         opt_jra=None, opt_jra_cols=None):
    """Render the per-trial 5-row summary from ghost data, mirroring
    Analyse.plot_summary's layout:
        row 1 kinematics; row 2 EMG vs SO/CEINMS(/optimise) activations;
        row 3 moments SO vs CEINMS(/optimise) vs ID; row 4 normalised fibre
        lengths; row 5 joint reaction force.
    The CEINMS curve is labelled with the alpha/beta/gamma weights used; if an
    optimise result is supplied it is overlaid (orange) as a third series."""
    import matplotlib.pyplot as plt
    import numpy as _np
    # Time-normalise everything to a common 0-100% grid so signals of differing
    # length align (as Analyse.plot_summary does via time_normalise_df).
    ik, idm, emg = _time_normalise(ik), _time_normalise(idm), _time_normalise(emg)
    so_forces, ceinms_forces = _time_normalise(so_forces), _time_normalise(ceinms_forces)
    so_act, ceinms_act = _time_normalise(so_act), _time_normalise(ceinms_act)
    marm = _time_normalise(marm)
    fibre_so, fibre_ceinms = _time_normalise(fibre_so), _time_normalise(fibre_ceinms)
    jra_so, jra_ceinms = _time_normalise(jra_so), _time_normalise(jra_ceinms)
    opt_forces, opt_act = _time_normalise(opt_forces), _time_normalise(opt_act)
    opt_fibre, opt_jra = _time_normalise(opt_fibre), _time_normalise(opt_jra)

    ceinms_lbl = f"CEINMS (a{abg[0]} b{abg[1]} g{abg[2]})"
    fig, ax = plt.subplots(5, 1, figsize=(7, 12))
    fig.suptitle(f"Trial summary: {dof}", fontsize=12)

    if dof in ik.columns:
        ax[0].plot(ik["time"], ik[dof], color="blue")
    ax[0].set_ylabel("Angle (deg)")

    # row 2: EMG vs SO / CEINMS / optimise activations
    for ch, ms in emg_map.items():
        if emg is not None and ch in emg.columns:
            ax[1].plot(emg["time"], emg[ch], color="gray", alpha=0.6, label=f"EMG {ch}")
        for src, c, lab in ((so_act, "green", "SO"), (ceinms_act, "red", ceinms_lbl),
                            (opt_act, "orange", "CEINMS-opt")):
            cc = [m for m in ms if src is not None and m in src.columns]
            if cc:
                ax[1].plot(src["time"], src[cc].mean(axis=1), color=c, label=lab)
    ax[1].set_ylabel("EMG / activation")

    # row 3: moments SO vs CEINMS(/optimise) vs ID
    mcol = f"{dof}_moment"
    if idm is not None and mcol in idm.columns:
        ax[2].plot(idm["time"], idm[mcol], color="black", label="ID")
    for forces, c, ls, lab in ((so_forces, "green", "--", "SO total"),
                               (ceinms_forces, "red", ":", f"{ceinms_lbl} total"),
                               (opt_forces, "orange", "-.", "CEINMS-opt total")):
        if forces is None or marm is None:
            continue
        common = [m for m in muscles if m in forces.columns and m in marm.columns]
        if common:
            mm = sum(forces[m].values * marm[m].values for m in common)
            ax[2].plot(forces["time"], mm, color=c, linestyle=ls, label=lab)
    ax[2].set_ylabel("Moment (Nm)"); ax[2].legend(fontsize=6)

    # row 4: normalised fibre lengths
    for src, c, ls in ((fibre_so, "green", "-"), (fibre_ceinms, "red", "--"),
                       (opt_fibre, "orange", "-.")):
        if src is None:
            continue
        for m in [x for x in muscles if x in src.columns]:
            ax[3].plot(src["time"], src[m], color=c, linestyle=ls, lw=0.7, alpha=0.7)
    ax[3].set_ylabel("Norm. fibre length")

    # row 5: joint reaction force resultant
    for jra, cols, c, lab in ((jra_so, jra_cols, "blue", "SO"),
                              (jra_ceinms, jra_cols, "red", "CEINMS"),
                              (opt_jra, opt_jra_cols, "orange", "CEINMS-opt")):
        if jra is None or not cols:
            continue
        res = _np.sqrt(sum(jra[col].values ** 2 for col in cols if col in jra.columns))
        ax[4].plot(jra["time"], res, color=c, linestyle="--", label=lab)
    ax[4].set_ylabel("JRF (N)"); ax[4].set_xlabel("time"); ax[4].legend(fontsize=6)

    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(save_path)
    plt.close(fig)
    return save_path


@unittest.skipUnless(HAS_OSIM and _has_ceinms_calibration(),
                     "OpenSim or ceinms-nn-calibrate.exe not available")
class TestKneeCEINMSCalibration(unittest.TestCase):
    """Full CEINMS calibration on the ghost knee, mirroring the pipeline.

    Laid out like a real bioscout session: the model at the session root, one
    folder per task (``ExtFlex_01``, ``ExtFlex_02``, ...) each holding its own
    joint_angles.mot / emg.mot / MuscleAnalysis/ / inverse_dynamics.sto, and all
    session-level CEINMS files grouped under ``ceinms_calibration/`` (subject,
    excitation generator, calibration cfg/setup, calibrated subject,
    calibrationOutput/). Asserts a calibrated subject XML is produced."""
    def test_calibrate(self):
        ceinms = _resolve_ceinms()
        paths = ghost_calibrate(ceinms, force=True)
        self.assertTrue(os.path.exists(paths["calibrated"]),
                        "CEINMS calibration did not produce subjectCalibrated.xml")
        self.assertGreater(os.path.getsize(paths["calibrated"]), 0)


@unittest.skipUnless(HAS_OSIM and _has_ceinms_calibration() and _has_ceinms_exe(),
                     "OpenSim / ceinms-nn-calibrate.exe / CEINMS.exe not available")
class TestKneeCEINMSPipeline(unittest.TestCase):
    """CEINMS execution + result plotting + session summary on the ghost session.

    setUpClass calibrates once (reusing a calibration already produced this run)
    and runs execution for every trial, so the test methods can assert the
    execution forces, the calibration/execution plots, and a session summary."""
    @classmethod
    def setUpClass(cls):
        _use_headless_matplotlib()
        cls.ceinms = _resolve_ceinms()
        cls.paths = ghost_calibrate(cls.ceinms)
        cls.exec_dirs = {
            t: ghost_execute(cls.ceinms, t, cls.paths["calibrated"], cls.paths["eg"])
            for t in cls.paths["trials"]
        }
        # CEINMS optimise (beta/gamma sweep) — only if the binary is present
        cls.opt_dirs = {}
        if _has_ceinms_optimise():
            for t in cls.paths["trials"]:
                try:
                    cls.opt_dirs[t] = ghost_optimise(
                        cls.ceinms, t, cls.paths["calibrated"], cls.paths["eg"])
                except Exception as e:   # don't let an optimise hiccup break the suite
                    print(f"[ghost] CEINMS optimise failed for {t}: {e}")
                    cls.opt_dirs[t] = None

    def test_execution_forces(self):
        import pandas as pd
        for tname, d in self.exec_dirs.items():
            f = os.path.join(d, "MuscleForces.sto")
            self.assertTrue(os.path.exists(f), f"{tname}: MuscleForces.sto not produced")
            df = _read_sto(f)
            cols = [c for c in df.columns if c != "time"]
            self.assertGreaterEqual(len(cols), 4)
            vals = df[cols].apply(pd.to_numeric, errors="coerce").values
            self.assertTrue(np.isfinite(vals).any(), f"{tname}: all CEINMS forces NaN")

    def test_calibration_parameter_plot(self):
        png = self.paths["calibrated"].replace(".xml", "_parameters.png")
        with _settings_context():
            self.ceinms.plot_ceinms_model_parameters(self.paths["calibrated"])
        self.assertTrue(os.path.exists(png), "calibration parameter plot not produced")

    def test_compare_models_plot(self):
        png = self.paths["calibrated"].replace(".xml", "_vs_uncalibrated.png")
        with _settings_context():
            self.ceinms.plot_compare_ceinms_models(
                uncalibratedModelPath=self.paths["uncal"],
                calibratedModelPath=self.paths["calibrated"])
        self.assertTrue(os.path.exists(png), "calibrated-vs-uncalibrated plot not produced")

    def test_execution_muscle_forces_plot(self):
        d = self.exec_dirs[self.paths["trials"][0]]
        f = os.path.join(d, "MuscleForces.sto")
        with _settings_context():
            self.ceinms.plot_ceinms_muscle_forces(f)
        self.assertTrue(os.path.exists(f.replace(".sto", ".png")),
                        "CEINMS muscle-forces plot not produced")

    def test_trial_summary_figures(self):
        """Every trial gets the full 5-row summary_plot.png (kinematics / EMG vs
        SO&CEINMS(/optimise) / moments / normalised fibre lengths / JRA),
        mirroring Analyse.plot_summary. Runs a real SO and CEINMS JointReaction
        per trial so the JRA row is populated, overlays the CEINMS-optimise
        result when available, and checks the knee reaction columns exist."""
        for trial_name in self.paths["trials"]:
            exe = self.exec_dirs[trial_name]
            opt = self.opt_dirs.get(trial_name)
            save, jra_so_f, jra_ceinms_f, jra_cols = build_and_render_trial_summary(
                trial_name, exe, opt_dir=opt)
            self.assertTrue(jra_so_f and os.path.exists(jra_so_f),
                            f"{trial_name}: SO JointReaction not produced")
            self.assertTrue(jra_ceinms_f and os.path.exists(jra_ceinms_f),
                            f"{trial_name}: CEINMS JointReaction not produced")
            self.assertEqual(len(jra_cols), 3,
                             f"{trial_name}: knee JRA force columns not found")
            self.assertTrue(os.path.exists(save),
                            f"{trial_name}: 5-row summary_plot.png not produced")

    @unittest.skipUnless(_has_ceinms_optimise(), "CEINMSoptimise.exe not available")
    def test_ceinms_optimise(self):
        """CEINMS optimise (beta/gamma sweep) runs and produces output for each
        trial; its results feed the optimise overlay in the trial summary."""
        for trial_name in self.paths["trials"]:
            d = self.opt_dirs.get(trial_name)
            self.assertTrue(d and os.path.isdir(d),
                            f"{trial_name}: CEINMS optimise produced no output dir")
            self.assertTrue(os.listdir(d),
                            f"{trial_name}: CEINMS optimise output dir is empty")
