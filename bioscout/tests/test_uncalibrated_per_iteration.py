"""`calibrated: false` on an ITERATION, not just the session.

b15 put the flag in the session-wide `ceinms:` block, which makes an
uncalibrated arm a whole separate session — the drift `emg_map` and
`calibration:` were moved into the file to end. The flag is now also an
iteration key, so the control lives beside the arms it is the control for.

    pytest bioscout/tests/test_uncalibrated_per_iteration.py
"""

import textwrap

import pytest

from bioscout.utils import session as S


def write(tmp_path, text):
    p = tmp_path / "session.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return str(p)


MIXED = """\
    subject: A03
    session: '25_03_31'
    emg_map: {EMG09_r: [gasmed_r, gaslat_r]}
    ceinms: {alpha: 1, beta: 1, gamma: 30}
    iterations:
      cateli__cal:   {generic: C.osim}
      cateli__uncal: {generic: C.osim, calibrated: false}
"""


def test_absent_flag_changes_nothing(tmp_path):
    write(tmp_path, MIXED.replace(", calibrated: false", ""))
    for it in ("cateli__cal", "cateli__uncal"):
        cfg = S.Iteration(str(tmp_path), it).trial_config("T")
        assert "ceinms_calibrated" not in cfg


def test_one_session_can_hold_both(tmp_path):
    write(tmp_path, MIXED)
    cal = S.Iteration(str(tmp_path), "cateli__cal").trial_config("T")
    unc = S.Iteration(str(tmp_path), "cateli__uncal").trial_config("T")
    assert "ceinms_calibrated" not in cal      # session says nothing -> default
    assert unc["ceinms_calibrated"] is False
    # the rest of the ceinms block still reaches both
    assert cal["gamma"] == 30 and unc["gamma"] == 30


def test_iteration_overrides_the_session_default(tmp_path):
    write(tmp_path, MIXED.replace(
        "ceinms: {alpha: 1, beta: 1, gamma: 30}",
        "ceinms: {alpha: 1, beta: 1, gamma: 30, calibrated: false}").replace(
        "cateli__cal:   {generic: C.osim}",
        "cateli__cal:   {generic: C.osim, calibrated: true}"))
    assert S.Iteration(str(tmp_path), "cateli__cal"
                       ).trial_config("T")["ceinms_calibrated"] is True
    assert S.Iteration(str(tmp_path), "cateli__uncal"
                       ).trial_config("T")["ceinms_calibrated"] is False


def test_session_level_still_applies_to_every_iteration(tmp_path):
    write(tmp_path, MIXED.replace(", calibrated: false", "").replace(
        "ceinms: {alpha: 1, beta: 1, gamma: 30}",
        "ceinms: {alpha: 1, beta: 1, gamma: 30, calibrated: false}"))
    for it in ("cateli__cal", "cateli__uncal"):
        assert S.Iteration(str(tmp_path), it
                           ).trial_config("T")["ceinms_calibrated"] is False


@pytest.mark.parametrize("value,expected", [
    ("false", False), ("'false'", False), ("no", False), ("off", False),
    ("0", False), ("true", True), ("'true'", True), ("yes", True),
])
def test_quoted_strings_are_not_all_true(tmp_path, value, expected):
    """`bool("false")` is True — the trap `yaml_bool` exists for."""
    write(tmp_path, MIXED.replace("calibrated: false", "calibrated: %s" % value))
    cfg = S.Iteration(str(tmp_path), "cateli__uncal").trial_config("T")
    assert cfg["ceinms_calibrated"] is expected


def test_the_flag_travels_with_iterations_as_a_list(tmp_path):
    write(tmp_path, """\
        emg_map: {E: [a]}
        iterations:
          - {name: cal,   generic: C.osim}
          - {name: uncal, generic: C.osim, calibrated: false}
    """)
    assert S.Iteration(str(tmp_path), "uncal"
                       ).trial_config("T")["ceinms_calibrated"] is False
    assert "ceinms_calibrated" not in S.Iteration(
        str(tmp_path), "cal").trial_config("T")


# --- an uncalibrated iteration needs no `calibration:` selector ------------
BOUNDS = """\
    emg_map: {E: [a]}
    calibration:
      b0.50-3.00: {optimalFiberLength: "0.5 3"}
      b0.75-1.25: {optimalFiberLength: "0.75 1.25"}
    iterations:
      cateli__wide:  {calibration: b0.50-3.00}
      cateli__tight: {calibration: b0.75-1.25}
      cateli__uncal: {calibrated: false}
"""


def test_an_uncalibrated_iteration_needs_no_calibration_selector(tmp_path):
    """Two configs and an iteration naming neither would normally refuse to
    load. It calibrates nothing, so there is nothing to name."""
    cfg = S.load_session_yaml(write(tmp_path, BOUNDS))
    assert S.iteration_is_calibrated(cfg, "cateli__wide")
    assert not S.iteration_is_calibrated(cfg, "cateli__uncal")


def test_a_CALIBRATED_iteration_still_must_choose(tmp_path):
    with pytest.raises(ValueError, match="does not say which"):
        S.load_session_yaml(write(tmp_path, BOUNDS.replace(
            "cateli__uncal: {calibrated: false}", "cateli__oops: {}")))


def test_trial_config_omits_the_bounds_for_an_uncalibrated_arm(tmp_path):
    write(tmp_path, BOUNDS)
    cal = S.Iteration(str(tmp_path), "cateli__tight").trial_config("T")
    assert cal["calibration_params"]["optimalFiberLength"] == "0.75 1.25"
    unc = S.Iteration(str(tmp_path), "cateli__uncal").trial_config("T")
    assert "calibration_params" not in unc
    assert "calibration_name" not in unc
    assert unc["ceinms_calibrated"] is False
