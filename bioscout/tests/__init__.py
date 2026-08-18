"""
bioscout.tests — self-test suite (``bioscout.test()`` runs this).

Two layers:
  * TestPackageWiring — a tiny, dependency-light smoke test that the package is
    wired up: version present, core names re-exported on ``bioscout`` and
    ``bioscout.utils``, and the Subject model imports from its canonical home
    (guards the import/rename/restructure churn).
  * the OpenSim/CEINMS knee integration tests (``test_knee_pipeline``), which
    self-skip when OpenSim — and, for calibration, the CEINMS binary — aren't
    available, so this suite is never broken on a machine without them.

Run:  python -c "import bioscout; bioscout.test()"
   or  python -m bioscout.tests
"""
import sys
import unittest


class TestPackageWiring(unittest.TestCase):
    def test_version(self):
        import bioscout
        self.assertIsInstance(bioscout.__version__, str)
        self.assertTrue(bioscout.__version__)

    def test_utils_version(self):
        from bioscout import utils
        self.assertIsInstance(utils.__version__, str)

    def test_package_level_names(self):
        import bioscout
        for name in ("Project", "Subject", "Session", "build_model_config",
                     "discover_subjects", "init_project", "__version__"):
            self.assertTrue(hasattr(bioscout, name), f"bioscout.{name} missing")

    def test_utils_reexports(self):
        from bioscout import utils
        for name in ("Analyse", "Project", "Subject", "Session",
                     "build_model_config", "discover_subjects",
                     "load_any_data_file", "write_sto_file",
                     "time_normalise_df", "trial_type", "select_subjects",
                     "subjects_in_simulations", "start_logging"):
            self.assertTrue(hasattr(utils, name), f"utils.{name} missing")

    def test_subject_import(self):
        # canonical home of the Subject / Session model
        from bioscout.utils.analysis import Subject, Session, build_model_config  # noqa: F401

    def test_subjects_in_simulations_safe(self):
        from bioscout import utils
        self.assertIsInstance(utils.subjects_in_simulations("/no/such/dir/xyz"), list)


