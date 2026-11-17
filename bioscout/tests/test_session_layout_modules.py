"""bioscout.session after the 2026-09-10 split and legacy removal.

* the old session.py shim, session.xml, Session.open/open_session and the
  MuscleAnalyser alias are gone;
* Session.add_iteration copies an iteration block in session.yaml, keeps the
  rest of the file (comments, line endings) and refuses bad input;
* an Iteration's attributes are its session.yaml keys (it.so_model,
  it.markerset ...); markerset lives per iteration; old key spellings warn;
* project-wide operations live on Project only.
"""
import os
import tempfile
import unittest
import warnings

YAML = (
    "subject: P01\r\n"
    "body_mass: 70\r\n"
    "# the arms of this session\r\n"
    "iterations:\r\n"
    "  gpk:\r\n"
    "    model_generic: ../../GPK/GPK.osim\r\n"
    "    model_scaled: ../../gpk_scaled.osim\r\n"
    "    label: Scaled (GPK)\r\n"
    "    color: firebrick\r\n"
    "  # keep me\r\n"
    "  cat:\r\n"
    "    model_generic: ../../Cat/Cat.osim\r\n"
    "trials:\r\n"
    "  Walk_01: {type: walking}\r\n"
)


class TestLegacyRemoved(unittest.TestCase):
    def test_gone(self):
        import importlib
        import bioscout as bs
        from bioscout.session import Session, Iteration
        for mod in ("bioscout.session.session", "bioscout.session.legacy"):
            with self.assertRaises(ImportError):
                importlib.import_module(mod)
        # the legacy Session.open(name) is gone; .open() now only opens
        # session.yaml in an editor (shared show/get/set/save/open API)
        from bioscout.session.config import _YamlEdit
        self.assertIs(Session.open, _YamlEdit.open)
        self.assertIs(Iteration.open, _YamlEdit.open)
        self.assertFalse(hasattr(Session, "prune_legacy_inputs"))
        import bioscout.session as _s
        with self.assertRaises(AttributeError):
            _s.open_session
        self.assertFalse(hasattr(bs.mew, "MuscleAnalyser"))
        from bioscout.session import config
        self.assertFalse(hasattr(config, "read_session_xml"))

    def test_package_level(self):
        import bioscout as bs
        from bioscout.session import Session, Iteration
        self.assertIs(bs.Session, Session)
        self.assertIs(bs.Iteration, Iteration)


class TestAddIteration(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="bs_addit_")
        self.yaml = os.path.join(self.dir, "session.yaml")
        with open(self.yaml, "wb") as fh:
            fh.write(YAML.encode())
        from bioscout.session.recording import Session
        self.s = Session(self.dir, bootstrap=False)
        self.cwd = os.getcwd()

    def tearDown(self):
        os.chdir(self.cwd)

    def test_copy_with_overrides(self):
        import yaml
        it = self.s.add_iteration("gpk_mri", copy_from="gpk",
                                  model_generic="../../GPK/GPK_mri.osim")
        self.assertTrue(os.path.isdir(it.path))
        with open(self.yaml) as fh:
            cfg = yaml.safe_load(fh)
        new = cfg["iterations"]["gpk_mri"]
        self.assertEqual(new["model_generic"], "../../GPK/GPK_mri.osim")
        self.assertEqual(new["model_scaled"], "../../gpk_mri_scaled.osim")  # not shared
        self.assertEqual(new["label"], "gpk_mri")
        self.assertEqual(new["color"], "firebrick")
        self.assertEqual(cfg["iterations"]["gpk"]["model_scaled"], "../../gpk_scaled.osim")
        self.assertEqual(list(cfg["iterations"]), ["gpk", "gpk_mri", "cat"])
        with open(self.yaml, "rb") as fh:
            raw = fh.read().decode()
        self.assertIn("# the arms of this session", raw)
        self.assertIn("# keep me", raw)
        self.assertEqual(raw.count("\r\n"), raw.count("\n"))          # CRLF kept
        self.assertIn("gpk_mri", self.s.iterations)

    def test_new_empty_iteration(self):
        import yaml
        it = self.s.add_iteration("fresh", model_generic="../../G/G.osim")
        with open(self.yaml) as fh:
            new = yaml.safe_load(fh)["iterations"]["fresh"]
        self.assertEqual(new["model_generic"], "../../G/G.osim")
        self.assertTrue(new["model_scaled"].endswith("models/personalised/"
                                                     + os.path.basename(os.path.dirname(self.dir))
                                                     + "/" + os.path.basename(self.dir)
                                                     + "/fresh_scaled.osim"))
        self.assertEqual(new["label"], "fresh")
        self.assertEqual(it.model_generic, os.path.normpath(os.path.join(self.dir, "G", "G.osim")))

    def test_new_iteration_in_a_file_without_iterations(self):
        import yaml
        with open(self.yaml, "wb") as fh:
            fh.write(b"subject: P01\r\ntrials:\r\n  Walk_01: {type: walking}\r\n")
        from bioscout.session.recording import Session
        s = Session(self.dir, bootstrap=False)
        s.add_iteration("gpk")
        with open(self.yaml) as fh:
            d = yaml.safe_load(fh)
        self.assertEqual(list(d["iterations"]), ["gpk"])
        self.assertIn("Walk_01", d["trials"])

    def test_refusals_leave_the_file_alone(self):
        def _read():
            with open(self.yaml, "rb") as fh:
                return fh.read()
        before = _read()
        for kw in (dict(name="gpk", copy_from="cat"), dict(name="GPK", copy_from="cat"),
                   dict(name="bad name", copy_from="gpk"), dict(name="new", copy_from="nope")):
            with self.assertRaises((ValueError, KeyError)):
                self.s.add_iteration(**kw)
        self.assertEqual(_read(), before)


