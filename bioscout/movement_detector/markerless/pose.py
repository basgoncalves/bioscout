"""
pose.py -- MediaPipe pose extraction from a video file.

Kept behind a thin interface so the rest of the app never imports MediaPipe
directly. On Android, MediaPipe is the fragile part of the build: if the import
fails at runtime the app degrades to "pick a poses.json" rather than crashing.
"""
from __future__ import annotations

import json
import os

from .kinematics import LANDMARK_NAMES

VIS_THRESH = 0.3

# The pose task file is 9.4 MB and is NOT in the repository -- `*.task` is
# gitignored, and it would not fit a sensible wheel anyway. It is fetched once
# and kept beside the code; bioscout/record/ is where this project already puts
# it, so look there before the package-local copy's own models/ folder.
_HERE = os.path.dirname(os.path.abspath(__file__))
_MODEL_CANDIDATES = [
    os.path.join(_HERE, "models", "pose_landmarker_full.task"),
    os.path.normpath(os.path.join(_HERE, "..", "..", "record",
                                  "pose_landmarker_full.task")),
]


class PoseBackendUnavailable(RuntimeError):
    """Raised when MediaPipe or OpenCV cannot be imported on this device."""


def find_task_model():
    for p in _MODEL_CANDIDATES:
        if os.path.exists(p):
            return p
    raise FileNotFoundError(
        "pose_landmarker_full.task not found. It is a 9.4 MB download, not "
        "part of the package. Put it in bioscout/record/ or in "
        "bioscout/movement_detector/markerless/models/. Get it from "
        "https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker"
        " (Pose landmarker, 'full' variant).")


def resolve_source(path, fps_hint=None):
    """Accept a video file, or a directory of numbered frames.

    Capture tools often write a folder of PNGs rather than a video. OpenCV can
    read those directly given a printf pattern, so a directory is turned into
    one here. A frame folder carries no frame rate, so fps_hint decides -- and
    if it is wrong, every angle is still right and every DURATION is wrong.
    """
    import glob
    import re

    if os.path.isfile(path):
        return path, None

    if not os.path.isdir(path):
        raise IOError("no such file or directory: %s" % path)

    files = sorted(glob.glob(os.path.join(path, "*.png")) +
                   glob.glob(os.path.join(path, "*.jpg")))
    if not files:
        raise IOError("no .png or .jpg frames in %s" % path)

    first = os.path.basename(files[0])
    m = re.match(r"^(.*?)(\d+)(\.[A-Za-z]+)$", first)
    if not m:
        raise IOError("frame names in %s are not numbered (%s)" % (path, first))
    stem, digits, ext = m.groups()
    pattern = os.path.join(path, "%s%%0%dd%s" % (stem, len(digits), ext))
    return pattern, (fps_hint or 30.0)


def extract_poses(video_path, progress=None, min_confidence=0.3, fps_hint=None):
    """video file OR frame directory -> ({frame: {landmark: (x, y)}}, fps).

    progress: optional callable(fraction_0_to_1) for the UI.
    """
    try:
        import cv2
        import numpy as np  # noqa: F401  (cv2 needs it present)
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision as mp_vision
        import mediapipe as mp
    except Exception as exc:  # pragma: no cover - device dependent
        raise PoseBackendUnavailable(str(exc))

    video_path, seq_fps = resolve_source(video_path, fps_hint)
    model_path = find_task_model()
    opts = mp_vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=model_path),
        running_mode=mp_vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=min_confidence,
        min_pose_presence_confidence=min_confidence,
        min_tracking_confidence=min_confidence,
    )

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise IOError("could not open video: %s" % video_path)
    fps = seq_fps or cap.get(cv2.CAP_PROP_FPS) or 30.0
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    poses = {}
    with mp_vision.PoseLandmarker.create_from_options(opts) as landmarker:
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            h, w = frame.shape[:2]
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts_ms = int(idx / fps * 1000)
            result = landmarker.detect_for_video(mp_image, ts_ms)
            if result.pose_landmarks:
                lms = result.pose_landmarks[0]
                frame_lm = {}
                for name, lm in zip(LANDMARK_NAMES, lms):
                    if getattr(lm, "visibility", 1.0) >= VIS_THRESH:
                        frame_lm[name] = (lm.x * w, lm.y * h)
                if frame_lm:
                    poses[idx] = frame_lm
            idx += 1
            if progress and n_total:
                progress(min(1.0, idx / n_total))
    cap.release()
    if not poses:
        raise ValueError("no poses detected -- is the whole body in frame?")
    return poses, float(fps)


def save_poses(path, poses, fps):
    payload = {"fps": fps,
               "poses": {str(k): {n: list(v) for n, v in lm.items()}
                         for k, lm in poses.items()}}
    with open(path, "w") as f:
        json.dump(payload, f)


def load_poses(path):
    with open(path) as f:
        data = json.load(f)
    fps = float(data.get("fps", 30.0))
    poses = {int(k): {n: tuple(v) for n, v in lm.items()}
             for k, lm in data["poses"].items()}
    return poses, fps
