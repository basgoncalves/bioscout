"""Named ``calibration`` configs in session.yaml.

CEINMS calibration bounds were global: `settings.CEINMSSettings`, one value per
project. Sweeping a bound meant copied sessions plus a runtime monkeypatch of
the settings module. They are now a session.yaml block with the same shape as
`emg_map` — one flat block, or several NAMED configs that iterations pick from
with `calibration: <name>`.

Two things this pins down beyond the shape. Parameter names are canonicalised,
because settings.py declared `optimal_fiber_length` while bioscout read
`optimalFiberLength` and four of the six ranges were therefore unreachable. And
an override is PARTIAL: naming one bound leaves the rest to settings.py.

    pytest bioscout/tests/test_calibration_configs.py
"""

import os
import textwrap

import pytest

from bioscout.utils import session as S


def write(tmp_path, text):
    p = tmp_path / "session.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return str(p)


NAMED = """\
    subject: A03
    session: '25_03_31'
    emg_map: {EMG09_r: [gasmed_r, gaslat_r]}
    calibration:
      wide:
        optimalFiberLength: "0.5 3"
        tendonSlackLength: "0.5 3"
      tight:
        optimal_fiber_length: [0.75, 1.25]
        tendon_slack_length: "0.75 1.25"
    iterations:
      cateli__wide:  {generic: C.osim, calibration: wide}
      cateli__tight: {generic: C.osim, calibration: tight}
"""


# --- a session with no calibration block is untouched ----------------------
def test_absent_block_changes_nothing(tmp_path):
    cfg = S.load_session_yaml(write(tmp_path, """\
        emg_map: {E: [a]}
        iterations: {cateli: {generic: C.osim}}
    """))
    assert S.calibration_configs(cfg) == {}
    assert S.resolve_calibration(cfg, "cateli") == {}
    assert S.calibration_name_for(cfg, "cateli") is None
    assert "calibration_params" not in S.Iteration(str(tmp_path),
                                                   "cateli").trial_config("T")


def test_a_flat_block_applies_to_every_iteration(tmp_path):
    cfg = S.load_session_yaml(write(tmp_path, """\
        calibration: {optimalFiberLength: "0.5 1.5"}
        iterations: {a: {}, b: {}}
    """))
    assert not S.is_named_calibration(cfg)
    for it in ("a", "b"):
        assert S.resolve_calibration(cfg, it) == {"optimalFiberLength": "0.5 1.5"}


# --- named configs ---------------------------------------------------------
def test_each_iteration_gets_its_own_bounds(tmp_path):
    cfg = S.load_session_yaml(write(tmp_path, NAMED))
    assert S.is_named_calibration(cfg)
    assert list(S.calibration_configs(cfg)) == ["wide", "tight"]
    assert S.resolve_calibration(cfg, "cateli__wide") == {
        "optimalFiberLength": "0.5 3", "tendonSlackLength": "0.5 3"}
    assert S.resolve_calibration(cfg, "cateli__tight") == {
        "optimalFiberLength": "0.75 1.25", "tendonSlackLength": "0.75 1.25"}


def test_snake_case_and_lists_are_canonicalised(tmp_path):
    """The bug this feature closes: settings.py said `optimal_fiber_length`,
    bioscout read `optimalFiberLength`, and the bound never arrived."""
    cfg = S.load_session_yaml(write(tmp_path, NAMED))
    tight = S.calibration_configs(cfg)["tight"]
    assert "optimal_fiber_length" not in tight        # normalised away
    assert tight["optimalFiberLength"] == "0.75 1.25"  # ...and the list joined


def test_trial_config_injects_the_bounds(tmp_path):
    write(tmp_path, NAMED)
    cfg = S.Iteration(str(tmp_path), "cateli__tight").trial_config("Walking_03")
    assert cfg["calibration_name"] == "tight"
    assert cfg["calibration_params"]["tendonSlackLength"] == "0.75 1.25"


def test_named_configs_survive_a_rewrite(tmp_path):
    spec = S.read_session_yaml(write(tmp_path, NAMED))
    assert sorted(spec.calibrations) == ["tight", "wide"]
    assert [m.calibration for m in spec.models] == ["wide", "tight"]
    out = str(tmp_path / "out" / "session.yaml")
    os.makedirs(os.path.dirname(out))
    S.write_session_yaml(spec, out)
    again = S.read_session_yaml(out)
    assert again.calibrations == spec.calibrations
    assert [m.calibration for m in again.models] == ["wide", "tight"]


# --- ambiguity is a load-time error ----------------------------------------
@pytest.mark.parametrize("body,needle", [
    (NAMED.replace("{generic: C.osim, calibration: tight}", "{generic: C.osim}"),
     "does not say which"),
    (NAMED.replace("calibration: tight}", "calibration: tigth}"), "not defined"),
    ("calibration: {optimalFiberLength: '0.5 3'}\n"
     "iterations: {a: {calibration: tight}}\n", "flat block"),
    ("calibration:\n  a: {c1: '-0.9 -0.1'}\n  A: {c1: '-0.8 -0.2'}\n"
     "iterations: {i: {calibration: a}}\n", "differ only"),
    ("calibration:\n  a: {c1: '-0.9 -0.1'}\n  c2: '-0.9 -0.1'\n"
     "iterations: {i: {calibration: a}}\n", "mixes named sub-blocks"),
    ("calibration:\n  a: {c1: x}\n  b: {c1: y}\ndefault_calibration: nope\n"
     "iterations: {i: {}}\n", "not a defined calibration"),
])
def test_bad_configs_fail_at_load(tmp_path, body, needle):
    with pytest.raises(ValueError, match=needle):
        S.load_session_yaml(write(tmp_path, body))


def test_default_calibration_resolves_silent_iterations(tmp_path):
    cfg = S.load_session_yaml(write(tmp_path, """\
        calibration:
          wide:  {optimalFiberLength: "0.5 3"}
          tight: {optimalFiberLength: "0.75 1.25"}
        default_calibration: tight
        iterations: {a: {}, b: {calibration: wide}}
    """))
    assert S.calibration_name_for(cfg, "a") == "tight"
    assert S.calibration_name_for(cfg, "b") == "wide"


# --- what actually reaches calibrationCfg.xml ------------------------------
def test_param_ranges_precedence():
    from bioscout.utils.ceinms.configs import calibration_param_ranges

    class Settings:                      # a project settings.py, snake_case
        optimal_fiber_length = "0.5 2"
        strength_coefficient = "0.75 3.5"

    base = calibration_param_ranges(Settings())
    # the snake_case name is finally read instead of silently ignored
    assert base["optimalFiberLength"] == "0.5 2"
    assert base["tendonSlackLength"] == "0.5 3"        # untouched default

    over = calibration_param_ranges(Settings(),
                                    {"optimalFiberLength": "0.75 1.25"})
    assert over["optimalFiberLength"] == "0.75 1.25"   # the iteration wins
    assert over["tendonSlackLength"] == "0.5 3"        # partial: rest unchanged
    assert over["strengthCoefficient"] == "0.75 3.5"   # still from settings
