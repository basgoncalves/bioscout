"""Tests for the config-file document model behind the File Editor tab.

The property worth pinning hardest is that editing YAML is *surgical*. Before
this module existed, saving a trial from the GUI re-dumped the whole
session.yaml and deleted every comment in it — including the block recording
why Walking_02 must never be re-enabled, the only place that decision was
written down. Losing that is silent and unrecoverable, so the tests below
assert not just "the value changed" but "nothing else did".

Fixtures are synthetic but shaped exactly like a real session.yaml: one-line
flow maps for trials, alignment padding, trailing comments, a quoted date-like
string and 0.00-style numbers — each one a thing a naive re-dump destroys.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from bioscout.utils.file_edit import (
    JsonDocument, UnsupportedFormat, XmlDocument, YamlDocument,
    describe_format, flow_map, load_document,
)

SESSION_YAML = """\
# Session config — comments here are load-bearing.
subject: Athlete_03
session: "25_03_31"
body_mass: 89.9                 # from the static trial
static_trial: Static_01

calibration_trials: [Walking_03, Squat_BW_01]

ceinms: {alpha: 10, beta: 1, gamma: 1000}

trials:
  Static_01:     {type: static, side: both, time_range: [0.00, 1.86]}
  Squat_BW_01:   {type: squat, side: both, time_range: [0.00, 3.54]}
  # Walking_02 REMOVED 2026-08-04 — do NOT re-enable. All 10 SO reserve
  # actuators hit the 50 Nm cap in four of the six models.
  # was: {type: walking, side: right, time_range: [0.17, 1.26]}
  Walking_03:    {type: walking, side: right}   # right-leg stance window

iterations:
  cateli:
    generic: Catelli/Catelli.osim
    so_model: scaled_opt_N10_mvicx3.00.osim
    linear_scaling: true
    mvic_factor: 3.0
    color: green
