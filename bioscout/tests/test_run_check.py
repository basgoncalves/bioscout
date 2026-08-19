"""bioscout.tests.test_run_check — the anti-silent-failure toolbox.

Each test here pins ONE of the silent-failure traps from
docs/IMPLEMENTATIONS.md §1. They are the class of bug that produces no error,
so a regression would also produce no error — only these tests would notice.

Standard library only; run_check is imported by file path with a stubbed
parent package so the suite also runs where bioscout.utils cannot import
(the scipy-at-import issue, utils-init-scipy-block).
"""
import importlib.util
import os
import shutil
import sys
import tempfile
import types
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_MOD = os.path.join(_HERE, "..", "utils", "run_check.py")

try:
    _spec = importlib.util.spec_from_file_location("run_check", _MOD)
    rc = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(rc)
    HAVE = True
except Exception:                                              # noqa: BLE001
    HAVE = False


@unittest.skipUnless(HAVE, "run_check.py not found")
class TestDuplicateYamlKeys(unittest.TestCase):
    def test_true_duplicate_in_one_scope(self):
        y = "trials:\n  A:\n    type: x\n  B:\n    type: y\n  A:\n    type: z\n"
        d = rc.duplicate_yaml_keys(y)
        self.assertEqual(d, [("A", 2, 6)])

    def test_same_key_in_sibling_scopes_is_fine(self):
        # emg_map: {m1: {Voltage_1: ...}, m2: {Voltage_1: ...}} — legal
        y = ("emg_map:\n  m1:\n    Voltage_1: [vasmed]\n"
             "  m2:\n    Voltage_1: [vaslat]\n")
        self.assertEqual(rc.duplicate_yaml_keys(y), [])

    def test_top_level_duplicate(self):
        y = "subject: a\nbody_mass: 60\nsubject: b\n"
        self.assertEqual(rc.duplicate_yaml_keys(y), [("subject", 1, 3)])

    def test_comments_and_blanks_ignored(self):
        y = "# subject: x\nsubject: a\n\n# subject: y\n"
        self.assertEqual(rc.duplicate_yaml_keys(y), [])

    def test_sequence_items_open_fresh_scopes(self):
        y = "trials:\n  - name: a\n    side: r\n  - name: b\n    side: l\n"
        self.assertEqual(rc.duplicate_yaml_keys(y), [])


@unittest.skipUnless(HAVE, "run_check.py not found")
class TestValidateEmgMap(unittest.TestCase):
    def test_missing_channel_fails(self):
        v = rc.validate_emg_map(["Voltage_9"], ["Voltage_1"])
        self.assertFalse(v["ok"])
        self.assertEqual(v["missing"], ["Voltage_9"])

    def test_bare_vs_tagged_is_suspicious_not_missing(self):
        # THE trap: both columns exist, the map keys the raw one — this must
        # warn (suspicious) while still validating, because only the rig's
        # owner knows which column is the conditioned signal.
        v = rc.validate_emg_map(["Voltage_1"],
                                ["Voltage_1", "Voltage_1-VM", "Voltage_2"])
        self.assertTrue(v["ok"])
        self.assertEqual(v["suspicious"], [("Voltage_1", "Voltage_1-VM")])

    def test_exact_match_is_clean(self):
        v = rc.validate_emg_map(["Voltage_1-VM"],
                                ["Voltage_1-VM", "Voltage_2-RF"])
        self.assertTrue(v["ok"])
        self.assertEqual(v["suspicious"], [])

    def test_prefix_of_unrelated_name_not_flagged(self):
        # "Volt" is not a bare twin of "Voltage_1" — the separator rule
        v = rc.validate_emg_map(["Voltage_1"], ["Voltage_1", "Voltage_10"])
        self.assertEqual(v["suspicious"], [])


@unittest.skipUnless(HAVE, "run_check.py not found")
class TestVerifyRun(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.mkdtemp(prefix="bs_rc_")
        self.it = os.path.join(self.t, "raj")
        self.exp = os.path.join(self.t, "2_experimental")

    def tearDown(self):
        shutil.rmtree(self.t, ignore_errors=True)

    def _touch(self, *parts):
        p = os.path.join(*parts)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").close()

    def test_missing_output_fails_the_report(self):
        self._touch(self.it, "T1", "static_optimisation", "x_force.sto")
        self._touch(self.exp, "T1", "marker_experimental.trc")
        os.makedirs(os.path.join(self.it, "T2"))
        r = rc.verify_run(self.it, ["T1", "T2"], ["export", "so"],
                          experimental_dir=self.exp)
        self.assertFalse(r["ok"])
        self.assertEqual(sorted(r["missing"]),
                         [("T2", "export"), ("T2", "so")])
        self.assertTrue(r["trials"]["T1"]["so"])

    def test_all_ok(self):
        self._touch(self.it, "T1", "external_biomechanics",
                    "joint_angles.mot")
        r = rc.verify_run(self.it, ["T1"], ["exbiomec"])
        self.assertTrue(r["ok"])

    def test_ceinms_glob_matches_execution_folders(self):
        self._touch(self.it, "T1", "ceinms", "Execution_a10_b1_g1000",
                    "MuscleForces.sto")
        r = rc.verify_run(self.it, ["T1"], ["ceinms"])
        self.assertTrue(r["ok"])

    def test_report_roundtrip_and_table(self):
        self._touch(self.it, "T1", "static_optimisation", "f_force.sto")
        r = rc.verify_run(self.it, ["T1"], ["so"])
        lines = rc.format_report(r)
        self.assertTrue(any("ok" in l for l in lines))
        out = rc.write_report(r, os.path.join(self.t, "run_report.json"))
        self.assertTrue(out and os.path.isfile(out))
        import json
        data = json.load(open(out))
        self.assertTrue(data["ok"])

    def test_unknown_stage_ignored(self):
        r = rc.verify_run(self.it, ["T1"], ["so", "nonsense"])
        self.assertEqual(r["stages"], ["so"])


@unittest.skipUnless(HAVE, "run_check.py not found")
class TestLongPaths(unittest.TestCase):
    def test_flags_paths_near_the_limit(self):
        t = tempfile.mkdtemp(prefix="bs_rc_")
        try:
            deep = os.path.join(t, "x" * 60, "y" * 60, "z" * 60)
            os.makedirs(deep)
            open(os.path.join(deep, "f.sto"), "w").close()
            limit = len(t) + 120                 # force a hit regardless of tmp
            hits = rc.long_paths(t, limit=limit, headroom=40)
            self.assertTrue(hits)
            self.assertGreaterEqual(hits[0][0], hits[-1][0])   # sorted desc
            short = rc.long_paths(t, limit=10_000)
            self.assertEqual(short, [])
        finally:
            shutil.rmtree(t, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
