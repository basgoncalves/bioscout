"""Where reports about a model are written.

Pure stdlib — no OpenSim, no data. These pin the one naming rule that five
call sites share (``muscle_inspect``'s three entry points, the TPS adapter and
``change_moment_arms``); before 2.0.0b11 each computed it itself and they drifted.
"""
import os
import unittest

from bioscout.muscle_inspect.paths import (
    VALIDATION_DIRNAME, is_report_dir, validation_dir,
)


class TestValidationDir(unittest.TestCase):
    MODEL = os.path.join(os.sep, "sim", "A03", "3_iterations", "cateli",
                         "scaled_opt_N10.osim")

    def test_layout_is_validation_slash_model_stem(self):
        out = validation_dir(self.MODEL)
        self.assertEqual(os.path.basename(out), "scaled_opt_N10")
        self.assertEqual(os.path.basename(os.path.dirname(out)), VALIDATION_DIRNAME)
        # ...and validation/ sits in the iteration folder, beside the model
        self.assertEqual(os.path.dirname(os.path.dirname(out)),
                         os.path.dirname(os.path.abspath(self.MODEL)))

    def test_kind_adds_one_level(self):
        out = validation_dir(self.MODEL, kind="moment_arm_change")
        self.assertEqual(os.path.basename(out), "moment_arm_change")
        self.assertEqual(os.path.basename(os.path.dirname(out)), "scaled_opt_N10")

    def test_two_models_in_one_iteration_do_not_collide(self):
        so = validation_dir(self.MODEL.replace(".osim", "_mvicx3.00.osim"))
        self.assertNotEqual(validation_dir(self.MODEL), so)
        # they still share one validation/ parent
        self.assertEqual(os.path.dirname(so),
                         os.path.dirname(validation_dir(self.MODEL)))

    def test_explicit_out_always_wins(self):
        want = os.path.join(os.sep, "tmp", "elsewhere")
        self.assertEqual(validation_dir(self.MODEL, out=want), want)
        self.assertEqual(validation_dir(self.MODEL, kind="x", out=want), want)

    def test_relative_out_is_resolved_against_cwd(self):
        out = validation_dir(self.MODEL, out="rel_out")
        self.assertTrue(os.path.isabs(out))
        self.assertEqual(out, os.path.join(os.getcwd(), "rel_out"))

    def test_base_override(self):
        self.assertEqual(os.path.basename(validation_dir(self.MODEL, base="custom")),
                         "custom")

    def test_missing_file_is_fine(self):
        # the folder is computed, not discovered — the model need not exist yet
        self.assertTrue(validation_dir("/no/such/model.osim").endswith(
            os.path.join(VALIDATION_DIRNAME, "model")))

    def test_result_is_absolute_and_not_created(self):
        out = validation_dir("scaled.osim")
        self.assertTrue(os.path.isabs(out))
        self.assertFalse(os.path.exists(out))


class TestIsReportDir(unittest.TestCase):
    def test_current_and_legacy_names(self):
        for name in ("validation", "muscle_inspect_scaled_opt_N10",
                     "moment_arm_change_scaled_wrapfix"):
            self.assertTrue(is_report_dir(name), name)

    def test_models_and_trials_are_not_reports(self):
        for name in ("cateli", "Squat_BW_01", "scaled.osim", "ceinms_calibration",
                     "3_iterations", "Geometry"):
            self.assertFalse(is_report_dir(name), name)

    def test_accepts_a_path_or_a_trailing_separator(self):
        self.assertTrue(is_report_dir(os.path.join("a", "b", "validation")))
        self.assertTrue(is_report_dir("validation" + os.sep))


if __name__ == "__main__":
    unittest.main(verbosity=2)