"""

GRF_XML = """\
<?xml version="1.0" encoding="UTF-8" ?>
<OpenSimDocument Version="40000">
\t<ExternalLoads name="GRF">
\t\t<!-- forces in N, moments in Nm -->
\t\t<objects>
\t\t\t<ExternalForce name="ExternalForce_1">
\t\t\t\t<applied_to_body>calcn_r</applied_to_body>
\t\t\t\t<isDisabled>false</isDisabled>
\t\t\t</ExternalForce>
\t\t\t<ExternalForce name="ExternalForce_2">
\t\t\t\t<applied_to_body>calcn_l</applied_to_body>
\t\t\t\t<isDisabled>false</isDisabled>
\t\t\t</ExternalForce>
\t\t</objects>
\t\t<datafile>grf.mot</datafile>
\t</ExternalLoads>
</OpenSimDocument>
"""


class _TmpFile(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name: str, text: str) -> Path:
        p = self.dir / name
        p.write_text(text, encoding="utf-8")
        return p

    def field(self, doc, node, label):
        for f in doc.fields_for(node):
            if f.label == label:
                return f
        raise AssertionError(f"no field {label!r} on {node.path_str()} "
                             f"(have {[f.label for f in doc.fields_for(node)]})")

    def child(self, node, label):
        for c in node.children:
            if c.label == label:
                return c
        raise AssertionError(f"no child {label!r} under {node.path_str()} "
                             f"(have {[c.label for c in node.children]})")


class TestYamlIsSurgical(_TmpFile):
    def setUp(self):
        super().setUp()
        self.path = self.write("session.yaml", SESSION_YAML)

    def test_clean_load_is_byte_identical(self):
        self.assertEqual(load_document(self.path).dumps(), SESSION_YAML)

    def test_browsing_everything_changes_nothing(self):
        """Opening a file and clicking through it must not modify it.

        This is the regression that would silently reformat every number in
        the file: a form showing the *parsed* 0.0 for a source 0.00 re-renders
        as 0.0 the moment the form is flushed, which the GUI does on every
        node change.
        """
        doc = load_document(self.path)

        def visit(node):
            for f in doc.fields_for(node):
                f.set(f.value)          # flush, unchanged
            for c in node.children:
                visit(c)

        visit(doc.root)
        self.assertEqual(doc.dumps(), SESSION_YAML)
        self.assertFalse(doc.dirty)

    def test_edit_touches_only_its_own_line(self):
        doc = load_document(self.path)
        trial = self.child(self.child(doc.root, "trials"), "Squat_BW_01")
        self.field(doc, trial, "side").set("right")
        self.field(doc, trial, "time_range").set("0.55, 2.10")
        out = doc.dumps()

        got = yaml.safe_load(out)["trials"]["Squat_BW_01"]
        self.assertEqual(got, {"type": "squat", "side": "right",
                               "time_range": [0.55, 2.10]})
        changed = [(a, b) for a, b in
                   zip(SESSION_YAML.splitlines(), out.splitlines()) if a != b]
        self.assertEqual(len(changed), 1, f"expected 1 changed line, got {changed}")
        self.assertEqual(len(out.splitlines()), len(SESSION_YAML.splitlines()))

    def test_comments_and_formatting_survive(self):
        doc = load_document(self.path)
        trial = self.child(self.child(doc.root, "trials"), "Squat_BW_01")
        self.field(doc, trial, "side").set("left")
        out = doc.dumps()
        for fragment in ("do NOT re-enable",
                         "# was: {type: walking, side: right",
                         "# from the static trial",
                         "# right-leg stance window",
                         '"25_03_31"',                    # quoting kept
                         "[0.00, 1.86]",                  # 0.00 not rewritten
                         "Static_01:     {type: static"):  # alignment kept
            self.assertIn(fragment, out, f"lost: {fragment}")

    def test_string_that_looks_like_a_number_stays_quoted(self):
        """``session: "25_03_31"`` unquoted parses as a subtraction, not a date."""
        doc = load_document(self.path)
        self.field(doc, doc.root, "session").set("25_04_01")
        out = doc.dumps()
        self.assertIn('session: "25_04_01"', out)
        self.assertEqual(yaml.safe_load(out)["session"], "25_04_01")

    def test_numeric_types_are_preserved(self):
        doc = load_document(self.path)
        self.field(doc, doc.root, "body_mass").set("91.2")
        self.assertEqual(yaml.safe_load(doc.dumps())["body_mass"], 91.2)

    def test_bool_field_round_trips(self):
        doc = load_document(self.path)
        it = self.child(self.child(doc.root, "iterations"), "cateli")
        f = self.field(doc, it, "linear_scaling")
        self.assertEqual(f.kind, "bool")
        f.set(False)
        self.assertIs(yaml.safe_load(doc.dumps())["iterations"]["cateli"]
                      ["linear_scaling"], False)

    def test_known_keys_offer_choices(self):
        doc = load_document(self.path)
        trial = self.child(self.child(doc.root, "trials"), "Static_01")
        self.assertIn("squat", self.field(doc, trial, "type").choices)
        self.assertEqual(list(self.field(doc, trial, "side").choices),
                         ["both", "left", "right"])
        it = self.child(self.child(doc.root, "iterations"), "cateli")
        self.assertIn("green", self.field(doc, it, "color").choices)

    def test_inline_comment_surfaces_as_a_hint(self):
        doc = load_document(self.path)
        self.assertIn("static trial", self.field(doc, doc.root, "body_mass").comment)


class TestYamlStructuralEdits(_TmpFile):
    def setUp(self):
        super().setUp()
        self.path = self.write("session.yaml", SESSION_YAML)

    def test_duplicate_then_edit_the_copy(self):
        """Spans must be recomputed after a structural edit.

        Without that, the second edit patches offsets from before the insert
        and lands in the middle of an unrelated line.
        """
        doc = load_document(self.path)
        trials = self.child(doc.root, "trials")
        doc.duplicate_entry(trials.ref, "Squat_BW_01", "Squat_BW_02")

        trials = self.child(doc.root, "trials")            # tree was rebuilt
        copy = self.child(trials, "Squat_BW_02")
        self.field(doc, copy, "type").set("deadlift")
        self.field(doc, copy, "time_range").set("1.0, 2.5")

        got = yaml.safe_load(doc.dumps())["trials"]
        self.assertEqual(got["Squat_BW_02"],
                         {"type": "deadlift", "side": "both",
                          "time_range": [1.0, 2.5]})
        self.assertEqual(got["Squat_BW_01"],
                         {"type": "squat", "side": "both",
                          "time_range": [0.0, 3.54]})
        self.assertIn("do NOT re-enable", doc.dumps())

    def test_add_and_delete(self):
        doc = load_document(self.path)
        doc.add_entry(self.child(doc.root, "ceinms").ref, "epsilon", "0.5")
        self.assertEqual(yaml.safe_load(doc.dumps())["ceinms"],
                         {"alpha": 10, "beta": 1, "gamma": 1000, "epsilon": 0.5})

        doc = load_document(self.path)
        trials = self.child(doc.root, "trials")
        doc.delete_entry(trials.ref, "Walking_03")
        out = yaml.safe_load(doc.dumps())
        self.assertNotIn("Walking_03", out["trials"])
        self.assertIn("Static_01", out["trials"])
        self.assertIn("do NOT re-enable", doc.dumps())

    def test_set_entry_source_replaces_only_the_value(self):
        """What Trial Analysis' Save button does — the trailing comment stays."""
        doc = load_document(self.path)
        trials = doc.map_node("trials")
        doc.set_entry_source(trials, "Walking_03",
                             flow_map({"type": "walking", "side": "left",
                                       "time_range": [0.2, 1.4]}))
        out = doc.dumps()
        self.assertEqual(yaml.safe_load(out)["trials"]["Walking_03"],
                         {"type": "walking", "side": "left",
                          "time_range": [0.2, 1.4]})
        self.assertIn("# right-leg stance window", out)
        self.assertIn("do NOT re-enable", out)

    def test_set_entry_source_adds_a_missing_trial(self):
        doc = load_document(self.path)
        before = len(yaml.safe_load(doc.dumps())["trials"])
        doc.set_entry_source(doc.map_node("trials"), "Squat_100kg_01",
                             flow_map({"type": "squat", "side": "both"}))
        after = yaml.safe_load(doc.dumps())["trials"]
        self.assertEqual(len(after), before + 1)
        self.assertEqual(after["Squat_100kg_01"], {"type": "squat", "side": "both"})

    def test_ensure_mapping_creates_a_missing_section(self):
        p = self.write("bare.yaml", "subject: A\n# keep me\nbody_mass: 80\n")
        doc = load_document(p)
        doc.set_entry_source(doc.ensure_mapping("trials"), "Static_01",
                             flow_map({"type": "static", "side": "both"}))
        out = doc.dumps()
        self.assertEqual(yaml.safe_load(out)["trials"],
                         {"Static_01": {"type": "static", "side": "both"}})
        self.assertIn("# keep me", out)

    def test_delete_from_a_flow_mapping_is_refused(self):
        """Better a clear refusal than a mangled one-line map."""
        doc = load_document(self.path)
        with self.assertRaises(ValueError):
            doc.delete_entry(doc.map_node("ceinms"), "alpha")


