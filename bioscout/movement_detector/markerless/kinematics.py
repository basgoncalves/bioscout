"""
kinematics.py -- pull-up rep detection and joint angles from 2-D pose landmarks.

Ported from the desktop scripts (run_analysis.py, export_mot_scaled.py) with
pandas and matplotlib stripped out: this module is numpy-only so it survives a
python-for-android build. Behaviour is intended to be identical to the desktop
pipeline for the same config.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

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

# OpenSim coordinates this pipeline can actually drive from a single camera.
DRIVEN_COORDS = [
    "pelvis_tilt", "pelvis_tx", "pelvis_ty", "pelvis_tz",
    "hip_flexion_r", "hip_flexion_l", "knee_angle_r", "knee_angle_l",
    "arm_flex_r", "arm_flex_l", "elbow_flex_r", "elbow_flex_l",
    "flex_extension",
]


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


# --------------------------------------------------------------------------
# feature extraction
# --------------------------------------------------------------------------
def build_features(poses):
    """poses: {frame_index: {landmark_name: (x_px, y_px)}} -> feature dict.

    Image coordinates, so y grows downward: a smaller y means higher up.
    """
    frames = sorted(poses.keys())
    if not frames:
        raise ValueError("no pose frames")
    lo, hi = frames[0], frames[-1]
    n = hi - lo + 1

    keys = ["shoulder_cy", "hip_cy", "wrist_cy", "nose_y",
            "elbow", "shoulder", "hip", "knee", "trunk", "hip_cx"]
    F = {k: np.full(n, np.nan) for k in keys}

    for fi, lm in poses.items():
        i = fi - lo
        g = lm.get
        ls, rs = g("left_shoulder"), g("right_shoulder")
        lh, rh = g("left_hip"), g("right_hip")
        le, re = g("left_elbow"), g("right_elbow")
        lw, rw = g("left_wrist"), g("right_wrist")
        lk, rk = g("left_knee"), g("right_knee")
        la, ra = g("left_ankle"), g("right_ankle")
        nose = g("nose")

        sh, hp, wr = _mid(ls, rs), _mid(lh, rh), _mid(lw, rw)
        if sh:
            F["shoulder_cy"][i] = sh[1]
        if hp:
            F["hip_cy"][i] = hp[1]
            F["hip_cx"][i] = hp[0]
        if wr:
            F["wrist_cy"][i] = wr[1]
        if nose:
            F["nose_y"][i] = nose[1]

        F["elbow"][i] = np.nanmean([_angle3(ls, le, lw), _angle3(rs, re, rw)])
        F["shoulder"][i] = np.nanmean([_angle3(lh, ls, le), _angle3(rh, rs, re)])
        F["hip"][i] = np.nanmean([_angle3(ls, lh, lk), _angle3(rs, rh, rk)])
        F["knee"][i] = np.nanmean([_angle3(lh, lk, la), _angle3(rh, rk, ra)])
        if sh and hp:
            dx, dy = hp[0] - sh[0], hp[1] - sh[1]
            F["trunk"][i] = abs(math.degrees(math.atan2(dx, dy)))

    torso = np.abs(F["shoulder_cy"] - F["hip_cy"])
    scale = np.nanmedian(torso)
    if not (scale and scale > 1e-6):
        scale = 1.0

    with np.errstate(invalid="ignore"):
        # Hands overhead: shoulders sit well below the wrists.
        F["hands_overhead"] = (
            (F["shoulder_cy"] - F["wrist_cy"]) > 0.30 * scale).astype(float)
    F["hands_overhead"][np.isnan(F["wrist_cy"]) | np.isnan(F["shoulder_cy"])] = np.nan

    dead = np.nanpercentile(F["shoulder_cy"], 90)  # lowest body position
    with np.errstate(invalid="ignore"):
        F["rise"] = (dead - F["shoulder_cy"]) / scale
        F["chin_gap"] = (F["nose_y"] - F["wrist_cy"]) / scale

    F["_lo"] = lo
    F["_n"] = n
    F["_scale"] = scale
    F["_coverage"] = len(poses) / n
    return F


# --------------------------------------------------------------------------
# rep detection
# --------------------------------------------------------------------------
@dataclass
class PullupConfig:
    name: str = "default"
    top_rise_frac: float = 0.50
    min_rep_frames: int = 12
    min_elbow_flexion_deg: float = 40.0
    smooth_win: int = 5
    require_overhead: bool = True

    def as_dict(self):
        return asdict(self)


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


def find_reps(F, cfg: PullupConfig):
    """-> ([(bottom0, top, bottom1), ...], smoothed_rise)

    hands_overhead is True at the dead hang but flips False at the TOP of a
    full rep (the shoulders rise to the hands), so the rep PEAK is never gated
    on overhead -- only the bout is.
    """
    n = F["_n"]
    rise = smooth(interp_nan(F["rise"]), cfg.smooth_win)
    elbow = interp_nan(F["elbow"])
    overhead = np.nan_to_num(
        F.get("hands_overhead", np.full(n, np.nan)), nan=0.0) > 0.5

    tops = _local_maxima(rise, cfg.min_rep_frames, cfg.top_rise_frac)
    reps = []
    for k, top in enumerate(tops):
        left = tops[k - 1] if k > 0 else 0
        right = tops[k + 1] if k < len(tops) - 1 else n - 1
        b0 = left + int(np.argmin(rise[left:top + 1])) if top > left else left
        b1 = top + int(np.argmin(rise[top:right + 1])) if right > top else right

        eb = float(np.nanmax([elbow[b0], elbow[b1]]))
        et = float(elbow[top])
        if np.isfinite(eb) and np.isfinite(et) and (eb - et) < cfg.min_elbow_flexion_deg:
            continue
        if (b1 - b0) < cfg.min_rep_frames:
            continue
        if (top - b0) < 3 or (b1 - top) < 3:
            continue
        if cfg.require_overhead:
            bout = overhead[b0:b1 + 1]
            if not (overhead[b0] or overhead[b1] or bout.mean() >= 0.5):
                continue
        reps.append((b0, top, b1))
    return reps, rise


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


# --------------------------------------------------------------------------
# OpenSim coordinate export
# --------------------------------------------------------------------------
def rep_coordinates(F, rep, fps, px_per_m, dead_hang_y, mid_x):
    """One rep -> (times, {coord_name: array}) in OpenSim conventions.

    Left and right are mirrored: a single camera cannot separate the sides.
    """
    b0, top, b1 = rep
    lo = F["_lo"]
    sl = slice(b0, b1 + 1)

    elbow = interp_nan(F["elbow"])[sl]
    shoulder = interp_nan(F["shoulder"])[sl]
    hip = interp_nan(F["hip"])[sl]
    knee = interp_nan(F["knee"])[sl]
    trunk = interp_nan(F["trunk"])[sl]
    hip_y = interp_nan(F["hip_cy"])[sl]
    hip_x = interp_nan(F["hip_cx"])[sl]

    times = (lo + np.arange(b0, b1 + 1)) / fps

    pelvis_ty = (dead_hang_y - hip_y) / px_per_m   # up = +metres
    pelvis_tz = (hip_x - mid_x) / px_per_m         # lateral sway

    hip_flex = np.clip(180.0 - hip, -20, 120)
    knee_ang = np.clip(180.0 - knee, 0, 140)
    arm_flex = np.clip(shoulder, 0, 180)
    elbow_flex = np.clip(180.0 - elbow, 0, 150)
    lumbar = np.clip(trunk, -30, 30)
    z = np.zeros_like(times)

    return times, {
        "pelvis_tilt": z, "pelvis_tx": z, "pelvis_ty": pelvis_ty, "pelvis_tz": pelvis_tz,
        "hip_flexion_r": hip_flex, "hip_flexion_l": hip_flex,
        "knee_angle_r": knee_ang, "knee_angle_l": knee_ang,
        "arm_flex_r": arm_flex, "arm_flex_l": arm_flex,
        "elbow_flex_r": elbow_flex, "elbow_flex_l": elbow_flex,
        "flex_extension": lumbar,
    }


def reference_positions(F):
    """(dead_hang_y, mid_x) in pixels -- the pelvis-translation datum."""
    hip_y = interp_nan(F["hip_cy"])
    hip_x = interp_nan(F["hip_cx"])
    return float(np.nanpercentile(hip_y, 90)), float(np.nanmedian(hip_x))


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
