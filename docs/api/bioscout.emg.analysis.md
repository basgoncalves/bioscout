# `bioscout.emg.analysis`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py)

EMG frequency content and muscle synergies.

Two analyses that sit either side of the same question — *is this EMG worth  
feeding to CEINMS, and what is it actually telling us?*

**Frequency** is the quality check. Surface EMG power lives roughly between 20  
and 450 Hz; anything concentrated at 50/60 Hz is mains pickup, anything below  
~20 Hz is motion artefact or cable sway, and a median frequency that falls  
steadily through a set is the classic fatigue signature. A power spectrum takes  
seconds to compute and catches problems that survive normalisation and then  
quietly distort every excitation CEINMS sees.

**Synergies** are an analysis in their own right: non-negative matrix  
factorisation of the channel-by-time envelope matrix into a small number of  
weight vectors (which muscles group together) and activation profiles (when  
each group is active). The usual reporting is VAF against synergy count, and  
the elbow of that curve is the number of synergies claimed.

Pure numpy/scipy — no OpenSim, no GUI — so this is testable and usable from a  
script. The GUI tab is a thin viewer over these functions.

Caveats worth carrying into any write-up:

* NMF has no unique solution. It is initialised randomly and converges to a  
  local optimum, so results shift run to run unless the seed is fixed. Every  
  function here takes ``random_state`` and defaults it to 0.  
* VAF rises monotonically with synergy count by construction. "4 synergies  
  explain 91%" is not evidence for 4; the elbow is a convention, not a test.  
* Synergies are computed on **envelopes** (rectified, low-pass), not raw EMG.  
  Passing raw signal gives noise factorisation.

## Contents

