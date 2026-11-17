# `bioscout.model.inspect.discontinuity`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/discontinuity.py)

Discontinuity detection for 1-D waveforms (no OpenSim dependency).

Ported from the MATLAB ``detectDiscontinuitiesInSignal``. Used here to flag  
sudden jumps in moment-arm / muscle-length curves so the inspection plots can  
mark them. The numerical thresholds match the original implementation.

## Contents

- [`mad`](#mad) — Median absolute deviation about the median (MATLAB ``mad(x, 1)``).
- [`detect_discontinuities`](#detect_discontinuities) — Return 0-based frame indices where ``x`` has a genuine discontinuity.

### `mad`

```python
mad(x: np.ndarray) -> float
```

| input | type | default |
|---|---|---|
| `x` | np.ndarray | required |

**returns** `float`

Median absolute deviation about the median (MATLAB ``mad(x, 1)``).

Note this is the *median*-based MAD, not numpy/statistics' default  
mean-based version.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/discontinuity.py#L17)</sub>

### `detect_discontinuities`

```python
detect_discontinuities(
    x: np.ndarray,
    min_jump_m: float = 0.001,
    k_d2: float = 7.0,
    k_local: float = 3.0,
    k_global: float = 8.0,
    win: int = 5
) -> list[int]
```

| input | type | default |
|---|---|---|
| `x` | np.ndarray | required |
| `min_jump_m` | float | `0.001` |
| `k_d2` | float | `7.0` |
| `k_local` | float | `3.0` |
| `k_global` | float | `8.0` |
| `win` | int | `5` |

**returns** `list[int]`

Return 0-based frame indices where ``x`` has a genuine discontinuity.

Algorithm (matching the MATLAB original); all thresholds are tunable:  
  1. second derivative ``d2y`` of the signal  
  2. flag frames where ``|d2y| > k_d2 * 1.4826 * MAD(d2y)``  
  3. for each flagged run of <= 2 samples, require the first-derivative jump  
     to exceed ``k_local`` * local sigma, ``k_global`` * global sigma, and  
     ``min_jump_m`` (metres) absolute.

Lower ``min_jump_m`` / ``k_global`` to catch smaller jumps (more sensitive);  
raise them to ignore noise (fewer false positives).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/discontinuity.py#L43)</sub>
