"""EMG filter settings: what was actually applied, and where it came from.

The gap this closes
-------------------
The EMG chain is band-pass → full-wave rectify → low-pass envelope, and until
now only *one* of its five parameters could be set at all
(``BatchSettings.emg_envelope_lowpass_hz``). The band-pass corners and both
filter orders were positional defaults inside
``emg_normalise.filter_emg(highcut_bp=95, lowcut_bp=20, order_bp=4,
order_lp=4)``, unreachable from any config file, and nothing recorded which
values a given result was produced with.

That matters because these are not cosmetic. The band-pass corners set which
part of the signal survives to become an excitation, and the envelope cutoff
sets how fast that excitation can change — both feed straight into CEINMS, so
two labs running "the same" pipeline on the same c3d can get different muscle
forces and have no way to see why. A result you cannot reproduce from its
session file is not a result.

Precedence, loosest last::

    session.yaml  emg_filter:            explicit, per session — wins
    settings.py   BatchSettings.emg_*    the two knobs that already existed
    DEFAULTS                             exactly today's hard-coded values

The defaults are deliberately identical to what the code did before, so adding
this module changes no existing result. A session that says nothing behaves
exactly as it did.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

__all__ = ["DEFAULTS", "KEYS", "settings_for", "from_session_dir",
           "session_config_near", "describe", "to_filter_kwargs"]

#: Precisely the values baked into ``emg_normalise.filter_emg`` before this
#: module existed. Changing one changes every result computed after it.
DEFAULTS: Dict[str, Any] = {
    "bandpass_low": 20.0,       # Hz, high-pass corner of the band-pass
    "bandpass_high": 95.0,      # Hz, low-pass corner of the band-pass
    "bandpass_order": 4,        # Butterworth order
    "envelope_lowpass": 6.0,    # Hz, low-pass applied after rectification
    "envelope_order": 4,        # Butterworth order
    "sampling_freq": None,      # None = take it from the file's time column
}

KEYS = tuple(DEFAULTS)

#: session.yaml spellings accepted for each key. The long names are canonical;
#: the short ones match ``filter_emg``'s own parameters so someone reading the
#: function can write the block without a lookup.
_ALIASES = {
    "bandpass_low": ("bandpass_low", "lowcut_bp", "band_low", "highpass"),
    "bandpass_high": ("bandpass_high", "highcut_bp", "band_high"),
    "bandpass_order": ("bandpass_order", "order_bp"),
    "envelope_lowpass": ("envelope_lowpass", "lowcut_lp", "envelope", "lowpass"),
    "envelope_order": ("envelope_order", "order_lp"),
    "sampling_freq": ("sampling_freq", "fs", "sampling_rate"),
}

#: BatchSettings attributes that already existed, kept working.
_BATCH = {
    "envelope_lowpass": "emg_envelope_lowpass_hz",
    "sampling_freq": "emg_sampling_freq",
}


def _coerce(key: str, value):
    if value is None:
        return None
    if key.endswith("_order"):
        return int(value)
    return float(value)


def settings_for(session_cfg: Optional[dict] = None,
                 batch_settings: Any = None) -> Dict[str, Any]:
    """Merge the three sources into one settings dict. Never raises."""
    out = dict(DEFAULTS)

    for key, attr in _BATCH.items():
        val = getattr(batch_settings, attr, None) if batch_settings is not None else None
        if val is not None:
            try:
                out[key] = _coerce(key, val)
            except (TypeError, ValueError):
                pass

    block = (session_cfg or {}).get("emg_filter") if isinstance(session_cfg, dict) else None
    if isinstance(block, dict):
        for key, names in _ALIASES.items():
            for name in names:
                if name in block and block[name] is not None:
                    try:
                        out[key] = _coerce(key, block[name])
                    except (TypeError, ValueError):
                        pass
                    break
    return out


def session_config_near(path) -> Dict[str, Any]:
    """Load the ``session.yaml`` governing *path*, searching upward.

    A trial only knows its own folder
    (``<session>/3_iterations/<iteration>/<trial>``), so the session config is
    found by walking up rather than threaded through every call site.
    """
    try:
        import yaml
    except Exception:
        return {}
    here = os.path.abspath(str(path))
    if os.path.isfile(here):
        here = os.path.dirname(here)
    for _ in range(6):
        cand = os.path.join(here, "session.yaml")
        if os.path.isfile(cand):
            try:
                with open(cand, "r", encoding="utf-8") as fh:
                    return yaml.safe_load(fh) or {}
            except Exception:
                return {}
        nxt = os.path.dirname(here)
        if nxt == here:
            break
        here = nxt
    return {}


def from_session_dir(path, batch_settings: Any = None) -> Dict[str, Any]:
    """``settings_for`` for whatever session governs *path*."""
    return settings_for(session_config_near(path), batch_settings)


def to_filter_kwargs(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Map the canonical names onto ``emg_normalise.filter_emg``'s parameters."""
    return {
        "lowcut_bp": settings["bandpass_low"],
        "highcut_bp": settings["bandpass_high"],
        "order_bp": settings["bandpass_order"],
        "lowcut_lp": settings["envelope_lowpass"],
        "order_lp": settings["envelope_order"],
    }


def describe(settings: Dict[str, Any]) -> str:
    """One line naming every value used — for the log and for provenance."""
    fs = settings.get("sampling_freq")
    return (f"band-pass {settings['bandpass_low']:g}-{settings['bandpass_high']:g} Hz "
            f"(order {settings['bandpass_order']}) -> rectify -> envelope "
            f"{settings['envelope_lowpass']:g} Hz (order {settings['envelope_order']})"
            + (f", fs {float(fs):g} Hz" if fs else ", fs from the time column"))
