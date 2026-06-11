"""
classifier.py — frame-level task classification + state-machine transitions.

Tasks
-----
standing            stationary
walking             slow gait with heel strikes, no aerial
running             fast gait OR aerial phase present
backward_walking    walking direction opposite to dominant travel direction
backward_running    running direction opposite to dominant travel direction
jumping             upward impulse + aerial phase + landing
squatting           repeated hip-depth cycles (low forward speed)
deceleration        rapid speed decrease from running/walking
side_cut            lateral direction change — MUST follow running/walking/jumping
shuffle             lateral movement — MUST follow standing/shuffle

Transition rules
----------------
side_cut  ← previous task in {running, walking, jumping}
shuffle   ← previous task in {standing, shuffle}
(A lateral move following any other context defaults to 'shuffle'.)
"""

from __future__ import annotations
import numpy as np
from typing import Dict, List

try:
    from scipy.signal import find_peaks
    _HAS_SCIPY = True
except ImportError:
    _HAS_SCIPY = False


# ---------------------------------------------------------------------------
# Transition-rule lookup
# ---------------------------------------------------------------------------

_LATERAL_ORIGINS_SIDE_CUT = {"running", "walking", "jumping",
                              "backward_running", "backward_walking"}
_LATERAL_ORIGINS_SHUFFLE   = {"standing", "shuffle", "unknown"}


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def classify_frames(
    F: Dict[str, np.ndarray],
    cfg,                        # DetectorConfig
) -> List[str]:
    """
    Return a list of task labels, one per frame index (0-based from min_frame).
    """
    n = len(next(iter(F.values())))
    labels: List[str] = ["unknown"] * n

    # --- detect heel strikes for gait cadence --------------------------------
    left_hs  = _detect_heel_strikes(F.get("left_heel_y",  np.array([])), cfg)
    right_hs = _detect_heel_strikes(F.get("right_heel_y", np.array([])), cfg)
    hs_mask  = np.zeros(n, dtype=bool)
    for i in left_hs + right_hs:
        if 0 <= i < n:
            hs_mask[i] = True

    # --- aerial phase --------------------------------------------------------
    aerial = _detect_aerial(F, cfg, n)

    speed      = F.get("speed",        np.full(n, np.nan))
    accel      = F.get("accel",        np.full(n, np.nan))
    lat_ratio  = F.get("lateral_ratio",np.full(n, np.nan))
    squat_rat  = F.get("squat_ratio",  np.full(n, np.nan))
    backward   = F.get("backward",     np.full(n, np.nan))
    vy         = F.get("vy",           np.full(n, np.nan))

    # --- per-frame primary classification ------------------------------------
    primary: List[str] = ["unknown"] * n
    for i in range(n):
        spd = float(speed[i]) if not np.isnan(speed[i]) else 0.0
        lat = float(lat_ratio[i]) if not np.isnan(lat_ratio[i]) else 0.0
        sq  = float(squat_rat[i]) if not np.isnan(squat_rat[i]) else 1.0
        bwd = bool(backward[i]) if not np.isnan(backward[i]) else False
        ac  = float(accel[i]) if not np.isnan(accel[i]) else 0.0

        if spd < cfg.speed_standing_max:
            if sq < cfg.squat_depth_ratio:
                primary[i] = "squatting"
            else:
                primary[i] = "standing"
        elif aerial[i]:
            primary[i] = "jumping"
        elif sq < cfg.squat_depth_ratio and spd < cfg.speed_walk_max:
            primary[i] = "squatting"
        elif lat > cfg.lateral_ratio_min:
            primary[i] = "lateral"          # resolved by state machine below
        elif ac < cfg.decel_accel_threshold and spd > cfg.speed_walk_max * 0.5:
            primary[i] = "deceleration"
        elif bwd:
            primary[i] = "backward_fast" if spd > cfg.speed_walk_max else "backward_slow"
        elif spd <= cfg.speed_walk_max:
            primary[i] = "walking"
        else:
            primary[i] = "running"

    # --- state machine: resolve "lateral" and apply transition rules ----------
    prev_task = "unknown"
    for i in range(n):
        p = primary[i]
        if p == "lateral":
            if prev_task in _LATERAL_ORIGINS_SIDE_CUT:
                labels[i] = "side_cut"
            else:
                labels[i] = "shuffle"
        elif p == "backward_fast":
            labels[i] = "backward_running"
        elif p == "backward_slow":
            labels[i] = "backward_walking"
        else:
            labels[i] = p

        # Update prev_task only on non-transient states
        if labels[i] not in ("unknown",):
            prev_task = labels[i]

    # --- smooth: remove very short isolated segments -------------------------
    labels = _smooth_labels(labels, cfg.min_segment_frames)

    return labels


