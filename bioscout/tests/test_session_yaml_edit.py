"""session.yaml: gait events format (bioscout.session.gait_events) and the
get / set / save / show editing API on Session."""
import os
import shutil
import tempfile
import unittest

try:
    import yaml
    from bioscout.session import gait_events as G
    from bioscout.session.recording import Session
    import ruamel.yaml  # noqa: F401
    HAVE = True
except Exception:                                              # noqa: BLE001
    HAVE = False

TEMPLATE = os.path.join(os.path.dirname(__file__), "..", "templates", "session_01", "session.yaml")
OLD_EVENTS = [
    {"name": "Right Foot Off", "time": 6.27, "source": "grf", "on_plate": True, "at_record_edge": False},
    {"name": "Left Foot Contact", "time": 5.32, "source": "markers", "on_plate": False,
     "at_record_edge": True},
    {"name": "Right Foot Contact", "time": 5.57, "source": "grf", "on_plate": True},
    {"name": "Right Foot Contact", "time": 6.71, "source": "markers"},
]


@unittest.skipUnless(HAVE, "pyyaml / ruamel.yaml / scipy not available")
class TestGaitEvents(unittest.TestCase):
    def test_old_list_becomes_named_mapping(self):
        ev = G.normalise(OLD_EVENTS)
        self.assertEqual(list(ev), ["foot_contact_1_l", "foot_contact_1_r", "foot_off_1_r",
                                    "foot_contact_2_r"])
        self.assertEqual(ev["foot_contact_1_l"], {"time": 5.32, "source": "markers",
                                                  "at_record_edge": True})
        self.assertEqual(G.normalise(ev), ev)                   # idempotent

    def test_bare_times_and_table(self):
        self.assertEqual(list(G.normalise([0.5, 1.0])), ["event_1", "event_2"])
        t = G.table(OLD_EVENTS)
        self.assertEqual(t.loc[t.name == "foot_contact_2_r", "n"].item(), 2)

    def test_migrate_text_folds_and_round_trips(self):
        text = yaml.safe_dump({"trials": {"W": {"type": "walking", "events": OLD_EVENTS}}},
                              sort_keys=False)
        new = G.migrate_text(text)
        self.assertIn("    events:\n      foot_contact_1_l: {time: 5.32,", new)
        self.assertEqual(yaml.safe_load(new)["trials"]["W"]["events"], G.normalise(OLD_EVENTS))


@unittest.skipUnless(HAVE, "pyyaml / ruamel.yaml / scipy not available")
class TestSessionEdit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.dir = os.path.join(self.tmp, "simulations", "S", "s1")
        os.makedirs(self.dir)
        shutil.copy(TEMPLATE, self.dir)
        self.s = Session(self.dir, bootstrap=False)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_get_set_save_keeps_everything_else(self):
        before = open(os.path.join(self.dir, "session.yaml"), encoding="utf-8").read()
        self.assertEqual(self.s.get("iterations.gpk.mvic_factor"), 1.0)
        self.s.set("body_mass", 78.2).set("iterations.gpk.mvic_factor", 2.0)
        self.assertEqual(self.s.body_mass, 78.2)
        self.assertEqual(self.s.unsaved, ["body_mass", "iterations.gpk.mvic_factor"])
        self.s.save(backup=False)
        after = open(os.path.join(self.dir, "session.yaml"), encoding="utf-8").read()
        changed = [(a, b) for a, b in zip(before.splitlines(), after.splitlines()) if a != b]
        self.assertEqual(len(changed), 2, changed)
        self.assertIn("# session.yaml", after)                      # comments kept
        again = Session(self.dir, bootstrap=False)
        self.assertEqual(again.body_mass, 78.2)
        self.assertEqual(again.events("Walking_01").shape[0], 8)

    def test_set_events_normalises(self):
        self.s.set("trials.Walking_01.events", OLD_EVENTS).save(backup=False)
        txt = open(os.path.join(self.dir, "session.yaml"), encoding="utf-8").read()
        self.assertIn("foot_contact_2_r: {time: 6.71, source: markers}", txt)


@unittest.skipUnless(HAVE, "pyyaml / ruamel.yaml / scipy not available")
class TestScaleMeasurements(unittest.TestCase):
    LIST = [{"name": "pelvis_width", "pairs": [["LASIS", "RASIS"]], "bodies": {"pelvis": "Z"}},
            {"name": "torso", "pairs": [["L5", "C7"]], "bodies": {"torso": "XYZ"}}]

    def test_mapping_and_list_give_the_same_spec(self):
        from bioscout.model.scale.measurements import spec_from_config
        as_map = {m["name"]: {"pairs": m["pairs"], "bodies": m["bodies"]} for m in self.LIST}
        self.assertEqual(spec_from_config(self.LIST), spec_from_config(as_map))

    def test_migrate_writes_one_line_each(self):
        text = yaml.safe_dump({"body_mass": 70, "scale_measurements": self.LIST}, sort_keys=False)
        new = G.migrate_scale_measurements(text)
        self.assertIn("scale_measurements:\n  pelvis_width: {pairs: [[LASIS, RASIS]], bodies: {pelvis: Z}}", new)
        self.assertEqual(list(yaml.safe_load(new)["scale_measurements"]), ["pelvis_width", "torso"])

    def test_template_scales_from_its_mapping(self):
        y = yaml.safe_load(open(TEMPLATE, encoding="utf-8"))
        self.assertIsInstance(y["scale_measurements"], dict)
        tmp = tempfile.mkdtemp()
        try:
            d = os.path.join(tmp, "simulations", "S", "s1"); os.makedirs(d)
            shutil.copy(TEMPLATE, d)
            it = Session(d, bootstrap=False).iteration("gpk")
            self.assertEqual(len(it.scale_measurements), 9)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
