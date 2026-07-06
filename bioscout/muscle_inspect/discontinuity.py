"""Discontinuity detection for 1-D waveforms (no OpenSim dependency).

Ported from the MATLAB ``detectDiscontinuitiesInSignal``. Used here to flag
sudden jumps in moment-arm / muscle-length curves so the inspection plots can
mark them. The numerical thresholds match the original implementation.
"""
from __future__ import annotations

import numpy as np

try:  # connected-components of the boolean flag mask (MATLAB bwconncomp)
    from scipy.ndimage import label as _label
except Exception:  # pragma: no cover - tiny fallback if scipy is unavailable
    _label = None


def mad(x: np.ndarray) -> float:
    """Median absolute deviation about the median (MATLAB ``mad(x, 1)``).

    Note this is the *median*-based MAD, not numpy/statistics' default
    mean-based version.
    """
    x = np.asarray(x, float)
    return float(np.median(np.abs(x - np.median(x))))


def _connected_runs(mask: np.ndarray):
    """Yield index arrays for each run of True values in a boolean mask."""
    if _label is not None:
        labels, n = _label(mask)
        for k in range(1, n + 1):
            yield np.flatnonzero(labels == k)
        return
    # Fallback: manual run detection.
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return
    splits = np.where(np.diff(idx) > 1)[0] + 1
    for run in np.split(idx, splits):
        yield run


def detect_discontinuities(
    x: np.ndarray,
    min_jump_m: float = 0.001,
    k_d2: float = 7.0,
    k_local: float = 3.0,
    k_global: float = 8.0,
    win: int = 5,
) -> list[int]:
    """Return 0-based frame indices where ``x`` has a genuine discontinuity.

    Algorithm (matching the MATLAB original); all thresholds are tunable:
      1. second derivative ``d2y`` of the signal
      2. flag frames where ``|d2y| > k_d2 * 1.4826 * MAD(d2y)``
      3. for each flagged run of <= 2 samples, require the first-derivative jump
         to exceed ``k_local`` * local sigma, ``k_global`` * global sigma, and
         ``min_jump_m`` (metres) absolute.

    Lower ``min_jump_m`` / ``k_global`` to catch smaller jumps (more sensitive);
    raise them to ignore noise (fewer false positives).
    """
    x = np.asarray(x, float)
    idx: list[int] = []
    min_abs_jump = min_jump_m

    n = x.size
    if n < 5:
        return idx

    d2y = np.diff(x, n=2)
    T2 = k_d2 * 1.4826 * mad(d2y)
    if T2 == 0:
        return idx

    mask = np.abs(d2y) > T2
    global_sigma = 1.4826 * mad(np.diff(x))

    N = n - 1  # length of first-derivative domain (MATLAB indexing)
    for region in _connected_runs(mask):
        if region.size > 2:
            continue
        # MATLAB: i = region(1) + 1 (1-based on d2y -> signal). Convert to 0-based.
        i = int(region[0]) + 1  # 0-based index into x
        i1 = max(0, i - win)
        i2 = min(N, i + win)
        if (i2 - i1) < 2 * win:
            if i1 == 0:
                i2 = min(N, i1 + 2 * win)
            elif i2 == N:
                i1 = max(0, i2 - 2 * win)
        local_dy = np.diff(x[i1 : i2 + 1])
        if local_dy.size == 0:
            continue
        local_sigma = 1.4826 * mad(local_dy)
        if local_sigma == 0:
            continue

        j = min(i + 1, n - 1)
        jump = abs(x[j] - x[i])
        if (jump > k_local * local_sigma and jump > min_abs_jump
                and jump > k_global * global_sigma):
            idx.append(i)
    return idx
