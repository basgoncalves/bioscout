# `bioscout.emg.filter`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/filter.py)

EMG filter settings: what was actually applied, and where it came from.

  
**The gap this closes**

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

## Contents

- [`settings_for`](#settings_for) — Merge the three sources into one settings dict. Never raises.
- [`session_config_near`](#session_config_near) — Load the ``session.yaml`` governing *path*, searching upward.
- [`from_session_dir`](#from_session_dir) — ``settings_for`` for whatever session governs *path*.
- [`to_filter_kwargs`](#to_filter_kwargs) — Map the canonical names onto ``emg_normalise.filter_emg``'s parameters.
- [`describe`](#describe) — One line naming every value used — for the log and for provenance.

### `settings_for`

```python
settings_for(
    session_cfg: Optional[dict] = None,
    batch_settings: Any = None
) -> Dict[str, Any]
```

| input | type | default |
|---|---|---|
| `session_cfg` | Optional[dict] | `None` |
| `batch_settings` | Any | `None` |

**returns** `Dict[str, Any]`

Merge the three sources into one settings dict. Never raises.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/filter.py#L98)</sub>

### `session_config_near`

```python
session_config_near(path) -> Dict[str, Any]
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `Dict[str, Any]`

Load the ``session.yaml`` governing *path*, searching upward.

A trial only knows its own folder  
(``<session>/3_iterations/<iteration>/<trial>``), so the session config is  
found by walking up rather than threaded through every call site.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/filter.py#L124)</sub>

### `from_session_dir`

```python
from_session_dir(path, batch_settings: Any = None) -> Dict[str, Any]
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `batch_settings` | Any | `None` |

**returns** `Dict[str, Any]`

``settings_for`` for whatever session governs *path*.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/filter.py#L153)</sub>

### `to_filter_kwargs`

```python
to_filter_kwargs(settings: Dict[str, Any]) -> Dict[str, Any]
```

| input | type | default |
|---|---|---|
| `settings` | Dict[str, Any] | required |

**returns** `Dict[str, Any]`

Map the canonical names onto ``emg_normalise.filter_emg``'s parameters.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/filter.py#L158)</sub>

### `describe`

```python
describe(settings: Dict[str, Any]) -> str
```

| input | type | default |
|---|---|---|
| `settings` | Dict[str, Any] | required |

**returns** `str`

One line naming every value used — for the log and for provenance.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/emg/filter.py#L170)</sub>
