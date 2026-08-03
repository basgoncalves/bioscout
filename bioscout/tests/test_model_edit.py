"""Tests for bioscout.model_edit.

Every test here runs WITHOUT OpenSim, on a synthetic model built in-file, so the
assertions do not depend on anyone's data and the suite stays in the
dependency-light tier. That is possible at all because the package declares
which ops need the bindings (``Op.needs_opensim``) and keeps the ``import
opensim`` inside the op body -- the registry, the naming rule, the validator,
the recipe engine and every pure-XML op are all exercisable offline.

The ops that DO need OpenSim (scale, mvic, muscle_opt, set_mass, lock,
place_markers, check_paths, inspect_change, ma_target) are covered only to the
point of "refuses cleanly when the bindings are missing". They must be run on a
machine with OpenSim before being trusted.
"""
from __future__ import annotations

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from bioscout.model_edit import list_ops
from bioscout.model_edit.introspect import muscles, summary, wraps
from bioscout.model_edit.naming import OutputExists, derive_out, prepare_out
from bioscout.model_edit.run import BadParam, MissingParam, apply, validate
from bioscout.model_edit.spec import REGISTRY, VERBS, get

# A minimal but structurally faithful .osim: a <defaults> template muscle (the
# thing that made an inventory over-count and a strength check falsely fail),
# two real muscles, a bilateral pair of scalable wraps, one unscalable wrap, a
# bilateral coordinate pair, and two markers, one of them bound to ground.
MODEL_XML = """<?xml version="1.0" encoding="UTF-8" ?>
<OpenSimDocument Version="40000">
  <Model name="test">
    <defaults>
      <Millard2012EquilibriumMuscle name="default">
        <max_isometric_force>546.0</max_isometric_force>
      </Millard2012EquilibriumMuscle>
      <WrapCylinder name="default_wrap">
        <radius>0.09</radius>
      </WrapCylinder>
    </defaults>
    <BodySet>
      <objects>
        <Body name="pelvis">
          <WrapObjectSet>
            <objects>
              <WrapCylinder name="Gmax_at_pelvis_r"><radius>0.0400</radius></WrapCylinder>
              <WrapCylinder name="Gmax_at_pelvis_l"><radius>0.0400</radius></WrapCylinder>
              <WrapEllipsoid name="EL_at_pelvis_r"><radius>0.01 0.02 0.03</radius></WrapEllipsoid>
            </objects>
          </WrapObjectSet>
        </Body>
        <Body name="femur_r"/>
      </objects>
    </BodySet>
    <JointSet>
      <objects>
        <CustomJoint name="hip_r">
          <coordinates>
            <Coordinate name="hip_flexion_r"><range>-0.5235987756 2.0943951024</range></Coordinate>
          </coordinates>
        </CustomJoint>
        <CustomJoint name="hip_l">
          <coordinates>
            <Coordinate name="hip_flexion_l"><range>-0.5235987756 2.0943951024</range></Coordinate>
          </coordinates>
        </CustomJoint>
      </objects>
    </JointSet>
    <ForceSet>
      <objects>
        <Millard2012EquilibriumMuscle name="glmax1_r">
          <max_isometric_force>1000.0</max_isometric_force>
          <GeometryPath>
            <PathPointSet><objects>
              <PathPoint name="glmax1_r-P1">
                <socket_parent_frame>/bodyset/pelvis</socket_parent_frame>
                <location>0.1 0.2 0.3</location>
              </PathPoint>
            </objects></PathPointSet>
          </GeometryPath>
        </Millard2012EquilibriumMuscle>
        <Millard2012EquilibriumMuscle name="glmax1_l">
          <max_isometric_force>2000.0</max_isometric_force>
          <GeometryPath>
            <PathPointSet><objects>
              <PathPoint name="glmax1_l-P1">
                <socket_parent_frame>/bodyset/pelvis</socket_parent_frame>
                <location>0.1 -0.2 0.3</location>
              </PathPoint>
            </objects></PathPointSet>
          </GeometryPath>
        </Millard2012EquilibriumMuscle>
        <CoordinateActuator name="reserve_hip_flexion_r"/>
      </objects>
    </ForceSet>
    <MarkerSet>
      <objects>
        <Marker name="RASI"><socket_parent_frame>/bodyset/pelvis</socket_parent_frame></Marker>
        <Marker name="BL"><socket_parent_frame>/ground</socket_parent_frame></Marker>
      </objects>
    </MarkerSet>
  </Model>
</OpenSimDocument>
"""


