"""
gap_fill.py — fill missing frames in a pose landmark dict using cubic-spline
(or linear) interpolation.

Usage
-----
    from movement_detector import fill_pose_gaps
    filled = fill_pose_gaps(poses, max_gap=10, method="cubic")
"""

from __future__ import annotations
from typing import Dict, Optional, Tuple

import numpy as np


Poses = Dict[int, Dict[str, Tuple[float, float]]]


def fill_pose_gaps(
    poses: Poses,
    max_gap: int = 10,
    method: str = "cubic",
) -> Poses:
    """
    Return a new pose dict with missing frames interpolated.

    Parameters
    ----------
    poses   : {frame_idx: {landmark_name: (x, y)}}
    max_gap : only fill gaps shorter than or equal to this many frames.
              Longer gaps are left as-is (no extrapolation).
    method  : "cubic" (default) or "linear"

    Returns
    -------
    New dict with filled frames added. Original frames are not modified.
    """
    if not poses:
        return dict(poses)

    all_frames = sorted(poses.keys())
    min_fi = all_frames[0]
    max_fi = all_frames[-1]

    # Collect all landmark names
    all_landmarks = set()
    for lm in poses.values():
        all_landmarks.update(lm.keys())

    # Per-landmark: build x and y arrays indexed by frame
    n = max_fi - min_fi + 1
    lm_x: Dict[str, np.ndarray] = {lm: np.full(n, np.nan) for lm in all_landmarks}
    lm_y: Dict[str, np.ndarray] = {lm: np.full(n, np.nan) for lm in all_landmarks}

    for fi, lm_dict in poses.items():
        idx = fi - min_fi
        for name, (x, y) in lm_dict.items():
            lm_x[name][idx] = x
            lm_y[name][idx] = y

    # Identify gap ranges to fill (below max_gap threshold)
    gaps = _find_gaps(all_frames, min_fi, max_fi, max_gap)

    if not gaps:
        return dict(poses)

    filled = dict(poses)

    for name in all_landmarks:
        xs = lm_x[name]
        ys = lm_y[name]
        known_idx = np.where(~np.isnan(xs))[0]
        if len(known_idx) < 2:
            continue

        xi = _interp_array(xs, known_idx, method)
        yi = _interp_array(ys, known_idx, method)

        for gap_start, gap_end in gaps:
            for fi in range(gap_start, gap_end + 1):
                idx = fi - min_fi
                if np.isnan(xs[idx]) and 0 <= idx < n:
                    if not np.isnan(xi[idx]) and not np.isnan(yi[idx]):
                        if fi not in filled:
                            filled[fi] = {}
                        filled[fi][name] = (float(xi[idx]), float(yi[idx]))

    return filled


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_gaps(
    known_frames,
    min_fi: int,
    max_fi: int,
    max_gap: int,
) -> list:
    """Return list of (gap_start, gap_end) frame ranges within the fill threshold."""
    known_set = set(known_frames)
    gaps = []
    i = min_fi
    while i <= max_fi:
        if i not in known_set:
            j = i
            while j <= max_fi and j not in known_set:
                j += 1
            gap_len = j - i
            if gap_len <= max_gap:
                gaps.append((i, j - 1))
            i = j
        else:
            i += 1
    return gaps


def _interp_array(arr: np.ndarray, known_idx: np.ndarray, method: str) -> np.ndarray:
    """Interpolate NaN positions in arr using known_idx as support."""
    all_idx = np.arange(len(arr))
    known_vals = arr[known_idx]

    if method == "cubic" and len(known_idx) >= 4:
        try:
            from scipy.interpolate import CubicSpline
            cs = CubicSpline(known_idx, known_vals, extrapolate=False)
            result = arr.copy()
            nan_mask = np.isnan(arr)
            interp_vals = cs(all_idx[nan_mask])
            result[nan_mask] = interp_vals
            return result
        except Exception:
            pass  # fall through to linear

    # Linear fallback
    result = arr.copy()
    nan_mask = np.isnan(arr)
    result[nan_mask] = np.interp(all_idx[nan_mask], known_idx, known_vals)
    return result
