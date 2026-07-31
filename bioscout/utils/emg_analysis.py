"""EMG frequency content and muscle synergies.

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
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

__all__ = [
    "SpectrumResult", "SynergyResult",
    "power_spectrum", "median_frequency", "frequency_report",
    "envelope", "synergies", "vaf_curve", "synergy_report",
    "read_emg_mot",
]


# ------------------------------------------------------------------ loading
def read_emg_mot(path) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """Read an OpenSim .mot/.sto storage file into ``(time, {channel: signal})``.

    Kept here rather than reusing the pipeline's loader so this module has no
    bioscout dependency and can be run against any storage file.
    """
    from pathlib import Path
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().lower() == "endheader":
            start = i + 1
            break
    else:
        start = 0
    header = lines[start].split()
    data = np.array([[float(x) for x in ln.split()]
                     for ln in lines[start + 1:] if ln.strip()], float)
    if data.size == 0:
        raise ValueError(f"no data rows in {path}")
    time = data[:, 0]
    return time, {name: data[:, j] for j, name in enumerate(header) if j > 0}


# --------------------------------------------------------------- frequency
@dataclass
class SpectrumResult:
    """One channel's spectrum and the summary numbers taken from it."""

    channel: str
    freqs: np.ndarray            # Hz
    power: np.ndarray            # power spectral density
    median_hz: float
    mean_hz: float
    band_fraction: Dict[str, float] = field(default_factory=dict)

    @property
    def mains_flag(self) -> bool:
        """True when a suspicious share of power sits in the mains band."""
        return self.band_fraction.get("mains_50_60", 0.0) > 0.10

    @property
    def artefact_flag(self) -> bool:
        """True when a suspicious share of power sits below the EMG band."""
        return self.band_fraction.get("below_20", 0.0) > 0.15


