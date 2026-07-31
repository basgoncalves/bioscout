"""Tests for EMG frequency content and synergy extraction.

Constructed signals with a known answer: a sine at a known frequency must land
in the right band, and a 3-channel set built from 2 underlying drives must be
recovered by 2 synergies.
"""
from __future__ import annotations

import numpy as np

from bioscout.utils.emg_analysis import (
    envelope, frequency_report, median_frequency, power_spectrum,
    synergies, synergy_report, vaf_curve,
)

FS = 1000.0
T = np.arange(0, 4, 1 / FS)


def _two_synergy_set(seed=0):
    """3 channels driven by 2 bursts — the ground truth is 2 synergies."""
    rng = np.random.default_rng(seed)
    a1 = np.exp(-((T - 1.0) ** 2) / 0.05)
    a2 = np.exp(-((T - 3.0) ** 2) / 0.05)
    return {
        "m1": (2.0 * a1) * rng.normal(size=T.size),
        "m2": (1.5 * a1 + 0.2 * a2) * rng.normal(size=T.size),
        "m3": (2.0 * a2) * rng.normal(size=T.size),
    }


def test_power_spectrum_peaks_at_the_input_frequency():
    f, p = power_spectrum(np.sin(2 * np.pi * 120 * T), FS)
    assert abs(f[int(np.argmax(p))] - 120.0) < 3.0


def test_median_frequency_of_a_pure_tone_is_that_tone():
    f, p = power_spectrum(np.sin(2 * np.pi * 80 * T), FS)
    assert abs(median_frequency(f, p) - 80.0) < 5.0


def test_mains_contamination_is_flagged_on_the_bad_channel_only():
    ch = _two_synergy_set()
    ch["m3"] = ch["m3"] + 0.5 * np.sin(2 * np.pi * 50 * T)
    rep = frequency_report(ch, FS)
    assert rep["m3"].mains_flag
    assert not rep["m1"].mains_flag
    assert not rep["m2"].mains_flag


def test_low_frequency_artefact_is_flagged():
    ch = {"m1": np.random.default_rng(1).normal(size=T.size)
          + 8.0 * np.sin(2 * np.pi * 3 * T)}
    assert frequency_report(ch, FS)["m1"].artefact_flag


def test_envelope_is_non_negative_and_smooth():
    e = envelope(np.random.default_rng(2).normal(size=T.size), FS)
    assert (e >= -1e-9).all()
    # a 6 Hz low-pass must have far less sample-to-sample variation than raw
    raw = np.abs(np.random.default_rng(2).normal(size=T.size))
    assert np.std(np.diff(e)) < np.std(np.diff(raw)) / 5


def test_two_underlying_drives_are_recovered_by_two_synergies():
    rep = synergy_report(_two_synergy_set(), FS, vaf_target=0.90)
    assert rep["n_chosen"] == 2
    assert rep["curve"][1].vaf > 0.9          # 2 synergies clear the target
    assert rep["curve"][0].vaf < 0.9          # 1 does not


def test_vaf_rises_monotonically_with_synergy_count():
    # True by construction, and the reason the count needs an elbow rather than
    # a maximum — worth pinning so nobody "fixes" the curve into a peak.
    envs = {k: envelope(v, FS) for k, v in _two_synergy_set().items()}
    vafs = [r.vaf for r in vaf_curve(envs)]
    assert all(b >= a - 1e-9 for a, b in zip(vafs, vafs[1:]))


def test_synergy_shapes_and_reproducibility():
    envs = {k: envelope(v, FS) for k, v in _two_synergy_set().items()}
    a = synergies(envs, 2, random_state=0)
    b = synergies(envs, 2, random_state=0)
    assert a.weights.shape == (3, 2)
    assert a.activations.shape == (2, T.size)
    assert np.allclose(a.vaf, b.vaf)          # fixed seed -> same answer
    assert (a.weights >= -1e-9).all() and (a.activations >= -1e-9).all()


def test_synergy_count_is_validated():
    envs = {k: envelope(v, FS) for k, v in _two_synergy_set().items()}
    for bad in (0, 4):
        try:
            synergies(envs, bad)
        except ValueError:
            continue
        raise AssertionError(f"n={bad} should have raised")
