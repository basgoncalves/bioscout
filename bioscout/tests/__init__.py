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
    # OpenSim/CEINMS knee integration tests — optional. They self-skip when
    # OpenSim (or the CEINMS binary) isn't available; the import is guarded so a
    # problem there can never break the lightweight suite.
    try:
        from . import test_knee_pipeline as _knee
        for cls in (_knee.TestKneeModelBuild, _knee.TestKneeOpenSim,
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
