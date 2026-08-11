"""Executing CEINMS against the UNCALIBRATED subject model.

CEINMS execution has only ever been driven by ``subjectCalibrated.xml``. There
was no way to ask for the other one -- ``subjectUncalibrated.xml``, written
straight from the .osim by ``create_ceinms_model()``, carrying OpenSim's own
optimal fibre lengths, tendon slack lengths, pennation angles and max isometric
forces with nothing fitted to the subject. That file is the only honest "no
calibration" control: it is what the model says before any parameter moved.

An iteration asks for it in session.yaml::

    ceinms:
      calibrated: false

Three things this pins down beyond the flag existing.

**The flag must survive `_overrides`.** session.yaml values are injected into
``Analyse._overrides`` and those WIN over plain attributes -- the lesson
``ceinms.modes._set_weights`` records after a bounds run silently solved every
arm at one gamma. A check that read the attribute alone would report
`calibrated` for an iteration session.yaml had switched off.

**A quoted "false" is still false.** PyYAML turns bare ``false`` into a bool,
but ``"false"`` arrives as a string and ``bool("false")`` is True -- which would
run the calibration the session asked to skip, silently.

**The output folder is tagged.** A calibrated and an uncalibrated solve of the
same trial and weights would otherwise write to the same ``Execution_a1_b1_g30``
and one would overwrite the other, leaving a result that reads as calibrated
whichever ran last.

    pytest bioscout/tests/test_uncalibrated_execution.py
"""

import os
import textwrap
import xml.etree.ElementTree as ET

import pytest

from bioscout.utils import analysis as A
from bioscout.utils import session as S


def write(tmp_path, text):
    p = tmp_path / "session.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return str(p)


# ===========================================================  yaml_bool
@pytest.mark.parametrize("v", [False, "false", "False", " FALSE ", "no", "off",
                               "0", "", "none", "uncalibrated"])
def test_falsey_spellings(v):
    assert S.yaml_bool(v) is False


@pytest.mark.parametrize("v", [True, "true", "yes", "on", "1", "calibrated"])
def test_truthy_spellings(v):
    assert S.yaml_bool(v) is True


def test_absent_defaults_to_calibrated():
    """No flag means the behaviour every existing project already had."""
    assert S.yaml_bool(None) is True
    assert S.yaml_bool(None, default=False) is False


# ==========================================  session.yaml -> trial config
def test_flag_reaches_the_trial_config(tmp_path):
    write(tmp_path, """\
        subject: A03
        session: '25_03_31'
        ceinms: {alpha: 1, beta: 1, gamma: 30, calibrated: false}
        iterations: {gpk: {generic: G.osim}}
    """)
    cfg = S.Iteration(str(tmp_path), "gpk").trial_config("Walking_03")
    assert cfg["ceinms_calibrated"] is False


def test_quoted_false_reaches_the_trial_config_as_false(tmp_path):
    write(tmp_path, """\
        subject: A03
        session: '25_03_31'
        ceinms: {gamma: 30, calibrated: "false"}
        iterations: {gpk: {generic: G.osim}}
    """)
    cfg = S.Iteration(str(tmp_path), "gpk").trial_config("Walking_03")
    assert cfg["ceinms_calibrated"] is False


def test_absent_flag_adds_no_key(tmp_path):
    """A session that never mentions it must be byte-for-byte the old path."""
    write(tmp_path, """\
        subject: A03
        session: '25_03_31'
        ceinms: {gamma: 30}
        iterations: {gpk: {generic: G.osim}}
    """)
    cfg = S.Iteration(str(tmp_path), "gpk").trial_config("Walking_03")
    assert "ceinms_calibrated" not in cfg


def test_true_reaches_the_trial_config(tmp_path):
    write(tmp_path, """\
        subject: A03
        session: '25_03_31'
        ceinms: {gamma: 30, calibrated: true}
        iterations: {gpk: {generic: G.osim}}
    """)
    cfg = S.Iteration(str(tmp_path), "gpk").trial_config("Walking_03")
    assert cfg["ceinms_calibrated"] is True


