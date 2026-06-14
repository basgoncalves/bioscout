"""
movement_detector — standalone module for detecting and segmenting
sports movements (running, walking, jumping, squatting, side-step cut,
shuffle, deceleration, backward walking/running) from 2-D pose landmark
time-series.

Public API
----------
    from movement_detector import detect_segments, fill_pose_gaps, MotionSegment, DetectorConfig
"""

from .detector import MotionSegment, DetectorConfig, detect_segments
from .gap_fill import fill_pose_gaps

__all__ = [
    "MotionSegment",
    "DetectorConfig",
    "detect_segments",
    "fill_pose_gaps",
]
