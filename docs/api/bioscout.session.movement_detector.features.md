# `bioscout.session.movement_detector.features`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/features.py)

features.py — extract kinematic time-series features from a pose dict.

  
**Input**

poses : dict[int, dict[str, tuple[float, float]]]  
    {frame_idx: {landmark_name: (x_px, y_px)}}  
fps   : float

  
**Output**

FeatureArray : dict[str, np.ndarray]  
    Arrays of length (max_frame - min_frame + 1), NaN where data is missing.  
    Index 0 = min_frame.  
min_frame : int

## Contents

- [`extract_features`](#extract_features) — Return (feature_arrays, min_frame).

### `extract_features`

```python
extract_features(
    poses: Dict[int, Dict[str, Tuple[float, float]]],
    fps: float
) -> Tuple[Dict[str, np.ndarray], int]
```

| input | type | default |
|---|---|---|
| `poses` | Dict[int, Dict[str, Tuple[float, float]]] | required |
| `fps` | float | required |

**returns** `Tuple[Dict[str, np.ndarray], int]`

Return (feature_arrays, min_frame).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/features.py#L28)</sub>
