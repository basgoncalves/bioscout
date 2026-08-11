"""``emg_gain`` — a per-channel multiplier on the SESSION-NORMALISED EMG.

The thing worth pinning down is not the arithmetic, it is the two silent
failures the key exists to make impossible:

* scaling the raw ``emg.mot`` is an exact NO-OP, because ``run_emg_normalise``
  divides each channel by its own session maximum and the factor divides
  straight back out. The gain therefore has to land AFTER the division;
* a channel name that is not in the data must RAISE. Passing it through would
  finish the run normally, hours later, on the unscaled signal.

    pytest bioscout/tests/test_emg_gain.py
"""

import textwrap

import pytest
import yaml

from bioscout.utils import session as S


CHANS = ["EMG_Channels_EMG01_vast_lat_l",
         "EMG_Channels_EMG09_gast_med_l",
         "EMG_Channels_EMG10_gast_med_r"]


def cfg(text):
    return yaml.safe_load(textwrap.dedent(text)) or {}


GAIN = """\
    subject: A03
    session: '25_03_31'
    emg_gain:
      EMG_Channels_EMG09_gast_med_l: 0.70
      EMG_Channels_EMG10_gast_med_r: 0.70
    trials:
      Walking_03: {type: walking}
"""


# ------------------------------------------------------------------ basics
def test_absent_block_is_no_gain():
    assert S.resolve_emg_gain(cfg("subject: A03")) == {}
    assert S.resolve_emg_gain({}) == {}
    assert S.resolve_emg_gain(None) == {}
    assert S.raw_emg_gain(None) == {}


def test_the_named_channels_get_their_factor():
    g = S.resolve_emg_gain(cfg(GAIN), channels=CHANS)
    assert g == {"EMG_Channels_EMG09_gast_med_l": 0.70,
                 "EMG_Channels_EMG10_gast_med_r": 0.70}
    # every other channel is untouched -- absence means 1.0, never 0.0
    assert "EMG_Channels_EMG01_vast_lat_l" not in g
    assert g.get("EMG_Channels_EMG01_vast_lat_l", 1.0) == 1.0


def test_integer_and_string_factors_are_accepted():
    g = S.resolve_emg_gain(cfg("""\
        emg_gain: {EMG_Channels_EMG09_gast_med_l: '0.7', EMG_Channels_EMG10_gast_med_r: 1}
    """), channels=CHANS)
    assert g["EMG_Channels_EMG09_gast_med_l"] == pytest.approx(0.7)
    assert g["EMG_Channels_EMG10_gast_med_r"] == 1.0


# ------------------------------------------------------- the loud failures
def test_a_channel_not_in_the_data_raises():
    with pytest.raises(ValueError, match="no such EMG channel"):
        S.resolve_emg_gain(cfg("""\
            emg_gain: {EMG_Channels_EMG09_gastroc_l: 0.7}
        """), channels=CHANS)


def test_the_error_names_the_channels_that_are_there():
    with pytest.raises(ValueError, match="EMG_Channels_EMG01_vast_lat_l"):
        S.resolve_emg_gain(cfg("emg_gain: {typo: 0.7}"), channels=CHANS)


@pytest.mark.parametrize("bad", ["0", "-0.5", "'abc'", "null"])
def test_a_non_positive_or_non_numeric_factor_raises(bad):
    with pytest.raises(ValueError, match="emg_gain is invalid"):
        S.resolve_emg_gain(cfg("emg_gain: {EMG_Channels_EMG09_gast_med_l: %s}" % bad),
                           channels=CHANS)


def test_no_channel_list_means_no_membership_check():
    """Read-only consumers that have not loaded the data still get the factors."""
    assert S.resolve_emg_gain(cfg("emg_gain: {whatever: 0.5}")) == {"whatever": 0.5}


def test_lenient_mode_warns_and_drops_instead_of_raising(capsys):
    g = S.resolve_emg_gain(cfg("""\
        emg_gain: {EMG_Channels_EMG09_gast_med_l: 0.7, nope: 0.5}
    """), channels=CHANS, strict=False)
    assert g == {"EMG_Channels_EMG09_gast_med_l": 0.7}
    assert "emg_gain is invalid" in capsys.readouterr().out


# --------------------------------------------------- the shape of the block
def test_there_is_no_named_form():
    """A NESTED block is not a set of named gains -- it is a mistake.

    `emg_map` and `calibration` are named-and-selected per iteration because
    each produces a per-iteration file. `emg_gain` rewrites ONE file under
    2_experimental/ that every iteration reads, so a per-iteration gain cannot
    be honoured. It must not look like it is.
    """
    with pytest.raises(ValueError, match="emg_gain is invalid"):
        S.resolve_emg_gain(cfg("""\
            emg_gain:
              scaled:   {EMG_Channels_EMG09_gast_med_l: 0.7}
              baseline: {EMG_Channels_EMG09_gast_med_l: 1.0}
        """), channels=CHANS)


def test_a_gain_block_survives_a_yaml_round_trip():
    text = yaml.safe_dump(cfg(GAIN), sort_keys=False)
    assert S.resolve_emg_gain(yaml.safe_load(text), channels=CHANS) == \
        S.resolve_emg_gain(cfg(GAIN), channels=CHANS)


# ------------------------------------------------------- the arithmetic bit
def test_gain_applies_after_the_session_max_division():
    """The property the whole key depends on, stated as arithmetic.

    Raw scaling: max(k*x)/... == max(x)/... -- the factor cancels. Normalised
    scaling: g * (x/max(x)) -- it does not. If this ever stops holding, the
    gain has been moved to the wrong side of the division.
    """
    raw = [0.0, 0.4, 1.0, 0.25]
    k = 0.70

    def normalise(v):
        m = max(v) or 1.0
        return [min(x / m, 1.0) for x in v]

    assert normalise([k * x for x in raw]) == normalise(raw)          # no-op
    after = [k * x for x in normalise(raw)]
    assert after == pytest.approx([0.0, 0.28, 0.70, 0.175])
    assert max(after) == pytest.approx(k)


def test_a_gain_above_one_is_clipped_by_the_writer():
    """resolve_emg_gain allows > 1; run_emg_normalise re-clips to [0, 1].

    CEINMS accepts excitations in [0, 1] only, so the clip is not optional --
    but it belongs at the write, not here, so the intent stays readable.
    """
    assert S.resolve_emg_gain(cfg("emg_gain: {EMG_Channels_EMG09_gast_med_l: 1.4}"),
                              channels=CHANS)["EMG_Channels_EMG09_gast_med_l"] == 1.4
    assert min(1.4 * 0.8, 1.0) == pytest.approx(1.0)
