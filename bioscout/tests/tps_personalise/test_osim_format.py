"""Tests for the OpenSim 3.x / 4.x compatibility layer and the TPS fallback.

These cover the additions made when the package was brought into bioscout:
the v3 schema support (needed by Rajagopal2015.osim), the dependency-free TPS
backend, and the bone-frame compatibility check.
"""
from __future__ import annotations

import textwrap
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from bioscout.tps_personalise._tps_backend import ThinPlateSpline
from bioscout.tps_personalise.landmarks import load_osim_bone_markers
from bioscout.tps_personalise.model_compat import compare_bone_frames
from bioscout.tps_personalise.osim_format import frame_of, is_v3, mesh_elements
from bioscout.tps_personalise.osim_model import OsimModelXML, detect_joint_centre_preset

V3_MODEL = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8" ?>
    <OpenSimDocument Version="30000">
      <Model name="v3">
        <BodySet><objects>
          <Body name="femur_r">
            <VisibleObject><GeometrySet><objects>
              <DisplayGeometry>
                <geometry_file>r_femur.vtp</geometry_file>
                <scale_factors>1 1 1</scale_factors>
                <transform>0 0 0 0 0 0</transform>
              </DisplayGeometry>
            </objects></GeometrySet></VisibleObject>
            <Joint><CustomJoint name="hip_r">
              <parent_body>pelvis</parent_body>
              <location_in_parent>-0.05 -0.08 0.08</location_in_parent>
            </CustomJoint></Joint>
          </Body>
        </objects></BodySet>
        <ForceSet><objects>
          <Thelen2003Muscle name="recfem_r"><GeometryPath>
            <PathPointSet><objects>
              <PathPoint name="recfem_r-P1">
                <location>0.01 -0.02 0.03</location>
                <body>femur_r</body>
              </PathPoint>
            </objects></PathPointSet>
          </GeometryPath></Thelen2003Muscle>
        </objects></ForceSet>
        <MarkerSet><objects>
          <Marker name="RASI"><body>pelvis</body><location>0.01 0.02 0.13</location></Marker>
        </objects></MarkerSet>
      </Model>
    </OpenSimDocument>
""")

V4_MODEL = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8" ?>
    <OpenSimDocument Version="40500">
      <Model name="v4">
        <BodySet><objects>
          <Body name="femur_r">
            <attached_geometry>
              <Mesh name="femur_r_geom_1">
                <mesh_file>r_femur.vtp</mesh_file>
                <scale_factors>1 1 1</scale_factors>
              </Mesh>
            </attached_geometry>
          </Body>
        </objects></BodySet>
        <MarkerSet><objects>
          <Marker name="RASI">
            <socket_parent_frame>/bodyset/pelvis</socket_parent_frame>
            <location>0.01 0.02 0.13</location>
          </Marker>
        </objects></MarkerSet>
      </Model>
    </OpenSimDocument>
""")


@pytest.fixture
def v3_path(tmp_path):
    p = tmp_path / "v3.osim"
    p.write_text(V3_MODEL)
    return p


@pytest.fixture
def v4_path(tmp_path):
    p = tmp_path / "v4.osim"
    p.write_text(V4_MODEL)
    return p


# --------------------------------------------------------------- schema layer
def test_version_detection(v3_path, v4_path):
    assert is_v3(ET.parse(v3_path).getroot())
    assert not is_v3(ET.parse(v4_path).getroot())


def test_frame_of_reads_both_schemas(v3_path, v4_path):
    for path in (v3_path, v4_path):
        marker = next(ET.parse(path).getroot().iter("Marker"))
        assert frame_of(marker) == "pelvis"


def test_markers_load_from_both_schemas(v3_path, v4_path):
    for path in (v3_path, v4_path):
        df = load_osim_bone_markers(path)
        assert list(df.index) == ["RASI"]
        assert df.loc["RASI", "body"] == "pelvis"


def test_mesh_elements_reads_both_schemas(v3_path, v4_path):
    for path in (v3_path, v4_path):
        found = list(mesh_elements(ET.parse(path).getroot()))
        assert len(found) == 1
        body, name, el, tag = found[0]
        assert body == "femur_r"
        assert el.findtext(tag).strip() == "r_femur.vtp"


def test_v3_path_points_and_body(v3_path):
    df = OsimModelXML(v3_path).muscle_path_points()
    assert list(df["label"]) == ["recfem_r-P1"]
    assert df.loc[0, "body"] == "femur_r"


def test_joint_preset_detection(v3_path, tmp_path):
    # A model with only hip_r matches the walker-knee preset (hip is shared),
    # and an unknown model raises rather than silently skipping joint centres.
    assert detect_joint_centre_preset(v3_path) in {"walker_knee", "lerner_knee"}
    empty = tmp_path / "empty.osim"
    empty.write_text('<OpenSimDocument Version="40500"><Model name="x"/></OpenSimDocument>')
    with pytest.raises(ValueError):
        detect_joint_centre_preset(empty)


# ---------------------------------------------------------- frame compatibility
def test_compare_bone_frames_matches_identical_attachment(v3_path, v4_path):
    """v3 and v4 models pinning the same unscaled mesh share the body frame."""
    rep = compare_bone_frames(v3_path, v4_path, bodies=("femur_r",))
    assert rep.matched_bodies == ["femur_r"]
    assert rep.compatible


def test_compare_bone_frames_flags_rescaled_mesh(v3_path, tmp_path):
    other = tmp_path / "scaled.osim"
    other.write_text(V4_MODEL.replace("<scale_factors>1 1 1", "<scale_factors>1.1 1 1"))
    rep = compare_bone_frames(v3_path, other, bodies=("femur_r",))
    assert not rep.compatible
    assert "femur_r" in rep.scale_mismatch


def test_compare_bone_frames_flags_different_bone(v3_path, tmp_path):
    other = tmp_path / "other.osim"
    other.write_text(V4_MODEL.replace("r_femur.vtp", "some_other_femur.vtp"))
    rep = compare_bone_frames(v3_path, other, bodies=("femur_r",))
    assert not rep.compatible
    assert "femur_r" in rep.mesh_mismatch


# ------------------------------------------------------------- TPS fallback
def test_tps_interpolates_landmarks_exactly():
    rng = np.random.default_rng(0)
    src = rng.normal(size=(12, 3))
    tgt = src * 1.1 + np.array([0.01, -0.02, 0.03])
    out = ThinPlateSpline(alpha=0.0).fit(src, tgt).transform(src)
    assert np.allclose(out, tgt, atol=1e-8)


def test_tps_reproduces_an_affine_map_everywhere():
    """A TPS fit on an affine correspondence must be that affine map."""
    rng = np.random.default_rng(1)
    src = rng.normal(size=(20, 3))
    A = np.array([[1.05, 0.0, 0.0], [0.0, 0.97, 0.0], [0.0, 0.0, 1.02]])
    b = np.array([0.1, -0.2, 0.05])
    spline = ThinPlateSpline(alpha=0.0).fit(src, src @ A.T + b)
    probe = rng.normal(size=(7, 3))
    assert np.allclose(spline.transform(probe), probe @ A.T + b, atol=1e-6)


def test_tps_requires_fit_before_transform():
    with pytest.raises(RuntimeError):
        ThinPlateSpline().transform(np.zeros((2, 3)))


def test_tps_rejects_mismatched_point_counts():
    with pytest.raises(ValueError):
        ThinPlateSpline().fit(np.zeros((4, 3)), np.zeros((5, 3)))
