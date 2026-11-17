# `bioscout.lab.record.video`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py)

## Contents

- class [`MotModelConfig`](#motmodelconfig) — Defines the column layout for an OpenSim MOT file.
  - [`MotModelConfig.column_names`](#motmodelconfigcolumn_names) — 
  - [`MotModelConfig.n_columns`](#motmodelconfign_columns) — 
- class [`MovementTracker`](#movementtracker) — Track human movement and ball trajectory from a camera feed.
  - [`MovementTracker.record_video`](#movementtrackerrecord_video) — Record raw camera footage for `duration_seconds` and save as video.mp4.
  - [`MovementTracker.track_and_display`](#movementtrackertrack_and_display) — Run the camera loop for `duration_seconds` wall-clock seconds.
  - [`MovementTracker.save_frames`](#movementtrackersave_frames) — Save every captured frame as a PNG with pose skeleton overlays.
  - [`MovementTracker.plot_joint_angles`](#movementtrackerplot_joint_angles) — Time-series of all detected joint angles — arms and legs, left and right.
  - [`MovementTracker.analyze_release`](#movementtrackeranalyze_release) — Detect ball release and catch; save two-panel figure if save_path given.
  - [`MovementTracker.write_opensim_mot`](#movementtrackerwrite_opensim_mot) — Write a full-session MOT file for the given OpenSim model.
- [`discover_available_models`](#discover_available_models) — Discover all .osim model files in MODULE_DIR and return as dict.
- [`main`](#main) — 

<a id="motmodelconfig"></a>

## class `MotModelConfig`

```python
MotModelConfig(
    name,
    osim_path,
    angle_columns,
    include_ball=False,
    ball_anchor_landmark='right_shoulder'
)
```

| input | type | default |
|---|---|---|
| `name` | – | required |
| `osim_path` | – | required |
| `angle_columns` | – | required |
| `include_ball` | – | `False` |
| `ball_anchor_landmark` | – | `'right_shoulder'` |

Defines the column layout for an OpenSim MOT file.

  
**Parameters**

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

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L65)</sub>

<a id="motmodelconfigcolumn_names"></a>

### `MotModelConfig.column_names`

```python
MotModelConfig.column_names()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L101)</sub>

<a id="motmodelconfign_columns"></a>

### `MotModelConfig.n_columns`

```python
MotModelConfig.n_columns()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L108)</sub>

<a id="movementtracker"></a>

## class `MovementTracker`

```python
MovementTracker(
    max_trajectory_length=200,
    hsv_lower=None,
    hsv_upper=None,
    ball_color='orange'
)
```

| input | type | default |
|---|---|---|
| `max_trajectory_length` | – | `200` |
| `hsv_lower` | – | `None` |
| `hsv_upper` | – | `None` |
| `ball_color` | – | `'orange'` |

Track human movement and ball trajectory from a camera feed.

One record is stored per video frame:  
    (annotated_bgr_frame, wall_clock_time, pose_lm_dict_or_None, ball_center_or_None)

  
**Outputs**

save_frames()         — every frame annotated with skeleton + ball path → folder  
plot_joint_angles()   — shoulder & elbow angle time-series → PNG  
analyze_release()     — two-panel release (top) / catch (bottom) figure → PNG  
write_opensim_mot()   — full-session MOT for arm26_ball.osim → .mot

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L351)</sub>

<a id="movementtrackerrecord_video"></a>

### `MovementTracker.record_video`

```python
MovementTracker.record_video(
    duration_seconds=10,
    camera_type='webcam',
    ip_address=None,
    output_dir=None,
    target_fps=None,
    detection_interval=1
)
```

| input | type | default |
|---|---|---|
| `duration_seconds` | – | `10` |
| `camera_type` | – | `'webcam'` |
| `ip_address` | – | `None` |
| `output_dir` | – | `None` |
| `target_fps` | – | `None` |
| `detection_interval` | – | `1` |

Record raw camera footage for `duration_seconds` and save as video.mp4.

Frames are also stored in self._records so all analysis methods  
(save_frames, plot_joint_angles, etc.) work normally afterward.

  
**Parameters**

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

  
**Returns**

Path  
    Path to the saved .mp4 file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L443)</sub>

<a id="movementtrackertrack_and_display"></a>

### `MovementTracker.track_and_display`

```python
MovementTracker.track_and_display(
    duration_seconds=10,
    camera_type='webcam',
    detection_interval=1
)
```

| input | type | default |
|---|---|---|
| `duration_seconds` | – | `10` |
| `camera_type` | – | `'webcam'` |
| `detection_interval` | – | `1` |

Run the camera loop for `duration_seconds` wall-clock seconds.

Every frame is stored in self._records with full annotations  
already drawn (pose skeleton + trajectory) in BGR.

  
**Parameters**

detection_interval : int  
    Run pose + ball detection only every N frames (default 1 = every  
    frame).  Increase to raise effective capture rate when inference  
    is the bottleneck; skipped frames reuse the last known result.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L817)</sub>

<a id="movementtrackersave_frames"></a>

### `MovementTracker.save_frames`

```python
MovementTracker.save_frames(folder)
```

| input | type | default |
|---|---|---|
| `folder` | – | required |

Save every captured frame as a PNG with pose skeleton overlays.

Each image shows the pose skeleton with joint-angle labels, drawn directly  
using OpenCV for speed. Supports both arm26_ball and Neck_model configs.  
Frames are written to `folder/frame_NNNNN.png`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L958)</sub>

<a id="movementtrackerplot_joint_angles"></a>

### `MovementTracker.plot_joint_angles`

```python
MovementTracker.plot_joint_angles(save_path=None)
```

| input | type | default |
|---|---|---|
| `save_path` | – | `None` |

Time-series of all detected joint angles — arms and legs, left and right.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L1103)</sub>

<a id="movementtrackeranalyze_release"></a>

### `MovementTracker.analyze_release`

```python
MovementTracker.analyze_release(
    proximity_threshold=100,
    velocity_smoothing=5,
    save_path=None
)
```

| input | type | default |
|---|---|---|
| `proximity_threshold` | – | `100` |
| `velocity_smoothing` | – | `5` |
| `save_path` | – | `None` |

Detect ball release and catch; save two-panel figure if save_path given.

Returns dict with release_point, catch_point, vx, vy, speed, angle_deg.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L1194)</sub>

<a id="movementtrackerwrite_opensim_mot"></a>

### `MovementTracker.write_opensim_mot`

```python
MovementTracker.write_opensim_mot(save_path, model_config=None)
```

| input | type | default |
|---|---|---|
| `save_path` | – | required |
| `model_config` | – | `None` |

Write a full-session MOT file for the given OpenSim model.

  
**Parameters**

save_path : str or Path  
    Output path for the .mot file.  
model_config : MotModelConfig, optional  
    Column layout and model metadata.  Defaults to ARM26_BALL_CONFIG  
    (right arm + ball, matching arm26_ball.osim).  Pass BUET_CONFIG  
    (or any custom MotModelConfig) for a different model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L1331)</sub>

### `discover_available_models`

```python
discover_available_models()
```

Discover all .osim model files in MODULE_DIR and return as dict.

  
**Returns**

dict  
    Dictionary mapping model name (without .osim) to MotModelConfig.  
    Special cases (arm26_ball, full_body_with_ball) use predefined configs.  
    Other models get generic configs with basic arm joint angles.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L287)</sub>

### `main`

```python
main()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/record/video.py#L1648)</sub>
