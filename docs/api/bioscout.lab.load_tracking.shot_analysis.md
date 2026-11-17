# `bioscout.lab.load_tracking.shot_analysis`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py)

BioScout — Shot Analysis (prototype)  
====================================

From a basketball video: count shot attempts, segment each shot, extract  
per-shot kinematics on a smooth 0-100% axis, support assisted made/missed  
tagging, and (low-fidelity) predict muscle forces from the kinematics with a  
kinematics-only surrogate model.

  
**Pipeline**

    video ──pose──▶ landmarks{frame:{name:(x,y)}}  
          ──detect_shots──▶ [Shot(start,release,end), ...]  
          ──shot_kinematics──▶ joint angles, time-normalised 0-100%  
          ──plot/CSV──▶ figures + shots.csv (mark 'made' column)  
          ──predict_muscle_forces──▶ per-shot muscle-force curves

  
**Pose**

2-D pose comes from BioScout's MediaPipe tracker (``record.video``), which runs  
on the user's machine. Pass ``poses=`` (a precomputed {frame:{name:(x,y)}} dict  
or a JSON path produced by the GUI) to skip detection — this also makes the rest  
of the pipeline testable without MediaPipe.

CLI (wired in __main__.py):  
    python -m bioscout --shots "video.mp4"  
    python -m bioscout --shots "video.mp4" --shooting-hand right  
    python -m bioscout --shots "video.mp4" --poses poses.json   # skip MediaPipe

