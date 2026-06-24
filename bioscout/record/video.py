# -*- coding: utf-8 -*-
import os
import sys
import io
import time
import threading
import urllib.request
import cv2
import numpy as np
import matplotlib.pyplot as plt
from collections import deque
from pathlib import Path
from datetime import datetime
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

# Fix stdout encoding on Windows to support Unicode characters
if sys.platform == 'win32':
    # Reconfigure stdout/stderr for UTF-8, but only if they haven't already been
    # replaced by a logging tee or similar wrapper (replacing a tee would lose
    # log output and could corrupt the stream).
    def _is_plain_text_io(s):
        return isinstance(s, io.TextIOWrapper)

    try:
        if _is_plain_text_io(sys.stdout) and hasattr(sys.stdout, 'buffer'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    try:
        if _is_plain_text_io(sys.stderr) and hasattr(sys.stderr, 'buffer'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


_LANDMARK_NAMES = [
    'nose', 'left_eye_inner', 'left_eye', 'left_eye_outer',
    'right_eye_inner', 'right_eye', 'right_eye_outer',
    'left_ear', 'right_ear', 'mouth_left', 'mouth_right',
    'left_shoulder', 'right_shoulder',
    'left_elbow', 'right_elbow',
    'left_wrist', 'right_wrist',
    'left_pinky', 'right_pinky',
    'left_index', 'right_index',
    'left_thumb', 'right_thumb',
    'left_hip', 'right_hip',
    'left_knee', 'right_knee',
    'left_ankle', 'right_ankle',
    'left_heel', 'right_heel',
    'left_foot_index', 'right_foot_index',
]

MODULE_DIR = os.path.dirname(__file__)
MODELS_DIR = os.path.join(os.path.dirname(MODULE_DIR), 'models')
# ======================================================================
# Model configuration
# ======================================================================

class MotModelConfig:
    """Defines the column layout for an OpenSim MOT file.

    Parameters
    ----------
    name : str
        Short identifier used in log messages and the MOT header.
    osim_path : str
        Absolute path to the .osim model file (informational only; not loaded).
    angle_columns : list of 7-tuples
        Each tuple: (col_name, lm_a, lm_vertex, lm_b, offset, clip_min, clip_max)

        * col_name   – column label written to the header row.
        * lm_a/b     – MediaPipe landmark names for the two outer points.
        * lm_vertex  – MediaPipe landmark name for the joint centre.
        * offset     – value subtracted from the raw angle before writing
                       (use 180 for the OpenSim elevation/flex complement
                       convention, 0 for the raw angle).
        * clip_min/max – output is clipped to [clip_min, clip_max].
    include_ball : bool
        If True, append six ball columns after the angle columns:
        ball_rx, ball_ry, ball_rz, ball_tx, ball_ty, ball_tz.
    ball_anchor_landmark : str
        Pose landmark used as the local origin for ball translation.
        Defaults to 'right_shoulder'.
    """

    def __init__(self, name, osim_path, angle_columns, include_ball=False,
                 ball_anchor_landmark='right_shoulder'):
        self.name = name
        self.osim_path = osim_path
        self.angle_columns = angle_columns
        self.include_ball = include_ball
        self.ball_anchor_landmark = ball_anchor_landmark

    @property
    def column_names(self):
        names = ['time'] + [c[0] for c in self.angle_columns]
        if self.include_ball:
            names += ['ball_rx', 'ball_ry', 'ball_rz', 'ball_tx', 'ball_ty', 'ball_tz']
        return names

    @property
    def n_columns(self):
        return len(self.column_names)


# ------------------------------------------------------------------
# Predefined model configs
# ------------------------------------------------------------------

# arm26_ball.osim — right arm only, includes ball object
# Coordinates: r_shoulder_elev, r_elbow_flex + 6 ball DOFs
ARM26_BALL_CONFIG = MotModelConfig(
    name='arm26_ball',
    osim_path=os.path.join(MODELS_DIR, 'arm26_ball.osim'),
    angle_columns=[
        # (col_name, lm_a, lm_vertex, lm_b, offset, clip_min, clip_max)
        ('r_shoulder_elev', 'right_hip',      'right_shoulder', 'right_elbow', 180, 0, 180),
        ('r_elbow_flex',    'right_shoulder', 'right_elbow',    'right_wrist', 180, 0, 130),
    ],
    include_ball=True,
    ball_anchor_landmark='right_shoulder',
)

# Full-body config tied to Full_Body_with_ball.osim
# Coordinate names below MUST match those in the .osim Coordinate set.
#
# Coordinates currently in Full_Body_with_ball.osim:
#   pelvis_tilt, pelvis_list, pelvis_rotation, pelvis_tx/ty/tz
#   hip_flexion_{r,l}, hip_adduction_{r,l}, hip_rotation_{r,l}
#   knee_angle_{r,l}, ankle_angle_{r,l}, subtalar_angle_{r,l}, mtp_angle_{r,l}
#   arm_flex_{r,l}, arm_add_{r,l}, arm_rot_{r,l}
#   elbow_flex_{r,l}, pro_sup_{r,l}
#   wrist_flex_{r,l}, wrist_dev_{r,l}
#   plus lumbar / cervical / thorax DOFs
FULL_BODY_CONFIG = MotModelConfig(
    name='full_body_with_ball',
    osim_path=os.path.join(MODELS_DIR, 'Full_Body_with_ball.osim'),
    angle_columns=[
        # ---------------- Right arm ----------------
        ('arm_flex_r',    'right_hip',      'right_shoulder', 'right_elbow',      180, -90, 180),
        ('elbow_flex_r',  'right_shoulder', 'right_elbow',    'right_wrist',      180,   0, 150),
        ('wrist_flex_r',  'right_elbow',    'right_wrist',    'right_index',      180, -90,  90),
        # ---------------- Left arm -----------------
        ('arm_flex_l',    'left_hip',       'left_shoulder',  'left_elbow',       180, -90, 180),
        ('elbow_flex_l',  'left_shoulder',  'left_elbow',     'left_wrist',       180,   0, 150),
        ('wrist_flex_l',  'left_elbow',     'left_wrist',     'left_index',       180, -90,  90),
        # ---------------- Right leg ----------------
        ('hip_flexion_r', 'right_shoulder', 'right_hip',      'right_knee',       180, -30, 120),
        ('knee_angle_r',  'right_hip',      'right_knee',     'right_ankle',      180,   0, 150),
        ('ankle_angle_r', 'right_knee',     'right_ankle',    'right_foot_index',  90, -45,  45),
        # ---------------- Left leg -----------------
        ('hip_flexion_l', 'left_shoulder',  'left_hip',       'left_knee',        180, -30, 120),
        ('knee_angle_l',  'left_hip',       'left_knee',      'left_ankle',       180,   0, 150),
        ('ankle_angle_l', 'left_knee',      'left_ankle',     'left_foot_index',   90, -45,  45),
    ],
    include_ball=True,
    ball_anchor_landmark='right_shoulder',
)

# ======================================================================
# NECK MODEL - DEFAULT (Head & Cervical Spine Tracking)
# ======================================================================
# Tracks 7 DOFs: head flexion, rotation, lateral flexion (2), cervical extension,
# shoulder elevation (2). Uses nose, ears, shoulders, hips, mouth landmarks.
# Best for: Head/neck movement analysis, cervical spine ROM
#
# To switch models, uncomment desired config below and update
# discover_available_models() to use it instead of NECK_MODEL_CONFIG
# ======================================================================

NECK_MODEL_CONFIG = MotModelConfig(
    name='Neck_model',
    osim_path=os.path.join(MODELS_DIR, 'Neck_model.osim'),
    angle_columns=[
        # Head flexion/extension: nose relative to shoulders
        ('head_flexion',      'right_shoulder',  'nose',            'left_shoulder',   90, -45,  45),
        # Head rotation: right ear relative to left ear through nose
        ('head_rotation',     'left_ear',        'nose',            'right_ear',       0,  -90,  90),
        # Right lateral flexion: right ear to nose to left shoulder
        ('head_lat_flex_r',   'left_shoulder',   'nose',            'right_ear',       90, -45,  45),
        # Left lateral flexion: left ear to nose to right shoulder
        ('head_lat_flex_l',   'right_shoulder',  'nose',            'left_ear',        90, -45,  45),
        # Cervical extension: chin/mouth relative to shoulders and ears
        ('cervical_ext',      'right_shoulder',  'mouth_left',      'left_shoulder',   90, -45,  45),
        # Right shoulder elevation: right shoulder relative to hips
        ('shoulder_elev_r',   'right_hip',       'right_shoulder',  'right_ear',       90,   0, 180),
        # Left shoulder elevation: left shoulder relative to hips
        ('shoulder_elev_l',   'left_hip',        'left_shoulder',   'left_ear',        90,   0, 180),
    ],
    include_ball=False,
)

# GPK_generic.osim — Lower body + lumbar spine (pelvis, hips, knees, ankles, lumbar)
#
# "midpoint_hips" and "midpoint_shoulders" are synthetic landmarks computed
# on-the-fly in write_opensim_mot() as the average of the left/right pair.
# Pelvis translations are approximated from pixel position scaled to metres.
GPK_GENERIC_CONFIG = MotModelConfig(
    name='GPK_generic',
    osim_path=os.path.join(MODELS_DIR, 'GPK_generic.osim'),
    angle_columns=[
        # Pelvis orientation (3 DOF) — 2-D approximations from sagittal view
        # tilt  : forward tilt of trunk — shoulder-to-hip angle vs vertical
        ('pelvis_tilt',        'right_shoulder',  'right_hip',       'right_knee',      180, -45,  45),
        # list  : lateral lean — left-hip to right-hip tilt
        ('pelvis_list',        'right_hip',       'midpoint_hips',   'left_hip',         90, -30,  30),
        # rotation: approximated as 0 (requires 3-D depth information)
        ('pelvis_rotation',    'right_shoulder',  'right_hip',       'left_hip',          0, -30,  30),
        # Pelvis translation — encoded as synthetic columns; resolved in writer
        ('pelvis_tx',          '_pelvis_tx_',     '_pelvis_tx_',     '_pelvis_tx_',       0, -15,  15),
        ('pelvis_ty',          '_pelvis_ty_',     '_pelvis_ty_',     '_pelvis_ty_',       0,  -1,   2),
        ('pelvis_tz',          'right_hip',       'left_hip',        'right_shoulder',    0,  -1,   1),
        # Right hip (3 DOF)
        # flexion: thigh angle relative to trunk  (shoulder→hip→knee)
        ('hip_flexion_r',      'right_shoulder',  'right_hip',       'right_knee',       180, -30, 120),
        # adduction: in-plane medial/lateral (hip→knee relative to pelvis width)
        ('hip_adduction_r',    'left_hip',        'right_hip',       'right_knee',        90, -30,  30),
        # rotation: set to 0 (not reliably estimated from 2-D)
        ('hip_rotation_r',     'right_shoulder',  'right_hip',       'left_hip',           0, -40,  40),
        # Right knee (2 DOF)
        # flexion: thigh-to-shank angle  (hip→knee→ankle)
        ('knee_angle_r',       'right_hip',       'right_knee',      'right_ankle',      180,   0, 150),
        # adduction: approximate from coronal projection
        ('knee_adduction_r',   'left_knee',       'right_knee',      'right_ankle',       90, -20,  20),
        # Right ankle (3 DOF)
        # dorsiflexion: shank-to-foot angle  (knee→ankle→foot_index)
        ('ankle_angle_r',      'right_knee',      'right_ankle',     'right_foot_index',  90, -40,  30),
        # subtalar: heel-to-toe relative to shank
        ('subtalar_angle_r',   'right_ankle',     'right_heel',      'right_foot_index',   0, -20,  20),
        # mtp: toe angle (ankle→heel→foot_index)
        ('mtp_angle_r',        'right_ankle',     'right_heel',      'right_foot_index',  90, -20,  20),
        # Left hip (3 DOF)
        ('hip_flexion_l',      'left_shoulder',   'left_hip',        'left_knee',        180, -30, 120),
        ('hip_adduction_l',    'right_hip',       'left_hip',        'left_knee',         90, -30,  30),
        ('hip_rotation_l',     'left_shoulder',   'left_hip',        'right_hip',          0, -40,  40),
        # Left knee (2 DOF)
        ('knee_angle_l',       'left_hip',        'left_knee',       'left_ankle',       180,   0, 150),
        ('knee_adduction_l',   'right_knee',      'left_knee',       'left_ankle',        90, -20,  20),
        # Left ankle (3 DOF)
        ('ankle_angle_l',      'left_knee',       'left_ankle',      'left_foot_index',   90, -40,  30),
        ('subtalar_angle_l',   'left_ankle',      'left_heel',       'left_foot_index',    0, -20,  20),
        ('mtp_angle_l',        'left_ankle',      'left_heel',       'left_foot_index',   90, -20,  20),
        # Lumbar spine (3 DOF) — uses synthetic midpoint landmarks
        # extension: trunk forward tilt (hip-midpoint → shoulder-midpoint)
        ('lumbar_extension',   'midpoint_hips',   'midpoint_shoulders', 'right_shoulder', 90, -60,  60),
        # bending: lateral lean of trunk
        ('lumbar_bending',     'right_shoulder',  'midpoint_shoulders','left_shoulder',   90, -45,  45),
        # rotation: approximated as 0
        ('lumbar_rotation',    'right_shoulder',  'right_hip',       'left_hip',           0, -45,  45),
    ],
    include_ball=False,
)


# ======================================================================
# ALTERNATIVE MODEL CONFIGURATIONS (Uncomment to use as default)
# ======================================================================

# OPTION 1: ARM26_BALL (Right Arm Only + Ball Tracking)
# Uncomment to use:
# DEFAULT_MODEL = ARM26_BALL_CONFIG
# Best for: Right arm throwing motion, ball tracking
#
# OPTION 2: FULL_BODY_WITH_BALL (Complete Body + Ball)
# Uncomment to use:
# DEFAULT_MODEL = FULL_BODY_CONFIG
# Best for: Full-body motion capture with ball
#
# OPTION 3: Any .osim file in this directory
# The discover_available_models() function automatically creates
# generic configs for any .osim files found. To use a specific one:
# 1. Place the .osim file in C:\Git\app\record\
# 2. Select it from the Recording tab dropdown
# 3. Or set in settings.py: DEFAULT_OSIM_MODEL = "your_model_name"


# ------------------------------------------------------------------
# Dynamic model discovery
# ------------------------------------------------------------------

def discover_available_models():
    """Discover all .osim model files in MODULE_DIR and return as dict.

    Returns
    -------
    dict
        Dictionary mapping model name (without .osim) to MotModelConfig.
        Special cases (arm26_ball, full_body_with_ball) use predefined configs.
        Other models get generic configs with basic arm joint angles.
    """
    models = {}

    # Add predefined configs first
    models['arm26_ball'] = ARM26_BALL_CONFIG
    models['full_body_with_ball'] = FULL_BODY_CONFIG
    models['Neck_model'] = NECK_MODEL_CONFIG
    models['GPK_generic'] = GPK_GENERIC_CONFIG

    # Scan directory for .osim files
    try:
        osim_files = [f for f in os.listdir(MODELS_DIR) if f.endswith('.osim')]

        for osim_file in osim_files:
            model_name = osim_file.replace('.osim', '')

            # Skip if already defined
            if model_name in models:
                continue

            # Create generic config for unknown models
            # Basic arm angles work for most models
            generic_config = MotModelConfig(
                name=model_name,
                osim_path=os.path.join(MODELS_DIR, osim_file),
                angle_columns=[
                    # Right arm
                    ('r_shoulder_flex', 'right_hip',      'right_shoulder', 'right_elbow', 180, -90, 180),
                    ('r_elbow_flex',    'right_shoulder', 'right_elbow',    'right_wrist', 180, 0, 150),
                    # Left arm
                    ('l_shoulder_flex', 'left_hip',       'left_shoulder',  'left_elbow',  180, -90, 180),
                    ('l_elbow_flex',    'left_shoulder',  'left_elbow',     'left_wrist',  180, 0, 150),
                    # Basic legs
                    ('r_hip_flex',      'right_hip',      'right_knee',     'right_ankle', 180, -30, 120),
                    ('r_knee_flex',     'right_knee',     'right_ankle',    'right_foot_index', 180, 0, 150),
                    ('l_hip_flex',      'left_hip',       'left_knee',      'left_ankle',  180, -30, 120),
                    ('l_knee_flex',     'left_knee',      'left_ankle',     'left_foot_index', 180, 0, 150),
                ],
                include_ball=False,
            )
            models[model_name] = generic_config

    except Exception as e:
        print(f"Warning: Could not discover models: {e}")

    return models


# Pre-compute available models at module load time
AVAILABLE_MODELS = discover_available_models()


class MovementTracker:
    """Track human movement and ball trajectory from a camera feed.

    One record is stored per video frame:
        (annotated_bgr_frame, wall_clock_time, pose_lm_dict_or_None, ball_center_or_None)

    Outputs
    -------
    save_frames()         — every frame annotated with skeleton + ball path → folder
    plot_joint_angles()   — shoulder & elbow angle time-series → PNG
    analyze_release()     — two-panel release (top) / catch (bottom) figure → PNG
    write_opensim_mot()   — full-session MOT for arm26_ball.osim → .mot
    """

    def __init__(self, max_trajectory_length=200, hsv_lower=None, hsv_upper=None,
                 ball_color='orange'):
        self.max_trajectory_length = max_trajectory_length
        self.trajectory = deque(maxlen=max_trajectory_length)
        self._records = []          # populated by track_and_display
        self._duration_seconds = 0
        self._frame_shape = None    # (h, w) set on first captured frame

        # MediaPipe Pose (Tasks API)
        # Use 'full' model for better accuracy on small/distant players
        _record_dir = Path(__file__).parent
        model_path = _record_dir / "pose_landmarker_full.task"
        if not model_path.exists():
            url = ("https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
                   "pose_landmarker_full/float16/latest/pose_landmarker_full.task")
            print("Downloading pose landmarker model (full)…")
            try:
                import urllib.request as _ur
                req = _ur.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with _ur.urlopen(req, timeout=20) as resp:
                    total = int(resp.headers.get("Content-Length", 0))
                    downloaded = 0
                    chunk = 1 << 16
                    with open(model_path, "wb") as fh:
                        while True:
                            buf = resp.read(chunk)
                            if not buf:
                                break
                            fh.write(buf)
                            downloaded += len(buf)
                            if total:
                                pct = int(downloaded / total * 100)
                                print(f"  {pct}% ({downloaded / 1_048_576:.1f} MB)", end="\r", flush=True)
                print("\n✓ Model downloaded successfully")
            except Exception as e:
                print(f"ERROR: Failed to download pose landmarker model: {e}")
                raise

        print(f"✓ Pose landmarker model found: {model_path.resolve()}")
        try:
            base_opts = mp_python.BaseOptions(model_asset_path=str(model_path))
            self._pose_landmarker = mp_vision.PoseLandmarker.create_from_options(
                mp_vision.PoseLandmarkerOptions(base_options=base_opts, num_poses=1)
            )
            print(f"✓ PoseLandmarker initialized successfully")
        except Exception as e:
            print(f"ERROR: Failed to create PoseLandmarker: {e}")
            raise

        # Ball HSV colour range — pick a preset or supply custom bounds
        _HSV_PRESETS = {
            # Basketball (NBA orange/brown)
            'orange': (np.array([5,  120,  80]), np.array([25, 255, 255])),
            # Tennis / soccer ball (yellow-green)
            'yellow': (np.array([25,  80,  80]), np.array([40, 255, 255])),
            # Green ball / marker
            'green':  (np.array([35,  50,  30]), np.array([85, 255, 255])),
        }
        if hsv_lower is not None and hsv_upper is not None:
            self.hsv_lower, self.hsv_upper = np.array(hsv_lower), np.array(hsv_upper)
        else:
            preset = _HSV_PRESETS.get(ball_color, _HSV_PRESETS['orange'])
            self.hsv_lower, self.hsv_upper = preset
        # Second HSV range for orange (wraps around hue=0 for red-orange tones)
        self._hsv_lower2 = np.array([170, 120,  80]) if ball_color == 'orange' else None
        self._hsv_upper2 = np.array([180, 255, 255]) if ball_color == 'orange' else None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _test_camera(self, camera_type='webcam'):
        """Test if the specified camera can be opened."""
        cap = cv2.VideoCapture(0 if camera_type == 'webcam' else "http://192.168.0.107:8080/video")
        if not cap.isOpened():
            print(f"Error: Unable to open {camera_type} camera.")
        cap.release()

    def record_video(self, duration_seconds=10, camera_type='webcam', ip_address=None, output_dir=None,
                     target_fps=None, detection_interval=1):
        """Record raw camera footage for `duration_seconds` and save as video.mp4.

        Frames are also stored in self._records so all analysis methods
        (save_frames, plot_joint_angles, etc.) work normally afterward.

        Parameters
        ----------
        duration_seconds : int or float
            How long to record.
        camera_type : str
            'webcam' for device 0, 'ip' for IP Webcam stream.
        ip_address : str, optional
            IP camera URL (only used when camera_type='ip').
            Example: "http://192.168.x.x:8080/video"
        output_dir : str or Path, optional
            Folder to write video.mp4 into.  Created if it does not exist.
            Defaults to outputs/test_<timestamp>/.
        target_fps : float, optional
            Override the camera-reported FPS for the VideoWriter.
            Useful when the camera reports an incorrect value or you want
            to record at a specific rate (e.g. 60).  Defaults to the value
            reported by cv2.CAP_PROP_FPS (fallback 30).
        detection_interval : int
            Run pose + ball detection only every N frames.  Set to 1 (default)
            for every frame; increase (e.g. 2 or 3) to raise the effective
            capture frame rate when processing is the bottleneck.  Frames
            that skip detection reuse the last known landmark / ball result.

        Returns
        -------
        Path
            Path to the saved .mp4 file.
        """
        if output_dir is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path(f"outputs/test_{ts}")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        self._duration_seconds = duration_seconds
        self._records.clear()
        self.trajectory.clear()

        # Determine camera source
        if camera_type == 'webcam':
            src = 0
        elif camera_type == 'ip':
            src = ip_address or "http://192.168.0.107:8080/video"  # Fallback to default if not provided
        else:
            src = 0  # Default to webcam

        print(f"Opening {camera_type} camera (source={src})...")
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            print(f"ERROR: Cannot open {camera_type} camera (source={src})")
            return None

        print(f"✓ Camera opened successfully")
        cam_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        fps = float(target_fps) if target_fps else cam_fps
        w    = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h    = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"  Camera properties: {w}x{h} @ {cam_fps:.1f} fps (will use {fps:.1f} fps)")
        # IP camera streams in portrait orientation rotated 90° CCW — swap dims
        if camera_type != 'webcam':
            w, h = h, w
        if self._frame_shape is None:
            self._frame_shape = (h, w)

        # VideoWriter setup with fallback approach
        video_path = output_dir / "video.avi"
        frames_dir_fallback = output_dir / "frames_raw"  # Fallback frame storage

        print(f"\n[Video Recording Setup]")
        print(f"  Frame size: {w}x{h}")
        print(f"  FPS: {fps}")
        print(f"  Output path: {video_path}")

        # Try to create VideoWriter, but don't fail if it doesn't work
        writer = None
        use_fallback = False

        try:
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            writer = cv2.VideoWriter(str(video_path), fourcc, fps, (w, h))

            if writer and writer.isOpened():
                print(f"  ✓ VideoWriter initialized with MJPEG codec")
            else:
                print(f"  ⚠ VideoWriter failed, using fallback frame capture")
                use_fallback = True
                writer = None
                frames_dir_fallback.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"  ⚠ VideoWriter error: {e}")
            print(f"  Using fallback frame capture")
            use_fallback = True
            writer = None
            frames_dir_fallback.mkdir(parents=True, exist_ok=True)

        print(f"  Mode: {'VideoWriter' if writer else 'Fallback (PNG frames)'}")

        detection_interval = max(1, int(detection_interval))

        # --- Background reader thread: drains camera buffer at full speed ---
        _stop = threading.Event()
        _latest = [None]   # holds (timestamp, frame) — always the newest

        def _reader():
            while not _stop.is_set():
                ret, f = cap.read()
                if not ret:
                    _stop.set(); break
                if camera_type != 'webcam':
                    f = cv2.rotate(f, cv2.ROTATE_90_COUNTERCLOCKWISE)
                _latest[0] = (time.time(), f)

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()
        print(f"Waiting for first frame from camera...")
        wait_start = time.time()
        while _latest[0] is None and not _stop.is_set():
            time.sleep(0.001)
            if time.time() - wait_start > 5:
                print(f"ERROR: No frames received from camera after 5 seconds")
                _stop.set()
                reader_thread.join(timeout=1)
                return None

        print(f"✓ First frame received from camera")
        print(f"Recording {duration_seconds}s @ {fps:.0f} fps "
              f"(detect every {detection_interval} frame(s)) -> {video_path.resolve()}")
        session_start = time.time()
        frame_idx = 0
        frames_written = 0
        last_pose_lm, last_center = None, None
        last_t = 0.0

        frame_checks = 0
        frames_skipped_same_t = 0
        frames_none = 0
        write_errors = 0

        print(f"\n[Frame Capture Loop Starting]")
        first_frame_logged = False

        print(f"  Starting main recording loop for {duration_seconds}s...")
        loop_start = time.time()

        while (time.time() - session_start) < duration_seconds and not _stop.is_set():
            frame_checks += 1
            item = _latest[0]
            if item is None:
                frames_none += 1
                # Print status periodically
                if frame_checks == 1:
                    print(f"  Waiting for camera frames...")
                if frame_checks % 1000 == 0:
                    elapsed_so_far = time.time() - session_start
                    print(f"  {elapsed_so_far:.1f}s: Still waiting for frames (checks: {frame_checks})")
                time.sleep(0.001); continue
            t, frame = item
            if t == last_t:          # no new frame yet
                frames_skipped_same_t += 1
                time.sleep(0.0005); continue
            last_t = t

            # Verify frame format
            if frame is None:
                print(f"WARNING: Frame is None at index {frame_idx}")
                continue

            if not isinstance(frame, np.ndarray):
                print(f"WARNING: Frame is not ndarray, got {type(frame)}")
                continue

            # Log first frame details
            if not first_frame_logged:
                print(f"  First frame received:")
                print(f"    Shape: {frame.shape}")
                print(f"    Dtype: {frame.dtype}")
                print(f"    Size: {frame.nbytes / (1024*1024):.2f} MB")
                first_frame_logged = True

            # Write to video file or fallback
            if writer:
                # NOTE: cv2.VideoWriter.write() returns None, NOT a success flag.
                # Detect real failures via exceptions / writer state, not the return value.
                try:
                    writer.write(frame)
                    if not writer.isOpened():
                        raise RuntimeError("VideoWriter closed unexpectedly")
                    frames_written += 1
                    if frames_written % 10 == 0:
                        print(f"  {frames_written} frames written to video...")
                except Exception as e:
                    write_errors += 1
                    if write_errors == 1:
                        print(f"  ⚠ Switching to fallback (writer.write() failed: {e})")
                        writer = None
                        use_fallback = True
                        frames_dir_fallback.mkdir(parents=True, exist_ok=True)

            if use_fallback:
                # Save frame as PNG in fallback directory
                try:
                    frame_path = frames_dir_fallback / f"frame_{frame_idx:06d}.png"
                    cv2.imwrite(str(frame_path), frame)
                    frames_written += 1
                    if frames_written % 10 == 0:
                        print(f"  {frames_written} frames saved (PNG fallback)...")
                except Exception as e:
                    write_errors += 1
                    if write_errors == 1:
                        print(f"  ✗ Even PNG fallback failed: {e}")

            # Pose + ball — only every detection_interval frames
            if frame_idx % detection_interval == 0:
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB,
                                  data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                pose_result = self._pose_landmarker.detect(mp_img)
                last_pose_lm = None
                if pose_result.pose_landmarks:
                    last_pose_lm = {
                        name: (lm.x * w, lm.y * h)
                        for name, lm in zip(_LANDMARK_NAMES, pose_result.pose_landmarks[0])
                        if (lm.visibility or 0.0) >= 0.3
                    }
                last_center = self._detect_ball(frame)

            if last_center:
                self.trajectory.append(last_center)

            self._records.append((frame.copy(), t, last_pose_lm, last_center))
            frame_idx += 1

            # Only show preview if display is available
            try:
                cv2.imshow('Recording', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            except:
                # No display available (running in subprocess)
                pass

        _stop.set()
        reader_thread.join(timeout=2)

        # Release writer and check file size
        if writer:
            writer.release()
        cap.release()

        try:
            cv2.destroyAllWindows()
        except:
            pass

        elapsed = time.time() - session_start
        ball_count = sum(1 for r in self._records if r[3] is not None)
        actual_fps = len(self._records) / elapsed if elapsed > 0 else 0

        # Check if video file was actually created
        if not video_path.exists():
            print(f"ERROR: Video file was not created at {video_path}")
            return None

        file_size = video_path.stat().st_size
        print(f"\n[Recording Complete]")
        print(f"  Frames captured: {len(self._records)}")
        print(f"  Frames written to file: {frames_written}")
        print(f"  Duration: {elapsed:.1f}s")
        print(f"  Actual FPS: {actual_fps:.1f}")
        print(f"  Ball detections: {ball_count}")
        print(f"  Video file size: {file_size / (1024*1024):.1f} MB")
        print(f"  Video path: {video_path.resolve()}")
        print(f"\n[Frame Loop Diagnostics]")
        print(f"  Loop iterations: {frame_checks}")
        print(f"  Frames skipped (no new frame): {frames_skipped_same_t}")
        print(f"  Iterations with None frame: {frames_none}")
        print(f"  Write operations attempted: {frames_written + write_errors}")
        print(f"  Write operations succeeded: {frames_written}")
        print(f"  Write operations failed: {write_errors}")
        print(f"  Effective frame capture rate: {frames_written / elapsed if elapsed > 0 else 0:.1f} fps")

        if not use_fallback and file_size == 0:
            print(f"\nERROR: Video file is empty (0 bytes).")
            if frames_written == 0:
                print(f"  → No frames were written to the file")
                print(f"  → Camera may not be providing frames")
                print(f"  → Check camera connection and permissions")
            else:
                print(f"  → {frames_written} frames were written but file is still empty (codec issue)")
            # Note: MOT file may still be generated if frames were captured in self._records
            if len(self._records) > 0:
                print(f"  → But {len(self._records)} frames ARE in records - MOT may still be generated")

        if use_fallback:
            print(f"\nℹ  Fallback mode was used (PNG frame capture)")
            print(f"  → Frames saved to: {frames_dir_fallback}")
            print(f"  → Video file may be empty but MOT file should be valid")
            if len(self._records) == 0:
                print(f"  ✗ ERROR: No frames captured even in fallback mode")
                return None

        return video_path

    def _detect_ball(self, frame):
        """Return (cx, cy) of the most circular coloured blob, or None.

        Uses self.hsv_lower/upper (primary range) and optionally
        self._hsv_lower2/upper2 (secondary range for orange hue wrap-around).
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self.hsv_lower, self.hsv_upper)
        if self._hsv_lower2 is not None:
            mask = cv2.bitwise_or(mask, cv2.inRange(hsv, self._hsv_lower2, self._hsv_upper2))

        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        best, best_score = None, 0
        for c in contours:
            area = cv2.contourArea(c)
            if area < 200:          # ~15px diameter minimum (works for distant balls)
                continue
            if area > 50000:        # ignore huge blobs (stands, jerseys)
                continue
            p = cv2.arcLength(c, True)
            if p == 0:
                continue
            circ = (4 * np.pi * area) / (p ** 2)
            if circ < 0.50:         # keep reasonably round shapes
                continue
            score = area * circ
            if score > best_score:
                best_score, best = score, c
        if best is not None:
            M = cv2.moments(best)
            if M["m00"] != 0:
                return (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
        return None

    @staticmethod
    def _angle_between(a, vertex, b):
        """Angle in degrees at `vertex` formed by points a-vertex-b."""
        va = np.array(a) - np.array(vertex)
        vb = np.array(b) - np.array(vertex)
        cos_a = np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb) + 1e-9)
        return float(np.degrees(np.arccos(np.clip(cos_a, -1.0, 1.0))))

    def _wrist_pts(self, lm):
        """Return list of (x, y) wrist positions from a pose landmark dict."""
        if lm is None:
            return []
        pts = []
        for k in ('left_wrist', 'right_wrist'):
            p = lm.get(k)
            if p is not None:
                pts.append(p)
        return pts

    def _ball_records(self):
        """Frames with ball detected: list of (record_index, timestamp, ball_center)."""
        return [(i, r[1], r[3]) for i, r in enumerate(self._records) if r[3] is not None]

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def track_and_display(self, duration_seconds=10, camera_type='webcam',
                          detection_interval=1):
        """Run the camera loop for `duration_seconds` wall-clock seconds.

        Every frame is stored in self._records with full annotations
        already drawn (pose skeleton + trajectory) in BGR.

        Parameters
        ----------
        detection_interval : int
            Run pose + ball detection only every N frames (default 1 = every
            frame).  Increase to raise effective capture rate when inference
            is the bottleneck; skipped frames reuse the last known result.
        """
        self._duration_seconds = duration_seconds
        self._records.clear()
        self.trajectory.clear()

        cap = cv2.VideoCapture(
            0 if camera_type == 'webcam' else "http://192.168.0.107:8080/video"
        )
        if not cap.isOpened():
            print("Error: Cannot open camera.")
            return

        detection_interval = max(1, int(detection_interval))

        # --- Background reader thread ---
        _stop = threading.Event()
        _latest = [None]

        def _reader():
            while not _stop.is_set():
                ret, f = cap.read()
                if not ret:
                    _stop.set(); break
                if camera_type != 'webcam':
                    f = cv2.rotate(f, cv2.ROTATE_90_CLOCKWISE)
                _latest[0] = (time.time(), f)

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()
        while _latest[0] is None and not _stop.is_set():
            time.sleep(0.001)
        if self._frame_shape is None and _latest[0]:
            self._frame_shape = _latest[0][1].shape[:2]

        print(f"Tracking for {duration_seconds} seconds "
              f"(detect every {detection_interval} frame(s)). Press 'q' to stop.")
        session_start = time.time()
        frame_idx = 0
        last_pose_lm, last_center = None, None
        last_t = 0.0

        while (time.time() - session_start) < duration_seconds and not _stop.is_set():
            item = _latest[0]
            if item is None:
                time.sleep(0.001); continue
            t, frame = item
            if t == last_t:
                time.sleep(0.0005); continue
            last_t = t
            frame = frame.copy()

            # --- Pose estimation (every detection_interval frames) ---
            if frame_idx % detection_interval == 0:
                mp_img = mp.Image(image_format=mp.ImageFormat.SRGB,
                                  data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                pose_result = self._pose_landmarker.detect(mp_img)
                last_pose_lm = None
                if pose_result.pose_landmarks:
                    h_f, w_f = frame.shape[:2]
                    last_pose_lm = {
                        name: (lm.x * w_f, lm.y * h_f)
                        for name, lm in zip(_LANDMARK_NAMES, pose_result.pose_landmarks[0])
                        if (lm.visibility or 0.0) >= 0.3
                    }
                last_center = self._detect_ball(frame)

            pose_lm = last_pose_lm
            center  = last_center

            # --- Draw full skeleton (arms + legs) ---
            if pose_lm is not None:
                all_joints = ('left_shoulder', 'right_shoulder',
                              'left_elbow', 'right_elbow',
                              'left_wrist', 'right_wrist',
                              'left_hip', 'right_hip',
                              'left_knee', 'right_knee',
                              'left_ankle', 'right_ankle')
                for joint in all_joints:
                    if joint in pose_lm:
                        jx, jy = int(pose_lm[joint][0]), int(pose_lm[joint][1])
                        cv2.circle(frame, (jx, jy), 5, (255, 100, 0), -1)
                for side in ('left', 'right'):
                    arm = [pose_lm.get(f'{side}_{j}')
                           for j in ('shoulder', 'elbow', 'wrist')]
                    leg = [pose_lm.get(f'{side}_{j}')
                           for j in ('hip', 'knee', 'ankle')]
                    for chain, color in ((arm, (255, 100, 0)), (leg, (0, 200, 100))):
                        for a, b in zip(chain, chain[1:]):
                            if a and b:
                                cv2.line(frame, (int(a[0]), int(a[1])),
                                         (int(b[0]), int(b[1])), color, 2)
                    # trunk line (shoulder → hip)
                    sh = pose_lm.get(f'{side}_shoulder')
                    hp = pose_lm.get(f'{side}_hip')
                    if sh and hp:
                        cv2.line(frame, (int(sh[0]), int(sh[1])),
                                 (int(hp[0]), int(hp[1])), (180, 60, 220), 2)

            # --- Ball ---
            if center:
                self.trajectory.append(center)
                cv2.circle(frame, center, 10, (0, 255, 0), 2)

            # --- Trajectory overlay ---
            if len(self.trajectory) > 1:
                pts = np.array(list(self.trajectory), dtype=np.int32)
                cv2.polylines(frame, [pts], False, (0, 255, 255), 2)

            self._records.append((frame.copy(), t, pose_lm, center))
            frame_idx += 1
            cv2.imshow('Movement Tracker', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        _stop.set()
        reader_thread.join(timeout=2)
        cap.release()
        cv2.destroyAllWindows()
        ball_count = sum(1 for r in self._records if r[3] is not None)
        elapsed = time.time() - session_start
        actual_fps = len(self._records) / elapsed if elapsed > 0 else 0
        print(f"Captured {len(self._records)} frames ({actual_fps:.1f} fps actual), "
              f"{ball_count} with ball detected.")

    # ------------------------------------------------------------------
    # Save ALL annotated frames
    # ------------------------------------------------------------------

    def save_frames(self, folder):
        """Save every captured frame as a PNG with pose skeleton overlays.

        Each image shows the pose skeleton with joint-angle labels, drawn directly
        using OpenCV for speed. Supports both arm26_ball and Neck_model configs.
        Frames are written to `folder/frame_NNNNN.png`.
        """
        if not self._records:
            print("No frames to save.")
            return
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)

        total = len(self._records)
        print(f"Saving {total} annotated frames to {folder.resolve()}")

        for fi, (frame_bgr, t, lm, center) in enumerate(self._records):
            # Create annotated frame using OpenCV (much faster than matplotlib)
            annotated = frame_bgr.copy()
            h, w = annotated.shape[:2]

            # Draw pose skeleton + angle labels
            if lm is not None:
                # Helper: draw a line between two landmarks if both visible
                def _line(p1, p2, color, thickness=2):
                    if p1 and p2:
                        cv2.line(annotated,
                                 (int(p1[0]), int(p1[1])),
                                 (int(p2[0]), int(p2[1])),
                                 color, thickness)

                def _dot(p, color, r=4):
                    if p:
                        cv2.circle(annotated, (int(p[0]), int(p[1])), r, color, -1)
                        cv2.circle(annotated, (int(p[0]), int(p[1])), r, (255, 255, 255), 1)

                # Collect pending angle labels → draw after skeleton to avoid overlap
                angle_labels = []  # list of (x, y, text, color)

                # ===== FULL BODY SKELETON =====
                # Right side: orange (#e07b39 → BGR 57,123,224)
                # Left side:  blue   (#39a7e0 → BGR 224,167,57)
                RIGHT = (57, 123, 224)
                LEFT  = (224, 167, 57)
                BODY  = (180, 180, 180)

                for side, color in (('left', LEFT), ('right', RIGHT)):
                    shoulder   = lm.get(f'{side}_shoulder')
                    elbow      = lm.get(f'{side}_elbow')
                    wrist      = lm.get(f'{side}_wrist')
                    hip        = lm.get(f'{side}_hip')
                    knee       = lm.get(f'{side}_knee')
                    ankle      = lm.get(f'{side}_ankle')
                    foot_index = lm.get(f'{side}_foot_index')
                    heel       = lm.get(f'{side}_heel')
                    index      = lm.get(f'{side}_index')

                    # Draw limb segments
                    _line(shoulder, elbow, color)
                    _line(elbow, wrist, color)
                    _line(hip, knee, color)
                    _line(knee, ankle, color)
                    _line(ankle, heel, color)
                    _line(heel, foot_index, color)

                    # Dot each joint
                    for pt in [shoulder, elbow, wrist, hip, knee, ankle, foot_index]:
                        _dot(pt, color)

                    # Shoulder-elbow angle (elbow flexion), label offset from elbow
                    if shoulder and elbow and wrist:
                        ang = self._angle_between(shoulder, elbow, wrist)
                        if 0 <= ang <= 180:
                            ex, ey = int(elbow[0]), int(elbow[1])
                            angle_labels.append((ex + 12, ey - 8, f"Elb {ang:.0f}d", color))

                    # Hip-knee angle (knee flexion), label offset from knee
                    if hip and knee and ankle:
                        ang = self._angle_between(hip, knee, ankle)
                        if 0 <= ang <= 180:
                            kx, ky = int(knee[0]), int(knee[1])
                            angle_labels.append((kx + 12, ky - 8, f"Kn {ang:.0f}d", color))

                    # Knee-ankle angle (ankle), label offset from ankle
                    if knee and ankle and foot_index:
                        ang = self._angle_between(knee, ankle, foot_index)
                        if 0 <= ang <= 180:
                            ax_, ay = int(ankle[0]), int(ankle[1])
                            angle_labels.append((ax_ + 12, ay - 8, f"Ank {ang:.0f}d", color))

                # Torso connections (shoulders ↔ hips)
                ls, rs = lm.get('left_shoulder'), lm.get('right_shoulder')
                lh, rh = lm.get('left_hip'),      lm.get('right_hip')
                _line(ls, rs, BODY)
                _line(lh, rh, BODY)
                _line(ls, lh, BODY)
                _line(rs, rh, BODY)

                # Head (nose)
                nose = lm.get('nose')
                _dot(nose, (0, 255, 255), r=5)
                if nose and ls and rs:
                    mid_sh = ((ls[0]+rs[0])/2, (ls[1]+rs[1])/2)
                    _line(nose, mid_sh, BODY)

                # ===== DRAW ANGLE LABELS (de-overlapped) =====
                # Sort by y so labels read top-to-bottom, then nudge any that collide
                angle_labels.sort(key=lambda t: t[1])
                min_gap = 18  # pixels between label baselines
                placed = []   # (x, y) of already-placed labels
                for lx, ly, txt, col in angle_labels:
                    # Push down if too close to a previous label
                    for px, py in placed:
                        if abs(lx - px) < 60 and abs(ly - py) < min_gap:
                            ly = py + min_gap
                    placed.append((lx, ly))
                    # Background rect for readability
                    (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                    cv2.rectangle(annotated, (lx - 2, ly - th - 2), (lx + tw + 2, ly + 2),
                                  (0, 0, 0), -1)
                    cv2.putText(annotated, txt, (lx, ly),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, col, 1, cv2.LINE_AA)

            # Draw ball position if detected
            if center is not None:
                x, y = int(center[0]), int(center[1])
                cv2.circle(annotated, (x, y), 8, (0, 255, 0), -1)
                cv2.circle(annotated, (x, y), 8, (255, 255, 255), 2)

            # Add frame number
            cv2.putText(annotated, f"Frame {fi + 1} / {total}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

            # Save frame
            cv2.imwrite(str(folder / f"frame_{fi + 1:05d}.png"), annotated)

            if (fi + 1) % 10 == 0:
                print(f"  Saved {fi + 1}/{total} frames...")

        print(f"Done — {total} frames saved.")

    # ------------------------------------------------------------------
    # Joint angle plot
    # ------------------------------------------------------------------

    def plot_joint_angles(self, save_path=None):
        """Time-series of all detected joint angles — arms and legs, left and right."""
        if not self._records:
            print("No data recorded.")
            return

        # (panel_label, [(series_label, lm_a, lm_vertex, lm_b, color), ...])
        # For GPK_generic: show right and left in same subplot for easier comparison
        PANELS = [
            ('Hip Flexion', [
                ('Right', 'right_hip',      'right_knee',     'right_ankle',      '#d94f1e'),
                ('Left',  'left_hip',       'left_knee',      'left_ankle',       '#1e7fd9'),
            ]),
            ('Hip Adduction', [
                ('Right', 'right_hip',      'right_knee',     'left_hip',         '#d94f1e'),
                ('Left',  'left_hip',       'left_knee',      'right_hip',        '#1e7fd9'),
            ]),
            ('Hip Rotation', [
                ('Right', 'right_hip',      'right_knee',     'right_shoulder',   '#d94f1e'),
                ('Left',  'left_hip',       'left_knee',      'left_shoulder',    '#1e7fd9'),
            ]),
            ('Knee Flexion', [
                ('Right', 'right_hip',      'right_knee',     'right_ankle',      '#e07b39'),
                ('Left',  'left_hip',       'left_knee',      'left_ankle',       '#39a7e0'),
            ]),
            ('Knee Adduction', [
                ('Right', 'right_knee',     'right_ankle',    'left_knee',        '#e07b39'),
                ('Left',  'left_knee',      'left_ankle',     'right_knee',       '#39a7e0'),
            ]),
            ('Ankle Angle', [
                ('Right', 'right_knee',     'right_ankle',    'right_foot_index', '#e07b39'),
                ('Left',  'left_knee',      'left_ankle',     'left_foot_index',  '#39a7e0'),
            ]),
        ]

        t0 = self._records[0][1]

        # Collect angles
        panel_data = []   # [(panel_label, [(series_label, color, ts, vals)], ...]
        any_data = False
        for panel_label, series_defs in PANELS:
            series_out = []
            for s_label, lm_a, lm_v, lm_b, color in series_defs:
                ts, vals = [], []
                for _, t, lm, _ in self._records:
                    if lm is None:
                        continue
                    pa = lm.get(lm_a)
                    pv = lm.get(lm_v)
                    pb = lm.get(lm_b)
                    if pa and pv and pb:
                        ts.append(t - t0)
                        vals.append(self._angle_between(pa, pv, pb))
                if ts:
                    series_out.append((s_label, color, ts, vals))
                    any_data = True
            panel_data.append((panel_label, series_out))

        if not any_data:
            print("No pose landmarks found in any frame.")
            return

        # Only draw panels that have at least one series with data
        active_panels = [(lbl, s) for lbl, s in panel_data if s]
        n = len(active_panels)
        fig, axes = plt.subplots(n, 1, figsize=(13, 3.5 * n), sharex=True)
        if n == 1:
            axes = [axes]

        for ax, (panel_label, series_list) in zip(axes, active_panels):
            for s_label, color, ts, vals in series_list:
                ax.plot(ts, vals, label=s_label, color=color,
                        linewidth=1.8, marker='o', markersize=2)
            ax.set_ylabel('Angle (\u00b0)', fontsize=10)
            ax.set_title(panel_label, fontsize=11)
            ax.legend(fontsize=9)
            ax.grid(True, alpha=0.3)
            ax.set_ylim(0, 200)

        axes[-1].set_xlabel('Time (s)', fontsize=10)
        plt.suptitle('Joint Angles Over Time', fontsize=13, fontweight='bold')
        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Joint angles saved to {os.path.abspath(save_path)}")
        plt.close()

    # ------------------------------------------------------------------
    # Release / catch two-panel figure
    # ------------------------------------------------------------------

    def analyze_release(self, proximity_threshold=100, velocity_smoothing=5, save_path=None):
        """Detect ball release and catch; save two-panel figure if save_path given.

        Returns dict with release_point, catch_point, vx, vy, speed, angle_deg.
        """
        ball_recs = self._ball_records()
        if len(ball_recs) < velocity_smoothing + 1:
            print("Not enough ball detections for release analysis.")
            return None

        positions   = [c for _, _, c in ball_recs]
        timestamps  = [t for _, t, _ in ball_recs]
        rec_indices = [i for i, _, _ in ball_recs]
        n = len(positions)

        def _min_dist(ball_pos, pts):
            if not pts:
                return float('inf')
            return min(np.hypot(ball_pos[0] - px, ball_pos[1] - py) for px, py in pts)

        # Release: first frame where ball moves from near-wrist to far
        was_close = False
        release_idx = 0
        for i in range(n):
            lm = self._records[rec_indices[i]][2]
            d  = _min_dist(positions[i], self._wrist_pts(lm))
            if d <= proximity_threshold:
                was_close = True
            elif was_close:
                release_idx = i
                break

        # Catch: ball returns near wrist after release
        catch_idx = n - 1
        for i in range(release_idx + 1, n):
            lm = self._records[rec_indices[i]][2]
            if _min_dist(positions[i], self._wrist_pts(lm)) <= proximity_threshold:
                catch_idx = i
                break

        # Velocity at release
        end_idx = min(release_idx + velocity_smoothing, n - 1)
        dt = timestamps[end_idx] - timestamps[release_idx]
        if dt == 0:
            print("Zero elapsed time; cannot compute velocity.")
            return None
        dx = positions[end_idx][0] - positions[release_idx][0]
        dy = positions[end_idx][1] - positions[release_idx][1]
        vx    = dx / dt
        vy    = -dy / dt          # flip: pixel-Y is down
        speed = np.hypot(vx, vy)
        angle_deg     = np.degrees(np.arctan2(vy, vx))
        release_point = positions[release_idx]
        catch_point   = positions[catch_idx]
        flight_time   = timestamps[catch_idx] - timestamps[release_idx]
        flight_dets   = catch_idx - release_idx

        print("\n--- Release & Catch ---")
        print(f"Release : {release_point}  [detection {release_idx}]")
        print(f"Catch   : {catch_point}  [detection {catch_idx}]")
        print(f"Speed   : {speed:.1f} px/s   Angle: {angle_deg:.1f}\u00b0   "
              f"Flight: {flight_time:.3f}s  ({flight_dets} detections)")

        result = {
            'release_point': release_point, 'catch_point': catch_point,
            'vx': vx, 'vy': vy, 'speed': speed, 'angle_deg': angle_deg,
        }
        if save_path is None:
            return result

        rel_frame_bgr = self._records[rec_indices[release_idx]][0]
        cat_frame_bgr = self._records[rec_indices[catch_idx]][0]
        all_pos   = np.array(positions)
        flight_pos = all_pos[release_idx:catch_idx + 1]

        fig, (ax_r, ax_c) = plt.subplots(2, 1, figsize=(13, 14))

        # --- TOP: release panel ---
        ax_r.imshow(cv2.cvtColor(rel_frame_bgr, cv2.COLOR_BGR2RGB))
        ax_r.plot(all_pos[:, 0], all_pos[:, 1], 'c-o',
                  linewidth=2, markersize=3, label='Trajectory', alpha=0.6)
        if len(flight_pos) > 1:
            ax_r.plot(flight_pos[:, 0], flight_pos[:, 1], 'w-',
                      linewidth=2.5, alpha=0.9, label='Flight arc')
        ax_r.plot(*release_point, 'yo', markersize=14,
                  markeredgecolor='white', markeredgewidth=2, label='Release', zorder=5)
        ax_r.text(release_point[0] + 12, release_point[1] - 12, 'Release',
                  color='yellow', fontsize=10, fontweight='bold',
                  bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.55))
        arrow_scale = min(rel_frame_bgr.shape[:2]) * 0.0001
        ax_r.annotate('',
                      xy=(release_point[0] + vx * arrow_scale,
                          release_point[1] - vy * arrow_scale),
                      xytext=release_point,
                      arrowprops=dict(arrowstyle='->', color='yellow', lw=2.5))
        arc_r = min(rel_frame_bgr.shape[:2]) * 0.06
        theta = np.linspace(0, np.radians(angle_deg), 40)
        ax_r.plot(release_point[0] + arc_r * np.cos(theta),
                  release_point[1] - arc_r * np.sin(theta), color='orange', lw=1.5)
        ax_r.text(release_point[0] + arc_r * 1.2 * np.cos(np.radians(angle_deg / 2)),
                  release_point[1] - arc_r * 1.2 * np.sin(np.radians(angle_deg / 2)),
                  f"{angle_deg:.1f}\u00b0", color='orange', fontsize=10, fontweight='bold')
        ax_r.set_title(
            f"RELEASE\n"
            f"Vx={vx:+.0f}  Vy={vy:+.0f}  Speed={speed:.0f} px/s  Angle={angle_deg:.1f}\u00b0",
            fontsize=11)
        ax_r.legend(loc='upper right', fontsize=9)
        ax_r.axis('off')

        # --- BOTTOM: catch panel ---
        ax_c.imshow(cv2.cvtColor(cat_frame_bgr, cv2.COLOR_BGR2RGB))
        ax_c.plot(all_pos[:, 0], all_pos[:, 1], 'c-o',
                  linewidth=2, markersize=3, label='Trajectory', alpha=0.6)
        if len(flight_pos) > 1:
            ax_c.plot(flight_pos[:, 0], flight_pos[:, 1], 'w-',
                      linewidth=2.5, alpha=0.9, label='Flight arc')
        ax_c.plot(*catch_point, 's', color='magenta', markersize=14,
                  markeredgecolor='white', markeredgewidth=2, label='Catch', zorder=5)
        ax_c.text(catch_point[0] + 12, catch_point[1] - 12, 'Catch',
                  color='magenta', fontsize=10, fontweight='bold',
                  bbox=dict(boxstyle='round,pad=0.2', facecolor='black', alpha=0.55))
        ax_c.set_title(
            f"CATCH\nFlight: {flight_time:.3f}s  ({flight_dets} detections)", fontsize=11)
        ax_c.legend(loc='upper right', fontsize=9)
        ax_c.axis('off')

        plt.suptitle('Release & Catch Analysis', fontsize=13, fontweight='bold')
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Release/catch figure saved to {os.path.abspath(save_path)}")
        plt.close()
        return result

    # ------------------------------------------------------------------
    # OpenSim MOT export
    # ------------------------------------------------------------------

    def write_opensim_mot(self, save_path, model_config=None):
        """Write a full-session MOT file for the given OpenSim model.

        Parameters
        ----------
        save_path : str or Path
            Output path for the .mot file.
        model_config : MotModelConfig, optional
            Column layout and model metadata.  Defaults to ARM26_BALL_CONFIG
            (right arm + ball, matching arm26_ball.osim).  Pass BUET_CONFIG
            (or any custom MotModelConfig) for a different model.
        """
        if model_config is None:
            model_config = ARM26_BALL_CONFIG
        if not self._records:
            print("No data to write.")
            return

        # Pixel-to-metre scale — use both arm sides for robustness
        scale_samples = []
        for _, _, lm, _ in self._records:
            if lm is None:
                continue
            for side in ('right', 'left'):
                sh = lm.get(f'{side}_shoulder')
                el = lm.get(f'{side}_elbow')
                wr = lm.get(f'{side}_wrist')
                if sh and el and wr:
                    arm_px = (np.hypot(el[0] - sh[0], el[1] - sh[1]) +
                              np.hypot(wr[0] - el[0], wr[1] - el[1]))
                    if arm_px > 10:
                        scale_samples.append(0.55 / arm_px)
        px_to_m = (float(np.median(scale_samples)) if scale_samples
                   else 1.8 / (self._frame_shape[0] if self._frame_shape else 720))

        # Ball lookup table (detected frames only)
        ball_ts   = np.array([r[1] for r in self._records if r[3] is not None], dtype=float)
        ball_px_x = np.array([r[3][0] for r in self._records if r[3] is not None], dtype=float)
        ball_px_y = np.array([r[3][1] for r in self._records if r[3] is not None], dtype=float)
        has_ball  = model_config.include_ball and len(ball_ts) > 0

        t0 = self._records[0][1]

        # --- Initial hip x for relative forward translation ---
        _init_hip_x = 0.0
        for _, _, _lm0, _ in self._records:
            if _lm0 is not None:
                _lh0 = _lm0.get('left_hip');  _rh0 = _lm0.get('right_hip')
                _m0 = ((_lh0[0] + _rh0[0]) / 2, (_lh0[1] + _rh0[1]) / 2) \
                      if (_lh0 and _rh0) else (_lh0 or _rh0)
                if _m0:
                    _init_hip_x = _m0[0]
                    break

        # --- Floor y: 95th-percentile of all foot/heel landmark y-positions ---
        # In image coords y increases downward, so the 95th percentile is near
        # the lowest foot position = floor level.  Robust to airborne frames.
        _foot_ys = []
        for _, _, _lm_f, _ in self._records:
            if _lm_f is None:
                continue
            for _key in ('left_heel', 'right_heel',
                         'left_foot_index', 'right_foot_index'):
                _pt = _lm_f.get(_key)
                if _pt:
                    _foot_ys.append(_pt[1])
        if _foot_ys:
            _floor_y_px = float(np.percentile(_foot_ys, 95))
        else:
            # Fallback: treat bottom of frame as floor
            _floor_y_px = float(self._frame_shape[0]) if self._frame_shape else 720.0

        rows = []
        for _, t, lm, _ in self._records:
            rel_t = t - t0

            # --- Build synthetic / midpoint landmarks for this frame ---
            def _midpoint(a, b):
                if a and b:
                    return ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
                return a or b  # fall back to whichever is available

            def _resolve(name):
                """Return (x,y) for a real or synthetic landmark name."""
                if lm is None:
                    return None
                if name == 'midpoint_hips':
                    return _midpoint(lm.get('left_hip'), lm.get('right_hip'))
                if name == 'midpoint_shoulders':
                    return _midpoint(lm.get('left_shoulder'), lm.get('right_shoulder'))
                return lm.get(name)

            # Pelvis translation: project midpoint-of-hips to metres
            if lm is not None:
                lh = lm.get('left_hip');  rh = lm.get('right_hip')
                mid_hip = _midpoint(lh, rh)
            else:
                mid_hip = None
            # tx: horizontal displacement from first frame (±15 m range)
            pelvis_tx_val = float((mid_hip[0] - _init_hip_x) * px_to_m) if mid_hip else 0.0
            # ty: height of hip above floor — floor at 95th-pctile foot position
            # Image y increases downward, so height = (floor_y - hip_y) * scale
            pelvis_ty_val = float((_floor_y_px - mid_hip[1]) * px_to_m) if mid_hip else 0.0

            # -------------------------------------------------------
            # Segment-angle helpers (image coords: Y positive = down)
            # seg_angle: angle of p1→p2 from downward vertical.
            #   0°  = pointing straight down
            #  +90° = pointing right
            #  -90° = pointing left
            # -------------------------------------------------------
            import math as _math

            def _seg_angle(p1, p2):
                if p1 is None or p2 is None:
                    return None
                dx = p2[0] - p1[0]
                dy = p2[1] - p1[1]   # positive = downward in image
                return _math.degrees(_math.atan2(dx, dy))

            def _angle_diff(a, b):
                """Signed difference b − a, normalised to (−180, 180]."""
                if a is None or b is None:
                    return None
                d = b - a
                while d >  180: d -= 360
                while d < -180: d += 360
                return d

            # --- Angle columns defined by the config ---
            angle_vals = []
            for col_name, lm_a, lm_vertex, lm_b, offset, clip_min, clip_max \
                    in model_config.angle_columns:
                # Handle pelvis translation synthetic columns
                if lm_a == '_pelvis_tx_':
                    angle_vals.append(float(np.clip(pelvis_tx_val, clip_min, clip_max)))
                    continue
                if lm_a == '_pelvis_ty_':
                    angle_vals.append(float(np.clip(pelvis_ty_val, clip_min, clip_max)))
                    continue

                if lm is not None:
                    pa = _resolve(lm_a)
                    pv = _resolve(lm_vertex)
                    pb = _resolve(lm_b)
                    if pa and pv and pb:
                        val = float(np.clip(
                            offset - self._angle_between(pa, pv, pb),
                            clip_min, clip_max))
                    else:
                        val = 0.0
                else:
                    val = 0.0
                angle_vals.append(val)

            # -------------------------------------------------------
            # GPK_generic override: replace hip/knee/ankle with
            # segment-angle-based values that are properly signed.
            #
            # Hip flexion  = angle of thigh relative to pelvis axis.
            #   +ve = leg forward (flexion), −ve = leg back (extension).
            # Knee flexion = absolute bend (0 = straight, 150 = full flex).
            # Ankle        = foot vs shank angle (dorsi/plantar flex).
            # -------------------------------------------------------
            if model_config.name == 'GPK_generic' and lm is not None:
                col_idx = {c[0]: i for i, c in enumerate(model_config.angle_columns)}

                # Determine facing direction from right foot:
                #   if foot_index is to the right of heel → facing right (+1)
                #   otherwise → facing left (−1)
                rfi = lm.get('right_foot_index')
                rhe = lm.get('right_heel')
                lfi = lm.get('left_foot_index')
                lhe = lm.get('left_heel')
                # Use whichever foot has both landmarks
                if rfi and rhe:
                    facing = 1 if rfi[0] > rhe[0] else -1
                elif lfi and lhe:
                    facing = -1 if lfi[0] > lhe[0] else 1
                else:
                    facing = 1   # default

                # --- Pelvis tilt: forward lean of trunk from vertical ---
                # Use whichever hip+shoulder pair is available
                _r_sh = lm.get('right_shoulder'); _r_hp = lm.get('right_hip')
                _l_sh = lm.get('left_shoulder');  _l_hp = lm.get('left_hip')
                _tilt_sh = _r_sh or _l_sh
                _tilt_hp = _r_hp or _l_hp
                if _tilt_sh and _tilt_hp:
                    _tdx = _tilt_sh[0] - _tilt_hp[0]
                    _tdy = _tilt_sh[1] - _tilt_hp[1]  # negative (shoulder above)
                    # atan2(facing*dx, -dy): 0=upright, +ve=forward lean
                    _tilt = _math.degrees(_math.atan2(facing * _tdx, -_tdy))
                    if 'pelvis_tilt' in col_idx:
                        _c = model_config.angle_columns[col_idx['pelvis_tilt']]
                        angle_vals[col_idx['pelvis_tilt']] = float(
                            np.clip(_tilt, _c[5], _c[6]))

                # pelvis_list can't be estimated from a sagittal 2-D view → zero
                if 'pelvis_list' in col_idx:
                    angle_vals[col_idx['pelvis_list']] = 0.0

                for side in ('r', 'l'):
                    s = 'right' if side == 'r' else 'left'
                    sf = facing if side == 'r' else -facing

                    shoulder = lm.get(f'{s}_shoulder')
                    hip      = lm.get(f'{s}_hip')
                    knee     = lm.get(f'{s}_knee')
                    ankle    = lm.get(f'{s}_ankle')
                    foot_idx = lm.get(f'{s}_foot_index')
                    heel     = lm.get(f'{s}_heel')

                    trunk_up = _seg_angle(hip, shoulder)   # ~0° = straight up
                    thigh    = _seg_angle(hip, knee)       # ~0° = straight down
                    shank    = _seg_angle(knee, ankle)
                    foot     = _seg_angle(ankle, foot_idx)

                    # Hip flexion: thigh vs pelvis-down axis
                    if trunk_up is not None and thigh is not None:
                        pelvis_down = _angle_diff(0.0, trunk_up + 180)
                        # raw diff (positive = forward relative to image x-axis)
                        raw_flex = _angle_diff(pelvis_down, thigh)
                        # apply facing sign so +ve is always anatomical flexion
                        hip_flex = sf * raw_flex
                        k = f'hip_flexion_{side}'
                        if k in col_idx:
                            c = model_config.angle_columns[col_idx[k]]
                            angle_vals[col_idx[k]] = float(np.clip(hip_flex, c[5], c[6]))

                    # Knee flexion: shank vs thigh (always 0–150)
                    if thigh is not None and shank is not None:
                        knee_flex = abs(_angle_diff(thigh, shank) or 0.0)
                        k = f'knee_angle_{side}'
                        if k in col_idx:
                            c = model_config.angle_columns[col_idx[k]]
                            angle_vals[col_idx[k]] = float(np.clip(knee_flex, c[5], c[6]))

                    # Ankle dorsiflexion: foot vs shank, neutral ≈ 90° difference
                    if shank is not None and foot is not None:
                        diff = _angle_diff(shank, foot)
                        ankle_val = (diff or 0.0) - 90.0  # 0 = neutral standing
                        k = f'ankle_angle_{side}'
                        if k in col_idx:
                            c = model_config.angle_columns[col_idx[k]]
                            angle_vals[col_idx[k]] = float(np.clip(ankle_val, c[5], c[6]))

                # DOFs that a single monocular camera cannot resolve. Leaving
                # them to the generic angle loop pinned them to their joint
                # limits (constant ±30/±40/±45), which made the .mot not track
                # the video at all. Hold them at neutral (0) instead so the
                # model moves only in the observed sagittal plane.
                _UNOBSERVABLE = (
                    'pelvis_list', 'pelvis_rotation', 'pelvis_tz',
                    'hip_adduction_r', 'hip_adduction_l',
                    'hip_rotation_r', 'hip_rotation_l',
                    'knee_adduction_r', 'knee_adduction_l',
                    'subtalar_angle_r', 'subtalar_angle_l',
                    'mtp_angle_r', 'mtp_angle_l',
                    'lumbar_bending', 'lumbar_rotation',
                )
                for _dof in _UNOBSERVABLE:
                    if _dof in col_idx:
                        angle_vals[col_idx[_dof]] = 0.0

            # --- Ball columns (optional) ---
            if has_ball:
                anchor = (lm.get(model_config.ball_anchor_landmark)
                          if lm is not None else None)
                tc  = float(np.clip(t, ball_ts[0], ball_ts[-1]))
                bpx = float(np.interp(tc, ball_ts, ball_px_x))
                bpy = float(np.interp(tc, ball_ts, ball_px_y))
                if anchor is not None:
                    btx = (bpx - anchor[0]) * px_to_m
                    bty = -(bpy - anchor[1]) * px_to_m   # flip: pixel-Y down
                else:
                    btx, bty = bpx * px_to_m, -bpy * px_to_m
                ball_vals = [0.0, 0.0, 0.0, btx, bty, 0.3]
            elif model_config.include_ball:
                # ball requested but no detections
                ball_vals = [0.0, 0.0, 0.0, 0.0, 0.0, 0.3]
            else:
                ball_vals = []

            rows.append([rel_t] + angle_vals + ball_vals)

        # Pad to exactly reach requested duration
        if rows and rows[-1][0] < self._duration_seconds - 0.001:
            rows.append([self._duration_seconds] + rows[-1][1:])

        col_header = '\t'.join(model_config.column_names)
        save_path = Path(save_path)
        with open(save_path, 'w') as f:
            f.write(f"{model_config.name}_from_video\n")
            f.write("version=1\n")
            f.write(f"nRows={len(rows)}\n")
            f.write(f"nColumns={model_config.n_columns}\n")
            f.write("inDegrees=yes\n\n")
            f.write("endheader\n")
            f.write(col_header + '\n')
            for row in rows:
                f.write('\t'.join(
                    f"{v:.6f}" if i == 0 else f"{v:.4f}"
                    for i, v in enumerate(row)
                ) + '\n')

        print(f"MOT saved to {os.path.abspath(save_path)}")
        print(f"  Model   : {model_config.name}")
        print(f"  .osim   : {model_config.osim_path}")
        print(f"  Rows    : {len(rows)}  (~{rows[-1][0]:.2f} s)")
        print(f"  px->m   : {px_to_m:.5f}  "
              f"({'arm joints' if scale_samples else 'frame-height fallback'})")
        print(f"  floor_y : {_floor_y_px:.1f} px  "
              f"({'foot landmarks' if _foot_ys else 'frame-height fallback'})")
        print(f"  Columns : {', '.join(model_config.column_names)}")


def main():
    # --- Quick recording session ---
    DURATION   = 10     # seconds to record
    CAMERA     = 'webcam'   # 'webcam' or 'ip'
    FPS        = None
    DETECT_INT = 2

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(f"outputs/test_{timestamp}")

    tracker = MovementTracker()
    tracker.record_video(duration_seconds=DURATION, camera_type=CAMERA,
                         output_dir=out, target_fps=FPS, detection_interval=DETECT_INT)

    tracker.save_frames(out / "frames")
    tracker.plot_joint_angles(save_path=str(out / "joint_angles.png"))
    tracker.analyze_release(save_path=str(out / "release_catch.png"))
    tracker.write_opensim_mot(save_path=str(out / "arm26_ball_motion.mot"),
                              model_config=ARM26_BALL_CONFIG)
    tracker.write_opensim_mot(save_path=str(out / "buet_motion.mot"),
                              model_config=FULL_BODY_CONFIG)
    tracker.write_opensim_mot(save_path=str(out / "full_body_motion.mot"),
                              model_config=FULL_BODY_CONFIG)


if __name__ == "__main__":
    main()
