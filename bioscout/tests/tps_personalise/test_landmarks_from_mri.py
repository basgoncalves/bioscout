"""Tests for MRI landmark extraction (pure geometry + writer).

No nibabel/scikit-image needed: mask reading is not exercised here; the sphere
fit, extremal selection and the Slicer .mrk.json writer are.
"""
from __future__ import annotations

import json

import numpy as np

from bioscout.tps_personalise.landmarks_from_mri import (
    fit_sphere, _extreme, _region, write_mrk_json,
)


def test_fit_sphere_recovers_centre_and_radius():
    rng = np.random.default_rng(0)
    u = rng.normal(size=(2000, 3))
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    centre = np.array([10.0, -5.0, 700.0])
    pts = centre + 25.0 * u
    c, r = fit_sphere(pts)
    assert np.allclose(c, centre, atol=0.5)
    assert abs(r - 25.0) < 0.5


def test_extreme_picks_the_right_end():
    pts = np.array([[0, 0, 0], [0, 10, 0], [0, -10, 0], [0, 5, 0]], float)
    # single most-anterior (+y) point
    assert np.allclose(_extreme(pts, (0, 1, 0)), [0, 10, 0])
    # most-posterior (-y)
    assert np.allclose(_extreme(pts, (0, -1, 0)), [0, -10, 0])


def test_region_takes_the_leading_fraction():
    # 20 points, so _region's >= 4 floor does not bind. The previous version of
    # this test used a 4-point cloud — exactly the floor — where _region
    # correctly returns everything and there is nothing left to assert.
    pts = np.zeros((20, 3))
    pts[:, 1] = np.arange(20, dtype=float)
    reg = _region(pts, (0, 1, 0), 0.5)
    assert len(reg) == 10
    assert reg[:, 1].min() == 10                        # anterior half only
    assert len(_region(pts[:3], (0, 1, 0), 0.5)) == 3   # floor clamps to size


def test_write_mrk_json_roundtrips_to_ras(tmp_path):
    lms = {"ASIS_r": np.array([123.4, -56.7, 890.1]),
           "femur_r_center": np.array([10.0, -5.0, 700.0])}
    out = tmp_path / "auto.mrk.json"
    write_mrk_json(lms, out)
    doc = json.loads(out.read_text())
    markup = doc["markups"][0]
    assert markup["coordinateSystem"] == "LPS"
    assert markup["coordinateUnits"] == "mm"
    for cp in markup["controlPoints"]:
        R = np.array(cp["orientation"], float).reshape(3, 3)
        pos = np.array(cp["position"], float)
        recovered = R @ pos            # orientation @ position must give RAS back
        assert np.allclose(recovered, lms[cp["label"]], atol=1e-9)