def suite():
    loader = unittest.TestLoader()
    s = unittest.TestSuite()
    s.addTests(loader.loadTestsFromTestCase(TestPackageWiring))
    # model_edit: dependency-light by design — the registry, naming rule,
    # validator, recipe engine and every pure-XML op run without OpenSim.
    try:
        from . import test_model_edit as _me
        for _cls in (_me.TestRegistry, _me.TestIntrospect, _me.TestNaming,
                     _me.TestValidation, _me.TestPureOps,
                     _me.TestOpenSimOpsDegradeCleanly, _me.TestRecipe):
            s.addTests(loader.loadTestsFromTestCase(_cls))
    except Exception as _e:  # pragma: no cover
        print(f"[tests] model_edit tests unavailable: {_e}")
    # validation paths: the one rule for where a report about a model goes.
    # Pure stdlib, so it always runs — and it is the only thing pinning the
    # five call sites that used to compute the folder name independently.
    try:
        from . import test_validation_paths as _vp
        for _cls in (_vp.TestValidationDir, _vp.TestIsReportDir):
            s.addTests(loader.loadTestsFromTestCase(_cls))
    except Exception as _e:  # pragma: no cover
        print(f"[tests] validation path tests unavailable: {_e}")
    # model: does every .osim still find its bones? Pure stdlib on
    # synthetic fixtures, so it always runs — including in a bare env, which is
    # the point: this is the check for a failure OpenSim reports as silence.
    try:
        from . import test_model as _mt
        for _cls in (_mt.TestReading, _mt.TestTiers, _mt.TestTree, _mt.TestCli,
                     _mt.TestRunPathWarning):
            s.addTests(loader.loadTestsFromTestCase(_cls))
    except Exception as _e:  # pragma: no cover
        print(f"[tests] model tests unavailable: {_e}")
    # session_form: the session editor's model. Every test asserts what did
    # NOT change as well as what did — a save that reflows session.yaml or drops
    # its comment block is unrecoverable and looks like success.
    try:
        from . import test_session_form as _sf
        for _cls in (_sf.TestReading, _sf.TestRedFlags, _sf.TestSurgicalEditing):
            s.addTests(loader.loadTestsFromTestCase(_cls))
    except Exception as _e:  # pragma: no cover
        print(f"[tests] session_form tests unavailable: {_e}")
    # session_paths + emg_filter: one path rule with base reporting, and the
    # EMG filter settings. Both stdlib-only, both about making a result
    # reproducible from its session file.
    for _mod, _names in (("test_session_paths",
                          ("TestBases", "TestRealFaisLayout", "TestResolveAll")),
                         ("test_emg_filter",
                          ("TestDefaults", "TestPrecedence", "TestFromSessionDir"))):
        try:
            _m = __import__(f"bioscout.tests.{_mod}", fromlist=["*"])
            for _n in _names:
                s.addTests(loader.loadTestsFromTestCase(getattr(_m, _n)))
        except Exception as _e:  # pragma: no cover
            print(f"[tests] {_mod} unavailable: {_e}")
    # gapfill: marker gap filling. Pure numpy on synthetic rigid bodies, so it
    # always runs. Half the tests assert what it REFUSES to fill — an absent
    # marker is one OpenSim ignores, a fabricated one is one it believes, and
    # the second failure is silent all the way to the joint contact forces.
    try:
        from . import test_gapfill as _gfm
        for _cls in (_gfm.TestRigidFill, _gfm.TestRefusal, _gfm.TestShortGaps,
                     _gfm.TestUsableWindow, _gfm.TestTrcIo):
            s.addTests(loader.loadTestsFromTestCase(_cls))
    except Exception as _e:  # pragma: no cover
        print(f"[tests] gapfill tests unavailable: {_e}")
    # cli: the verb surface and, more importantly, the legacy translation table.
    # A wrong entry there does not crash — it silently runs a different command,
    # so every verb is pinned to the exact argv it produces. Pure stdlib.
    try:
        from . import test_cli as _cli
        for _cls in (_cli.TestParser, _cli.TestTranslation, _cli.TestLegacyHint,
                     _cli.TestStaysLight):
            s.addTests(loader.loadTestsFromTestCase(_cls))
    except Exception as _e:  # pragma: no cover
        print(f"[tests] cli tests unavailable: {_e}")
    # file_edit: config-file editing (session.yaml / OpenSim XML / JSON).
    # Pure stdlib + PyYAML, so it always runs. Pins that a YAML edit is
    # surgical — losing session.yaml's comments is silent and unrecoverable.
    try:
        from . import test_file_edit as _fe
        for _cls in (_fe.TestYamlIsSurgical, _fe.TestYamlStructuralEdits,
                     _fe.TestSaving, _fe.TestChecks, _fe.TestXml, _fe.TestJson,
                     _fe.TestDispatch, _fe.TestFlowMap):
            s.addTests(loader.loadTestsFromTestCase(_cls))
    except Exception as _e:  # pragma: no cover
        print(f"[tests] file_edit tests unavailable: {_e}")
    # plot: the tidy table, the muscle-work integral and the comparison
    # figures. numpy + pandas + matplotlib only — no OpenSim, no scipy — so a
    # collaborator with nothing but the results table can still check it.
    try:
        from . import test_plot as _plt
        for _cls in (_plt.TestTidy, _plt.TestWork, _plt.TestCompare):
            s.addTests(loader.loadTestsFromTestCase(_cls))
    except Exception as _e:  # pragma: no cover
        print(f"[tests] plot tests unavailable: {_e}")
    # OpenSim/CEINMS knee integration tests — optional. They self-skip when
    # OpenSim (or the CEINMS binary) isn't available; the import is guarded so a
    # problem there can never break the lightweight suite.
    #
    # TestGhostSessionLayout is FIRST and is NOT skipped: it checks that the
    # ghost session the others run inside was created correctly (numbered
    # layout, iteration under 3_iterations/, a session.yaml that Session.open
    # accepts). That is session-creation coverage, needs no OpenSim, and would
    # otherwise be skipped away on exactly the machines most likely to have a
    # layout problem.
    try:
        from . import test_knee_pipeline as _knee
        for cls in (_knee.TestGhostSessionLayout,
                    _knee.TestKneeModelBuild, _knee.TestKneeOpenSim,
                    _knee.TestKneeCEINMSWiring, _knee.TestKneeCEINMSCalibration,
                    _knee.TestKneeCEINMSPipeline):
            s.addTests(loader.loadTestsFromTestCase(cls))
    except Exception as _e:  # pragma: no cover
        print(f"[tests] knee integration tests unavailable: {_e}")
    return s


class _Tee:
    """Write to several streams at once (console + log file)."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, s):
        for st in self.streams:
            try:
                st.write(s); st.flush()
            except Exception:
                pass
        return len(s)

    def flush(self):
        for st in self.streams:
            try:
                st.flush()
            except Exception:
                pass


def run(verbosity=2):
    """Run the suite; return True if everything passed.

    The full run (unittest results, Python prints, the streamed CEINMS log) is
    saved to ``bioscout/tests/_results/test_run.log`` so it can be read or sent
    without copy-pasting the console. OpenSim's own C++ messages are captured
    separately to ``_results/opensim_tests.log`` (they go through OpenSim's
    logger, not Python stdout).
    """
    import os

    results_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_results")
    os.makedirs(results_root, exist_ok=True)
    log_path = os.path.join(results_root, "test_run.log")
    osim_log_path = os.path.join(results_root, "opensim_tests.log")

    # Route OpenSim's C++ logger to a file too (its [info] lines bypass Python).
    try:
        import opensim
        try:
            opensim.Logger.removeFileSink()
        except Exception:
            pass
        opensim.Logger.addFileSink(osim_log_path)
    except Exception:
        osim_log_path = None

    real_out, real_err = sys.stdout, sys.stderr
    with open(log_path, "w", encoding="utf-8") as logf:
        tee = _Tee(real_out, logf)
        sys.stdout = sys.stderr = tee
        try:
            result = unittest.TextTestRunner(stream=tee, verbosity=verbosity).run(suite())
        finally:
            sys.stdout, sys.stderr = real_out, real_err

    print(f"\nFull test log saved to: {log_path}")
    if osim_log_path:
        print(f"OpenSim log saved to:   {osim_log_path}")
    return result.wasSuccessful()


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
