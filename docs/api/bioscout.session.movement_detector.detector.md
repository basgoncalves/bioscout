# `bioscout.session.movement_detector.detector`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/detector.py)

detector.py — public API: MotionSegment, DetectorConfig, detect_segments().

## Contents

- class [`MotionSegment`](#motionsegment) — A labelled, contiguous block of frames with a single movement task.
  - [`MotionSegment.duration_frames`](#motionsegmentduration_frames) — 
- class [`DetectorConfig`](#detectorconfig) — Tunable thresholds for the movement detector.
- [`detect_segments`](#detect_segments) — Detect and segment movements in a pose time-series.
- [`segments_to_dict`](#segments_to_dict) — Serialise segments to a list of plain dicts (JSON-friendly).
- [`segments_from_dict`](#segments_from_dict) — Deserialise from a list of dicts (e.g. loaded from JSON).

<a id="motionsegment"></a>

## class `MotionSegment`

A labelled, contiguous block of frames with a single movement task.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/detector.py#L35)</sub>

<a id="motionsegmentduration_frames"></a>

### `MotionSegment.duration_frames`

```python
MotionSegment.duration_frames() -> int
```

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/detector.py#L44)</sub>

<a id="detectorconfig"></a>

## class `DetectorConfig`

Tunable thresholds for the movement detector.

All speed thresholds are in **pixels / frame**.  You may need to scale  
these if your video resolution / field of view differs substantially from  
a standard 1080p side-view sport recording.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/detector.py#L56)</sub>

### `detect_segments`

```python
detect_segments(
    poses: Dict[int, Dict[str, Tuple[float, float]]],
    fps: float = 30.0,
    config: Optional[DetectorConfig] = None
) -> List[MotionSegment]
```

| input | type | default |
|---|---|---|
| `poses` | Dict[int, Dict[str, Tuple[float, float]]] | required |
| `fps` | float | `30.0` |
| `config` | Optional[DetectorConfig] | `None` |

**returns** `List[MotionSegment]`

Detect and segment movements in a pose time-series.

  
**Parameters**

poses   : {frame_idx: {landmark_name: (x_px, y_px)}}  
fps     : video frame rate (used for display; thresholds are in px/frame)  
config  : DetectorConfig instance, or None for defaults

  
**Returns**

List[MotionSegment] sorted by start_frame.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/detector.py#L103)</sub>

### `segments_to_dict`

```python
segments_to_dict(segments: List[MotionSegment]) -> List[dict]
```

| input | type | default |
|---|---|---|
| `segments` | List[MotionSegment] | required |

**returns** `List[dict]`

Serialise segments to a list of plain dicts (JSON-friendly).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/detector.py#L158)</sub>

### `segments_from_dict`

```python
segments_from_dict(data: List[dict]) -> List[MotionSegment]
```

| input | type | default |
|---|---|---|
| `data` | List[dict] | required |

**returns** `List[MotionSegment]`

Deserialise from a list of dicts (e.g. loaded from JSON).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/detector.py#L172)</sub>