# ---------------------------------------------------------------------------
# Heel-strike detection
# ---------------------------------------------------------------------------

def _detect_heel_strikes(heel_y: np.ndarray, cfg) -> List[int]:
    """Return indices of heel-strike events (local maxima in y = foot nearest ground)."""
    if len(heel_y) < 5:
        return []
    arr = np.where(np.isnan(heel_y), np.nanmedian(heel_y) if not np.all(np.isnan(heel_y)) else 0, heel_y)
    if _HAS_SCIPY:
        peaks, props = find_peaks(
            arr,
            prominence=cfg.heel_strike_min_prominence,
            distance=max(3, int(5)),
        )
        return peaks.tolist()
    else:
        # Fallback: simple local maxima
        peaks = []
        for i in range(1, len(arr) - 1):
            if arr[i] > arr[i-1] and arr[i] > arr[i+1]:
                peaks.append(i)
        return peaks


# ---------------------------------------------------------------------------
# Aerial phase detection
# ---------------------------------------------------------------------------

def _detect_aerial(F: Dict[str, np.ndarray], cfg, n: int) -> np.ndarray:
    """
    Boolean array: True where both feet appear elevated above their
    resting position (proxy for aerial phase in jump or sprint).
    """
    aerial = np.zeros(n, dtype=bool)

    lhy = F.get("left_heel_y",  np.full(n, np.nan))
    rhy = F.get("right_heel_y", np.full(n, np.nan))
    vy  = F.get("vy",           np.full(n, np.nan))

    # Baseline heel height = upper quartile (in image y, larger = lower)
    l_base = np.nanpercentile(lhy, 75) if not np.all(np.isnan(lhy)) else np.nan
    r_base = np.nanpercentile(rhy, 75) if not np.all(np.isnan(rhy)) else np.nan

    if np.isnan(l_base) or np.isnan(r_base):
        return aerial

    l_elev = lhy < (l_base - cfg.heel_strike_min_prominence)
    r_elev = rhy < (r_base - cfg.heel_strike_min_prominence)

    candidate = l_elev & r_elev

    # Require upward velocity context (vy negative = moving up in image)
    up_vel = vy < -cfg.jump_velocity_min
    # Expand candidate slightly: aerial is valid if within a window of upward vel
    for i in np.where(candidate)[0]:
        win = slice(max(0, i - cfg.aerial_phase_min_frames),
                    min(n, i + cfg.aerial_phase_min_frames + 1))
        if up_vel[win].any():
            aerial[i] = True

    return aerial


# ---------------------------------------------------------------------------
# Label smoothing
# ---------------------------------------------------------------------------

def _smooth_labels(labels: List[str], min_frames: int) -> List[str]:
    """
    Merge segments shorter than min_frames into adjacent dominant segment.
    """
    if not labels:
        return labels

    # Build run-length segments
    segs = _rle(labels)

    changed = True
    while changed:
        changed = False
        new_segs = []
        i = 0
        while i < len(segs):
            label, length = segs[i]
            if length < min_frames and len(segs) > 1:
                # Merge into longer neighbour
                prev_lbl = segs[i-1][0] if i > 0 else None
                next_lbl = segs[i+1][0] if i < len(segs)-1 else None
                # Use neighbour that results in a longer combined run
                if prev_lbl is not None and (next_lbl is None or
                        segs[i-1][1] >= (segs[i+1][1] if i < len(segs)-1 else 0)):
                    new_segs[-1] = (prev_lbl, new_segs[-1][1] + length)
                elif next_lbl is not None:
                    # merge forward: delay by consuming next
                    segs[i+1] = (next_lbl, segs[i+1][1] + length)
                    i += 1
                    changed = True
                    continue
                else:
                    new_segs.append((label, length))
                changed = True
            else:
                new_segs.append((label, length))
            i += 1
        segs = new_segs

    # Reconstruct flat list
    out = []
    for label, length in segs:
        out.extend([label] * length)
    # Pad/trim to original length
    orig = len(labels)
    if len(out) < orig:
        out.extend([out[-1]] * (orig - len(out)))
    return out[:orig]


def _rle(labels: List[str]):
    """Run-length encoding: [(label, count), ...]"""
    if not labels:
        return []
    result = []
    cur, cnt = labels[0], 1
    for lb in labels[1:]:
        if lb == cur:
            cnt += 1
        else:
            result.append((cur, cnt))
            cur, cnt = lb, 1
    result.append((cur, cnt))
    return result
