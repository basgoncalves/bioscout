# `bioscout.session.movement_detector.classifier`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/classifier.py)

classifier.py — frame-level task classification + state-machine transitions.

  
**Tasks**

standing            stationary  
walking             slow gait with heel strikes, no aerial  
running             fast gait OR aerial phase present  
backward_walking    walking direction opposite to dominant travel direction  
backward_running    running direction opposite to dominant travel direction  
jumping             upward impulse + aerial phase + landing  
squatting           repeated hip-depth cycles (low forward speed)  
deceleration        rapid speed decrease from running/walking  
side_cut            lateral direction change — MUST follow running/walking/jumping  
shuffle             lateral movement — MUST follow standing/shuffle

  
**Transition rules**

side_cut  ← previous task in {running, walking, jumping}  
shuffle   ← previous task in {standing, shuffle}  
(A lateral move following any other context defaults to 'shuffle'.)

## Contents

- [`classify_frames`](#classify_frames) — Return a list of task labels, one per frame index (0-based from min_frame).

### `classify_frames`

```python
classify_frames(F: Dict[str, np.ndarray], cfg) -> List[str]
```

| input | type | default |
|---|---|---|
| `F` | Dict[str, np.ndarray] | required |
| `cfg` | – | required |

**returns** `List[str]`

Return a list of task labels, one per frame index (0-based from min_frame).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/movement_detector/classifier.py#L48)</sub>
