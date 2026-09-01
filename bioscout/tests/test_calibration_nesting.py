"""bioscout.tests.test_calibration_nesting — `calibration:` belongs under `ceinms:`.

2026-08-24. The calibration parameter bounds are CEINMS's and nothing else
reads them, but they sat at the TOP LEVEL of session.yaml next to `subject` and
`body_mass` as though they were session facts — while `ceinms.alpha/beta/gamma`
were already nested. `ceinms.calibration` is now canonical.

The top-level spelling still loads: a reader that refused it could not be used
to migrate the files that need migrating. It is deprecated, and
`migrate_calibration_block` rewrites it in place.

What these tests pin:

* nested wins over top-level, with NO merging — two blocks that disagree must
  not quietly produce bounds nobody wrote;
* `default_calibration` follows its block, so a nested block is never selected
  from by a top-level selector;
* migration is behaviour-preserving (same config chosen, same bounds resolved,
  per iteration), idempotent, and surgical — comments and key order survive,
  because these files carry hand-written notes explaining why a bound is what
  it is.

Standard library + PyYAML only; session.py is imported by file path with a
stubbed parent package so this runs where `bioscout.utils` cannot
(utils-init-scipy-block).
"""
import importlib.util
import os
import sys
import tempfile
import textwrap
import types
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.normpath(os.path.join(_HERE, ".."))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_PKG, rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


try:
    if "bioscout.utils.session" in sys.modules:
        S = sys.modules["bioscout.utils.session"]
    else:
        _pkg = types.ModuleType("bioscout")
        _pkg.__path__ = [_PKG]
        _u = types.ModuleType("bioscout.utils")
        _u.__path__ = [os.path.join(_PKG, "utils")]
        sys.modules.setdefault("bioscout", _pkg)
        sys.modules.setdefault("bioscout.utils", _u)
        _u.file_edit = _load("bioscout.utils.file_edit", "utils/file_edit.py")
        S = _load("bioscout.utils.session", "utils/session.py")
        _u.session = S
    import yaml
    HAVE = True
except Exception:                                              # noqa: BLE001
    HAVE = False

LEGACY = textwrap.dedent("""\
    subject: Athlete_03
    body_mass: 89.9
    ceinms:
      alpha: 1
      beta: 1
      gamma: 30

    # Why these bounds: t23/t24 point here. `prod` is kept for the control.
    default_calibration: prod
    calibration:
      prod:
        optimalFiberLength: "0.5 3"
        learningRate: 0.02
      lit:
        optimalFiberLength: "0.75 1.25"
        learningRate: 0.005
    iterations:
      cateli:
        generic: Catelli.osim
        calibration: lit
      gpk:
        generic: gpk.osim
    """)


@unittest.skipUnless(HAVE, "session.py / PyYAML not importable")
class TestNestedWins(unittest.TestCase):
    def test_nested_is_read(self):
        cfg = yaml.safe_load(LEGACY)
        cfg["ceinms"]["calibration"] = {"only": {"optimalFiberLength": "1 1"}}
        self.assertEqual(sorted(S.calibration_configs(cfg)), ["only"])

    def test_nested_does_not_merge_with_top_level(self):
        """The failure mode worth a test: bounds nobody wrote."""
        cfg = yaml.safe_load(LEGACY)
        cfg["ceinms"]["calibration"] = {"prod": {"optimalFiberLength": "9 9"}}
        blocks = S.calibration_configs(cfg)
        self.assertEqual(sorted(blocks), ["prod"])          # not prod + lit
        self.assertEqual(blocks["prod"]["optimalFiberLength"], "9 9")
        self.assertNotIn("learningRate", blocks["prod"])

    def test_default_follows_its_block(self):
        cfg = yaml.safe_load(LEGACY)
        cfg["ceinms"]["calibration"] = {"a": {"optimalFiberLength": "1 1"},
                                        "b": {"optimalFiberLength": "2 2"}}
        cfg["ceinms"]["default_calibration"] = "b"
        # top-level default_calibration is still 'prod', which is not in the
        # nested block — the nested selector must win, not raise.
        self.assertEqual(S.calibration_name_for(cfg, "gpk"), "b")

    def test_legacy_still_loads(self):
        cfg = yaml.safe_load(LEGACY)
        self.assertTrue(S.uses_legacy_calibration(cfg))
        self.assertEqual(sorted(S.calibration_configs(cfg)), ["lit", "prod"])
        self.assertEqual(S.calibration_name_for(cfg, "cateli"), "lit")
        self.assertEqual(S.calibration_name_for(cfg, "gpk"), "prod")


@unittest.skipUnless(HAVE, "session.py / PyYAML not importable")
class TestMigration(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "session.yaml")
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(LEGACY)

    def _cfg(self):
        with open(self.path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def test_moves_and_preserves_behaviour(self):
        before = self._cfg()
        names_before = {it: S.calibration_name_for(before, it)
                        for it in before["iterations"]}
        bounds_before = {it: S.resolve_calibration(before, it)
                         for it in before["iterations"]}

        changed, _note = S.migrate_calibration_block(self.path)
        self.assertTrue(changed)

        after = self._cfg()
        self.assertNotIn("calibration", after)
        self.assertNotIn("default_calibration", after)
        self.assertIn("calibration", after["ceinms"])
        self.assertEqual(after["ceinms"]["default_calibration"], "prod")
        self.assertFalse(S.uses_legacy_calibration(after))

        self.assertEqual(
            names_before,
            {it: S.calibration_name_for(after, it) for it in after["iterations"]})
        self.assertEqual(
            bounds_before,
            {it: S.resolve_calibration(after, it) for it in after["iterations"]})

    def test_alpha_beta_gamma_untouched(self):
        S.migrate_calibration_block(self.path)
        ce = self._cfg()["ceinms"]
        self.assertEqual((ce["alpha"], ce["beta"], ce["gamma"]), (1, 1, 30))

    def test_idempotent(self):
        self.assertTrue(S.migrate_calibration_block(self.path)[0])
        again, note = S.migrate_calibration_block(self.path)
        self.assertFalse(again)
        self.assertIn("already nested", note)

    def test_comments_and_other_keys_survive(self):
        """Surgical, not a safe_load/dump round trip.

        These files carry hand-written notes next to the bounds; re-dumping
        would delete every one of them silently.
        """
        S.migrate_calibration_block(self.path)
        with open(self.path, "r", encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("# Why these bounds: t23/t24 point here.", text)
        self.assertIn("subject: Athlete_03", text)
        self.assertIn("generic: Catelli.osim", text)

    def test_reports_orphaned_comments(self):
        """A comment above a moved key stays put — it must SAY so.

        Nothing is lost, but a paragraph explaining a bound now sits above
        whatever follows it, and a migration that does not mention that is
        quietly misleading.
        """
        _changed, note = S.migrate_calibration_block(self.path)
        self.assertIn("comment line(s)", note)

    def test_dry_run_writes_nothing(self):
        before = open(self.path, encoding="utf-8").read()
        changed, diff = S.migrate_calibration_block(self.path, apply=False)
        self.assertTrue(changed)
        self.assertEqual(open(self.path, encoding="utf-8").read(), before)
        self.assertTrue(diff)

    def test_already_nested_file_untouched(self):
        S.migrate_calibration_block(self.path)
        text = open(self.path, encoding="utf-8").read()
        S.migrate_calibration_block(self.path)
        self.assertEqual(open(self.path, encoding="utf-8").read(), text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