- class [`SpectrumResult`](#spectrumresult) — One channel's spectrum and the summary numbers taken from it.
  - [`SpectrumResult.mains_flag`](#spectrumresultmains_flag) — True when a suspicious share of power sits in the mains band.
  - [`SpectrumResult.artefact_flag`](#spectrumresultartefact_flag) — True when a suspicious share of power sits below the EMG band.
- class [`SynergyResult`](#synergyresult) — One NMF factorisation: ``data ~= weights @ activations``.
- [`read_emg_mot`](#read_emg_mot) — Read an OpenSim .mot/.sto storage file into ``(time, {channel: signal})``.
- [`power_spectrum`](#power_spectrum) — Welch power spectral density, falling back to a periodogram.
- [`median_frequency`](#median_frequency) — Frequency below which half the spectral power lies.
- [`frequency_report`](#frequency_report) — Spectrum + summary per channel, for a whole trial at once.
- [`envelope`](#envelope) — Linear envelope: rectify, then low-pass at ``cutoff`` Hz.
- [`synergies`](#synergies) — Extract ``n`` synergies from a channel-by-time envelope matrix.
- [`vaf_curve`](#vaf_curve) — One factorisation per synergy count, 1..max_n.
- [`synergy_report`](#synergy_report) — Envelope -> VAF curve -> the count that first reaches ``vaf_target``.

<a id="spectrumresult"></a>

## class `SpectrumResult`

One channel's spectrum and the summary numbers taken from it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L73)</sub>

<a id="spectrumresultmains_flag"></a>

### `SpectrumResult.mains_flag`

```python
SpectrumResult.mains_flag() -> bool
```

**returns** `bool`

True when a suspicious share of power sits in the mains band.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L84)</sub>

<a id="spectrumresultartefact_flag"></a>

### `SpectrumResult.artefact_flag`

```python
SpectrumResult.artefact_flag() -> bool
```

**returns** `bool`

True when a suspicious share of power sits below the EMG band.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L89)</sub>

<a id="synergyresult"></a>

## class `SynergyResult`

One NMF factorisation: ``data ~= weights @ activations``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L160)</sub>

### `read_emg_mot`

```python
read_emg_mot(path) -> Tuple[np.ndarray, Dict[str, np.ndarray]]
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `Tuple[np.ndarray, Dict[str, np.ndarray]]`

Read an OpenSim .mot/.sto storage file into ``(time, {channel: signal})``.

Kept here rather than reusing the pipeline's loader so this module has no  
bioscout dependency and can be run against any storage file.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L48)</sub>

### `power_spectrum`

```python
power_spectrum(
    signal: Sequence[float],
    fs: float,
    detrend: bool = True
) -> Tuple[np.ndarray, np.ndarray]
```

| input | type | default |
|---|---|---|
| `signal` | Sequence[float] | required |
| `fs` | float | required |
| `detrend` | bool | `True` |

**returns** `Tuple[np.ndarray, np.ndarray]`

Welch power spectral density, falling back to a periodogram.

Welch rather than a single FFT because EMG is not stationary across a lift;  
averaging over segments gives a spectrum that is not dominated by whichever  
burst happened to be longest.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L94)</sub>

### `median_frequency`

```python
median_frequency(freqs, power) -> float
```

| input | type | default |
|---|---|---|
| `freqs` | – | required |
| `power` | – | required |

**returns** `float`

Frequency below which half the spectral power lies.

The standard fatigue index: as a muscle fatigues, conduction velocity drops  
and this falls, usually well before force does.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L117)</sub>

### `frequency_report`

```python
frequency_report(
    channels: Dict[str, Sequence[float]],
    fs: float
) -> Dict[str, SpectrumResult]
```

| input | type | default |
|---|---|---|
| `channels` | Dict[str, Sequence[float]] | required |
| `fs` | float | required |

**returns** `Dict[str, SpectrumResult]`

Spectrum + summary per channel, for a whole trial at once.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L139)</sub>

### `envelope`

```python
envelope(
    signal: Sequence[float],
    fs: float,
    cutoff: float = 6.0,
    already_rectified: bool = False
) -> np.ndarray
```

| input | type | default |
|---|---|---|
| `signal` | Sequence[float] | required |
| `fs` | float | required |
| `cutoff` | float | `6.0` |
| `already_rectified` | bool | `False` |

**returns** `np.ndarray`

Linear envelope: rectify, then low-pass at ``cutoff`` Hz.

Synergy extraction operates on envelopes. Feeding raw EMG factorises noise:  
the raw signal is zero-mean and roughly symmetric, so the non-negativity  
constraint that gives NMF its meaning has nothing to bite on.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L171)</sub>

### `synergies`

```python
synergies(
    envelopes: Dict[str, Sequence[float]],
    n: int,
    random_state: int = 0,
    normalise: bool = True
) -> SynergyResult
```

| input | type | default |
|---|---|---|
| `envelopes` | Dict[str, Sequence[float]] | required |
| `n` | int | required |
| `random_state` | int | `0` |
| `normalise` | bool | `True` |

**returns** `SynergyResult`

Extract ``n`` synergies from a channel-by-time envelope matrix.

``normalise`` scales each channel to unit peak first, which is the usual  
convention: without it a channel with a large raw amplitude dominates the  
factorisation for reasons of electrode placement rather than physiology.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L210)</sub>

### `vaf_curve`

```python
vaf_curve(
    envelopes: Dict[str, Sequence[float]],
    max_n: Optional[int] = None,
    random_state: int = 0
) -> List[SynergyResult]
```

| input | type | default |
|---|---|---|
| `envelopes` | Dict[str, Sequence[float]] | required |
| `max_n` | Optional[int] | `None` |
| `random_state` | int | `0` |

**returns** `List[SynergyResult]`

One factorisation per synergy count, 1..max_n.

VAF rises monotonically with count by construction, so this curve is read  
for its *elbow*, not its maximum. Reporting "n synergies explain X%"  
without the curve hides the fact that n+1 always explains more.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L250)</sub>

### `synergy_report`

```python
synergy_report(
    channels: Dict[str, Sequence[float]],
    fs: float,
    max_n: Optional[int] = None,
    vaf_target: float = 0.9,
    random_state: int = 0
) -> dict
```

| input | type | default |
|---|---|---|
| `channels` | Dict[str, Sequence[float]] | required |
| `fs` | float | required |
| `max_n` | Optional[int] | `None` |
| `vaf_target` | float | `0.9` |
| `random_state` | int | `0` |

**returns** `dict`

Envelope -> VAF curve -> the count that first reaches ``vaf_target``.

Returns the curve as well as the chosen count, because the count alone is  
the least informative part of the result.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/analysis.py#L263)</sub>
