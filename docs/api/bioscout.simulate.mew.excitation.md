# `bioscout.simulate.mew.excitation`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/excitation.py)

EMG -> muscle excitation.

Takes bioscout's already-normalised ``emg_filtered_normalised.mot`` when it  
exists (the preferred path -- MVC normalisation belongs to the session, not to  
this solver), and can do the filtering itself when handed raw EMG.

The channel->muscle mapping is bioscout's ``emg_map`` format verbatim::

    {"RF": ["recfem_r"], "VAS": ["vasmed_r", "vaslat_r", "vasint_r"]}

One channel can drive several muscles (a shared excitation), which is exactly  
what CEINMS does and what makes 16 electrodes able to inform 80 muscles.

## Contents

- [`process_raw`](#process_raw) — band-pass -> rectify -> low-pass -> normalise. Needs scipy.
- [`apply_delay`](#apply_delay) — Electromechanical delay: shift excitation forward in time.
- [`map_to_muscles`](#map_to_muscles) — Spread channels over muscles.
- [`excitation_to_activation`](#excitation_to_activation) — Full neural pathway: excitation -> activation dynamics -> nonlinearity.
- [`emg_targets`](#emg_targets) — Convenience: EMG frame -> ``(a_emg (nt,nm), mask (nm,), channels)``.

### `process_raw`

```python
process_raw(
    df: pd.DataFrame,
    band=(30.0, 400.0),
    lowpass=6.0,
    mvc: Optional[Dict[str, float]] = None
) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `df` | pd.DataFrame | required |
| `band` | – | `(30.0, 400.0)` |
| `lowpass` | – | `6.0` |
| `mvc` | Optional[Dict[str, float]] | `None` |

**returns** `pd.DataFrame`

band-pass -> rectify -> low-pass -> normalise. Needs scipy.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/excitation.py#L27)</sub>

### `apply_delay`

```python
apply_delay(df: pd.DataFrame, delay_s=0.045) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `df` | pd.DataFrame | required |
| `delay_s` | – | `0.045` |

**returns** `pd.DataFrame`

Electromechanical delay: shift excitation forward in time.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/excitation.py#L49)</sub>

### `map_to_muscles`

```python
map_to_muscles(
    emg: pd.DataFrame,
    emg_map: Dict[str, List[str]],
    muscles: Sequence[str],
    gains: Optional[Dict[str, float]] = None
) -> Tuple[np.ndarray, np.ndarray, List[str]]
```

| input | type | default |
|---|---|---|
| `emg` | pd.DataFrame | required |
| `emg_map` | Dict[str, List[str]] | required |
| `muscles` | Sequence[str] | required |
| `gains` | Optional[Dict[str, float]] | `None` |

**returns** `Tuple[np.ndarray, np.ndarray, List[str]]`

Spread channels over muscles.

Returns ``(u, mask, used_channels)`` where ``u`` is (nt, nm) excitation and  
``mask`` is (nm,) bool marking which muscles an electrode actually informs.  
Unmapped muscles keep u=0 and mask=False -- the solver must be free to  
choose their activation, so it is important the mask is honest here.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/excitation.py#L61)</sub>

### `excitation_to_activation`

```python
excitation_to_activation(
    u: np.ndarray,
    times: np.ndarray,
    params: MuscleParameters
) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `u` | np.ndarray | required |
| `times` | np.ndarray | required |
| `params` | MuscleParameters | required |

**returns** `np.ndarray`

Full neural pathway: excitation -> activation dynamics -> nonlinearity.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/excitation.py#L95)</sub>

### `emg_targets`

```python
emg_targets(
    emg: Optional[pd.DataFrame],
    emg_map,
    muscles,
    params,
    times: np.ndarray,
    gains=None,
    delay_s=0.0
)
```

| input | type | default |
|---|---|---|
| `emg` | Optional[pd.DataFrame] | required |
| `emg_map` | – | required |
| `muscles` | – | required |
| `params` | – | required |
| `times` | np.ndarray | required |
| `gains` | – | `None` |
| `delay_s` | – | `0.0` |

Convenience: EMG frame -> ``(a_emg (nt,nm), mask (nm,), channels)``.

Returns zeros and an all-False mask when there is no usable EMG, so callers  
never need to branch on ``emg is None``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/mew/excitation.py#L103)</sub>
