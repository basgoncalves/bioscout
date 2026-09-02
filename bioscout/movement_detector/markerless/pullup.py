"""
pullup.py -- the pull-up activity: features, rep detection, OpenSim coordinates.

One activity module among several, sitting alongside squat.py. It was not
always: this code used to occupy the generic names in kinematics.py
(``build_features``, ``find_reps``, ``PULLUP_DRIVEN_COORDS``) while the squat had to
qualify all of its own, which quietly made "the pipeline" mean "the pull-up
pipeline" and left no obvious place to add a third movement. The names are
qualified on both sides now, and kinematics.py holds only what every activity
shares.

A rep is a vertical cycle ``bottom -> top -> bottom``: dead hang, chin to the
bar, back to the hang. The rep oscillator is the normalised body-rise signal,
gated on elbow flexion so a sway is not counted as a rep.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

from .kinematics import (
    _angle3, _local_maxima, _mid, interp_nan, smooth,
)

# OpenSim coordinates this pipeline can actually drive from a single camera.
PULLUP_DRIVEN_COORDS = [
    "pelvis_tilt", "pelvis_tx", "pelvis_ty", "pelvis_tz",
    "hip_flexion_r", "hip_flexion_l", "knee_angle_r", "knee_angle_l",
    "arm_flex_r", "arm_flex_l", "elbow_flex_r", "elbow_flex_l",
    "flex_extension",
]

# --------------------------------------------------------------------------
# feature extraction
# --------------------------------------------------------------------------
def build_pullup_features(poses):
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



def find_pullup_reps(F, cfg: PullupConfig):
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
# OpenSim coordinate export
# --------------------------------------------------------------------------
def pullup_rep_coordinates(F, rep, fps, px_per_m, dead_hang_y, mid_x):
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
