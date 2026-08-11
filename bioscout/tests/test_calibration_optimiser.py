"""The `<optimiser>` half of session.yaml's `calibration:` block (2.0.0b16).

`calibration:` has carried the six PARAMETER BOUNDS since b14. b16 lets the
same named block also carry how the calibration SEARCHES — learning rate, the
iteration ceiling, the early-stopping rule — so a learning-rate sweep is a
statement in the session file instead of a runtime monkeypatch of
`settings.CEINMSSettings` that leaves no trace in the session it produced.

The failure this file mostly exists to prevent: an optimiser key silently
landing in `parametersToCalibrate` as `<parameter name="learningRate">`. CEINMS
would ignore it, the learning rate would stay at 0.02, and every report would
say the arm ran at 0.005. See `tests/GPKv3/t25_calibration_variance` (F2).
"""
import xml.etree.ElementTree as ET

import pytest

from bioscout.utils import session as S
from bioscout.utils.ceinms.configs import (
    calibration_optimiser_settings, calibration_param_ranges, is_optimiser_key,
)


class Settings:
    """The subset of settings.CEINMSSettings these functions read."""
    learning_rate = 0.02
    max_iterations = 1000
    early_stopping_patience = 20
    early_stopping_min_improvement = 0.1
    num_synergies = 4
    optimal_fiber_length = "0.5 3"
    tendon_slack_length = "0.5 3"


# --------------------------------------------------------------------------
# which half of the block does a key belong to
# --------------------------------------------------------------------------
@pytest.mark.parametrize("key", [
    "learningRate", "learning_rate", "maxIterations", "max_iterations",
    "patience", "early_stopping_patience", "minImprovement",
    "early_stopping_min_improvement", "numberOfSynergies", "num_synergies",
    "learningRateDecay", "minLearningRate",
])
def test_optimiser_keys_recognised(key):
    assert is_optimiser_key(key)


@pytest.mark.parametrize("key", [
    "optimalFiberLength", "optimal_fiber_length", "tendonSlackLength",
    "c1", "c2", "shapefactor", "strengthCoefficient",
])
def test_bound_keys_are_not_optimiser_keys(key):
    assert not is_optimiser_key(key)


# --------------------------------------------------------------------------
# resolution + precedence
# --------------------------------------------------------------------------
def test_settings_supply_the_defaults():
    opt = calibration_optimiser_settings(Settings())
    assert opt["learningRate"] == 0.02
    assert opt["maxIterations"] == 1000
    assert opt["patience"] == 20
    assert opt["minImprovement"] == 0.1
    assert opt["numberOfSynergies"] == 4


def test_iteration_beats_settings_and_the_override_is_partial():
    opt = calibration_optimiser_settings(Settings(),
                                         {"learningRate": 0.005})
    assert opt["learningRate"] == 0.005
    assert opt["maxIterations"] == 1000        # untouched
    assert opt["patience"] == 20               # untouched


def test_both_spellings_reach_the_same_knob():
    a = calibration_optimiser_settings(Settings(), {"learningRate": 0.005})
    b = calibration_optimiser_settings(Settings(), {"learning_rate": 0.005})
    assert a == b


def test_decay_is_absent_unless_asked_for():
    assert "decay" not in calibration_optimiser_settings(Settings())
    opt = calibration_optimiser_settings(
        Settings(), {"learningRateDecay": 0.99, "minLearningRate": 1e-4})
    assert opt["decay"] == 0.99 and opt["minLearningRate"] == 1e-4


# --------------------------------------------------------------------------
# THE ONE THAT MATTERS: optimiser keys must not become bounds
# --------------------------------------------------------------------------
def test_optimiser_keys_never_become_parameters():
    ranges = calibration_param_ranges(
        Settings(), {"learningRate": 0.005, "maxIterations": 400,
                     "optimalFiberLength": "0.75 1.25"})
    assert "learningRate" not in ranges
    assert "maxIterations" not in ranges
    assert ranges["optimalFiberLength"] == "0.75 1.25"
    assert ranges["tendonSlackLength"] == "0.5 3"       # untouched


