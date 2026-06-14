"""
detector.py — public API: MotionSegment, DetectorConfig, detect_segments().
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from .features import extract_features
from .classifier import classify_frames, _rle


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

TASK_LABELS = (
    "standing",
    "walking",
    "running",
    "backward_walking",
    "backward_running",
    "jumping",
    "squatting",
    "deceleration",
    "side_cut",
    "shuffle",
    "unknown",
)


@dataclass
class MotionSegment:
    """A labelled, contiguous block of frames with a single movement task."""
    start_frame: int
    end_frame: int
    task: str
    rep: int = 1
    confidence: float = 1.0

    @property
    def duration_frames(self) -> int:
        return self.end_frame - self.start_frame + 1

    def __repr__(self) -> str:
        return (
            f"MotionSegment(task={self.task!r}, rep={self.rep}, "
            f"frames={self.start_frame}-{self.end_frame}, "
            f"dur={self.duration_frames}fr)"
        )


@dataclass
class DetectorConfig:
    """Tunable thresholds for the movement detector.

    All speed thresholds are in **pixels / frame**.  You may need to scale
    these if your video resolution / field of view differs substantially from
    a standard 1080p side-view sport recording.
    """

    # --- speed thresholds (px/frame) ----------------------------------------
    speed_standing_max: float = 3.0
    """Hip CoM speed below this → standing."""

    speed_walk_max: float = 12.0
    """Hip CoM speed above this + aerial OR cadence → running."""

    # --- lateral movement ----------------------------------------------------
    lateral_ratio_min: float = 0.65
    """Fraction of speed that is lateral before classifying as lateral move."""

    # --- squat ---------------------------------------------------------------
    squat_depth_ratio: float = 0.82
    """hip_ankle_dist drops below (baseline × this) → squatting."""

    # --- jumping -------------------------------------------------------------
    jump_velocity_min: float = 4.0
    """Minimum upward velocity (px/frame, vy < 0 in image) to seed aerial detection."""

    aerial_phase_min_frames: int = 3
    """Minimum frames for a valid aerial window."""

    # --- deceleration --------------------------------------------------------
    decel_accel_threshold: float = -2.5
    """Speed acceleration below this → deceleration."""

    # --- gait ----------------------------------------------------------------
    heel_strike_min_prominence: float = 3.0
    """Minimum peak prominence (px) in heel-y signal to count as a heel strike."""

    # --- segment cleanup -----------------------------------------------------
    min_segment_frames: int = 8
    """Segments shorter than this are merged into adjacent segments."""


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def detect_segments(
    poses: Dict[int, Dict[str, Tuple[float, float]]],
    fps: float = 30.0,
    config: Optional[DetectorConfig] = None,
) -> List[MotionSegment]:
    """
    Detect and segment movements in a pose time-series.

    Parameters
    ----------
    poses   : {frame_idx: {landmark_name: (x_px, y_px)}}
    fps     : video frame rate (used for display; thresholds are in px/frame)
    config  : DetectorConfig instance, or None for defaults

    Returns
    -------
    List[MotionSegment] sorted by start_frame.
    """
    if not poses:
        return []

    cfg = config or DetectorConfig()

    # 1. Feature extraction
    F, min_frame = extract_features(poses, fps)
    if not F:
        return []

    # 2. Per-frame classification
    labels = classify_frames(F, cfg)

    # 3. Run-length encode → segments
    segments: List[MotionSegment] = []
    rep_counters: Dict[str, int] = {}
    offset = 0
    for task, length in _rle(labels):
        start = min_frame + offset
        end   = min_frame + offset + length - 1
        rep   = rep_counters.get(task, 0) + 1
        rep_counters[task] = rep
        segments.append(MotionSegment(
            start_frame=start,
            end_frame=end,
            task=task,
            rep=rep,
        ))
        offset += length

    return segments


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def segments_to_dict(segments: List[MotionSegment]) -> List[dict]:
    """Serialise segments to a list of plain dicts (JSON-friendly)."""
    return [
        {
            "start_frame": s.start_frame,
            "end_frame":   s.end_frame,
            "task":        s.task,
            "rep":         s.rep,
            "confidence":  s.confidence,
        }
        for s in segments
    ]


def segments_from_dict(data: List[dict]) -> List[MotionSegment]:
    """Deserialise from a list of dicts (e.g. loaded from JSON)."""
    return [
        MotionSegment(
            start_frame=d["start_frame"],
            end_frame=d["end_frame"],
            task=d["task"],
            rep=d.get("rep", 1),
            confidence=d.get("confidence", 1.0),
        )
        for d in data
    ]