class TestSaving(_TmpFile):
    def setUp(self):
        super().setUp()
        self.path = self.write("session.yaml", SESSION_YAML)

    def test_save_is_atomic_and_keeps_a_backup(self):
        doc = load_document(self.path)
        trial = self.child(self.child(doc.root, "trials"), "Static_01")
        self.field(doc, trial, "side").set("left")
        doc.save()

        self.assertEqual(yaml.safe_load(self.path.read_text(encoding="utf-8"))
                         ["trials"]["Static_01"]["side"], "left")
        self.assertTrue((self.dir / "session.yaml.bak").is_file())
        self.assertEqual((self.dir / "session.yaml.bak").read_text(encoding="utf-8"),
                         SESSION_YAML)
        self.assertFalse((self.dir / "session.yaml.tmp").exists())
        self.assertFalse(doc.dirty)

    def test_invalid_output_is_never_written(self):
        doc = load_document(self.path)
        with self.assertRaises(ValueError):
            doc.save(text="trials:\n  a: [unclosed\n")
        self.assertEqual(self.path.read_text(encoding="utf-8"), SESSION_YAML)

    def test_revert(self):
        doc = load_document(self.path)
        trial = self.child(self.child(doc.root, "trials"), "Static_01")
        self.field(doc, trial, "side").set("left")
        self.assertTrue(doc.dirty)
        doc.revert()
        self.assertFalse(doc.dirty)
        self.assertEqual(doc.dumps(), SESSION_YAML)


