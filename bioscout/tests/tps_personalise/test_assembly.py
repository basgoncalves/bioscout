"""Tests for the .osim assembly (osim_model.write_personalised_model).

Runs without opensim/pyvista: a tiny inline model fixture is written, updated,
then re-parsed to assert locations and joint-centre translations changed.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from bioscout.tps_personalise.osim_model import write_personalised_model

MODEL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<OpenSimDocument Version="40000">
  <Model name="scaled">
    <BodySet><objects>
      <Body name="pelvis">
        <Marker name="femur_r_center_in_pelvis"><location>0 0 0</location></Marker>
        <Marker name="ASIS_r"><location>0 0 0</location></Marker>
        <Mesh name="pelvis_geom_1"><mesh_file>r_pelvis.vtp</mesh_file><scale_factors>0.9 0.9 0.9</scale_factors></Mesh>
      </Body>
    </objects></BodySet>
    <JointSet><objects>
      <CustomJoint name="hip_r">
        <PhysicalOffsetFrame name="pelvis_offset"><translation>1 1 1</translation></PhysicalOffsetFrame>
        <PhysicalOffsetFrame name="femur_r_offset"><translation>2 2 2</translation></PhysicalOffsetFrame>
      </CustomJoint>
      <PinJoint name="ankle_r">
        <PhysicalOffsetFrame name="tibia_r_offset"><translation>3 3 3</translation></PhysicalOffsetFrame>
      </PinJoint>
    </objects></JointSet>
    <ForceSet><objects>
      <Millard2012EquilibriumMuscle name="recfem_r">
        <GeometryPath><PathPointSet><objects>
          <PathPoint name="recfem_r-P1"><location>0 0 0</location></PathPoint>
        </objects></PathPointSet></GeometryPath>
        <WrapCylinder name="KnExt_at_fem_r"><translation>5 5 5</translation><radius>0.03</radius></WrapCylinder>
      </Millard2012EquilibriumMuscle>
    </objects></ForceSet>
  </Model>
</OpenSimDocument>
"""


def _build(tmp_path):
    src = tmp_path / "scaled.osim"
    src.write_text(MODEL_XML)
    return src


def test_writes_and_updates(tmp_path):
    src = _build(tmp_path)
    out = tmp_path / "personalised.osim"
    markers = {
        "femur_r_center_in_pelvis": [0.11, 0.22, 0.33],
        "ASIS_r": [0.4, 0.5, 0.6],
        "talus_r_center_in_tibia": [0.7, 0.8, 0.9],
    }
    muscles = {"recfem_r-P1": [1.1, 1.2, 1.3]}

    counts = write_personalised_model(
        src, markers, muscles, out, model_name="tps_transformed",
        wraps={"KnExt_at_fem_r": [0.5, 0.6, 0.7]},
        mesh_files={"pelvis_geom_1": "bones/r_pelvis.stl"},
        validate=False,
    )

    assert out.exists()
    assert counts["muscle_points"] == 1
    assert counts["markers"] == 2
    # hip_r (pelvis_offset) + ankle_r (tibia_r_offset)
    assert counts["joint_centres"] == 2
    assert counts["wraps"] == 1
    assert counts["meshes"] == 1

    root0 = ET.parse(out).getroot()
    wrap = next(root0.iter("WrapCylinder"))
    assert [float(v) for v in wrap.find("translation").text.split()] == [0.5, 0.6, 0.7]
    mesh = next(root0.iter("Mesh"))
    assert mesh.find("mesh_file").text == "bones/r_pelvis.stl"
    assert mesh.find("scale_factors").text == "1 1 1"

    root = ET.parse(out).getroot()
    assert next(root.iter("Model")).attrib["name"] == "tps_transformed"

    pp = next(root.iter("PathPoint"))
    assert [float(v) for v in pp.find("location").text.split()] == [1.1, 1.2, 1.3]

    mk = {m.attrib["name"]: m.find("location").text for m in root.iter("Marker")}
    assert [float(v) for v in mk["femur_r_center_in_pelvis"].split()] == [0.11, 0.22, 0.33]

    # hip_r pelvis_offset translation should equal the femur_r centre marker
    hip = next(j for j in root.iter("CustomJoint") if j.attrib["name"] == "hip_r")
    off = next(f for f in hip.iter("PhysicalOffsetFrame") if f.attrib["name"] == "pelvis_offset")
    assert [float(v) for v in off.find("translation").text.split()] == [0.11, 0.22, 0.33]
    # the other offset frame is untouched
    fem = next(f for f in hip.iter("PhysicalOffsetFrame") if f.attrib["name"] == "femur_r_offset")
    assert fem.find("translation").text == "2 2 2"


def test_missing_joint_marker_is_skipped(tmp_path):
    src = _build(tmp_path)
    out = tmp_path / "p2.osim"
    # no femur_r_center_in_pelvis -> hip_r centre must be left unchanged
    counts = write_personalised_model(
        src, {"ASIS_r": [1, 2, 3]}, {}, out, validate=False
    )
    root = ET.parse(out).getroot()
    hip = next(j for j in root.iter("CustomJoint") if j.attrib["name"] == "hip_r")
    off = next(f for f in hip.iter("PhysicalOffsetFrame") if f.attrib["name"] == "pelvis_offset")
    assert off.find("translation").text == "1 1 1"
    assert counts["joint_centres"] == 0