# ================================================  the Analyse properties
def make_trial(tmp_path, **attrs):
    """An Analyse with only the path fields these properties read.

    Built with ``__new__`` on purpose: ``Analyse.__init__`` wants a real trial
    folder and a settings file, and none of that is what is under test here.
    """
    t = A.Analyse.__new__(A.Analyse)
    t.path = str(tmp_path)
    t.alpha, t.beta, t.gamma = 1, 1, 30
    t.ceinms_exe_dir = os.path.join("ceinms", "Execution")
    t.ceinms_calibrated_model = os.path.join("..", "ceinms_calibration",
                                             "subjectCalibrated.xml")
    t.ceinms_uncalibrated_model = os.path.join("..", "ceinms_calibration",
                                               "subjectUncalibrated.xml")
    t.ceinms_input_data = os.path.join("ceinms", "inputData.xml")
    t.ceinms_exe_cfg = os.path.join("ceinms", "ceinms_cfg.xml")
    t.ceinms_exe_setup = os.path.join("ceinms", "ceinms_setup.xml")
    t.ceinms_excitation_generator = os.path.join("..", "ceinms_calibration",
                                                 "excitationGenerator.xml")
    for k, v in attrs.items():
        setattr(t, k, v)
    return t


def test_default_is_the_calibrated_subject(tmp_path):
    t = make_trial(tmp_path)
    assert t.ceinms_is_calibrated is True
    assert t.ceinms_execution_subject.endswith("subjectCalibrated.xml")
    assert t.ceinms_exe_tag == ""


def test_flag_selects_the_uncalibrated_subject(tmp_path):
    t = make_trial(tmp_path, ceinms_calibrated=False)
    assert t.ceinms_is_calibrated is False
    assert t.ceinms_execution_subject.endswith("subjectUncalibrated.xml")


def test_overrides_win_over_the_attribute(tmp_path):
    """session.yaml lands in _overrides, and _overrides is authoritative."""
    t = make_trial(tmp_path, ceinms_calibrated=True,
                   _overrides={"ceinms_calibrated": False})
    assert t.ceinms_is_calibrated is False
    assert t.ceinms_execution_subject.endswith("subjectUncalibrated.xml")


def test_overrides_without_the_key_do_not_mask_the_attribute(tmp_path):
    t = make_trial(tmp_path, ceinms_calibrated=False, _overrides={"gamma": 30})
    assert t.ceinms_is_calibrated is False


def test_quoted_false_on_the_trial(tmp_path):
    t = make_trial(tmp_path, ceinms_calibrated="false")
    assert t.ceinms_is_calibrated is False


# ==========================================  the output folder is tagged
def test_calibrated_folder_name_is_unchanged(tmp_path):
    """The name every existing result on disk already carries."""
    t = make_trial(tmp_path)
    assert os.path.basename(t.ceinms_exe_out_rel()) == "Execution_a1_b1_g30"


def test_uncalibrated_folder_is_tagged(tmp_path):
    t = make_trial(tmp_path, ceinms_calibrated=False)
    assert os.path.basename(t.ceinms_exe_out_rel()) == "Execution_uncal_a1_b1_g30"


def test_tagged_folder_still_matches_the_mode_glob(tmp_path):
    """``ceinms.modes`` finds a solve by globbing ``Execution_*``."""
    import fnmatch
    t = make_trial(tmp_path, ceinms_calibrated=False)
    assert fnmatch.fnmatch(os.path.basename(t.ceinms_exe_out_rel()),
                           "Execution_*")


# ==============================  the setup XML names the right subject file
def _subject_file(setup_path):
    named = ET.parse(setup_path).getroot().findtext("subjectFile")
    return os.path.normpath(os.path.join(os.path.dirname(setup_path), named))


def test_setup_xml_names_the_uncalibrated_subject(tmp_path, monkeypatch):
    # `save_pretty_xml` writes to the path it is given, relative to the CWD;
    # the production caller chdirs into the trial first.
    monkeypatch.chdir(tmp_path)
    t = make_trial(tmp_path, ceinms_calibrated=False)
    t.create_ceinms_exe_setup()
    got = _subject_file(os.path.join(str(tmp_path), t.ceinms_exe_setup))
    assert os.path.basename(got) == "subjectUncalibrated.xml"


def test_setup_xml_still_names_the_calibrated_subject_by_default(tmp_path,
                                                                 monkeypatch):
    monkeypatch.chdir(tmp_path)
    t = make_trial(tmp_path)
    t.create_ceinms_exe_setup()
    got = _subject_file(os.path.join(str(tmp_path), t.ceinms_exe_setup))
    assert os.path.basename(got) == "subjectCalibrated.xml"
