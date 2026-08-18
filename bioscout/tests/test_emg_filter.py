"""Tests for :mod:`bioscout.utils.emg_filter`.

The load-bearing test is :meth:`TestDefaults.test_defaults_match_the_old_hardcoded_values`:
adding a config block must not silently change any result computed before it
existed. Everything else is precedence.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from bioscout.utils.emg_filter import (DEFAULTS, describe, from_session_dir,
                                       session_config_near, settings_for,
                                       to_filter_kwargs)


class _Batch:
    """Stand-in for settings.BatchSettings."""
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class TestDefaults(unittest.TestCase):
    def test_defaults_match_the_old_hardcoded_values(self):
        """emg_normalise.filter_emg's signature, before this module existed."""
        s = settings_for()
        self.assertEqual(s["bandpass_low"], 20.0)
        self.assertEqual(s["bandpass_high"], 95.0)
        self.assertEqual(s["bandpass_order"], 4)
        self.assertEqual(s["envelope_lowpass"], 6.0)
        self.assertEqual(s["envelope_order"], 4)
        self.assertIsNone(s["sampling_freq"])

    def test_filter_kwargs_map_onto_the_real_signature(self):
        kw = to_filter_kwargs(settings_for())
        self.assertEqual(kw, {"lowcut_bp": 20.0, "highcut_bp": 95.0, "order_bp": 4,
                              "lowcut_lp": 6.0, "order_lp": 4})

    def test_empty_session_config_changes_nothing(self):
        self.assertEqual(settings_for({}), dict(DEFAULTS))
        self.assertEqual(settings_for({"emg_filter": None}), dict(DEFAULTS))

    def test_describe_names_every_value(self):
        text = describe(settings_for())
        for token in ("20", "95", "6", "order 4"):
            self.assertIn(token, text)


class TestPrecedence(unittest.TestCase):
    def test_batch_settings_still_work(self):
        s = settings_for({}, _Batch(emg_envelope_lowpass_hz=10.0, emg_sampling_freq=2000))
        self.assertEqual(s["envelope_lowpass"], 10.0)
        self.assertEqual(s["sampling_freq"], 2000.0)

    def test_session_yaml_beats_batch_settings(self):
        s = settings_for({"emg_filter": {"envelope_lowpass": 4.0}},
                         _Batch(emg_envelope_lowpass_hz=10.0))
        self.assertEqual(s["envelope_lowpass"], 4.0)

    def test_session_yaml_sets_the_bandpass_that_was_unreachable(self):
        s = settings_for({"emg_filter": {"bandpass_low": 30, "bandpass_high": 300,
                                         "bandpass_order": 2}})
        self.assertEqual((s["bandpass_low"], s["bandpass_high"], s["bandpass_order"]),
                         (30.0, 300.0, 2))

    def test_partial_block_leaves_the_rest_at_defaults(self):
        s = settings_for({"emg_filter": {"bandpass_high": 400}})
        self.assertEqual(s["bandpass_high"], 400.0)
        self.assertEqual(s["bandpass_low"], DEFAULTS["bandpass_low"])
        self.assertEqual(s["envelope_order"], DEFAULTS["envelope_order"])

    def test_filter_emg_parameter_names_are_accepted(self):
        """So the block can be written straight from the function signature."""
        s = settings_for({"emg_filter": {"lowcut_bp": 25, "highcut_bp": 400,
                                         "order_bp": 2, "lowcut_lp": 8, "order_lp": 3}})
        self.assertEqual(to_filter_kwargs(s),
                         {"lowcut_bp": 25.0, "highcut_bp": 400.0, "order_bp": 2,
                          "lowcut_lp": 8.0, "order_lp": 3})

    def test_orders_are_integers(self):
        s = settings_for({"emg_filter": {"bandpass_order": "2", "envelope_order": 3.0}})
        self.assertIsInstance(s["bandpass_order"], int)
        self.assertIsInstance(s["envelope_order"], int)

    def test_garbage_falls_back_instead_of_raising(self):
        s = settings_for({"emg_filter": {"bandpass_low": "twenty"}})
        self.assertEqual(s["bandpass_low"], DEFAULTS["bandpass_low"])

    def test_a_non_dict_block_is_ignored(self):
        self.assertEqual(settings_for({"emg_filter": [20, 95]}), dict(DEFAULTS))


class TestFromSessionDir(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="bioscout_emgfilter_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.sess = self.tmp / "022" / "pre"
        self.trial = self.sess / "3_iterations" / "rajagopal_fai" / "Run_baselineA1"
        self.trial.mkdir(parents=True)

    def write(self, body):
        (self.sess / "session.yaml").write_text(body, encoding="utf-8")

    def test_walks_up_from_a_trial_folder(self):
        self.write("subject: 22\nemg_filter:\n  bandpass_high: 350\n")
        s = from_session_dir(self.trial)
        self.assertEqual(s["bandpass_high"], 350.0)

    def test_no_session_yaml_is_not_an_error(self):
        self.assertEqual(from_session_dir(self.trial), dict(DEFAULTS))

    def test_session_config_near_returns_the_whole_config(self):
        self.write("subject: 22\nbody_mass: 89.4\n")
        cfg = session_config_near(self.trial)
        self.assertEqual(cfg["body_mass"], 89.4)

    def test_a_file_path_works_as_well_as_a_folder(self):
        self.write("emg_filter: {envelope_lowpass: 9}\n")
        probe = self.trial / "inputs" / "emg.mot"
        probe.parent.mkdir(parents=True)
        probe.write_text("x", encoding="utf-8")
        self.assertEqual(from_session_dir(probe)["envelope_lowpass"], 9.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
