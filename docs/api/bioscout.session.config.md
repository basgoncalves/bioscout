# `bioscout.session.config`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py)

session.yaml — the per-session configuration, read and written.

Everything that turns the YAML file into Python and back: :class:`SessionSpec`  
/ :class:`Model`, ``read_session_yaml`` / ``write_session_yaml`` /  
``scaffold_session_yaml``, the strict loader that refuses duplicate keys, and  
the resolvers for the named blocks inside it (EMG maps, EMG gains, CEINMS  
calibration configs, per-iteration settings).

No OpenSim, no Analyse: importing this is cheap.

## Contents

- class [`SessionKeys`](#sessionkeys) — session.yaml, top level. ``session.<key>``; any other key in the file works too (``session.implanted_side``), just not autocompleted.
  - [`SessionKeys.yaml_path`](#sessionkeysyaml_path) — This session's session.yaml.
  - [`SessionKeys.config`](#sessionkeysconfig) — The whole session.yaml (iteration keys normalised).
  - [`SessionKeys.source`](#sessionkeyssource) — ``<path>/session.yaml:<line>`` of ``key`` -- click it in the output to open the file at that line. Dotted for nested keys: ``session.source("iterations.gpk.mvic_factor")``.
- class [`IterationKeys`](#iterationkeys) — session.yaml, ``iterations.<name>:``. ``it.<key>``. File keys come back as absolute paths. They are written relative to the session's ``models_dir`` (model_generic, model_scaled) or ``setup_dir`` (markerset, so_actuators) when the session sets that root, else relative to the iteration folder (<session>/3_iterations/<name>). ``<subject>``, ``<session>`` and ``<iteration>`` in a path are replaced by this iteration's values. One iteration = ONE scaled model: CEINMS uses ``model_scaled``, everything else ``it.model_so`` (x mvic_factor, derived).
  - [`IterationKeys.set`](#iterationkeysset) — 
  - [`IterationKeys.yaml_path`](#iterationkeysyaml_path) — The session.yaml this iteration is declared in.
  - [`IterationKeys.config`](#iterationkeysconfig) — This iteration's block from session.yaml (key names normalised).
  - [`IterationKeys.relpath`](#iterationkeysrelpath) — ``path`` as session.yaml writes it for ``key``: relative to that key's root (models_dir / setup_dir, see ``_file_root``; the iteration folder when ``key`` is None or the root is unset), forward slashes, ``./``-led when under the root.
  - [`IterationKeys.source`](#iterationkeyssource) — ``<path>/session.yaml:<line>`` of ``iterations.<name>.<key>`` (or of the iteration block) -- click it in the output to open that line.
  - [`IterationKeys.model_so`](#iterationkeysmodel_so) — The SO model: ``model_scaled`` with every max isometric force x ``mvic_factor``, written next to it as ``<name>_mvicx<f>.osim``. The same file when ``mvic_factor`` is 1. Derived -- never in session.yaml.
- [`yaml_bool`](#yaml_bool) — A session.yaml flag as a bool, tolerating quoted strings.
- [`yaml_key_line`](#yaml_key_line) — 1-based line of ``key`` in a YAML file, or None. ``key`` is dotted for nested keys: ``"body_mass"``, ``"iterations.gpk.mvic_factor"``, ``"trials.Walking_01.time_range"``. Stops at the deepest key that exists.
- [`normalise_iterations`](#normalise_iterations) — Return ``cfg`` with every iteration block in the canonical shape.
- [`is_named_emg_map`](#is_named_emg_map) — True when `emg_map` holds NAMED sub-maps rather than channels.
- [`emg_maps`](#emg_maps) — ``{name: {channel: [muscles]}}`` for every mapping in a session config.
- [`emg_map_name_for`](#emg_map_name_for) — Which named mapping `iteration` runs with — see :func:`resolve_emg_map`.
- [`resolve_emg_map`](#resolve_emg_map) — The ``{channel: [muscles]}`` map one iteration should actually run with.
- [`ceinms_for`](#ceinms_for) — CEINMS settings for ONE iteration: the iteration's own ``ceinms:`` block over the session-wide one (2026-10-01: alpha/beta/gamma, mode and ``calibrated`` belong to the iteration -- two arms of one session can differ). Without an iteration, the session-wide block.
- [`uses_legacy_calibration`](#uses_legacy_calibration) — True when the calibration block is still at the top level.
- [`is_named_calibration`](#is_named_calibration) — True when `calibration` holds NAMED configs rather than bare parameters.
- [`calibration_configs`](#calibration_configs) — ``{name: {parameter: "min max"}}`` for every calibration config.
- [`calibration_name_for`](#calibration_name_for) — Which named calibration config `iteration` runs with.
- [`resolve_calibration`](#resolve_calibration) — The CEINMS calibration parameter bounds one iteration should run with.
- [`read_session_yaml`](#read_session_yaml) — Parse a ``session.yaml`` into a :class:`SessionSpec`. ``path`` may be the yaml file or the session folder containing it.
- [`write_session_yaml`](#write_session_yaml) — Serialise a :class:`SessionSpec` to ``session.yaml``. Returns the path.
- [`migrate_calibration_block`](#migrate_calibration_block) — Move a top-level ``calibration:`` / ``default_calibration:`` under ``ceinms:``.

<a id="sessionkeys"></a>

## class `SessionKeys`(_YamlEdit)

session.yaml, top level. ``session.<key>``; any other key in the file  
works too (``session.implanted_side``), just not autocompleted.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L669)</sub>

<a id="sessionkeysyaml_path"></a>

### `SessionKeys.yaml_path`

```python
SessionKeys.yaml_path()
```

This session's session.yaml.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L739)</sub>

<a id="sessionkeysconfig"></a>

### `SessionKeys.config`

```python
SessionKeys.config() -> dict
```

**returns** `dict`

The whole session.yaml (iteration keys normalised).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L744)</sub>

<a id="sessionkeyssource"></a>

### `SessionKeys.source`

```python
SessionKeys.source(key)
```

| input | type | default |
|---|---|---|
| `key` | – | required |

``<path>/session.yaml:<line>`` of ``key`` -- click it in the output to  
open the file at that line. Dotted for nested keys:  
``session.source("iterations.gpk.mvic_factor")``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L748)</sub>

<a id="iterationkeys"></a>

## class `IterationKeys`(_YamlEdit)

session.yaml, ``iterations.<name>:``. ``it.<key>``. File keys come back as  
absolute paths. They are written relative to the session's ``models_dir``  
(model_generic, model_scaled) or ``setup_dir`` (markerset, so_actuators)  
when the session sets that root, else relative to the iteration folder  
(<session>/3_iterations/<name>). ``<subject>``, ``<session>`` and  
``<iteration>`` in a path are replaced by this iteration's values. One iteration = ONE scaled model: CEINMS uses  
``model_scaled``, everything else ``it.model_so`` (x mvic_factor, derived).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L757)</sub>

<a id="iterationkeysset"></a>

### `IterationKeys.set`

```python
IterationKeys.set(key, value, save=False)
```

| input | type | default |
|---|---|---|
| `key` | – | required |
| `value` | – | required |
| `save` | – | `False` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L811)</sub>

<a id="iterationkeysyaml_path"></a>

### `IterationKeys.yaml_path`

```python
IterationKeys.yaml_path()
```

The session.yaml this iteration is declared in.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L824)</sub>

<a id="iterationkeysconfig"></a>

### `IterationKeys.config`

```python
IterationKeys.config() -> dict
```

**returns** `dict`

This iteration's block from session.yaml (key names normalised).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L883)</sub>

<a id="iterationkeysrelpath"></a>

### `IterationKeys.relpath`

```python
IterationKeys.relpath(path, key=None)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `key` | – | `None` |

``path`` as session.yaml writes it for ``key``: relative to that key's  
root (models_dir / setup_dir, see ``_file_root``; the iteration folder  
when ``key`` is None or the root is unset), forward slashes, ``./``-led  
when under the root.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L962)</sub>

<a id="iterationkeyssource"></a>

### `IterationKeys.source`

```python
IterationKeys.source(key=None)
```

| input | type | default |
|---|---|---|
| `key` | – | `None` |

``<path>/session.yaml:<line>`` of ``iterations.<name>.<key>`` (or of  
the iteration block) -- click it in the output to open that line.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L972)</sub>

<a id="iterationkeysmodel_so"></a>

### `IterationKeys.model_so`

```python
IterationKeys.model_so()
```

The SO model: ``model_scaled`` with every max isometric force x  
``mvic_factor``, written next to it as ``<name>_mvicx<f>.osim``. The  
same file when ``mvic_factor`` is 1. Derived -- never in session.yaml.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L980)</sub>

### `yaml_bool`

```python
yaml_bool(v, default=True)
```

| input | type | default |
|---|---|---|
| `v` | – | required |
| `default` | – | `True` |

A session.yaml flag as a bool, tolerating quoted strings.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L311)</sub>

### `yaml_key_line`

```python
yaml_key_line(path, key)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `key` | – | required |

1-based line of ``key`` in a YAML file, or None. ``key`` is dotted for  
nested keys: ``"body_mass"``, ``"iterations.gpk.mvic_factor"``,  
``"trials.Walking_01.time_range"``. Stops at the deepest key that exists.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L433)</sub>

### `normalise_iterations`

```python
normalise_iterations(cfg, path=None, warn=_warn_once)
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |
| `path` | – | `None` |
| `warn` | – | `_warn_once` |

Return ``cfg`` with every iteration block in the canonical shape.

* ``models:`` -> ``iterations:``, a list of blocks -> ``{name: block}``  
* old key spellings are renamed (``generic`` -> ``model_generic``) and the  
  two old model keys (``so_model``, ``ceinms_model``) collapse into  
  ``model_scaled`` -- an error if they named different models  
* a session-level ``markerset`` is copied into every iteration that has  
  none, and dropped from the top level — the marker set belongs to the  
  model it scales  
* unknown iteration keys are reported (a typo is otherwise just ignored)

Each fix prints one warning naming the file, so the file can be updated.  
The input is not modified.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1066)</sub>

### `is_named_emg_map`

```python
is_named_emg_map(cfg) -> bool
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |

**returns** `bool`

True when `emg_map` holds NAMED sub-maps rather than channels.

emg_map: {EMG01_vast_lat_l: [vaslat_l, ...]}        -> flat  (legacy)  
emg_map: {narrow: {EMG01_vast_lat_l: [...]}, ...}   -> named

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1229)</sub>

### `emg_maps`

```python
emg_maps(cfg) -> Dict[str, Dict[str, list]]
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |

**returns** `Dict[str, Dict[str, list]]`

``{name: {channel: [muscles]}}`` for every mapping in a session config.

A legacy flat `emg_map` comes back as a single entry under the name  
``'default'``, so callers never need to branch on the form. Insertion  
order follows the YAML.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1238)</sub>

### `emg_map_name_for`

```python
emg_map_name_for(cfg, iteration=None) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |
| `iteration` | – | `None` |

**returns** `Optional[str]`

Which named mapping `iteration` runs with — see :func:`resolve_emg_map`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1254)</sub>

### `resolve_emg_map`

```python
resolve_emg_map(cfg, iteration=None, strict=True) -> Dict[str, list]
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |
| `iteration` | – | `None` |
| `strict` | – | `True` |

**returns** `Dict[str, list]`

The ``{channel: [muscles]}`` map one iteration should actually run with.

Resolution order: the iteration's own ``emg_map: <name>`` selector, then  
the session-wide ``default_emg_map``, then a mapping literally called  
``default``, then the only mapping if there is exactly one. Anything left  
over is ambiguous and raises.

With ``strict=False`` an ambiguous or unknown selection falls back to the  
first mapping in YAML order instead of raising — for read-only consumers  
(plots, reports) where a missing figure is worse than an approximate one.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1261)</sub>

### `ceinms_for`

```python
ceinms_for(cfg, iteration=None) -> dict
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |
| `iteration` | – | `None` |

**returns** `dict`

CEINMS settings for ONE iteration: the iteration's own ``ceinms:`` block  
over the session-wide one (2026-10-01: alpha/beta/gamma, mode and  
``calibrated`` belong to the iteration -- two arms of one session can  
differ). Without an iteration, the session-wide block.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1453)</sub>

### `uses_legacy_calibration`

```python
uses_legacy_calibration(cfg) -> bool
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |

**returns** `bool`

True when the calibration block is still at the top level.

Having both is NOT an error and NOT a merge: the nested one wins outright,  
exactly as :func:`_raw_calibration` reads it. Silently merging two blocks  
that disagree is how you end up with bounds nobody wrote.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1508)</sub>

### `is_named_calibration`

```python
is_named_calibration(cfg) -> bool
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |

**returns** `bool`

True when `calibration` holds NAMED configs rather than bare parameters.

calibration: {optimalFiberLength: "0.5 3"}          -> flat  
calibration: {tight: {optimalFiberLength: "0.75 1.25"}, ...}   -> named

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1525)</sub>

### `calibration_configs`

```python
calibration_configs(cfg) -> Dict[str, Dict[str, str]]
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |

**returns** `Dict[str, Dict[str, str]]`

``{name: {parameter: "min max"}}`` for every calibration config.

A flat block comes back under the name ``'default'``. Parameter names are  
canonicalised, so `optimal_fiber_length` and `optimalFiberLength` are the  
same knob and both actually reach the XML.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1534)</sub>

### `calibration_name_for`

```python
calibration_name_for(cfg, iteration=None) -> Optional[str]
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |
| `iteration` | – | `None` |

**returns** `Optional[str]`

Which named calibration config `iteration` runs with.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1551)</sub>

### `resolve_calibration`

```python
resolve_calibration(cfg, iteration=None, strict=True) -> Dict[str, str]
```

| input | type | default |
|---|---|---|
| `cfg` | – | required |
| `iteration` | – | `None` |
| `strict` | – | `True` |

**returns** `Dict[str, str]`

The CEINMS calibration parameter bounds one iteration should run with.

Same shape and the same rules as :func:`resolve_emg_map`: an iteration  
names its config with ``calibration: <name>``, or the session names a  
``default_calibration``, or there is only one. Ambiguity raises.

Anything the config does not mention is left to settings.py — a config  
naming only ``optimalFiberLength`` overrides that bound and nothing else.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1567)</sub>

### `read_session_yaml`

```python
read_session_yaml(path) -> SessionSpec
```

| input | type | default |
|---|---|---|
| `path` | – | required |

**returns** `SessionSpec`

Parse a ``session.yaml`` into a :class:`SessionSpec`. ``path`` may be the  
yaml file or the session folder containing it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1710)</sub>

### `write_session_yaml`

```python
write_session_yaml(spec: SessionSpec, path=None) -> str
```

| input | type | default |
|---|---|---|
| `spec` | SessionSpec | required |
| `path` | – | `None` |

**returns** `str`

Serialise a :class:`SessionSpec` to ``session.yaml``. Returns the path.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L1904)</sub>

### `migrate_calibration_block`

```python
migrate_calibration_block(yaml_path, apply=True, backup=True)
```

| input | type | default |
|---|---|---|
| `yaml_path` | – | required |
| `apply` | – | `True` |
| `backup` | – | `True` |

Move a top-level ``calibration:`` / ``default_calibration:`` under ``ceinms:``.

-> ``(changed: bool, note: str)``. Idempotent: a file already nested (or  
with no calibration at all) reports ``(False, ...)`` and is not touched.

Done with the SURGICAL patcher, not a safe_load/dump round trip: these  
files are hand-written and full of comments explaining why a bound is what  
it is, and re-dumping would silently delete every one of them. The block's  
source text is lifted verbatim, re-indented one level, and re-inserted —  
so a migrated file diffs as a move, which is what it is.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/session/config.py#L2163)</sub>