class TestChecks(_TmpFile):
    def test_flags_a_backwards_time_range(self):
        p = self.write("session.yaml",
                       "trials:\n  A: {type: squat, side: both, "
                       "time_range: [3.0, 1.0]}\n")
        self.assertTrue(any("not after" in m for m in load_document(p).problems()))

    def test_flags_an_unknown_side(self):
        p = self.write("session.yaml", "trials:\n  A: {type: squat, side: middle}\n")
        self.assertTrue(any("left/right/both" in m
                            for m in load_document(p).problems()))

    def test_flags_a_static_trial_with_no_entry(self):
        p = self.write("session.yaml",
                       "static_trial: Static_09\ntrials:\n  A: {type: squat}\n")
        self.assertTrue(any("static_trial" in m for m in load_document(p).problems()))

    def test_clean_file_has_nothing_to_flag(self):
        p = self.write("session.yaml",
                       "static_trial: A\ntrials:\n"
                       "  A: {type: static, side: both, time_range: [0.0, 1.0]}\n")
        self.assertEqual(load_document(p).problems(), [])


class TestXml(_TmpFile):
    def setUp(self):
        super().setUp()
        self.path = self.write("GRF.xml", GRF_XML)

    def test_tree_shows_containers_only(self):
        doc = load_document(self.path)
        objects = doc.root.children[0].children[0]
        self.assertEqual([c.label.split()[0] for c in objects.children],
                         ["ExternalForce", "ExternalForce"])

    def test_edit_attribute_text_and_child(self):
        doc = load_document(self.path)
        force = doc.root.children[0].children[0].children[0]
        self.field(doc, force, "@name").set("plate_2")
        self.field(doc, force, "applied_to_body").set("calcn_l")
        self.field(doc, force, "isDisabled").set(True)
        out = doc.dumps()
        self.assertIn('name="plate_2"', out)
        self.assertIn("<applied_to_body>calcn_l</applied_to_body>", out)
        self.assertEqual(out.count("<isDisabled>true</isDisabled>"), 1)

    def test_comments_survive(self):
        """Plain ET.fromstring drops comments; OpenSim setups use them for units."""
        doc = load_document(self.path)
        self.assertIn("<!-- forces in N, moments in Nm -->", doc.dumps())

    def test_repeated_values_become_a_dropdown(self):
        doc = load_document(self.path)
        force = doc.root.children[0].children[0].children[0]
        self.assertEqual(sorted(self.field(doc, force, "applied_to_body").choices),
                         ["calcn_l", "calcn_r"])

    def test_save_round_trips(self):
        doc = load_document(self.path)
        force = doc.root.children[0].children[0].children[0]
        self.field(doc, force, "isDisabled").set(True)
        doc.save()
        again = load_document(self.path)
        self.assertFalse(again.dirty)
        force = again.root.children[0].children[0].children[0]
        self.assertEqual(self.field(again, force, "isDisabled").value, "true")


class TestJson(_TmpFile):
    def test_types_are_kept(self):
        p = self.write("c.json", json.dumps(
            {"user": "bas", "port": 8080, "debug": False, "tags": ["a", "b"]}))
        doc = load_document(p)
        self.field(doc, doc.root, "port").set("9090")
        self.field(doc, doc.root, "debug").set(True)
        self.field(doc, doc.root, "tags").set("a, b, c")
        doc.save()
        self.assertEqual(json.loads(p.read_text(encoding="utf-8")),
                         {"user": "bas", "port": 9090, "debug": True,
                          "tags": ["a", "b", "c"]})


class TestDispatch(_TmpFile):
    def test_suffix_mapping(self):
        self.assertEqual(describe_format("a.yaml"), "yaml")
        self.assertEqual(describe_format("a.YML"), "yaml")
        self.assertEqual(describe_format("a.osim"), "xml")
        self.assertEqual(describe_format("a.json"), "json")
        self.assertIsNone(describe_format("a.mot"))

    def test_unsupported_suffix_raises(self):
        p = self.write("a.mot", "whatever\n")
        with self.assertRaises(UnsupportedFormat):
            load_document(p)

    def test_classes(self):
        self.assertIsInstance(load_document(self.write("a.yaml", "k: 1\n")), YamlDocument)
        self.assertIsInstance(load_document(self.write("a.xml", "<r><a><b>1</b></a></r>")), XmlDocument)
        self.assertIsInstance(load_document(self.write("a.json", "{}")), JsonDocument)