def power_spectrum(signal: Sequence[float], fs: float, *,
                   detrend: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """Welch power spectral density, falling back to a periodogram.

    Welch rather than a single FFT because EMG is not stationary across a lift;
    averaging over segments gives a spectrum that is not dominated by whichever
    burst happened to be longest.
    """
    x = np.asarray(signal, float)
    x = x[np.isfinite(x)]
    if x.size < 16:
        raise ValueError("signal too short for a spectrum")
    if detrend:
        x = x - np.mean(x)
    try:
        from scipy.signal import welch
        nper = int(min(len(x), max(256, fs)))       # ~1 s windows
        return welch(x, fs=fs, nperseg=nper)
    except Exception:
        spec = np.abs(np.fft.rfft(x)) ** 2 / len(x)
        return np.fft.rfftfreq(len(x), 1.0 / fs), spec


def median_frequency(freqs, power) -> float:
    """Frequency below which half the spectral power lies.

    The standard fatigue index: as a muscle fatigues, conduction velocity drops
    and this falls, usually well before force does.
    """
    f, p = np.asarray(freqs, float), np.asarray(power, float)
    tot = np.trapezoid(p, f) if hasattr(np, "trapezoid") else np.trapz(p, f)
    if tot <= 0:
        return float("nan")
    cum = np.cumsum((p[1:] + p[:-1]) * 0.5 * np.diff(f))
    idx = int(np.searchsorted(cum, tot / 2.0))
    return float(f[min(idx + 1, len(f) - 1)])


_BANDS = {
    "below_20":      (0.0, 20.0),      # motion artefact, cable sway
    "mains_50_60":   (48.0, 62.0),     # mains pickup (either standard)
    "emg_20_450":    (20.0, 450.0),    # the band EMG actually lives in
}


def frequency_report(channels: Dict[str, Sequence[float]], fs: float
                     ) -> Dict[str, SpectrumResult]:
    """Spectrum + summary per channel, for a whole trial at once."""
    out: Dict[str, SpectrumResult] = {}
    for name, sig in channels.items():
        try:
            f, p = power_spectrum(sig, fs)
        except Exception:
            continue
        tot = float(np.sum(p)) or 1.0
        bands = {k: float(np.sum(p[(f >= lo) & (f < hi)]) / tot)
                 for k, (lo, hi) in _BANDS.items()}
        mean_hz = float(np.sum(f * p) / (np.sum(p) or 1.0))
        out[name] = SpectrumResult(channel=name, freqs=f, power=p,
                                   median_hz=median_frequency(f, p),
                                   mean_hz=mean_hz, band_fraction=bands)
    return out


# --------------------------------------------------------------- synergies
@dataclass
class SynergyResult:
    """One NMF factorisation: ``data ~= weights @ activations``."""

    n_synergies: int
    weights: np.ndarray          # (channels, n) — which muscles group together
    activations: np.ndarray      # (n, samples) — when each group is active
    vaf: float                   # total variance accounted for, 0..1
    vaf_per_channel: np.ndarray  # (channels,)
    channels: List[str] = field(default_factory=list)


def envelope(signal: Sequence[float], fs: float, *, cutoff: float = 6.0,
             already_rectified: bool = False) -> np.ndarray:
    """Linear envelope: rectify, then low-pass at ``cutoff`` Hz.

    Synergy extraction operates on envelopes. Feeding raw EMG factorises noise:
    the raw signal is zero-mean and roughly symmetric, so the non-negativity
    constraint that gives NMF its meaning has nothing to bite on.
    """
    x = np.asarray(signal, float)
    x = np.nan_to_num(x)
    if not already_rectified:
        x = np.abs(x)
    try:
        from scipy.signal import butter, filtfilt
        b, a = butter(4, cutoff / (fs / 2.0), btype="low")
        return np.asarray(filtfilt(b, a, x), float)
    except Exception:                      # no scipy: moving average
        w = max(1, int(fs / max(cutoff, 1e-6)))
        return np.convolve(x, np.ones(w) / w, mode="same")


def _nmf(V, n, *, random_state=0, max_iter=500, tol=1e-6):
    """Multiplicative-update NMF, used when scikit-learn is not installed."""
    rng = np.random.default_rng(random_state)
    m, t = V.shape
    W = rng.random((m, n)) + 0.1
    H = rng.random((n, t)) + 0.1
    prev = np.inf
    eps = 1e-12
    for _ in range(max_iter):
        H *= (W.T @ V) / (W.T @ W @ H + eps)
        W *= (V @ H.T) / (W @ H @ H.T + eps)
        err = float(np.linalg.norm(V - W @ H))
        if abs(prev - err) < tol * max(prev, 1.0):
            break
        prev = err
    return W, H


def synergies(envelopes: Dict[str, Sequence[float]], n: int, *,
              random_state: int = 0, normalise: bool = True) -> SynergyResult:
    """Extract ``n`` synergies from a channel-by-time envelope matrix.

    ``normalise`` scales each channel to unit peak first, which is the usual
    convention: without it a channel with a large raw amplitude dominates the
    factorisation for reasons of electrode placement rather than physiology.
    """
    names = list(envelopes)
    V = np.vstack([np.asarray(envelopes[k], float) for k in names])
    V = np.nan_to_num(V)
    V[V < 0] = 0.0
    if normalise:
        peak = np.max(V, axis=1, keepdims=True)
        peak[peak <= 0] = 1.0
        V = V / peak
    if n < 1 or n > V.shape[0]:
        raise ValueError(f"n must be 1..{V.shape[0]} (channels), got {n}")

    try:
        from sklearn.decomposition import NMF
        model = NMF(n_components=n, init="nndsvda", random_state=random_state,
                    max_iter=1000)
        W = model.fit_transform(V)
        H = model.components_
    except Exception:
        W, H = _nmf(V, n, random_state=random_state)

    R = W @ H
    resid = V - R
    sse = float(np.sum(resid ** 2))
    sst = float(np.sum(V ** 2)) or 1.0
    per_ch = 1.0 - (np.sum(resid ** 2, axis=1) /
                    np.where(np.sum(V ** 2, axis=1) > 0,
                             np.sum(V ** 2, axis=1), 1.0))
    return SynergyResult(n_synergies=n, weights=W, activations=H,
                         vaf=1.0 - sse / sst, vaf_per_channel=per_ch,
                         channels=names)


def vaf_curve(envelopes: Dict[str, Sequence[float]], *, max_n: Optional[int] = None,
              random_state: int = 0) -> List[SynergyResult]:
    """One factorisation per synergy count, 1..max_n.

    VAF rises monotonically with count by construction, so this curve is read
    for its *elbow*, not its maximum. Reporting "n synergies explain X%"
    without the curve hides the fact that n+1 always explains more.
    """
    top = max_n or len(envelopes)
    return [synergies(envelopes, k, random_state=random_state)
            for k in range(1, min(top, len(envelopes)) + 1)]


def synergy_report(channels: Dict[str, Sequence[float]], fs: float, *,
                   max_n: Optional[int] = None, vaf_target: float = 0.90,
                   random_state: int = 0) -> dict:
    """Envelope -> VAF curve -> the count that first reaches ``vaf_target``.

    Returns the curve as well as the chosen count, because the count alone is
    the least informative part of the result.
    """
    envs = {k: envelope(v, fs) for k, v in channels.items()}
    curve = vaf_curve(envs, max_n=max_n, random_state=random_state)
    chosen = next((r.n_synergies for r in curve if r.vaf >= vaf_target),
                  curve[-1].n_synergies if curve else 0)
    return {"curve": curve, "n_chosen": chosen, "vaf_target": vaf_target,
            "envelopes": envs,
            "vaf": [r.vaf for r in curve],
            "best": next((r for r in curve if r.n_synergies == chosen), None)}
