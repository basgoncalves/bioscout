"""
squat.py -- rep detection and joint angles for squats.

A squat is not a pull-up upside down; it needs its own detector. The pull-up
code tracks the body RISING from a dead hang and gates on the hands being
overhead. A squat starts standing, descends, and returns, with the hands
nowhere near the head -- run through find_reps() it yields nothing at all.

Sign conventions here are Rajagopal's, because that is what the FAIS force
model was trained on. Confirmed empirically from the model's own
standardisation means (knee_angle_r mean +56.9 deg, so flexion is POSITIVE;
pelvis_tilt mean -10.3 deg, so anterior tilt is NEGATIVE). Note this is the
opposite of the gait2392/GPK knee convention -- see the project's
gpk_motion_data notes before feeding these files to a GPK model.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np

from .kinematics import _angle3, _mid, interp_nan, smooth

#: Ankle joint centre height above the floor, in metres. Used to turn a
#: measured hip-above-ankle distance into an absolute pelvis height.
ANKLE_JOINT_HEIGHT_M = 0.07

#: Knee sign per model family. OpenSim will happily accept a .mot whose values
#: sit outside a coordinate's range and render a collapsed figure, so this has
#: to be right rather than nearly right.
#:   rajagopal      knee_angle range 0..+145 deg, flexion POSITIVE
#:   gpk/gait2392   knee_angle range -145..+10 deg, flexion NEGATIVE
KNEE_SIGN = {"rajagopal": +1.0, "gpk": -1.0, "gait2392": -1.0}

# OpenSim coordinates a sagittal camera can drive for a squat. More than the
# pull-up set: the legs are the whole movement, and they are all in view.
SQUAT_DRIVEN_COORDS = [
    "pelvis_tilt", "pelvis_tx", "pelvis_ty", "pelvis_tz",
    "hip_flexion_r", "hip_flexion_l",
    "knee_angle_r", "knee_angle_l",
    "ankle_angle_r", "ankle_angle_l",
    "lumbar_extension",
]


@dataclass
class SquatConfig:
    name: str = "default"
    #: fraction of standing hip-to-ankle length the hips must drop to count
    min_depth_frac: float = 0.12
    min_rep_frames: int = 12
    #: knee must flex through at least this range between stand and bottom
    min_knee_flexion_deg: float = 45.0
    smooth_win: int = 5
    #: reject "reps" where the trunk barely moves and only the knees bend a
    #: little -- usually the athlete shifting weight between sets
    min_hip_flexion_deg: float = 25.0

    def as_dict(self):
        return asdict(self)


def build_squat_features(poses):
    """poses -> feature dict. Image coords, so y grows downward."""
    frames = sorted(poses.keys())
    if not frames:
        raise ValueError("no pose frames")
    lo, hi = frames[0], frames[-1]
    n = hi - lo + 1

    keys = ["hip_cy", "hip_cx", "shoulder_cy", "shoulder_cx",
            "ankle_cy", "ankle_cx", "knee_cy", "knee_cx", "toe_cy", "toe_cx",
            "knee_flex", "hip_flex", "ankle_dorsi", "trunk_lean", "shank_len"]
    F = {k: np.full(n, np.nan) for k in keys}

    for fi, lm in poses.items():
        i = fi - lo
        g = lm.get
        ls, rs = g("left_shoulder"), g("right_shoulder")
        lh, rh = g("left_hip"), g("right_hip")
        lk, rk = g("left_knee"), g("right_knee")
        la, ra = g("left_ankle"), g("right_ankle")
        lf, rf = g("left_foot_index"), g("right_foot_index")

        sh, hp, an = _mid(ls, rs), _mid(lh, rh), _mid(la, ra)
        kn, ft = _mid(lk, rk), _mid(lf, rf)
        if sh:
            F["shoulder_cy"][i] = sh[1]
            F["shoulder_cx"][i] = sh[0]
        if hp:
            F["hip_cy"][i] = hp[1]
            F["hip_cx"][i] = hp[0]
        if an:
            F["ankle_cy"][i] = an[1]
            F["ankle_cx"][i] = an[0]
        if kn:
            F["knee_cy"][i] = kn[1]
            F["knee_cx"][i] = kn[0]
        if ft:
            F["toe_cy"][i] = ft[1]
            F["toe_cx"][i] = ft[0]

        # Knee flexion: straight leg is 180 deg interior, so flexion = 180 - it.
        knee_interior = np.nanmean([_angle3(lh, lk, la), _angle3(rh, rk, ra)])
        F["knee_flex"][i] = 180.0 - knee_interior

        # Hip flexion: trunk-to-thigh, same convention.
        hip_interior = np.nanmean([_angle3(ls, lh, lk), _angle3(rs, rh, rk)])
        F["hip_flex"][i] = 180.0 - hip_interior

        # Ankle dorsiflexion: shank-to-foot, neutral is 90 deg interior.
        ankle_interior = np.nanmean([_angle3(lk, la, lf), _angle3(rk, ra, rf)])
        F["ankle_dorsi"][i] = 90.0 - ankle_interior

        # Trunk lean from vertical, forward positive.
        if sh and hp:
            dx, dy = sh[0] - hp[0], hp[1] - sh[1]
            F["trunk_lean"][i] = math.degrees(math.atan2(dx, max(dy, 1e-6)))

        if hp and an:
            F["shank_len"][i] = abs(hp[1] - an[1])

    # Depth is measured against the standing hip height, in units of the
    # standing hip-to-ankle distance -- scale-free, so it survives any camera
    # distance or resolution.
    hip_y = F["hip_cy"]
    stand_y = np.nanpercentile(hip_y, 10)      # highest hips = standing
    scale = np.nanmedian(F["shank_len"])
    if not (scale and scale > 1e-6):
        scale = 1.0
    with np.errstate(invalid="ignore"):
        F["depth"] = (hip_y - stand_y) / scale   # down = positive

    F["_lo"] = lo
    F["_n"] = n
    F["_scale"] = scale
    F["_stand_y"] = float(stand_y)
    #: Floor level in image pixels: the lowest foot position observed.
    F["_floor_y"] = float(np.nanmax(np.concatenate(
        [F["toe_cy"][np.isfinite(F["toe_cy"])],
         F["ankle_cy"][np.isfinite(F["ankle_cy"])]])) ) if np.any(
        np.isfinite(F["toe_cy"])) or np.any(np.isfinite(F["ankle_cy"])) else 0.0
    F["_coverage"] = len(poses) / n
    return F


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


def find_squat_reps(F, cfg: SquatConfig):
    """-> ([(top_start, bottom, top_end), ...], smoothed_depth).

    Mirror image of the pull-up detector: the extremum of interest is the
    BOTTOM of the descent, and the rep is bounded by the standing positions
    either side of it.
    """
    depth = smooth(interp_nan(F["depth"]), cfg.smooth_win)
    knee = interp_nan(F["knee_flex"])
    hip = interp_nan(F["hip_flex"])
    n = F["_n"]

    bottoms = _local_maxima(depth, cfg.min_rep_frames, cfg.min_depth_frac)
    reps = []
    for k, bot in enumerate(bottoms):
        left = bottoms[k - 1] if k > 0 else 0
        right = bottoms[k + 1] if k < len(bottoms) - 1 else n - 1
        t0 = left + int(np.argmin(depth[left:bot + 1])) if bot > left else left
        t1 = bot + int(np.argmin(depth[bot:right + 1])) if right > bot else right

        knee_stand = float(np.nanmin([knee[t0], knee[t1]]))
        if (knee[bot] - knee_stand) < cfg.min_knee_flexion_deg:
            continue
        hip_stand = float(np.nanmin([hip[t0], hip[t1]]))
        if (hip[bot] - hip_stand) < cfg.min_hip_flexion_deg:
            continue
        if (t1 - t0) < cfg.min_rep_frames:
            continue
        if (bot - t0) < 3 or (t1 - bot) < 3:
            continue
        reps.append((t0, bot, t1))
    return reps, depth


def squat_rep_coordinates(F, rep, fps, px_per_m, stand_hip_y, mid_x,
                          model="gpk", ankle_valid=True):
    """One rep -> (times, {coord: array}) for the given model family.

    Left and right are mirrored: one camera cannot separate the sides.

    pelvis_ty is an ABSOLUTE height above the floor, not a displacement.
    OpenSim's pelvis_ty is the pelvis origin's height (GPK defaults to 0.93 m),
    so writing a displacement that starts near zero drops the model through the
    floor. It is measured here as the hip-to-ankle vertical distance plus the
    ankle joint height, which needs no anthropometric assumption beyond the
    pixel scale already computed.
    """
    t0, bot, t1 = rep
    lo = F["_lo"]
    sl = slice(t0, t1 + 1)

    knee = interp_nan(F["knee_flex"])[sl]
    hip = interp_nan(F["hip_flex"])[sl]
    ankle = interp_nan(F["ankle_dorsi"])[sl]
    lean = interp_nan(F["trunk_lean"])[sl]
    hip_y = interp_nan(F["hip_cy"])[sl]
    hip_x = interp_nan(F["hip_cx"])[sl]
    ankle_y = interp_nan(F["ankle_cy"])[sl]

    times = (lo + np.arange(t0, t1 + 1)) / fps

    # Absolute pelvis height: hips above ankles, plus the ankle joint height.
    pelvis_ty = (ankle_y - hip_y) / px_per_m + ANKLE_JOINT_HEIGHT_M
    pelvis_tz = (hip_x - mid_x) / px_per_m

    sign = KNEE_SIGN.get(model, -1.0)
    hip_flex = np.clip(hip, -20.0, 130.0)
    knee_ang = sign * np.clip(knee, 0.0, 145.0)
    # A frontal view makes the knee-ankle-toe angle meaningless and pins it at
    # the clip bound. Emitting a saturated constant would look like data; zero
    # at least reads as "not measured", and the caller is told separately.
    ankle_ang = np.clip(ankle, -40.0, 40.0) if ankle_valid else np.zeros_like(ankle)
    # Anterior pelvic tilt is negative in Rajagopal. A sagittal camera cannot
    # separate pelvis tilt from lumbar flexion, so the trunk lean is attributed
    # to the lumbar spine and the pelvis is left for the model's own prior.
    lumbar = np.clip(-lean, -60.0, 30.0)
    z = np.zeros_like(times)

    return times, {
        "pelvis_tx": z, "pelvis_ty": pelvis_ty, "pelvis_tz": pelvis_tz,
        "hip_flexion_r": hip_flex, "hip_flexion_l": hip_flex,
        "knee_angle_r": knee_ang, "knee_angle_l": knee_ang,
        "ankle_angle_r": ankle_ang, "ankle_angle_l": ankle_ang,
        "lumbar_extension": lumbar,
    }


def joint_positions_m(F, rep, px_per_m, floor_y):
    """Landmark positions for one rep in METRES, world frame, y UP.

    Image y grows downward and the floor is at the lowest observed foot
    position, so this flips and offsets into a physical frame the dynamics can
    use directly.
    """
    t0, _, t1 = rep
    sl = slice(t0, t1 + 1)

    def xy(xk, yk):
        x = interp_nan(F[xk])[sl] / px_per_m
        y = (floor_y - interp_nan(F[yk])[sl]) / px_per_m
        return np.column_stack([x, y])

    return {
        "ankle": xy("ankle_cx", "ankle_cy"),
        "knee": xy("knee_cx", "knee_cy"),
        "hip": xy("hip_cx", "hip_cy"),
        "shoulder": xy("shoulder_cx", "shoulder_cy"),
        "toe": xy("toe_cx", "toe_cy"),
    }


def reference_positions(F):
    """(standing_hip_y, mid_x) in pixels -- the pelvis-translation datum."""
    hip_x = interp_nan(F["hip_cx"])
    return F["_stand_y"], float(np.nanmedian(hip_x))