class TestFlowMap(unittest.TestCase):
    def test_render(self):
        self.assertEqual(
            flow_map({"type": "squat", "side": "both", "time_range": [0.0, 3.5]}),
            "{type: squat, side: both, time_range: [0.0, 3.5]}")

    def test_round_trips_through_yaml(self):
        block = {"type": "walking", "side": "left", "time_range": [0.2, 1.4],
                 "note": "yes"}
        self.assertEqual(yaml.safe_load(flow_map(block)), block)

    def test_quotes_a_value_that_would_reparse_as_a_number(self):
        self.assertEqual(yaml.safe_load(flow_map({"id": "25_03_31"}))["id"],
                         "25_03_31")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestSameIndentBlockSequences(_TmpFile):
    """Entries whose value is a block list at the SAME column as the key.

    PyYAML's own dump writes exactly this shape (emg_map in every real
    session.yaml), and `_entry_bounds` used to treat the "- item" lines as
    siblings. `delete_entry` then removed only the key line and the orphaned
    items were swallowed by the PREVIOUS entry's list — muscles silently
    remapped to the wrong EMG channel. Found 2026-08-18 building the CEINMS
    Setup tab; these pin the fix.
    """

    YAML = (
        "subject: '021'\n"
        "emg_map:\n"
        "  Voltage_1-VM:\n"
        "  - vasmed_r\n"
        "  - vasint_r\n"
        "  Voltage_2-VL:\n"
        "  - vaslat_r\n"
        "  Voltage_3-RF:\n"
        "  - recfem_r\n"
        "body_mass: 61.3\n"
    )

    def _doc(self, text=None):
        return load_document(self.write("session.yaml", text or self.YAML))

    def test_entry_source_includes_the_items(self):
        doc = self._doc()
        src = doc.entry_source(doc.map_node("emg_map"), "Voltage_2-VL")
        self.assertIn("Voltage_2-VL:", src)
        self.assertIn("- vaslat_r", src)
        self.assertNotIn("Voltage_3-RF", src)

    def test_delete_takes_the_items_with_the_key(self):
        doc = self._doc()
        doc.delete_entry(doc.map_node("emg_map"), "Voltage_2-VL")
        data = yaml.safe_load(doc.dumps())
        self.assertNotIn("Voltage_2-VL", data["emg_map"])
        # THE bug: the orphaned "- vaslat_r" used to join the previous list
        self.assertEqual(data["emg_map"]["Voltage_1-VM"],
                         ["vasmed_r", "vasint_r"])
        self.assertEqual(data["emg_map"]["Voltage_3-RF"], ["recfem_r"])

    def test_replace_entry_swaps_block_list_for_flow(self):
        doc = self._doc()
        doc.replace_entry(doc.map_node("emg_map"), "Voltage_3-RF",
                          "[recfem_r, vasint_r]")
        data = yaml.safe_load(doc.dumps())
        self.assertEqual(data["emg_map"]["Voltage_3-RF"],
                         ["recfem_r", "vasint_r"])
        self.assertEqual(data["emg_map"]["Voltage_2-VL"], ["vaslat_r"])
        # untouched lines stay byte-identical
        self.assertIn("  Voltage_1-VM:\n  - vasmed_r\n", doc.dumps())
        self.assertIn("body_mass: 61.3", doc.dumps())

    def test_replace_entry_adds_when_absent(self):
        doc = self._doc()
        doc.replace_entry(doc.map_node("emg_map"), "Voltage_9-NEW",
                          "[soleus_r]")
        data = yaml.safe_load(doc.dumps())
        self.assertEqual(data["emg_map"]["Voltage_9-NEW"], ["soleus_r"])

    def test_dash_prefixed_key_is_still_a_sibling(self):
        # a mapping KEY that merely starts with "-" must not be mistaken for
        # a sequence item of the entry above it
        doc = self._doc("m:\n  a: 1\n  '-weird': 2\n")
        src = doc.entry_source(doc.map_node("m"), "a")
        self.assertNotIn("-weird", src)
