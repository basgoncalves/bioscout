"""Recording module for the Analysis App.

Includes:
- screen_record: ScreenRecorder for desktop recording
- video: MovementTracker for webcam/IP camera with pose estimation
- video_recorder: Command-line video recording script
- video_analyzer: Command-line video analysis script
"""

# Try to import ScreenRecorder, but don't fail if cv2 is not available
try:
    from .screen_record import ScreenRecorder
except ImportError:
    ScreenRecorder = None

try:
    from .video import MovementTracker, ARM26_BALL_CONFIG, FULL_BODY_CONFIG
except ImportError:
    MovementTracker = None
    ARM26_BALL_CONFIG = None
    FULL_BODY_CONFIG = None

__all__ = [
    "ScreenRecorder",
    "MovementTracker",
    "ARM26_BALL_CONFIG",
    "FULL_BODY_CONFIG",
]
