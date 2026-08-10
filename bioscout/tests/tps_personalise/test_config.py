"""Tests for the config layer (the fix for hard-coded subjects)."""
import json

import pytest

from bioscout.tps_personalise.config import PersonalisationConfig, SubjectInfo


def test_subject_validation():
    with pytest.raises(ValueError):
        SubjectInfo(id="x", mass_kg=0, height_m=1.8)
    with pytest.raises(ValueError):
        SubjectInfo(id="x", mass_kg=80, height_m=180)  # cm by mistake
    s = SubjectInfo(id="012", mass_kg=89.9, height_m=1.80, age_years=33)
    assert s.id == "012"


def _write_inputs(tmp_path):
    for name in ("g.osim", "s.osim", "lm.json", "m.xml"):
        (tmp_path / name).write_text("x")
    (tmp_path / "Geometry").mkdir()


def test_from_yaml_roundtrip_and_resolve(tmp_path):
    _write_inputs(tmp_path)
    cfg_yaml = tmp_path / "config.yaml"
    cfg_yaml.write_text(
        "subject:\n  id: '012'\n  mass_kg: 89.9\n  height_m: 1.80\n"
        "generic_model: g.osim\nscaled_model: s.osim\nmri_landmarks: lm.json\n"
        "bone_marker_template: m.xml\ngeometry_dir: Geometry\noutput_dir: out\n"
        "tps_alpha: 0.01\n"
    )
    cfg = PersonalisationConfig.from_yaml(cfg_yaml)
    assert cfg.subject.mass_kg == 89.9
    assert cfg.tps_alpha == 0.01
    assert cfg.generic_model.is_absolute()
    cfg.validate_inputs()  # all inputs exist -> no raise
    cfg.ensure_dirs()
    assert cfg.output_dir.exists()


def test_validate_inputs_fails_fast(tmp_path):
    cfg = PersonalisationConfig(
        subject=SubjectInfo(id="1", mass_kg=80, height_m=1.8),
        generic_model=tmp_path / "missing.osim",
        scaled_model=tmp_path / "missing2.osim",
        mri_landmarks=tmp_path / "missing.json",
        bone_marker_template=tmp_path / "missing.xml",
        geometry_dir=tmp_path / "missing_dir",
        output_dir=tmp_path / "out",
    )
    with pytest.raises(FileNotFoundError):
        cfg.validate_inputs()


def test_from_bioscout_reads_players_json(tmp_path):
    (tmp_path / "players.json").write_text(
        json.dumps({"012": {"mass": 89.9, "height": 1.80, "age": 33, "sex": "M"}})
    )
    cfg = PersonalisationConfig.from_bioscout("012", tmp_path, trial="HAB1")
    assert cfg.subject.mass_kg == 89.9
    assert cfg.subject.age_years == 33
    assert cfg.output_dir.name == "personalised"
    assert "simulations" in str(cfg.scaled_model)
