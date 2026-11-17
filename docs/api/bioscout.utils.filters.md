# `bioscout.utils.filters`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/filters.py)

Generic zero-phase signal filtering -- the primitives, with no domain in them.

Pulled out of ``emg_normalise.filter_emg()``'s inline ``scipy.signal``  
butter+filtfilt calls (docs/RESTRUCTURE_PLAN.md, stage 11). Nothing here knows  
what EMG is: ``bioscout.emg.normalise`` supplies the cutoffs and the column  
loop, this supplies the filter. Other inline filtering in the codebase  
(``simulate/gapfill.py`` is the next candidate) migrates in over time rather  
than in one audit.

``filtfilt`` is used rather than ``lfilter`` on purpose: it filters forwards  
and backwards, so the result has no phase lag. That matters for anything whose  
TIMING is read afterwards -- an EMG envelope lined up against a gait event, a  
force trace lined up against a marker trajectory. The cost is that the  
effective filter order is doubled, which is why the orders here look low.

    from bioscout.utils.filters import bandpass, lowpass

    env = lowpass(np.abs(bandpass(raw, fs=2000, lowcut=20, highcut=95)),  
                  fs=2000, cutoff=6)

## Contents

- [`nyquist_fraction`](#nyquist_fraction) — ``freq`` as a fraction of the Nyquist rate -- what ``butter`` wants.
- [`bandpass`](#bandpass) — Zero-phase Butterworth band-pass of a 1-D signal.
- [`lowpass`](#lowpass) — Zero-phase Butterworth low-pass of a 1-D signal.

### `nyquist_fraction`

```python
nyquist_fraction(freq, fs)
```

| input | type | default |
|---|---|---|
| `freq` | – | required |
| `fs` | – | required |

``freq`` as a fraction of the Nyquist rate -- what ``butter`` wants.

Returns >= 1.0 when the cutoff is at or above Nyquist, which is the caller's  
cue that the request is not filterable at this sampling rate.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/filters.py#L26)</sub>

### `bandpass`

```python
bandpass(x, fs, lowcut, highcut, order=4)
```

| input | type | default |
|---|---|---|
| `x` | – | required |
| `fs` | – | required |
| `lowcut` | – | required |
| `highcut` | – | required |
| `order` | – | `4` |

Zero-phase Butterworth band-pass of a 1-D signal.

  
**Args**

    x: the samples (anything ``filtfilt`` accepts -- list, ndarray, Series).  
    fs: sampling rate in Hz.  
    lowcut, highcut: passband edges in Hz.  
    order: Butterworth order BEFORE the forward-backward pass doubles it.

Raises ValueError when the band is not realisable at this sampling rate  
(edges crossed, or at/above Nyquist) rather than returning a silently  
wrong signal -- scipy would otherwise raise a less specific error, or  
design a filter that does not do what was asked.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/filters.py#L35)</sub>

### `lowpass`

```python
lowpass(x, fs, cutoff, order=4)
```

| input | type | default |
|---|---|---|
| `x` | – | required |
| `fs` | – | required |
| `cutoff` | – | required |
| `order` | – | `4` |

Zero-phase Butterworth low-pass of a 1-D signal.

Same contract as :func:`bandpass`; raises ValueError when ``cutoff`` is at  
or above Nyquist.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/filters.py#L65)</sub>
