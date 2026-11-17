# `bioscout.model.edit.ops.markers`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/markers.py)

Marker placement and marker-set edits.

``place_markers`` is the standalone-IK registration that replaced ScaleTool's  
MarkerPlacer (whose internal IK segfaults on the Catelli and MRI models). It is  
exposed as its own op because it is useful on a model that is already scaled --  
re-registering markers does not require re-scaling, and re-scaling is the  
expensive step.

``drop_markers`` is the fix for a marker that is not on the body: BL and BR are  
barbell/rack references bound to ``/ground``, and IK matching a ground-fixed  
virtual marker against a bar travelling 1.4 m through a lift is worth hundreds of  
millimetres of marker RMS on every loaded trial.

## Contents

- [`place_markers`](#place_markers) — 
- [`drop_markers`](#drop_markers) — 

### `place_markers`

```python
place_markers(model, out, static_trc, marker_set=None, time_range=None, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `static_trc` | – | required |
| `marker_set` | – | `None` |
| `time_range` | – | `None` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/markers.py#L42)</sub>

### `drop_markers`

```python
drop_markers(model, out, markers, ground_bound=False, **_)
```

| input | type | default |
|---|---|---|
| `model` | – | required |
| `out` | – | required |
| `markers` | – | required |
| `ground_bound` | – | `False` |
| `**_` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/edit/ops/markers.py#L78)</sub>
