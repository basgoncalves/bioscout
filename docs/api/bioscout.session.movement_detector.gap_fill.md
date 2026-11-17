# `bioscout.session.movement_detector.gap_fill`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/gap_fill.py)

gap_fill.py — fill missing frames in a pose landmark dict using cubic-spline  
(or linear) interpolation.

  
**Usage**

    from bioscout.session.movement_detector import fill_pose_gaps  
    filled = fill_pose_gaps(poses, max_gap=10, method="cubic")

## Contents

- [`fill_pose_gaps`](#fill_pose_gaps) — Return a new pose dict with missing frames interpolated.

### `fill_pose_gaps`

```python
fill_pose_gaps(poses: Poses, max_gap: int = 10, method: str = 'cubic') -> Poses
```

| input | type | default |
|---|---|---|
| `poses` | Poses | required |
| `max_gap` | int | `10` |
| `method` | str | `'cubic'` |

**returns** `Poses`

Return a new pose dict with missing frames interpolated.

  
**Parameters**

poses   : {frame_idx: {landmark_name: (x, y)}}  
max_gap : only fill gaps shorter than or equal to this many frames.  
          Longer gaps are left as-is (no extrapolation).  
method  : "cubic" (default) or "linear"

  
**Returns**

New dict with filled frames added. Original frames are not modified.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/gap_fill.py#L20)</sub>