NOTE on muscle forces: predicting muscle forces from joint angles ALONE is  
inherently low fidelity (forces scale with subject strength/size, which angles  
don't encode; cross-subject R^2 is poor). Treat the force output as indicative  
shape, not calibrated magnitude.

## Contents

- class [`Shot`](#shot) — 
  - [`Shot.t_release`](#shott_release) — 
- [`detect_ball_hoop_yolo`](#detect_ball_hoop_yolo) — Per-frame best ball & hoop boxes via a YOLO (ultralytics) model trained on 'Basketball' + 'Basketball Hoop'. Returns (ball, hoop, fps) where each is {frame: (cx, cy, w, h)}. Requires `pip install ultralytics` + a model.
- [`detect_shots_via_hoop`](#detect_shots_via_hoop) — avishah3 up/down/through-rim logic. ``ball``/``hoop`` = {frame:(cx,cy,w,h)}. Returns Shots with ``made`` set (True/False) per the trajectory through the rim. The release frame is estimated as the ball's apex just before the rim pass.
- [`extract_poses`](#extract_poses) — Run BioScout's MediaPipe pose landmarker on a video. Returns (poses, fps).
- [`load_poses_json`](#load_poses_json) — 
- [`detect_shots`](#detect_shots) — Detect shot attempts by BALL FLIGHT.
- [`shot_kinematics`](#shot_kinematics) — Per-shot joint angles, time-normalised + smoothed to n points (0-100%).
- [`load_force_model`](#load_force_model) — Load the FAIS surrogate, refusing a file that fails its own check.
- [`kinematics_to_coords`](#kinematics_to_coords) — The four sagittal angles a video gives, as OpenSim coordinates.
- [`predict_muscle_forces`](#predict_muscle_forces) — Per-shot muscle forces (N) and joint contact forces (bodyweight).
- [`plot_kinematics`](#plot_kinematics) — 
- [`plot_muscle_forces`](#plot_muscle_forces) — 
- [`write_shots_csv`](#write_shots_csv) — One row per attempt; 'made' left blank for assisted tagging (1/0).
- [`load_tags`](#load_tags) — Read a filled shots.csv ('made' = 1/0) back onto the shots.
- [`save_release_thumbnails`](#save_release_thumbnails) — Save the release frame of each shot to help manual made/missed tagging.
- [`save_score_frames`](#save_score_frames) — For each hoop-scored shot, draw the rim, the ball path and the predicted rim crossing on the frame the ball reached the hoop, label IN/OUT, and save.
- [`release_angle_from_poses`](#release_angle_from_poses) — Launch angle (deg from horizontal) from the shooting wrist's motion across the release frame. Positive = upward.
- [`save_shot_summary_frames`](#save_shot_summary_frames) — Per shot, a side-by-side card: release (stick figure + joint angles + release angle)  |  shot path (rim + trajectory + IN/OUT). -> shot_NN_card.png
- [`analyze_video`](#analyze_video) — Full prototype pipeline. Returns a dict summary; writes figures + CSV.

<a id="shot"></a>

## class `Shot`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L66)</sub>

<a id="shott_release"></a>

### `Shot.t_release`

```python
Shot.t_release() -> float
```

**returns** `float`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L79)</sub>

### `detect_ball_hoop_yolo`

```python
detect_ball_hoop_yolo(video_path, model_path, conf=0.3, every=1)
```

| input | type | default |
|---|---|---|
| `video_path` | – | required |
| `model_path` | – | required |
| `conf` | – | `0.3` |
| `every` | – | `1` |

Per-frame best ball & hoop boxes via a YOLO (ultralytics) model trained  
on 'Basketball' + 'Basketball Hoop'. Returns (ball, hoop, fps) where each is  
{frame: (cx, cy, w, h)}. Requires `pip install ultralytics` + a model.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L125)</sub>

### `detect_shots_via_hoop`

```python
detect_shots_via_hoop(
    ball: dict,
    hoop: dict,
    fps: float,
    follow_through_s: float = 0.4
) -> List[Shot]
```

| input | type | default |
|---|---|---|
| `ball` | dict | required |
| `hoop` | dict | required |
| `fps` | float | required |
| `follow_through_s` | float | `0.4` |

**returns** `List[Shot]`

avishah3 up/down/through-rim logic. ``ball``/``hoop`` = {frame:(cx,cy,w,h)}.  
Returns Shots with ``made`` set (True/False) per the trajectory through the rim.  
The release frame is estimated as the ball's apex just before the rim pass.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L177)</sub>

### `extract_poses`

```python
extract_poses(
    video_path: str,
    every: int = 1,
    vis_thresh: float = 0.0,
    roi_zoom: bool = True,
    shooting_hand: str = 'right',
    detect_ball: bool = True
) -> Tuple[Dict[int, dict], dict, float]
```

| input | type | default |
|---|---|---|
| `video_path` | str | required |
| `every` | int | `1` |
| `vis_thresh` | float | `0.0` |
| `roi_zoom` | bool | `True` |
| `shooting_hand` | str | `'right'` |
| `detect_ball` | bool | `True` |

**returns** `Tuple[Dict[int, dict], dict, float]`

Run BioScout's MediaPipe pose landmarker on a video. Returns (poses, fps).

poses = {frame_idx: {landmark_name: (x_px, y_px)}}. Uses MovementTracker's  
``_pose_landmarker`` (Tasks API, num_poses=1). Landmarks are kept in  
full-frame pixel coords. ``roi_zoom`` re-detects on a crop around the last  
detection to better catch a small/distant subject (common in game footage).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L263)</sub>

### `load_poses_json`

```python
load_poses_json(path: str) -> Dict[int, dict]
```

| input | type | default |
|---|---|---|
| `path` | str | required |

**returns** `Dict[int, dict]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L340)</sub>

### `detect_shots`

```python
detect_shots(
    poses: Dict[int, dict],
    fps: float,
    shooting_hand: str = 'right',
    min_gap_s: float = 1.0,
    follow_through_s: float = 0.4,
    balls: Optional[dict] = None,
    hoop_side: str = 'auto'
) -> List[Shot]
```

| input | type | default |
|---|---|---|
| `poses` | Dict[int, dict] | required |
| `fps` | float | required |
| `shooting_hand` | str | `'right'` |
| `min_gap_s` | float | `1.0` |
| `follow_through_s` | float | `0.4` |
| `balls` | Optional[dict] | `None` |
| `hoop_side` | str | `'auto'` |

**returns** `List[Shot]`

Detect shot attempts by BALL FLIGHT.

A release = a ball at the shooter's hand (near the raised wrist, above the  
shoulders, above the head) that, in the next 1-3 frames, travels clearly  
UPWARD and toward the hoop. This rejects gathers/dribbles/pump-fakes (the  
ball doesn't fly to the basket) and the static scoreboard/rack balls.

``balls`` = {frame: [(x, y, r), ...]} all candidates per frame.  
``hoop_side`` 'right' | 'left' | 'auto' (inferred from the ball flight).  
Pose-only ("wrist above head") is the fallback when no ball is available.  
A hard refractory of >=1 s (or ``min_gap_s`` if larger) is enforced.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L370)</sub>

### `shot_kinematics`

```python
shot_kinematics(
    poses: Dict[int, dict],
    shot: Shot,
    side: str = 'right',
    n: int = 1000,
    smooth_frac: float = 0.12
) -> Dict[str, np.ndarray]
```

| input | type | default |
|---|---|---|
| `poses` | Dict[int, dict] | required |
| `shot` | Shot | required |
| `side` | str | `'right'` |
| `n` | int | `1000` |
| `smooth_frac` | float | `0.12` |

**returns** `Dict[str, np.ndarray]`

Per-shot joint angles, time-normalised + smoothed to n points (0-100%).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L537)</sub>

### `load_force_model`

```python
load_force_model(path: str)
```

| input | type | default |
|---|---|---|
| `path` | str | required |

Load the FAIS surrogate, refusing a file that fails its own check.

See ``bioscout/models/force_model.py``. The pre-2026-09  
``kinematics_only_model.pkl`` is rejected here rather than used: it was  
exported from a BatchNorm network without its running statistics and  
predicts 113,250 N on a trial from its own training set.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L558)</sub>

### `kinematics_to_coords`

```python
kinematics_to_coords(
    kin: Dict[str, np.ndarray],
    side: str = 'right'
) -> Dict[str, np.ndarray]
```

| input | type | default |
|---|---|---|
| `kin` | Dict[str, np.ndarray] | required |
| `side` | str | `'right'` |

**returns** `Dict[str, np.ndarray]`

The four sagittal angles a video gives, as OpenSim coordinates.

Everything else -- the other limb, the pelvis, the trunk -- is left out, and  
the model holds it at its training mean. That is a real limitation of a  
single view and is reported by :func:`predict_muscle_forces` rather than  
hidden.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L594)</sub>

### `predict_muscle_forces`

```python
predict_muscle_forces(
    kin: Dict[str, np.ndarray],
    model,
    side: str = 'right',
    smooth_frac: float = 0.06,
    duration_s: Optional[float] = None,
    mass_kg: float = 75.0,
    height_m: float = 1.75
) -> Dict[str, np.ndarray]
```

| input | type | default |
|---|---|---|
| `kin` | Dict[str, np.ndarray] | required |
| `model` | – | required |
| `side` | str | `'right'` |
| `smooth_frac` | float | `0.06` |
| `duration_s` | Optional[float] | `None` |
| `mass_kg` | float | `75.0` |
| `height_m` | float | `1.75` |

**returns** `Dict[str, np.ndarray]`

Per-shot muscle forces (N) and joint contact forces (bodyweight).

``duration_s`` is the wall-clock length of the shot. It matters: the model  
reads joint velocity and acceleration, which are differentiated from the  
time axis, and the 0-100% axis in ``kin`` has had real time normalised out  
of it. Without a duration the shot is treated as one second, and the  
dynamics are then only as right as that guess.

The returned dict carries the force curves on the same 0-100% axis as  
``kin``, plus ``_meta`` describing how far outside the training data the  
inputs sat -- which for a basketball shot is the number worth reading first.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L613)</sub>

### `plot_kinematics`

```python
plot_kinematics(shots_kin: List[Dict[str, np.ndarray]], shots: List[Shot], out_path: str)
```

| input | type | default |
|---|---|---|
| `shots_kin` | List[Dict[str, np.ndarray]] | required |
| `shots` | List[Shot] | required |
| `out_path` | str | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L662)</sub>

### `plot_muscle_forces`

```python
plot_muscle_forces(
    shots_forces: List[Dict[str, np.ndarray]],
    shots: List[Shot],
    out_path: str,
    muscles: Optional[List[str]] = None
)
```

| input | type | default |
|---|---|---|
| `shots_forces` | List[Dict[str, np.ndarray]] | required |
| `shots` | List[Shot] | required |
| `out_path` | str | required |
| `muscles` | Optional[List[str]] | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L684)</sub>

### `write_shots_csv`

```python
write_shots_csv(shots: List[Shot], path: str)
```

| input | type | default |
|---|---|---|
| `shots` | List[Shot] | required |
| `path` | str | required |

One row per attempt; 'made' left blank for assisted tagging (1/0).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L724)</sub>

### `load_tags`

```python
load_tags(shots: List[Shot], path: str) -> List[Shot]
```

| input | type | default |
|---|---|---|
| `shots` | List[Shot] | required |
| `path` | str | required |

**returns** `List[Shot]`

Read a filled shots.csv ('made' = 1/0) back onto the shots.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L738)</sub>

### `save_release_thumbnails`

```python
save_release_thumbnails(video_path: str, shots: List[Shot], out_dir: str)
```

| input | type | default |
|---|---|---|
| `video_path` | str | required |
| `shots` | List[Shot] | required |
| `out_dir` | str | required |

Save the release frame of each shot to help manual made/missed tagging.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L755)</sub>

### `save_score_frames`

```python
save_score_frames(video_path: str, shots: List[Shot], out_dir: str)
```

| input | type | default |
|---|---|---|
| `video_path` | str | required |
| `shots` | List[Shot] | required |
| `out_dir` | str | required |

For each hoop-scored shot, draw the rim, the ball path and the predicted  
rim crossing on the frame the ball reached the hoop, label IN/OUT, and save.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L780)</sub>

### `release_angle_from_poses`

```python
release_angle_from_poses(poses, rel_frame, side)
```

| input | type | default |
|---|---|---|
| `poses` | – | required |
| `rel_frame` | – | required |
| `side` | – | required |

Launch angle (deg from horizontal) from the shooting wrist's motion  
across the release frame. Positive = upward.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L832)</sub>

### `save_shot_summary_frames`

```python
save_shot_summary_frames(video_path, shots, poses, out_dir, side='right')
```

| input | type | default |
|---|---|---|
| `video_path` | – | required |
| `shots` | – | required |
| `poses` | – | required |
| `out_dir` | – | required |
| `side` | – | `'right'` |

Per shot, a side-by-side card: release (stick figure + joint angles +  
release angle)  |  shot path (rim + trajectory + IN/OUT). -> shot_NN_card.png

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L908)</sub>

### `analyze_video`

```python
analyze_video(
    video_path: str,
    out_dir: Optional[str] = None,
    shooting_hand: str = 'right',
    poses=None,
    model_path: Optional[str] = None,
    fps: Optional[float] = None,
    min_gap_s: float = 1.0,
    n_points: int = 1000,
    smooth_frac: float = 0.12,
    hoop_side: str = 'auto',
    yolo_model: Optional[str] = None,
    hoop: Optional[tuple] = None
) -> dict
```

| input | type | default |
|---|---|---|
| `video_path` | str | required |
| `out_dir` | Optional[str] | `None` |
| `shooting_hand` | str | `'right'` |
| `poses` | – | `None` |
| `model_path` | Optional[str] | `None` |
| `fps` | Optional[float] | `None` |
| `min_gap_s` | float | `1.0` |
| `n_points` | int | `1000` |
| `smooth_frac` | float | `0.12` |
| `hoop_side` | str | `'auto'` |
| `yolo_model` | Optional[str] | `None` |
| `hoop` | Optional[tuple] | `None` |

**returns** `dict`

Full prototype pipeline. Returns a dict summary; writes figures + CSV.

fps: override the video frame rate (e.g. footage exported at 5 fps). When  
None it is read from the file. Detection/segmentation timing uses it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/lab/load_tracking/shot_analysis.py#L958)</sub>
