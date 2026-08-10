"""
movement_detector — detecting and segmenting sports movements.

Two independent paths, for two kinds of input:

**Video / 2-D pose** — frame-level segmentation of running, walking, jumping,
squatting, side-step cut, shuffle, deceleration and backward gait from pose
landmark time-series::

    from bioscout.movement_detector import detect_segments, DetectorConfig
    segments = detect_segments(landmarks)

**Marker-based mocap** — whole-TRIAL classification from the markers and
ground reaction forces BioScout exports into
``<session>/2_experimental/<trial>/``. Answers "what task is this trial?"
rather than "what is happening in this frame", so a project can check its
trials against their filenames::

    from bioscout.movement_detector import classify_trial
    label, conf, why, feats = classify_trial(exp_dir, body_mass=61.3)

Thresholds for the mocap path are SI (m, s, body weights) and live in
``MocapConfig``; the video path's are pixels/frame in ``DetectorConfig``.
"""

from .detector import MotionSegment, DetectorConfig, detect_segments
from .gap_fill import fill_pose_gaps
from .mocap import (
    detect_window,
    segment_trial,
    TaskSegment,
    contact_feet,
    foot_events_from_markers,
    plot_trial_tasks,
    TASK_COLOURS,
    MOCAP_TASK_LABELS,
    MocapConfig,
    TrialFeatures,
    classify_trial,
    classify_features,
    extract_trial_features,
    read_trc,
    read_grf,
)

__all__ = [
    # video / 2-D pose
    "MotionSegment",
    "DetectorConfig",
    "detect_segments",
    "fill_pose_gaps",
    # marker-based mocap
    "MOCAP_TASK_LABELS",
    "MocapConfig",
    "TrialFeatures",
    "classify_trial",
    "classify_features",
    "extract_trial_features",
    "detect_window",
    "segment_trial",
    "TaskSegment",
    "contact_feet",
    "foot_events_from_markers",
    "plot_trial_tasks",
    "TASK_COLOURS",
    "read_trc",
    "read_grf",
]
