"""Tests for landmark and OSIM-XML parsing against tiny fixtures."""
import json

import numpy as np

from bioscout.tps_personalise.landmarks import (
    load_mri_landmarks, load_osim_bone_markers, match_by_name, _strip_socket,
)
from bioscout.tps_personalise.osim_model import OsimModelXML


OSIM_MARKERS_XML = """<OpenSimDocument>
 <MarkerSet><objects>
  <Marker name="ASIS_r"><socket_parent_frame>/bodyset/pelvis</socket_parent_frame>
   <location>0.1 0.2 0.3</location></Marker>
  <Marker name="knee_r_med"><socket_parent_frame>/bodyset/femur_r</socket_parent_frame>
   <location>0.0 -0.4 0.05</location></Marker>
 </objects></MarkerSet>
</OpenSimDocument>"""

MODEL_XML = """<OpenSimDocument><Model>
 <ForceSet><objects>
  <Millard2012EquilibriumMuscle name="recfem_r">
   <GeometryPath><PathPointSet><objects>
     <PathPoint name="recfem_r-P1"><socket_parent_frame>/bodyset/pelvis</socket_parent_frame>
       <location>0.01 0.02 0.03</location></PathPoint>
     <PathPoint name="recfem_r-P2"><socket_parent_frame>/bodyset/femur_r</socket_parent_frame>
       <location>0.04 0.05 0.06</location></PathPoint>
   </objects></PathPointSet></GeometryPath>
   <PathWrapSet><objects><PathWrap><wrap_object>KnatWrap_r</wrap_object>
     <method>hybrid</method><range>1 2</range></PathWrap></objects></PathWrapSet>
  </Millard2012EquilibriumMuscle>
 </objects></ForceSet>
 <BodySet><objects>
  <Body name="femur_r"><WrapObjectSet><objects>
    <WrapCylinder name="KnatWrap_r"><xyz_body_rotation>0 0 0</xyz_body_rotation>
      <translation>0.1 0.2 0.3</translation><radius>0.03</radius><length>0.1</length>
    </WrapCylinder></objects></WrapObjectSet></Body>
 </objects></BodySet>
</Model></OpenSimDocument>"""


def test_strip_socket():
    assert _strip_socket("/bodyset/femur_r") == "femur_r"
    assert _strip_socket("/ground") == "ground"
    assert _strip_socket(None) is None


def test_load_osim_bone_markers(tmp_path):
    p = tmp_path / "m.xml"
    p.write_text(OSIM_MARKERS_XML)
    df = load_osim_bone_markers(p)
    assert list(df.index) == ["ASIS_r", "knee_r_med"]
    assert df.loc["ASIS_r", "body"] == "pelvis"
    assert df.loc["knee_r_med", "a"] == -0.4


def test_load_mri_landmarks_orientation(tmp_path):
    data = {"markups": [{"controlPoints": [
        {"label": "ASIS_r", "position": [1, 2, 3],
         "orientation": [1, 0, 0, 0, 1, 0, 0, 0, 1]},
    ]}]}
    p = tmp_path / "lm.json"
    p.write_text(json.dumps(data))
    df = load_mri_landmarks(p, apply_orientation=True)
    assert np.allclose(df.loc["ASIS_r", ["r", "a", "s"]].to_numpy(float), [1, 2, 3])


def test_match_by_name(tmp_path):
    (tmp_path / "m.xml").write_text(OSIM_MARKERS_XML)
    osim = load_osim_bone_markers(tmp_path / "m.xml")
    data = {"markups": [{"controlPoints": [
        {"label": "ASIS_r", "position": [0, 0, 0], "orientation": [1,0,0,0,1,0,0,0,1]},
        {"label": "extra_pt", "position": [0, 0, 0], "orientation": [1,0,0,0,1,0,0,0,1]},
    ]}]}
    (tmp_path / "lm.json").write_text(json.dumps(data))
    mri = load_mri_landmarks(tmp_path / "lm.json")
    matched, only_mri, only_osim = match_by_name(osim, mri)
    assert matched == ["ASIS_r"]
    assert only_mri == ["extra_pt"]
    assert "knee_r_med" in only_osim


def test_osim_model_parsing(tmp_path):
    p = tmp_path / "model.osim"
    p.write_text(MODEL_XML)
    m = OsimModelXML(p)
    mp = m.muscle_path_points()
    assert set(mp["muscle"]) == {"recfem_r"}
    assert set(mp["body"]) == {"pelvis", "femur_r"}
    wr = m.wrap_surfaces()
    assert "KnatWrap_r" in wr.index
    assert wr.loc["KnatWrap_r", "muscle"] == "recfem_r"
    assert np.isclose(wr.loc["KnatWrap_r", "radius"], 0.03)
