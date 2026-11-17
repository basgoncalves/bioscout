"""Tests for bs.model(path) (bioscout/model/osim_model.py) -- plain XML, no OpenSim."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

XML = """<?xml version="1.0" encoding="UTF-8" ?>
<OpenSimDocument Version="40000">
  <Model name="t">
    <defaults>
      <Marker name="RASIS"><location>9 9 9</location></Marker>
    </defaults>
    <ForceSet name="forceset"><objects>
      <Millard2012EquilibriumMuscle name="psoas_r">
        <max_isometric_force>1000</max_isometric_force>
        <optimal_fiber_length>0.1</optimal_fiber_length>
        <GeometryPath name="path"><PathPointSet><objects>
          <PathPoint name="psoas_r-P1"><location>0 0 0</location><socket_parent_frame>/bodyset/pelvis</socket_parent_frame></PathPoint>
          <PathPoint name="psoas_r-P2"><location>0.1 0 0</location><socket_parent_frame>/bodyset/femur_r</socket_parent_frame></PathPoint>
        </objects></PathPointSet>
        <PathWrapSet><objects><PathWrap name="pw1"><wrap_object>PS_at_brim_r</wrap_object></PathWrap></objects></PathWrapSet>
        </GeometryPath>
      </Millard2012EquilibriumMuscle>
    </objects></ForceSet>
    <WrapObjectSet name="wrapobjectset"><objects>
      <WrapCylinder name="PS_at_brim_r"><translation>0 0 0</translation><radius>0.02</radius></WrapCylinder>
    </objects></WrapObjectSet>
    <MarkerSet name="markerset"><objects>
      <Marker name="RASIS"><socket_parent_frame>/bodyset/pelvis</socket_parent_frame><location>0.03 0.01 0.14</location><fixed>false</fixed></Marker>
      <Marker name="LASIS"><socket_parent_frame>/bodyset/pelvis</socket_parent_frame><location>0.03 0.01 -0.14</location><fixed>false</fixed></Marker>
    </objects></MarkerSet>
  </Model>
</OpenSimDocument>
"""


class TestModel(unittest.TestCase):
    def setUp(self):
        import bioscout as bs
        self.dir = Path(tempfile.mkdtemp())
        self.src = self.dir / "t.osim"
        self.src.write_text(XML, encoding="utf-8")
        self.m = bs.model(self.src)

    def test_marker_location_and_defaults_skipped(self):
        r = self.m.marker("RASIS")
        np.testing.assert_allclose(r.location, [0.03, 0.01, 0.14])   # not the <defaults> one
        self.assertEqual(r.parent_frame, "/bodyset/pelvis")

    def test_move_and_set(self):
        r = self.m.marker("RASIS")
        r.move([0, -20, 0], unit="mm")
        np.testing.assert_allclose(r.location, [0.03, -0.01, 0.14])
        r.location = r.location + [0, 0.02, 0]
        np.testing.assert_allclose(r.location, [0.03, 0.01, 0.14])
        self.m.move_markers("*ASIS", [10, 0, 0], unit="mm")
        np.testing.assert_allclose(self.m.marker("LASIS").location, [0.04, 0.01, -0.14])

    def test_properties(self):
        ps = self.m.muscle("psoas_r")
        ps.max_isometric_force *= 0.8
        self.assertAlmostEqual(ps.max_isometric_force, 800.0)
        ps.set("optimal_fiber_length", 0.12)
        self.assertAlmostEqual(ps.get("optimal_fiber_length"), 0.12)
        self.assertEqual(ps.wraps, ["PS_at_brim_r"])
        self.assertEqual([p.name for p in ps.path_points], ["psoas_r-P1", "psoas_r-P2"])
        self.assertEqual(self.m.scale("max_isometric_force", 0.5, "psoas*"), 1)
        self.assertAlmostEqual(ps.max_isometric_force, 400.0)
        w = self.m.wrap("PS_at_brim_r")
        w.radius = 0.03
        self.assertEqual(len(self.m.find("*", "Wrap")), 1)          # not the WrapObjectSet
        with self.assertRaises(AttributeError):
            ps.no_such_prop

    def test_lookup_errors(self):
        with self.assertRaises(KeyError) as e:
            self.m.get("RASI")
        self.assertIn("RASIS", str(e.exception))

    def test_save_roundtrip_and_no_overwrite(self):
        import bioscout as bs
        self.m.marker("RASIS").move([0, 0, 0.001])
        with self.assertRaises(FileExistsError):
            self.m.save(self.src)
        out = self.m.save()
        self.assertEqual(out.name, "t_edited.osim")
        m2 = bs.model(out)
        np.testing.assert_allclose(m2.marker("RASIS").location, [0.03, 0.01, 0.141])
        np.testing.assert_array_equal(m2.marker("LASIS").location, self.m.marker("LASIS").location)
        self.assertEqual(len(self.m.changes), 1)


if __name__ == "__main__":
    unittest.main()
