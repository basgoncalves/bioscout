"""
bioscout.tests — lightweight self-test suite.

Run it with::

    python -c "import bioscout; bioscout.test()"

or::

    python -m bioscout.tests

It is intentionally dependency-light: it checks that the package wiring is
intact (every name the package promises is importable from where it should
come), that the small shared helpers behave, and that the analysis object model
builds. Tests that would need OpenSim, CEINMS or real trial data are skipped
automatically when those aren't available, so the suite is safe to run anywhere.
"""
import unittest

import numpy as np
import pandas as pd


class TestPackageWiring(unittest.TestCase):
    def test_version(self):
        import bioscout
        self.assertTrue(isinstance(bioscout.__version__, str) and bioscout.__version__)

    def test_utils_imports(self):
        from bioscout import utils
        self.assertTrue(isinstance(utils.__version__, str))

    def test_reexports_present(self):
        """Names the public API promises must resolve from utils, wherever they
        actually live now (shared / io / stats / emg / plot / analysis / tools)."""
        from bioscout import utils
        for name in (
            # shared helpers
            "updir", "print_to_log", "time_normalise_df", "time_normalise_file",
            "create_session", "get_mean_across_trial_dfs", "get_unique_names",
            "create_color_and_style_dict", "rename_all_files_in_dir",
            # stats
            "rmse", "rsquared", "compare_curves", "sum3d",
            # io
            "load_any_data_file", "write_sto_file", "check_path",
            # classes / tools
            "Plot", "Analyse", "osimTools", "gitTools", "Organise",
            # analysis object model
            "Project", "Subject", "Session", "build_model_config", "discover_subjects",
        ):
            self.assertTrue(hasattr(utils, name), f"utils.{name} missing")

    def test_package_level_names(self):
        import bioscout
        for name in ("Project", "Subject", "Session", "build_model_config", "init_project"):
            self.assertTrue(hasattr(bioscout, name), f"bioscout.{name} missing")

    def test_subject_shim(self):
        from bioscout.subject import Subject, build_model_config  # noqa: F401


class TestSharedHelpers(unittest.TestCase):
    def test_updir(self):
        from bioscout import utils
        p = utils.updir(utils.os.path.join("a", "b", "c", "d"), 2)
        self.assertTrue(p.endswith("a" + utils.os.sep + "b") or p.endswith("a/b"))

    def test_time_normalise_df(self):
        from bioscout import utils
        df = pd.DataFrame({"time": np.linspace(0, 2, 37), "x": np.linspace(0, 10, 37)})
        out = utils.time_normalise_df(df)
        self.assertEqual(len(out), 101)
        self.assertAlmostEqual(float(out["x"].iloc[0]), 0.0, places=6)
        self.assertAlmostEqual(float(out["x"].iloc[-1]), 10.0, places=6)

    def test_time_normalise_df_requires_time(self):
        from bioscout import utils
        with self.assertRaises(Exception):
            utils.time_normalise_df(pd.DataFrame({"x": [1, 2, 3]}))


class TestAnalysisModel(unittest.TestCase):
    def test_subject_to_config(self):
        from bioscout import Subject, build_model_config
        s = Subject("Athlete_X", label="X", color="red", model_so="m.osim")
        cfg = build_model_config([s], force_types=("SO", "CEINMS"))
        self.assertIn("X", cfg)
        self.assertIn("X - CEINMS", cfg)
        self.assertEqual(cfg["X"]["color"], "red")

    def test_session_repr(self):
        from bioscout import Subject, Session
        s = Subject("Athlete_X", session="25_03_31")
        sess = Session(s, "25_03_31")
        self.assertIn("25_03_31", repr(sess) + sess.name)


def suite():
    loader = unittest.TestLoader()
    s = unittest.TestSuite()
    for cls in (TestPackageWiring, TestSharedHelpers, TestAnalysisModel):
        s.addTests(loader.loadTestsFromTestCase(cls))
    return s


def run(verbosity=2):
    """Run the suite; return True if everything passed."""
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite())
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
