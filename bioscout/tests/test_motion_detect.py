"""Tests for movement-window detection.

Synthetic TRC files with a known window, so the assertions do not depend on
anyone's data. The one property worth pinning hardest is the fallback: an
undetectable trial must return the FULL capture and say so, because silently
returning a plausible-looking wrong window is the failure mode that would
corrupt a study without anyone noticing.
"""
from __future__ import annotations

import numpy as np

from bioscout.utils.motion_detect import (
    DEFAULT_THRESHOLD, TimeRange, detect_time_range, read_trc,
)

FS = 200.0
DUR = 8.0
T = np.arange(0, DUR, 1 / FS)


def _write_trc(path, markers: dict, t=T):
    """Minimal but real TRC: OpenSim's blank-separated triplet layout."""
    names = list(markers)
    n = len(t)
    head = [
        f"PathFileType\t4\t(X/Y/Z)\t{path}",
        "DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\tOrigDataRate\t"
        "OrigDataStartFrame\tOrigNumFrames",
        f"{FS:.6f}\t{int(FS)}\t{n}\t{len(names)}\tmm\t{FS:.6f}\t0\t{n}",
        "Frame#\tTime\t" + "\t\t\t".join(names) + "\t\t\t",
        "\t\t" + "\t".join(f"X{i+1}\tY{i+1}\tZ{i+1}" for i in range(len(names))),
    ]
    rows = []
    for i in range(n):
        vals = [str(i + 1), f"{t[i]:.5f}"]
        for nm in names:
            x, y, z = markers[nm][i]
            vals += [f"{x:.4f}", f"{y:.4f}", f"{z:.4f}"]
        rows.append("\t".join(vals))
    path.write_text("\n".join(head + rows) + "\n", encoding="utf-8")


def _bar(y):
    """(n, 3) array with a constant x/z and the given vertical trace."""
    return np.stack([np.full_like(y, 100.0), y, np.full_like(y, -50.0)], axis=1)


def _squat_trace(t0=2.0, t1=5.0, top=1300.0, bottom=800.0):
    """Bar rests high, dips between t0 and t1, returns."""
    y = np.full_like(T, top)
    m = (T >= t0) & (T <= t1)
    phase = (T[m] - t0) / (t1 - t0)
    y[m] = top - (top - bottom) * np.sin(np.pi * phase)
    return y


def _deadlift_trace(t0=3.0, t1=6.0, floor=250.0, lockout=900.0):
    """Bar rests on the floor, rises between t0 and t1, returns."""
    y = np.full_like(T, floor)
    m = (T >= t0) & (T <= t1)
    phase = (T[m] - t0) / (t1 - t0)
    y[m] = floor + (lockout - floor) * np.sin(np.pi * phase)
    return y


def test_squat_window_is_found_and_slightly_generous(tmp_path):
    d = tmp_path / "Squat_01"
    d.mkdir()
    _write_trc(d / "marker_experimental.trc",
               {"BL": _bar(_squat_trace()), "BR": _bar(_squat_trace())})
    tr = detect_time_range(d)
    assert tr.method == "bar"
    assert tr.detected
    # A 5%-of-range threshold cuts in slightly INSIDE the true window, so the
    # detected span is a little shorter — never longer.
    assert 2.0 <= tr.start <= 2.4
    assert 4.6 <= tr.end <= 5.0
    assert "falling" in tr.note


def test_deadlift_direction_is_inferred_not_assumed(tmp_path):
    d = tmp_path / "Deadlift_01"
    d.mkdir()
    _write_trc(d / "marker_experimental.trc",
               {"BL": _bar(_deadlift_trace()), "BR": _bar(_deadlift_trace())})
    tr = detect_time_range(d)
    assert tr.method == "bar"
    assert "rising" in tr.note          # bar starts low -> it goes up
    assert 3.0 <= tr.start <= 3.4
    assert 5.6 <= tr.end <= 6.0


def test_pelvis_is_used_when_there_is_no_bar(tmp_path):
    d = tmp_path / "Squat_02"
    d.mkdir()
    _write_trc(d / "marker_experimental.trc",
               {"SACROL": _bar(_squat_trace(top=950.0, bottom=520.0))})
    tr = detect_time_range(d)
    assert tr.method == "pelvis"
    assert tr.reference == "SACROL"


def test_motionless_trial_falls_back_to_the_full_capture(tmp_path):
    d = tmp_path / "Static_01"
    d.mkdir()
    flat = np.full_like(T, 1000.0)
    _write_trc(d / "marker_experimental.trc", {"BL": _bar(flat)})
    tr = detect_time_range(d)
    assert tr.method == "full"
    assert not tr.detected
    assert tr.start == 0.0
    assert abs(tr.end - T[-1]) < 1e-6
    assert "no movement detected" in tr.note


def test_missing_files_fall_back_rather_than_raising(tmp_path):
    d = tmp_path / "Empty_01"
    d.mkdir()
    tr = detect_time_range(d)
    assert tr.method == "full"
    assert tr.start == tr.end == 0.0
    assert "no marker or GRF" in tr.note


def test_vertical_axis_is_detected_not_assumed(tmp_path):
    """Same movement written with Z vertical must give the same window."""
    d = tmp_path / "Squat_Z"
    d.mkdir()
    y = _squat_trace()
    swapped = np.stack([np.full_like(y, 100.0), np.full_like(y, -50.0), y], axis=1)
    _write_trc(d / "marker_experimental.trc", {"BL": swapped})
    tr = detect_time_range(d)
    assert tr.detected
    assert 2.0 <= tr.start <= 2.4


def test_short_blips_do_not_count_as_a_movement(tmp_path):
    d = tmp_path / "Blip_01"
    d.mkdir()
    y = np.full_like(T, 1000.0)
    y[100:110] = 400.0                  # 50 ms spike, below MIN_DURATION
    _write_trc(d / "marker_experimental.trc", {"BL": _bar(y)})
    tr = detect_time_range(d)
    assert tr.method == "full"


def test_time_range_rounds_for_yaml(tmp_path):
    tr = TimeRange(1.23456, 4.98765, "bar")
    assert tr.as_list() == [1.235, 4.988]
    assert abs(tr.duration - 3.75309) < 1e-9


def test_read_trc_handles_gaps(tmp_path):
    d = tmp_path / "Gap_01"
    d.mkdir()
    y = _squat_trace()
    _write_trc(d / "marker_experimental.trc", {"BL": _bar(y)})
    txt = (d / "marker_experimental.trc").read_text(encoding="utf-8").splitlines()
    txt[20] = "\t".join(txt[20].split("\t")[:2] + ["", "", ""])   # a dropped frame
    (d / "marker_experimental.trc").write_text("\n".join(txt) + "\n", encoding="utf-8")
    t, markers = read_trc(d / "marker_experimental.trc")
    assert np.isnan(markers["BL"][15]).all()
    assert detect_time_range(d).detected        # a gap must not break detection
