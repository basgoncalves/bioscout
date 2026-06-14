"""
features.py — extract kinematic time-series features from a pose dict.

Input
-----
poses : dict[int, dict[str, tuple[float, float]]]
    {frame_idx: {landmark_name: (x_px, y_px)}}
fps   : float

Output
------
FeatureArray : dict[str, np.ndarray]
    Arrays of length (max_frame - min_frame + 1), NaN where data is missing.
    Index 0 = min_frame.
min_frame : int
"""

from __future__ import annotations
import math
import numpy as np
from typing import Dict, Tuple


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_features(
    poses: Dict[int, Dict[str, Tuple[float, float]]],
    fps: float,
) -> Tuple[Dict[str, np.ndarray], int]:
    """Return (feature_arrays, min_frame)."""
    if not poses:
        return {}, 0

    all_frames = sorted(poses.keys())
    min_fi = all_frames[0]
    max_fi = all_frames[-1]
    n = max_fi - min_fi + 1

    F: Dict[str, np.ndarray] = {k: np.full(n, np.nan) for k in _FEATURE_KEYS}

    for fi, lm in poses.items():
        idx = fi - min_fi
        _fill_frame(F, idx, lm)

    # --- velocities (central differences, px/frame) -------------------------
    for raw, vel in (
        ("hip_cx",        "vx"),
        ("hip_cy",        "vy"),
        ("left_heel_y",   "left_heel_vy"),
        ("right_heel_y",  "right_heel_vy"),
    ):
        arr = F[raw].copy()
        # interpolate small gaps so gradient doesn't explode at edges
        arr = _interp_nan(arr)
        F[vel] = np.gradient(arr)
        F[vel][np.isnan(F[raw])] = np.nan

    # speed magnitude
    F["speed"] = np.hypot(
        np.where(np.isnan(F["vx"]), 0.0, F["vx"]),
        np.where(np.isnan(F["vy"]), 0.0, F["vy"]),
    )
    F["speed"][np.isnan(F["hip_cx"]) & np.isnan(F["hip_cy"])] = np.nan

    # lateral ratio: |vx| / speed  (1 = pure lateral, 0 = pure vertical/fwd)
    with np.errstate(invalid="ignore", divide="ignore"):
        F["lateral_ratio"] = np.where(
            F["speed"] > 1e-3,
            np.abs(F["vx"]) / F["speed"],
            np.nan,
        )

    # signed lateral velocity (positive = rightward in image)
    F["lateral_vel"] = F["vx"].copy()

    # acceleration of speed
    spd = _interp_nan(F["speed"].copy())
    F["accel"] = np.gradient(spd)
    F["accel"][np.isnan(F["speed"])] = np.nan

    # squat depth ratio: current hip_ankle_dist / baseline (median)
    had = F["hip_ankle_dist"]
    baseline = np.nanmedian(had)
    if baseline and baseline > 0:
        F["squat_ratio"] = had / baseline
    else:
        F["squat_ratio"][:] = np.nan

    # backward flag: moving opposite to the dominant forward direction
    # We use the sign of vx (or vy depending on dominant axis) relative to
    # the median velocity over the whole clip.
    median_vx = np.nanmedian(F["vx"])
    median_vy = np.nanmedian(F["vy"])
    # dominant axis is whichever has higher absolute median
    if abs(median_vy) >= abs(median_vx):
        # side-view: forward = dominant vy direction
        dom_sign = np.sign(median_vy) if median_vy != 0 else 1.0
        F["backward"] = (np.sign(F["vy"]) != dom_sign).astype(float)
        F["backward"][np.isnan(F["vy"])] = np.nan
    else:
        # front-view with lateral drift: use vx
        dom_sign = np.sign(median_vx) if median_vx != 0 else 1.0
        F["backward"] = (np.sign(F["vx"]) != dom_sign).astype(float)
        F["backward"][np.isnan(F["vx"])] = np.nan

    return F, min_fi


# ---------------------------------------------------------------------------
# Per-frame fill
# ---------------------------------------------------------------------------

_FEATURE_KEYS = [
    "hip_cx", "hip_cy",
    "shoulder_cy",
    "left_heel_y", "left_heel_x",
    "right_heel_y", "right_heel_x",
    "left_knee_angle", "right_knee_angle",
    "hip_ankle_dist",
    # computed later:
    "vx", "vy",
    "left_heel_vy", "right_heel_vy",
    "speed", "lateral_ratio", "lateral_vel",
    "accel", "squat_ratio", "backward",
]


def _fill_frame(
    F: Dict[str, np.ndarray],
    idx: int,
    lm: Dict[str, Tuple[float, float]],
) -> None:
    get = lm.get

    lh = get("left_hip");  rh = get("right_hip")
    ls = get("left_shoulder"); rs = get("right_shoulder")
    la = get("left_ankle");  ra = get("right_ankle")
    lheel = get("left_heel") or la
    rheel = get("right_heel") or ra
    lknee = get("left_knee"); rknee = get("right_knee")

    # hip centre
    if lh and rh:
        F["hip_cx"][idx] = (lh[0] + rh[0]) / 2
        F["hip_cy"][idx] = (lh[1] + rh[1]) / 2
    elif lh:
        F["hip_cx"][idx], F["hip_cy"][idx] = lh
    elif rh:
        F["hip_cx"][idx], F["hip_cy"][idx] = rh

    # shoulder centre (for body-height normalisation later if needed)
    if ls and rs:
        F["shoulder_cy"][idx] = (ls[1] + rs[1]) / 2

    # heel positions
    if lheel:
        F["left_heel_y"][idx], F["left_heel_x"][idx] = lheel[1], lheel[0]
    if rheel:
        F["right_heel_y"][idx], F["right_heel_x"][idx] = rheel[1], rheel[0]

    # knee angles
    for side, hip, knee, ankle in (
        ("left",  lh,  lknee, la),
        ("right", rh,  rknee, ra),
    ):
        if hip and knee and ankle:
            F[f"{side}_knee_angle"][idx] = _angle3(hip, knee, ankle)

    # hip-to-ankle vertical distance
    hip_y = F["hip_cy"][idx]
    ankle_ys = [v[1] for v in (la, ra) if v is not None]
    if not np.isnan(hip_y) and ankle_ys:
        F["hip_ankle_dist"][idx] = abs(np.mean(ankle_ys) - hip_y)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _angle3(
    a: Tuple[float, float],
    b: Tuple[float, float],
    c: Tuple[float, float],
) -> float:
    """Angle at vertex *b* formed by a-b-c (degrees)."""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag = math.hypot(*v1) * math.hypot(*v2)
    if mag < 1e-9:
        return 180.0
    return math.degrees(math.acos(max(-1.0, min(1.0, dot / mag))))


def _interp_nan(arr: np.ndarray) -> np.ndarray:
    """Linear interpolation over NaN gaps (in-place copy)."""
    nans = np.isnan(arr)
    if not nans.any():
        return arr
    idx = np.arange(len(arr))
    arr[nans] = np.interp(idx[nans], idx[~nans], arr[~nans]) if nans.sum() < len(arr) else arr
    return arr
