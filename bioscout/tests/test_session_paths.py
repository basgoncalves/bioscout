"""Tests for :mod:`bioscout.utils.session_paths`.

The case that motivated the module is :meth:`TestRealFaisLayout` — a value that
resolves against a base other than the one it was written for. That is not an
exception, it is a wrong file read successfully, so the test asserts on
``.base`` and ``.preferred``, not just on truthiness.

Stdlib only.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from bioscout.utils.session_paths import BASES, Resolved, report, resolve, resolve_all


class _Project(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bioscout_paths_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.proj = self.tmp / "FAIS"
        self.sess = self.proj / "simulations" / "022" / "pre"
        self.iter_dir = self.sess / "3_iterations" / "rajagopal_fai"
        for d in (self.sess / "1_c3dfiles", self.iter_dir,
                  self.proj / "models", self.proj / "generic models",
                  self.proj / "setup_files", self.proj / "c3d_files" / "022"):
            d.mkdir(parents=True, exist_ok=True)

    def touch(self, *parts) -> Path:
        p = self.tmp.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
        return p

    def r(self, key, raw, **kw):
        kw.setdefault("session_dir", self.sess)
        kw.setdefault("project_dir", self.proj)
        kw.setdefault("iteration_dir", self.iter_dir)
        return resolve(key, raw, **kw)


class TestBases(_Project):
    def test_project_scoped_key(self):
        self.touch("FAIS", "setup_files", "setup_IK.xml")
        got = self.r("setup_folder", "setup_files")
        self.assertTrue(got.ok)
        self.assertEqual(got.base, "project")
        self.assertTrue(got.preferred)
        self.assertIsNone(got.note())

    def test_session_scoped_key(self):
        self.touch("FAIS", "simulations", "022", "pre", "raw", "x.c3d")
        got = self.r("c3d_source", "raw")
        self.assertEqual(got.base, "session")
        self.assertTrue(got.preferred)

    def test_model_search_prefers_the_iteration_folder(self):
        self.touch("FAIS", "models", "022.osim")
        self.touch("FAIS", "simulations", "022", "pre", "3_iterations",
                   "rajagopal_fai", "022.osim")
        got = self.r("so_model", "022.osim")
        self.assertEqual(got.base, "iteration")
        self.assertTrue(str(got.path).endswith(str(Path("rajagopal_fai") / "022.osim")))

    def test_model_falls_back_to_models_dir(self):
        self.touch("FAIS", "models", "022.osim")
        got = self.r("so_model", "022.osim")
        self.assertEqual(got.base, "models")
        self.assertTrue(got.ok)
        self.assertFalse(got.preferred)          # found, but not where expected

    def test_generic_prefers_generic_models(self):
        self.touch("FAIS", "models", "Raja.osim")
        self.touch("FAIS", "generic models", "Raja.osim")
        self.assertEqual(self.r("generic", "Raja.osim").base, "generic_models")

    def test_absolute_path_is_used_as_is(self):
        target = self.touch("elsewhere", "markers.xml")
        got = self.r("markerset", str(target))
        self.assertEqual(got.base, "absolute")
        self.assertTrue(got.ok)

    def test_absolute_path_that_is_missing(self):
        got = self.r("markerset", str(self.tmp / "nope" / "markers.xml"))
        self.assertFalse(got.ok)
        self.assertIn("not found", got.note())

    def test_windows_separators(self):
        self.touch("FAIS", "setup_files", "markers_FAIS.xml")
        got = self.r("markerset", r"setup_files\markers_FAIS.xml")
        self.assertTrue(got.ok)
        self.assertEqual(got.base, "project")

    def test_unknown_key_uses_the_default_order(self):
        self.touch("FAIS", "thing.txt")
        got = self.r("some_new_key", "thing.txt")
        self.assertEqual(got.base, "project")

    def test_missing_points_at_the_intended_location(self):
        got = self.r("setup_folder", "setup_files_typo")
        self.assertFalse(got.ok)
        self.assertEqual(got.base, "project", "should name where it SHOULD be")
        self.assertIn("not found", got.note())

    def test_empty_value_is_not_an_error(self):
        got = self.r("c3d_source", None)
        self.assertFalse(got.ok)
        self.assertIsNone(got.path)


class TestRealFaisLayout(_Project):
    """The value that started this: session-relative, resolved project-relative."""

    def test_session_relative_c3d_source_now_resolves(self):
        self.touch("FAIS", "c3d_files", "022", "trial.c3d")
        got = self.r("c3d_source", "../../../c3d_files/022")
        self.assertTrue(got.ok, "the FAIS value must resolve")
        self.assertEqual(got.base, "session")
        self.assertEqual(got.path, (self.proj / "c3d_files" / "022").resolve())

    def test_project_relative_form_also_resolves_but_is_flagged(self):
        """`c3d_files/022` is project-relative; it works, and it says so."""
        self.touch("FAIS", "c3d_files", "022", "trial.c3d")
        got = self.r("c3d_source", "c3d_files/022")
        self.assertTrue(got.ok)
        self.assertEqual(got.base, "project")
        self.assertFalse(got.preferred)
        self.assertIn("session-relative", got.note())

    def test_markerset_no_longer_needs_the_model_resolver(self):
        """It used to land right only because the model search ended at the project."""
        self.touch("FAIS", "setup_files", "markers_FAIS.xml")
        got = self.r("markerset", "setup_files/markers_FAIS.xml")
        self.assertEqual(got.base, "project")
        self.assertTrue(got.preferred)

    def test_project_can_be_inferred_from_the_session(self):
        self.touch("FAIS", "c3d_files", "022", "trial.c3d")
        got = resolve("c3d_source", "../../../c3d_files/022", session_dir=self.sess)
        self.assertTrue(got.ok)


class TestResolveAll(_Project):
    def cfg(self):
        return {
            "c3d_source": "../../../c3d_files/022",
            "setup_folder": "setup_files",
            "markerset": "setup_files/markers_FAIS.xml",
            "iterations": {
                "rajagopal_fai": {
                    "generic": "Rajagopal.osim",
                    "so_model": "022.osim",
                    "ceinms_model": "022.osim",
                },
            },
        }

    def test_every_path_key_is_checked(self):
        got = resolve_all(self.cfg(), self.sess, self.proj)
        keys = [r.key for r in got]
        self.assertIn("c3d_source", keys)
        self.assertIn("iterations.rajagopal_fai.so_model", keys)
        self.assertEqual(len([k for k in keys if k.startswith("iterations.")]), 3)

    def test_report_lists_missing_first(self):
        self.touch("FAIS", "setup_files", "markers_FAIS.xml")
        self.touch("FAIS", "c3d_files", "022", "t.c3d")
        lines = report(resolve_all(self.cfg(), self.sess, self.proj))
        self.assertTrue(lines)
        self.assertIn("not found", lines[0])

    def test_clean_project_reports_nothing(self):
        self.touch("FAIS", "setup_files", "markers_FAIS.xml")
        self.touch("FAIS", "setup_files", "keep.txt")
        self.touch("FAIS", "c3d_files", "022", "t.c3d")
        self.touch("FAIS", "generic models", "Rajagopal.osim")
        self.touch("FAIS", "simulations", "022", "pre", "3_iterations",
                   "rajagopal_fai", "022.osim")
        self.assertEqual(report(resolve_all(self.cfg(), self.sess, self.proj)), [])

    def test_one_iteration_can_be_scoped(self):
        cfg = self.cfg()
        cfg["iterations"]["mri_torsion"] = {"so_model": "022_mri.osim"}
        got = resolve_all(cfg, self.sess, self.proj, iteration="mri_torsion")
        self.assertEqual([r for r in got if r.key.startswith("iterations.")][0].key,
                         "iterations.mri_torsion.so_model")


if __name__ == "__main__":
    unittest.main(verbosity=2)