class TestProjectWide(unittest.TestCase):
    def test_moved_to_project(self):
        from bioscout.core.analysis import Project
        for name in ("sessions", "run", "reset"):
            self.assertTrue(callable(getattr(Project, name)))

    def test_old_names_are_gone(self):
        from bioscout.session.recording import Session
        for name in ("batch_sessions", "reset_project"):
            self.assertFalse(hasattr(Session, name))


# iteration folder = <tmp>/3_iterations/<name>, so the session folder is ../..
ITER_YAML = """\
subject: P01
project_dir: .
body_mass: 70
static_trial: Static_01
markerset: setup/markers.xml
iterations:
  gpk:
    model_generic: ../../GPK/GPK.osim
    model_scaled: ../../gpk_scaled.osim
    muscle_opt: false
    mvic_factor: 2.0
    label: Scaled (GPK)
  old:
    generic: Old/Old.osim
    so_model: old_x.osim
    ceinms_model: old_x.osim
    markerset: setup/other.xml
    prescaled: true
    typo_key: 1
trials:
  Static_01: {type: static}
  Walk_01: {type: walking, time_range: [0.1, 1.0]}
"""


class TestIterationKeys(unittest.TestCase):
    """One scaled model per iteration; it.<key> is iterations.<name>.<key>;
    file keys are relative to the iteration folder."""

    def _session(self):
        import contextlib
        import io
        from bioscout.session.recording import Session
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            s = Session(self.dir, bootstrap=False)
        return s, buf.getvalue()

    def setUp(self):
        import time
        self.dir = tempfile.mkdtemp(prefix="bs_itkeys_")
        with open(os.path.join(self.dir, "session.yaml"), "w") as fh:
            fh.write(ITER_YAML)
        for sub in ("setup", "GPK", "Old"):
            os.makedirs(os.path.join(self.dir, sub), exist_ok=True)
        for rel in ("setup/markers.xml", "setup/other.xml", "GPK/GPK.osim",
                    "gpk_scaled.osim", "old_x.osim"):
            open(os.path.join(self.dir, rel), "w").close()
        time.sleep(0.01)
        open(os.path.join(self.dir, "gpk_scaled_mvicx2.00.osim"), "w").close()  # newer
        from bioscout.session import config
        config._WARNED.clear()
        self.s, self.out = self._session()
        self.gpk = self.s.iteration("gpk")
        self.old = self.s.iteration("old")

    def p(self, rel):
        return os.path.normpath(os.path.join(self.dir, rel))

    def test_attributes_match_yaml(self):
        it = self.gpk
        self.assertEqual(it.label, "Scaled (GPK)")
        self.assertEqual(it.tag, f"{os.path.basename(self.dir)}/gpk")
        self.assertFalse(it.muscle_opt)
        self.assertEqual(it.mvic_factor, 2.0)
        self.assertTrue(it.linear_scaling)             # default
        self.assertEqual(it.static_trial, "Static_01")  # from the session
        self.assertEqual(it.model_generic, self.p("GPK/GPK.osim"))
        self.assertEqual(it.model_scaled, self.p("gpk_scaled.osim"))
        self.assertEqual(it.model_so, self.p("gpk_scaled_mvicx2.00.osim"))   # derived
        self.assertEqual(it.config["model_scaled"], "../../gpk_scaled.osim")
        self.assertEqual(it.relpath(it.model_scaled), "../../gpk_scaled.osim")

    def test_one_model_for_every_stage(self):
        self.assertEqual(self.gpk.model_file("CEINMS"), self.gpk.model_scaled)
        self.assertEqual(self.gpk.model_file("SO"), self.gpk.model_so)
        cfg = self.gpk.trial_config("Walk_01")
        for gone in ("model_dir", "so_model", "ceinms_model"):
            self.assertNotIn(gone, cfg)
        self.assertEqual(cfg["model_scaled"], self.gpk.model_scaled)

    def test_markerset_per_iteration_and_old_paths_found_with_warning(self):
        import contextlib
        import io
        self.assertIn("markerset", self.out)             # moved-in warning
        self.assertIn("iterations.gpk", self.out)
        self.assertNotIn("markerset", self.s._cfg)
        from bioscout.session import config
        config._WARNED.clear()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):            # resolved when the iteration is read
            ms = self.s.iteration("gpk").markerset       # 'setup/markers.xml': old style
        self.assertEqual(ms, self.p("setup/markers.xml"))
        self.assertIn("not relative to the iteration folder", buf.getvalue())
        self.assertIn("`markerset: ../../setup/markers.xml`", buf.getvalue())

    def test_old_spellings_collapse_to_one_model(self):
        cfg = self.old.config
        self.assertEqual(cfg["model_scaled"], "old_x.osim")
        self.assertEqual(cfg["model_generic"], "Old/Old.osim")
        for gone in ("so_model", "ceinms_model", "generic", "prescaled"):
            self.assertNotIn(gone, cfg)
        self.assertIn("`model_scaled`", self.out)
        self.assertIn("iterations.old.prescaled", self.out)
        self.assertIn("is gone", self.out)
        self.assertIn("typo_key", self.out)

    def test_two_different_models_are_refused(self):
        with open(os.path.join(self.dir, "session.yaml")) as fh:
            txt = fh.read()
        with open(os.path.join(self.dir, "session.yaml"), "w") as fh:
            fh.write(txt.replace("ceinms_model: old_x.osim", "ceinms_model: other.osim"))
        with self.assertRaisesRegex(ValueError, "two iterations"):
            self._session()

    def test_session_keys_and_source_lines(self):
        self.assertEqual(self.s.body_mass, 70.0)
        self.assertEqual(self.s.static_trial, "Static_01")
        self.assertEqual(self.s.subject, "P01")
        self.assertIn("Walk_01", self.s.trials)
        self.assertTrue(self.s.source("body_mass").endswith("session.yaml:3"))
        self.assertTrue(self.s.source("trials.Walk_01").endswith(":22"))
        self.assertTrue(self.gpk.source("mvic_factor").endswith(":11"))
        self.assertTrue(self.gpk.source().endswith(":7"))

    def test_keys_are_one_list_in_config(self):
        import inspect
        from bioscout.session import config
        from bioscout.session.recording import Session
        from bioscout.session.iteration import Iteration
        self.assertIn("body_mass", config.SESSION_KEYS)
        self.assertEqual(list(config.ITERATION_KEYS)[:3],
                         ["model_generic", "model_scaled", "markerset"])
        for cls in (Session, Iteration):                 # defined once, in config.py
            owner = next(k for k in cls.__mro__ if "__annotations__" in k.__dict__
                         and k.__module__ == config.__name__)
            self.assertTrue(inspect.getsourcefile(owner).endswith("config.py"))

    def test_any_top_level_key_is_an_attribute(self):
        with open(os.path.join(self.dir, "session.yaml")) as fh:
            txt = fh.read()
        with open(os.path.join(self.dir, "session.yaml"), "w") as fh:
            fh.write("implanted_side: l\n" + txt)
        s, _ = self._session()
        self.assertEqual(s.implanted_side, "l")
        self.assertEqual(s.measured_side, "l")      # old name still read
        with self.assertRaisesRegex(AttributeError, "no top-level key 'nope'"):
            s.nope

    def test_project_dir(self):
        self.assertEqual(self.s.project_dir, os.path.abspath(self.dir))
        self.assertEqual(self.gpk._project_dir(), os.path.abspath(self.dir))

    def test_describe(self):
        lines = []
        self.s.describe(log=lines.append)
        text = "\n".join(lines)
        for want in ("project_dir", "iteration 'gpk'", "model_scaled", "model_so",
                     "model_generic", "Walk_01"):
            self.assertIn(want, text)

    def test_reader_writer_use_the_same_keys(self):
        import yaml
        from bioscout.session import config
        spec = config.read_session_yaml(self.dir)
        self.assertIsNone(spec.markerset)
        self.assertEqual(spec.project_dir, ".")
        out = os.path.join(self.dir, "rt.yaml")
        config.write_session_yaml(spec, out)
        with open(out) as fh:
            d = yaml.safe_load(fh)
        self.assertNotIn("markerset", d)
        self.assertEqual(d["project_dir"], ".")
        g = d["iterations"]["gpk"]
        self.assertEqual(g["model_generic"], "../../GPK/GPK.osim")
        self.assertEqual(g["model_scaled"], "../../gpk_scaled.osim")
        self.assertEqual(g["markerset"], "setup/markers.xml")
        self.assertIs(g["muscle_opt"], False)

    def test_migrate_rewrites_the_file(self):
        import contextlib
        import io
        import yaml
        with contextlib.redirect_stdout(io.StringIO()):
            self.s.migrate()
        with open(os.path.join(self.dir, "session.yaml")) as fh:
            d = yaml.safe_load(fh)
        self.assertNotIn("markerset", d)
        g, o = d["iterations"]["gpk"], d["iterations"]["old"]
        self.assertEqual(g["markerset"], "../../setup/markers.xml")
        self.assertEqual(o["model_scaled"], "../../old_x.osim")
        self.assertEqual(o["markerset"], "../../setup/other.xml")
        self.assertEqual(o["model_generic"], "Old/Old.osim")      # missing: kept as is
        self.assertNotIn("so_model", o)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "session.yaml.bak")))
        from bioscout.session import config
        config._WARNED.clear()
        s2, out = self._session()
        self.assertNotIn("markerset:` is set for the whole session", out)
        self.assertEqual(s2.iteration("old").model_scaled, self.p("old_x.osim"))