class _Tmp(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.dir = Path(self._dir.name)
        self.model = self.dir / "base.osim"
        self.model.write_text(MODEL_XML, encoding="utf-8")

    def tearDown(self):
        self._dir.cleanup()


class TestRegistry(_Tmp):
    def test_registry_is_populated(self):
        self.assertTrue(list_ops(), "no operations registered")

    def test_every_op_is_well_formed(self):
        for o in list_ops():
            with self.subTest(op=o.name):
                self.assertIn(o.verb, VERBS)
                self.assertTrue(o.summary.strip())
                self.assertIs(REGISTRY[o.name], o)
                names = [p.name for p in o.params]
                self.assertEqual(len(names), len(set(names)),
                                 "duplicate parameter name")
                for p in o.params:
                    self.assertTrue(p.help.strip(), f"{p.name} has no help")

    def test_suffix_templates_reference_real_parameters(self):
        """An op whose suffix names a parameter it does not have is a bug that
        only shows up when someone finally runs that op."""
        from bioscout.model_edit.ops import SUFFIX_HOOKS
        for o in list_ops():
            if not o.suffix:
                continue
            with self.subTest(op=o.name):
                params = {p.name: (p.default if p.default is not None else 1)
                          for p in o.params}
                hook = SUFFIX_HOOKS.get(o.name)
                if hook:
                    params = hook(params)
                derive_out(self.model, o.suffix, params)   # must not raise

    def test_ops_that_write_a_model_can_name_their_output(self):
        for o in list_ops():
            if o.writes_model:
                with self.subTest(op=o.name):
                    self.assertTrue(
                        o.suffix,
                        f"{o.name} writes a model but declares no suffix, so a "
                        f"caller cannot omit out=")


class TestIntrospect(_Tmp):
    def test_defaults_block_is_excluded(self):
        """The <defaults> template muscle is not part of the model.

        Counting it inflates the inventory and makes a correct SO/CEINMS pair
        fail the 'every muscle is exactly xN' check, because the template's
        force is not multiplied.
        """
        self.assertEqual(muscles(self.model), ["glmax1_r", "glmax1_l"])
        self.assertNotIn("default_wrap", wraps(self.model))

    def test_reserve_actuators_are_not_muscles(self):
        self.assertNotIn("reserve_hip_flexion_r", muscles(self.model))

    def test_summary(self):
        s = summary(self.model)
        self.assertEqual(s["muscles"], 2)
        self.assertEqual(s["coordinates"], 2)
        self.assertEqual(s["markers"], 2)
        self.assertEqual(s["wraps"], 3)
        self.assertEqual(s["wraps_scalable"], 2)   # the ellipsoid is not


class TestNaming(_Tmp):
    def test_derive(self):
        out = derive_out(self.model, "_mvicx{factor:.2f}", {"factor": 3.0})
        self.assertEqual(out.name, "base_mvicx3.00.osim")

    def test_refuses_to_write_over_the_input(self):
        with self.assertRaises(ValueError):
            prepare_out(self.model, self.model, "", {})

    def test_refuses_existing_output_then_backs_it_up(self):
        target = self.dir / "base_x.osim"
        target.write_text("old", encoding="utf-8")
        with self.assertRaises(OutputExists):
            prepare_out(self.model, target, "", {})
        prepare_out(self.model, target, "", {}, overwrite=True)
        kept = self.dir / "_backup_model_edit" / "base_x.osim"
        self.assertTrue(kept.exists())
        self.assertEqual(kept.read_text(encoding="utf-8"), "old")


class TestValidation(_Tmp):
    def test_unknown_parameter_is_an_error(self):
        with self.assertRaises(BadParam):
            validate(get("set_range"), {"coordinate": "hip_flexion_r", "hihi": 1})

    def test_missing_required_parameter(self):
        with self.assertRaises(MissingParam):
            validate(get("set_range"), {})

    def test_list_accepts_commas_or_spaces(self):
        clean = validate(get("ma_scale_wraps"), {"wraps": "a, b c"})
        self.assertEqual(clean["wraps"], ["a", "b", "c"])

    def test_bad_number(self):
        with self.assertRaises(BadParam):
            validate(get("ma_scale_wraps"), {"wraps": ["a"], "factor": "big"})


class TestPureOps(_Tmp):
    def test_ma_scale_wraps_mirrors_and_scales(self):
        res = apply("ma_scale_wraps", self.model,
                    wraps=["Gmax_at_pelvis_r"], factor=1.25)
        self.assertTrue(res.ok, res.reason)
        self.assertEqual(set(res.changed), {"Gmax_at_pelvis_r", "Gmax_at_pelvis_l"},
                         "a one-sided wrap edit must be mirrored")
        for v in res.changed.values():
            self.assertAlmostEqual(v["new_radius_m"] / v["old_radius_m"], 1.25, places=9)

    def test_ma_scale_wraps_refuses_unscalable_and_unknown(self):
        self.assertFalse(apply("ma_scale_wraps", self.model,
                               wraps=["EL_at_pelvis_r"], factor=1.1).ok)
        self.assertFalse(apply("ma_scale_wraps", self.model,
                               wraps=["nope"], factor=1.1).ok)

    def test_set_range_widens_in_degrees_and_mirrors(self):
        res = apply("set_range", self.model, coordinate="hip_flexion_r", hi=134.0)
        self.assertTrue(res.ok, res.reason)
        self.assertEqual(set(res.changed), {"hip_flexion_r", "hip_flexion_l"})
        self.assertAlmostEqual(res.changed["hip_flexion_r"]["new_deg"][1], 134.0, places=2)
        # written as radians
        txt = Path(res.model).read_text(encoding="utf-8")
        import re
        m = re.search(r'<Coordinate name="hip_flexion_r">.*?<range>([^<]*)</range>',
                      txt, re.S)
        self.assertAlmostEqual(float(m.group(1).split()[1]), 2.3387411977, places=6)

    def test_set_range_refuses_to_shrink_by_default(self):
        res = apply("set_range", self.model, coordinate="hip_flexion_r", hi=100.0)
        self.assertFalse(res.ok, "narrowing a bound must not happen silently")
        res = apply("set_range", self.model, coordinate="hip_flexion_r",
                    hi=100.0, allow_shrink=True)
        self.assertTrue(res.ok, res.reason)

    def test_drop_markers(self):
        res = apply("drop_markers", self.model, markers=["BL"])
        self.assertTrue(res.ok, res.reason)
        self.assertEqual(list(res.changed), ["BL"])
        from bioscout.model_edit.introspect import markers as _mk
        self.assertEqual(_mk(res.model), ["RASI"])

    def test_diff_ignores_float_noise(self):
        twin = self.dir / "twin.osim"
        twin.write_text(MODEL_XML.replace("0.0400</radius>",
                                          "0.040000000000000001</radius>"),
                        encoding="utf-8")
        res = apply("diff", self.model, against=twin)
        self.assertTrue(res.ok, res.reason)
        self.assertTrue(res.data["identical"],
                        "a re-serialisation must not read as a real difference")

    def test_apply_reports_a_missing_model_rather_than_raising(self):
        res = apply("info", self.dir / "nope.osim")
        self.assertFalse(res.ok)
        self.assertIn("not found", res.reason)


class TestOpenSimOpsDegradeCleanly(_Tmp):
    def test_needs_opensim_ops_refuse_with_a_useful_message(self):
        try:
            from bioscout.utils import get_openSim
            get_openSim()
            self.skipTest("OpenSim is available — nothing to degrade")
        except Exception:
            pass
        res = apply("mvic", self.model, factor=3.0)
        self.assertFalse(res.ok)
        self.assertIn("OpenSim", res.reason)
        self.assertFalse((self.dir / "base_mvicx3.00.osim").exists(),
                         "a refused op must not leave a partial model behind")


class TestRecipe(_Tmp):
    def _write(self, text):
        p = self.dir / "r.yaml"
        p.write_text(text, encoding="utf-8")
        return p

    def setUp(self):
        super().setUp()
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("PyYAML not installed")

    def test_chain_and_branch(self):
        from bioscout.model_edit.recipe import run
        p = self._write(
            "base: base.osim\n"
            "steps:\n"
            "  - op: set_range\n"
            "    coordinate: hip_flexion_r\n"
            "    hi: 134\n"
            "    save_as: rom.osim\n"
            "  - op: ma_scale_wraps\n"
            "    wraps: [Gmax_at_pelvis_r]\n"
            "    factor: 1.25\n"
            "    save_as: ma.osim\n"
            "  - op: diff\n"
            "    from: rom.osim\n"          # branch back, not from ma.osim
            "    against: base.osim\n")
        results = run(p, self.dir, log=lambda *_: None)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.ok for r in results), [r.reason for r in results])
        # step 3 compared rom.osim with base.osim -> only the range differs,
        # so no wrap difference should be reported.
        self.assertEqual(results[2].data["wraps"], {})

    def test_validation_catches_everything_before_running(self):
        from bioscout.model_edit.recipe import RecipeError, run
        p = self._write(
            "base: base.osim\n"
            "steps:\n"
            "  - op: set_range\n"
            "    coordinat: hip_flexion_r\n"     # typo
            "    save_as: a.osim\n"
            "  - op: nosuchop\n")
        with self.assertRaises(RecipeError) as ctx:
            run(p, self.dir, log=lambda *_: None)
        msg = str(ctx.exception)
        self.assertIn("coordinat", msg)
        self.assertIn("nosuchop", msg)
        self.assertFalse((self.dir / "a.osim").exists(),
                         "an invalid recipe must not half-run")

    def test_unknown_from_reference_is_caught(self):
        from bioscout.model_edit.recipe import RecipeError, run
        p = self._write(
            "base: base.osim\n"
            "steps:\n"
            "  - op: info\n"
            "    from: never_produced.osim\n")
        with self.assertRaises(RecipeError):
            run(p, self.dir, log=lambda *_: None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
