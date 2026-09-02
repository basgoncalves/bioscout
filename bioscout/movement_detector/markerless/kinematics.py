"""
kinematics.py -- shared geometry for markerless single-camera analysis.

Landmark naming, angle and smoothing helpers, the pixel-to-metre scaling and
the view-quality check: everything that is true of any movement seen from one
camera. The per-movement logic -- what counts as a rep, which OpenSim
coordinates it drives -- lives in the activity module (pullup.py, squat.py),
never here. A helper that only one activity needs is a sign it is in the wrong
file.

Ported from the desktop scripts (run_analysis.py, export_mot_scaled.py) with
pandas and matplotlib stripped out: numpy-only, so it survives a
python-for-android build and runs anywhere the package installs.
"""
from __future__ import annotations

import math

import numpy as np

# MediaPipe Pose 33-landmark order (matches BioScout naming).
LANDMARK_NAMES = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer",
    "right_eye_inner", "right_eye", "right_eye_outer",
    "left_ear", "right_ear", "mouth_left", "mouth_right",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_pinky", "right_pinky",
    "left_index", "right_index", "left_thumb", "right_thumb",
    "left_hip", "right_hip", "left_knee", "right_knee",
    "left_ankle", "right_ankle", "left_heel", "right_heel",
    "left_foot_index", "right_foot_index",
]

# Winter / Drillis-Contini segment length as a fraction of stature.
DEFAULT_FRACTIONS = {
    "trunk": 0.288, "thigh": 0.245, "shank": 0.246,
    "upper_arm": 0.186, "forearm": 0.146,
}

# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------
def _angle3(a, b, c) -> float:
    """Interior angle at b, in degrees. NaN if any point is missing."""
    if a is None or b is None or c is None:
        return float("nan")
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag = math.hypot(*v1) * math.hypot(*v2)
    if mag < 1e-9:
        return float("nan")
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / mag))))


def _mid(a, b):
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)


def _seg_len(lm, a, b) -> float:
    pa, pb = lm.get(a), lm.get(b)
    if pa and pb:
        return math.hypot(pa[0] - pb[0], pa[1] - pb[1])
    return float("nan")


def interp_nan(arr):
    """Linear-interpolate interior NaNs; all-NaN becomes zeros."""
    arr = np.asarray(arr, float).copy()
    nans = np.isnan(arr)
    if nans.all():
        return np.zeros_like(arr)
    if nans.any():
        idx = np.arange(len(arr))
        arr[nans] = np.interp(idx[nans], idx[~nans], arr[~nans])
    return arr


def smooth(arr, win):
    if win <= 1 or len(arr) < win:
        return np.asarray(arr, float)
    return np.convolve(np.asarray(arr, float), np.ones(win) / win, mode="same")


def _local_maxima(arr, min_distance, min_height):
    n = len(arr)
    cand = [i for i in range(1, n - 1)
            if arr[i] >= min_height and arr[i] >= arr[i - 1] and arr[i] > arr[i + 1]]
    cand.sort(key=lambda i: arr[i], reverse=True)
    chosen = []
    for i in cand:
        if all(abs(i - j) >= min_distance for j in chosen):
            chosen.append(i)
    chosen.sort()
    return chosen


# --------------------------------------------------------------------------
# pixel -> metre scaling
# --------------------------------------------------------------------------
_SEGMENT_PAIRS = {
    "trunk":     [("left_shoulder", "left_hip"), ("right_shoulder", "right_hip")],
    "thigh":     [("left_hip", "left_knee"), ("right_hip", "right_knee")],
    "shank":     [("left_knee", "left_ankle"), ("right_knee", "right_ankle")],
    "upper_arm": [("left_shoulder", "left_elbow"), ("right_shoulder", "right_elbow")],
    "forearm":   [("left_elbow", "left_wrist"), ("right_elbow", "right_wrist")],
}


def compute_px_per_m(poses, height_m, fractions=None):
    """Median px-per-metre from rigid bone pixel lengths vs their metric length.

    Resolution differs between clips, so this is recomputed per video; the
    subject's stature is the shared constant.
    """
    fractions = {**DEFAULT_FRACTIONS, **(fractions or {})}
    ests, detail = [], {}
    for seg, pairs in _SEGMENT_PAIRS.items():
        lengths = []
        for lm in poses.values():
            for a, b in pairs:
                L = _seg_len(lm, a, b)
                if np.isfinite(L):
                    lengths.append(L)
        if not lengths:
            continue
        med_px = float(np.median(lengths))
        metric = fractions[seg] * height_m
        est = med_px / metric
        ests.append(est)
        detail[seg] = {"median_px": round(med_px, 1),
                       "metric_m": round(metric, 3),
                       "px_per_m": round(est, 1)}
    if not ests:
        raise ValueError("no usable segments for pixel scaling")
    return float(np.median(ests)), detail


def view_quality(poses):
    """How side-on the camera is, and whether the feet are usable.

    Every angle this pipeline computes is a SAGITTAL angle, which is only
    meaningful from the side. Filmed face-on, the knee and hip still produce
    plausible-looking numbers while measuring something else entirely, and the
    ankle degenerates completely -- so this has to be checked, not assumed.

    frontality = shoulder separation / torso length.
        ~0.1  fully side-on, the intended view
        ~0.6  fully face-on, sagittal angles are not valid

    ankle_usable is False when the foot is pointing at or away from the camera,
    which collapses the knee-ankle-toe angle onto a straight line.
    """
    seps, torsos, ankle_angles = [], [], []
    for lm in poses.values():
        ls, rs = lm.get("left_shoulder"), lm.get("right_shoulder")
        lh, rh = lm.get("left_hip"), lm.get("right_hip")
        if ls and rs:
            seps.append(abs(ls[0] - rs[0]))
        sh, hp = _mid(ls, rs), _mid(lh, rh)
        if sh and hp:
            torsos.append(math.hypot(sh[0] - hp[0], sh[1] - hp[1]))
        for side in ("left", "right"):
            a = _angle3(lm.get("%s_knee" % side), lm.get("%s_ankle" % side),
                        lm.get("%s_foot_index" % side))
            if np.isfinite(a):
                ankle_angles.append(a)

    torso = np.median(torsos) if torsos else 1.0
    frontality = float(np.median(seps) / torso) if seps and torso > 1e-6 else float("nan")

    # A foot seen end-on makes knee-ankle-toe collinear (near 180 deg).
    ankle_usable = bool(ankle_angles) and float(np.median(ankle_angles)) < 155.0

    if not np.isfinite(frontality):
        view = "unknown"
    elif frontality < 0.30:
        view = "sagittal"
    elif frontality < 0.45:
        view = "oblique"
    else:
        view = "frontal"
    return {"frontality": round(frontality, 3) if np.isfinite(frontality) else None,
            "view": view,
            "ankle_usable": ankle_usable,
            "median_ankle_interior_deg": round(float(np.median(ankle_angles)), 1)
            if ankle_angles else None}


def write_mot(path, name, colnames, rows):
    with open(path, "w") as w:
        w.write(name + "\n")
        w.write("version=1\n")
        w.write("nRows=%d\n" % len(rows))
        w.write("nColumns=%d\n" % len(colnames))
        w.write("inDegrees=yes\n")
        w.write("endheader\n")
        w.write("\t".join(colnames) + "\n")
        for r in rows:
            w.write("\t".join("%16.8f" % v for v in r) + "\n")