def test_a_typo_still_warns_by_landing_in_ranges():
    # An unrecognised key keeps b14's behaviour — it reaches the XML as a
    # parameter and the load-time check warns. Only KNOWN optimiser keys are
    # diverted; a typo must stay visible rather than vanish.
    ranges = calibration_param_ranges(Settings(), {"learninRate": 0.005})
    assert "learninRate" in ranges


# --------------------------------------------------------------------------
# session.yaml side
# --------------------------------------------------------------------------
CFG = """
calibration:
  lr0.020__r01: {learningRate: 0.02,  optimalFiberLength: "0.5 3"}
  lr0.005__r01: {learning_rate: 0.005, optimal_fiber_length: [0.5, 3]}
iterations:
  cateli__lr0.020__r01: {calibration: lr0.020__r01}
  cateli__lr0.005__r01: {calibration: lr0.005__r01}
"""


def _cfg(tmp_path, text=CFG):
    p = tmp_path / "session.yaml"
    p.write_text(text)
    return S.read_session_yaml(str(p))


def test_optimiser_keys_are_canonicalised_on_load(tmp_path):
    cfg = _cfg(tmp_path)
    got = S.resolve_calibration(cfg, "cateli__lr0.005__r01")
    assert got["learningRate"] == "0.005"
    assert got["optimalFiberLength"] == "0.5 3"


def test_the_two_arms_differ_only_in_the_learning_rate(tmp_path):
    cfg = _cfg(tmp_path)
    a = S.resolve_calibration(cfg, "cateli__lr0.020__r01")
    b = S.resolve_calibration(cfg, "cateli__lr0.005__r01")
    assert {k for k in a if a[k] != b.get(k)} == {"learningRate"}


def test_repeats_of_one_arm_are_configuration_identical(tmp_path):
    # t25's premise: N repeats differ in NAME and in nothing else. If this
    # ever fails the variance test is measuring a configuration difference.
    text = """
calibration:
  lr0.020__r01: {learningRate: 0.02, optimalFiberLength: "0.5 3"}
  lr0.020__r02: {learningRate: 0.02, optimalFiberLength: "0.5 3"}
  lr0.020__r03: {learningRate: 0.02, optimalFiberLength: "0.5 3"}
iterations:
  c__r01: {calibration: lr0.020__r01}
  c__r02: {calibration: lr0.020__r02}
  c__r03: {calibration: lr0.020__r03}
"""
    cfg = _cfg(tmp_path, text)
    got = [S.resolve_calibration(cfg, f"c__r0{i}") for i in (1, 2, 3)]
    assert got[0] == got[1] == got[2]


def test_no_unknown_parameter_warning_for_optimiser_keys(tmp_path, capsys):
    _cfg(tmp_path)
    assert "WARNING" not in capsys.readouterr().out


def test_a_real_typo_still_warns(tmp_path, capsys):
    _cfg(tmp_path, 'calibration: {learninRate: 0.005}\niterations: {c: {}}\n')
    assert "WARNING" in capsys.readouterr().out


# --------------------------------------------------------------------------
# end to end: does it reach the XML, and in the right element
# --------------------------------------------------------------------------
def _xml(tmp_path, override):
    from bioscout.utils.ceinms import configs
    out = tmp_path / "calibrationCfg.xml"
    configs.create_calibrationCfg(osimModelPath="m.osim",
                                  inputPaths=["Walking_03/inputData.xml"],
                                  outputPath=str(out),
                                  params_override=override)
    return ET.parse(str(out)).getroot()


@pytest.mark.xfail(reason="needs settings.py on the path (project-level import)",
                   strict=False)
def test_learning_rate_reaches_the_optimiser_element(tmp_path):
    root = _xml(tmp_path, {"learningRate": 0.005})
    assert root.find("./optimiser/learningRate").text == "0.005"
    assert root.find("./optimiser/earlyStopping/patience") is not None
    names = [p.get("name")
             for p in root.iterfind("./calibrationTargets/parametersToCalibrate/parameter")]
    assert "learningRate" not in names
