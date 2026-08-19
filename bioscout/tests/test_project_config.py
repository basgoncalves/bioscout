"""bioscout.tests.test_project_config — project.yaml replaces settings.py.

Pins docs/IMPLEMENTATIONS.md §2.9 steps 1+2: the overlay precedence
(session.yaml -> project.yaml -> settings.py -> bioscout defaults) and the
`bioscout project init` extractor. The failure class here is silent again —
a lab fact that quietly does NOT apply just runs the pipeline with the wrong
electrode map — so each contract is pinned.

Standard library only at import; project_config is imported BY FILE PATH so
the suite runs where bioscout.utils cannot (utils-init-scipy-block). Tests
that parse/write real YAML skip when PyYAML is missing.
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import types
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "utils", "project_config.py")

try:
    _spec = importlib.util.spec_from_file_location("project_config", _MOD)
    pc = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(pc)
    HAVE = True
except Exception:                                              # noqa: BLE001
    HAVE = False

try:
    import yaml
    HAVE_YAML = True
except Exception:                                              # noqa: BLE001
    HAVE_YAML = False


def _ns_settings(**batch):
    """A minimal settings-like namespace with a BatchSettings class."""
    return types.SimpleNamespace(
        BatchSettings=type("BatchSettings", (), dict(batch)))


@unittest.skipUnless(HAVE, "project_config.py not found")
class TestFindProjectYaml(unittest.TestCase):
    def test_walks_up_from_a_session_folder(self):
        t = tempfile.mkdtemp(prefix="bs_pc_")
        try:
            deep = os.path.join(t, "simulations", "023", "pre")
            os.makedirs(deep)
            p = os.path.join(t, "project.yaml")
            open(p, "w").close()
            self.assertEqual(pc.find_project_yaml(deep), p)
        finally:
            shutil.rmtree(t, ignore_errors=True)

    def test_none_when_absent(self):
        t = tempfile.mkdtemp(prefix="bs_pc_")
        try:
            self.assertIsNone(pc.find_project_yaml(t))
        finally:
            shutil.rmtree(t, ignore_errors=True)


@unittest.skipUnless(HAVE, "project_config.py not found")
class TestApply(unittest.TestCase):
    def test_sections_land_on_the_right_classes(self):
        base = _ns_settings(emg_sampling_freq=1000)
        n = pc.apply(base, {"batch": {"emg_sampling_freq": 2000},
                            "ceinms": {"calibration_trial_names": ["SquatA1"]},
                            "log_type": "minimal"})
        self.assertEqual(n, 3)
        self.assertEqual(base.BatchSettings.emg_sampling_freq, 2000)
        # CEINMSSettings did not exist on the base -> created, not crashed
        self.assertEqual(base.CEINMSSettings.calibration_trial_names,
                         ["SquatA1"])
        self.assertEqual(base.LOG_TYPE, "minimal")

    def test_untouched_defaults_survive(self):
        base = _ns_settings(emg_sampling_freq=1000, MUSCLE_GROUPS={"a": ["x"]})
        pc.apply(base, {"batch": {"emg_sampling_freq": 2000}})
        self.assertEqual(base.BatchSettings.MUSCLE_GROUPS, {"a": ["x"]})


@unittest.skipUnless(HAVE, "project_config.py not found")
class TestExtract(unittest.TestCase):
    def test_only_deviations_from_the_baseline(self):
        baseline = _ns_settings(emg_sampling_freq=1000, dof_list=["knee"])
        proj = _ns_settings(emg_sampling_freq=2000, dof_list=["knee"])
        data = pc.extract(proj, baseline=baseline)
        self.assertEqual(data["batch"], {"emg_sampling_freq": 2000})

    def test_run_selection_and_paths_are_never_lab_facts(self):
        proj = _ns_settings(SUBJECTS=["021"], sessions=["pre"],
                            trial_list=["Run1"], replace_existing=True,
                            RUN_PIPELINE=True, DO_SO=True,
                            MODELS_DIR="C:/x", PROJECT_ROOT="C:/x",
                            emg_sampling_freq=2000)
        data = pc.extract(proj, baseline=_ns_settings())
        self.assertEqual(data.get("batch"), {"emg_sampling_freq": 2000})

    def test_shared_lab_fact_is_not_written_twice(self):
        """settings.py routinely sets CEINMSSettings.emg_muscle_mapping =
        BatchSettings.emg_muscle_mapping; a faithful extraction then wrote two
        identical 70-line blocks — the drift project.yaml exists to end."""
        m = {"EMG02": ["gasmed_l"]}
        proj = types.SimpleNamespace(
            BatchSettings=type("B", (), {"emg_muscle_mapping": m}),
            CEINMSSettings=type("C", (), {"emg_muscle_mapping": m,
                                          "alpha": 10}))
        data = pc.extract(proj, baseline=_ns_settings())
        self.assertIn("emg_muscle_mapping", data["batch"])
        self.assertNotIn("emg_muscle_mapping", data.get("ceinms") or {})
        self.assertEqual(data["ceinms"]["alpha"], 10)   # the rest survives
        base = _ns_settings()
        pc.apply(base, data)
        self.assertEqual(base.CEINMSSettings.emg_muscle_mapping, m)

    def test_a_genuinely_different_ceinms_value_is_kept_and_wins(self):
        m, other = {"A": ["x"]}, {"B": ["y"]}
        proj = types.SimpleNamespace(
            BatchSettings=type("B", (), {"emg_muscle_mapping": m}),
            CEINMSSettings=type("C", (), {"emg_muscle_mapping": other}))
        data = pc.extract(proj, baseline=_ns_settings())
        self.assertEqual(data["ceinms"]["emg_muscle_mapping"], other)
        base = _ns_settings()
        pc.apply(base, data)
        self.assertEqual(base.CEINMSSettings.emg_muscle_mapping, other)

    def test_code_is_never_extracted_and_tuples_become_lists(self):
        proj = _ns_settings(helper=lambda: 1, dofs=("hip", "knee"))
        data = pc.extract(proj, baseline=_ns_settings())
        self.assertEqual(data["batch"], {"dofs": ["hip", "knee"]})


@unittest.skipUnless(HAVE and HAVE_YAML, "needs project_config + PyYAML")
class TestInitRoundtrip(unittest.TestCase):
    def test_extract_write_load_apply(self):
        t = tempfile.mkdtemp(prefix="bs_pc_")
        try:
            with open(os.path.join(t, "settings.py"), "w") as fh:
                fh.write("class BatchSettings:\n"
                         "    emg_sampling_freq = 2000\n"
                         "    SUBJECTS = ['021']\n"
                         "class CEINMSSettings:\n"
                         "    calibration_trial_names = ['SquatA1']\n")
            code = pc.init_project_yaml(t, baseline=_ns_settings())
            self.assertEqual(code, 0)
            ypath = os.path.join(t, "project.yaml")
            self.assertTrue(os.path.isfile(ypath))
            # refuse to clobber without --force
            self.assertEqual(pc.init_project_yaml(t, baseline=_ns_settings()), 1)
            # the written file applies back exactly
            base = _ns_settings()
            n = pc.apply(base, pc._load_yaml(ypath))
            self.assertGreaterEqual(n, 2)
            self.assertEqual(base.BatchSettings.emg_sampling_freq, 2000)
            self.assertEqual(base.CEINMSSettings.calibration_trial_names,
                             ["SquatA1"])
            self.assertFalse(hasattr(base.BatchSettings, "SUBJECTS"))
        finally:
            shutil.rmtree(t, ignore_errors=True)


@unittest.skipUnless(HAVE, "project_config.py not found")
class TestOverlay(unittest.TestCase):
    def test_no_yaml_returns_base_unchanged(self):
        base = _ns_settings(emg_sampling_freq=1000)
        t = tempfile.mkdtemp(prefix="bs_pc_")
        try:
            out = pc.overlay(base, start=t)
            self.assertIs(out, base)
            self.assertEqual(out.BatchSettings.emg_sampling_freq, 1000)
        finally:
            shutil.rmtree(t, ignore_errors=True)

    @unittest.skipUnless(HAVE_YAML, "needs PyYAML")
    def test_yaml_wins_over_the_base(self):
        base = _ns_settings(emg_sampling_freq=1000)
        t = tempfile.mkdtemp(prefix="bs_pc_")
        try:
            with open(os.path.join(t, "project.yaml"), "w") as fh:
                fh.write("schema: 1\nbatch:\n  emg_sampling_freq: 2000\n")
            out = pc.overlay(base, start=t)
            self.assertEqual(out.BatchSettings.emg_sampling_freq, 2000)
        finally:
            shutil.rmtree(t, ignore_errors=True)

    def test_never_raises(self):
        t = tempfile.mkdtemp(prefix="bs_pc_")
        try:
            with open(os.path.join(t, "project.yaml"), "w") as fh:
                fh.write(":: not yaml at all {{{{")
            base = _ns_settings()
            self.assertIs(pc.overlay(base, start=t), base)
        finally:
            shutil.rmtree(t, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
