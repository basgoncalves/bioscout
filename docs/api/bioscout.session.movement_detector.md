# `bioscout.session.movement_detector`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py)

movement_detector — detecting and segmenting sports movements.

Two independent paths, for two kinds of input:

**Video / 2-D pose** — frame-level segmentation of running, walking, jumping,  
squatting, side-step cut, shuffle, deceleration and backward gait from pose  
landmark time-series::

    from bioscout.session.movement_detector import detect_segments, DetectorConfig  
    segments = detect_segments(landmarks)

**Marker-based mocap** — whole-TRIAL classification from the markers and  
ground reaction forces BioScout exports into  
``<session>/2_experimental/<trial>/``. Answers "what task is this trial?"  
rather than "what is happening in this frame", so a project can check its  
trials against their filenames::

    from bioscout.session.movement_detector import classify_trial  
    label, conf, why, feats = classify_trial(exp_dir, body_mass=61.3)

Thresholds for the mocap path are SI (m, s, body weights) and live in  
``MocapConfig``; the video path's are pixels/frame in ``DetectorConfig``.

**Mesh conversion** — a small utility for the surface meshes that come out of  
phone scans and photogrammetry, so they can be used as OpenSim geometry::

    from bioscout.session.movement_detector import convert_to_stl  
    convert_to_stl("3DModel.obj", scale=0.001)   # mm -> m, writes 3DModel.stl

See ``bioscout.session.movement_detector.mesh_convert``.

**Body mesh from video** — a fixed camera, a subject turning on the spot, and a  
shape-from-silhouette carve gives the closed mesh that ``mesh_rig`` rigs::

    from bioscout.session.movement_detector import carve_from_video, rig_mesh  
    res = carve_from_video("turn.mp4", "subject01/body.stl",  
                           "front=0,right=3.1,back=6.4,left=9.2",  
                           CarveConfig(target_height=1.81))  
    rig_mesh(res.mesh_path, out_dir="subject01", name="bas")

See ``bioscout.session.movement_detector.mesh_from_video``.

## Available as `bioscout.session.movement_detector.<name>`

- [`bioscout.session.movement_detector.MotionSegment`](bioscout.session.movement_detector.detector.md#motionsegment) — from `bioscout.session.movement_detector.detector`
- [`bioscout.session.movement_detector.DetectorConfig`](bioscout.session.movement_detector.detector.md#detectorconfig) — from `bioscout.session.movement_detector.detector`
- [`bioscout.session.movement_detector.detect_segments`](bioscout.session.movement_detector.detector.md#detect_segments) — from `bioscout.session.movement_detector.detector`
- [`bioscout.session.movement_detector.fill_pose_gaps`](bioscout.session.movement_detector.gap_fill.md#fill_pose_gaps) — from `bioscout.session.movement_detector.gap_fill`
- [`bioscout.session.movement_detector.detect_window`](bioscout.session.movement_detector.mocap.md#detect_window) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.segment_trial`](bioscout.session.movement_detector.mocap.md#segment_trial) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.TaskSegment`](bioscout.session.movement_detector.mocap.md#tasksegment) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.contact_feet`](bioscout.session.movement_detector.mocap.md#contact_feet) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.foot_events_from_markers`](bioscout.session.movement_detector.mocap.md#foot_events_from_markers) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.gait_cycles`](bioscout.session.movement_detector.mocap.md#gait_cycles) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.plot_trial_tasks`](bioscout.session.movement_detector.mocap.md#plot_trial_tasks) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.TASK_COLOURS`](bioscout.session.movement_detector.mocap.md#task_colours) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.FOOT_COLOURS`](bioscout.session.movement_detector.mocap.md#foot_colours) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.MOCAP_TASK_LABELS`](bioscout.session.movement_detector.mocap.md#mocap_task_labels) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.MocapConfig`](bioscout.session.movement_detector.mocap.md#mocapconfig) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.TrialFeatures`](bioscout.session.movement_detector.mocap.md#trialfeatures) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.classify_trial`](bioscout.session.movement_detector.mocap.md#classify_trial) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.classify_features`](bioscout.session.movement_detector.mocap.md#classify_features) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.extract_trial_features`](bioscout.session.movement_detector.mocap.md#extract_trial_features) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.read_trc`](bioscout.session.movement_detector.mocap.md#read_trc) — from `bioscout.session.movement_detector.mocap`
- [`bioscout.session.movement_detector.read_grf`](bioscout.session.movement_detector.mocap.md#read_grf) — from `bioscout.session.movement_detector.mocap`

## Contents

- [`prepare_cycle_runs`](#prepare_cycle_runs) — Lazy re-export; see bioscout.session.movement_detector.cycle_runs.
- [`write_cycle_files`](#write_cycle_files) — Lazy re-export; see bioscout.session.movement_detector.cycle_runs.
- [`classify_session`](#classify_session) — Lazy re-export; see bioscout.session.movement_detector.session.
- [`convert_to_stl`](#convert_to_stl) — Lazy re-export; see bioscout.session.movement_detector.mesh_convert.
- [`obj_to_stl`](#obj_to_stl) — Lazy re-export; see bioscout.session.movement_detector.mesh_convert.
- [`convert_dir`](#convert_dir) — Lazy re-export; see bioscout.session.movement_detector.mesh_convert.
- [`read_obj`](#read_obj) — Lazy re-export; see bioscout.session.movement_detector.mesh_convert.
- [`write_stl`](#write_stl) — Lazy re-export; see bioscout.session.movement_detector.mesh_convert.
- [`carve_from_video`](#carve_from_video) — Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.
- [`parse_views`](#parse_views) — Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.
- [`hull_bias`](#hull_bias) — Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.
- [`silhouette`](#silhouette) — Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.
- [`carve_visual_hull`](#carve_visual_hull) — Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.
- [`surface_nets`](#surface_nets) — Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.
- [`regularise_occupancy`](#regularise_occupancy) — Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.
- [`is_watertight`](#is_watertight) — Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.
- [`make_segmenter`](#make_segmenter) — Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.

### `prepare_cycle_runs`

```python
prepare_cycle_runs(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.cycle_runs.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L117)</sub>

### `write_cycle_files`

```python
write_cycle_files(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.cycle_runs.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L123)</sub>

### `classify_session`

```python
classify_session(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.session.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L129)</sub>

### `convert_to_stl`

```python
convert_to_stl(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_convert.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L136)</sub>

### `obj_to_stl`

```python
obj_to_stl(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_convert.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L142)</sub>

### `convert_dir`

```python
convert_dir(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_convert.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L148)</sub>

### `read_obj`

```python
read_obj(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_convert.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L154)</sub>

### `write_stl`

```python
write_stl(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_convert.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L160)</sub>

### `carve_from_video`

```python
carve_from_video(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L232)</sub>

### `parse_views`

```python
parse_views(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L238)</sub>

### `hull_bias`

```python
hull_bias(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L244)</sub>

### `silhouette`

```python
silhouette(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L250)</sub>

### `carve_visual_hull`

```python
carve_visual_hull(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L256)</sub>

### `surface_nets`

```python
surface_nets(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L262)</sub>

### `regularise_occupancy`

```python
regularise_occupancy(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L268)</sub>

### `is_watertight`

```python
is_watertight(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L274)</sub>

### `make_segmenter`

```python
make_segmenter(*a, **k)
```

| input | type | default |
|---|---|---|
| `*a` | – | – |
| `**k` | – | – |

Lazy re-export; see bioscout.session.movement_detector.mesh_from_video.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/__init__.py#L280)</sub>