class TestIterationPathCase(unittest.TestCase):
    """layout.iteration_path on a case-INsensitive filesystem (Windows).

    A session holding a ``GPK/`` folder of model files made ``isdir(<session>/gpk)``
    True on Windows, so iteration ``gpk`` resolved to the model folder and every
    iteration-relative path was one level off (TestIterationKeys failed on
    Windows only, 2026-09-11). os.path.isdir is patched case-insensitive so
    this runs the Windows behaviour on any OS."""

    def setUp(self):
        from unittest import mock
        from bioscout.session import layout
        self.layout = layout
        self.dir = tempfile.mkdtemp(prefix="bs_itcase_")
        real_isdir = os.path.isdir

        def isdir_nocase(p):
            p = os.path.normpath(p)
            parent, name = os.path.split(p)
            try:
                return any(n.lower() == name.lower() and real_isdir(os.path.join(parent, n))
                           for n in os.listdir(parent))
            except OSError:
                return False
        patcher = mock.patch.object(layout.os.path, "isdir", isdir_nocase)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_other_case_folder_is_not_the_iteration(self):
        os.makedirs(os.path.join(self.dir, "GPK"))
        self.assertEqual(self.layout.iteration_path(self.dir, "gpk"),
                         os.path.join(self.dir, "3_iterations", "gpk"))

    def test_exact_flat_iteration_still_found(self):
        os.makedirs(os.path.join(self.dir, "gpk"))
        self.assertEqual(self.layout.iteration_path(self.dir, "gpk"),
                         os.path.join(self.dir, "gpk"))

    def test_shared_folder_is_never_an_iteration(self):
        os.makedirs(os.path.join(self.dir, "models"))
        self.assertEqual(self.layout.iteration_path(self.dir, "models"),
                         os.path.join(self.dir, "3_iterations", "models"))

    def test_numbered_layout_wins(self):
        os.makedirs(os.path.join(self.dir, "3_iterations", "gpk"))
        os.makedirs(os.path.join(self.dir, "gpk"))
        self.assertEqual(self.layout.iteration_path(self.dir, "gpk"),
                         os.path.join(self.dir, "3_iterations", "gpk"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
