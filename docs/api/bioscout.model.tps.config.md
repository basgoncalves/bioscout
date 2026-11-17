# `bioscout.model.tps.config`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/config.py)

Configuration objects.

This module replaces the original ``paths_setup.py``, which hard-coded  
subject-specific values (mass ``89.9``, height ``1.80``, filenames like  
``orientation_Katya.mrk.json``) as module-level constants and created  
directories on import.

Here, all subject and path information lives in a dataclass that can be built  
from:  
  * a YAML file (standalone use), or  
  * a BioScout ``players.json`` entry + project layout (integrated use).

Nothing is created or read at import time. Directory creation is explicit via  
:meth:`PersonalisationConfig.ensure_dirs`.

## Contents

- class [`SubjectInfo`](#subjectinfo) — Person-specific anthropometry. Previously hard-coded strings.
- class [`PersonalisationConfig`](#personalisationconfig) — All inputs/outputs for one personalisation run.
  - [`PersonalisationConfig.resolved_model_name`](#personalisationconfigresolved_model_name) — Output file name, defaulting to ``<generic_model_stem>_tps.osim``.
  - [`PersonalisationConfig.personalised_model_path`](#personalisationconfigpersonalised_model_path) — 
  - [`PersonalisationConfig.ensure_dirs`](#personalisationconfigensure_dirs) — Create output directories. Explicit — never happens on import.
  - [`PersonalisationConfig.validate_inputs`](#personalisationconfigvalidate_inputs) — Fail fast with a clear message if required inputs are missing.
  - [`PersonalisationConfig.from_yaml`](#personalisationconfigfrom_yaml) — Build from a standalone YAML file (see ``examples/config.example.yaml``).
  - [`PersonalisationConfig.from_dict`](#personalisationconfigfrom_dict) — 
  - [`PersonalisationConfig.from_bioscout`](#personalisationconfigfrom_bioscout) — Build a config from a BioScout project layout.
  - [`PersonalisationConfig.to_dict`](#personalisationconfigto_dict) — 

<a id="subjectinfo"></a>

## class `SubjectInfo`

Person-specific anthropometry. Previously hard-coded strings.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/config.py#L27)</sub>

<a id="personalisationconfig"></a>

## class `PersonalisationConfig`

All inputs/outputs for one personalisation run.

Paths are :class:`pathlib.Path`. Relative paths are resolved against  
``project_root`` when set.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/config.py#L47)</sub>

<a id="personalisationconfigresolved_model_name"></a>

### `PersonalisationConfig.resolved_model_name`

```python
PersonalisationConfig.resolved_model_name() -> str
```

**returns** `str`

Output file name, defaulting to ``<generic_model_stem>_tps.osim``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/config.py#L120)</sub>

<a id="personalisationconfigpersonalised_model_path"></a>

### `PersonalisationConfig.personalised_model_path`

```python
PersonalisationConfig.personalised_model_path() -> Path
```

**returns** `Path`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/config.py#L128)</sub>

<a id="personalisationconfigensure_dirs"></a>

### `PersonalisationConfig.ensure_dirs`

```python
PersonalisationConfig.ensure_dirs() -> None
```

**returns** `None`

Create output directories. Explicit — never happens on import.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/config.py#L131)</sub>

<a id="personalisationconfigvalidate_inputs"></a>

### `PersonalisationConfig.validate_inputs`

```python
PersonalisationConfig.validate_inputs() -> None
```

**returns** `None`

Fail fast with a clear message if required inputs are missing.

``geometry_dir`` is deliberately NOT required: it is read only to warp  
bone meshes, which is optional (needs ``pyvista``) and already degrades  
to "keep the generic surfaces, log it" downstream. Requiring it here  
blocked the entire personalisation — joint centres, muscle paths,  
wraps — over cosmetic geometry.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/config.py#L136)</sub>

<a id="personalisationconfigfrom_yaml"></a>

### `PersonalisationConfig.from_yaml`

```python
PersonalisationConfig.from_yaml(path: str | Path) -> 'PersonalisationConfig'
```

| input | type | default |
|---|---|---|
| `path` | str \| Path | required |

**returns** `'PersonalisationConfig'`

Build from a standalone YAML file (see ``examples/config.example.yaml``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/config.py#L167)</sub>

<a id="personalisationconfigfrom_dict"></a>

### `PersonalisationConfig.from_dict`

```python
PersonalisationConfig.from_dict(raw: dict) -> 'PersonalisationConfig'
```

| input | type | default |
|---|---|---|
| `raw` | dict | required |

**returns** `'PersonalisationConfig'`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/config.py#L176)</sub>

<a id="personalisationconfigfrom_bioscout"></a>

### `PersonalisationConfig.from_bioscout`

```python
PersonalisationConfig.from_bioscout(
    player_id: str,
    project_root: str | Path,
    players_json: str | Path | None = None,
    trial: str | None = None,
    **overrides
) -> 'PersonalisationConfig'
```

| input | type | default |
|---|---|---|
| `player_id` | str | required |
| `project_root` | str \| Path | required |
| `players_json` | str \| Path \| None | `None` |
| `trial` | str \| None | `None` |
| `**overrides` | – | – |

**returns** `'PersonalisationConfig'`

Build a config from a BioScout project layout.

Mirrors BioScout conventions::

    <project_root>/players.json  
    <project_root>/models/generic/GPK/GPK_v4_016.osim  
    <project_root>/Models/Geometry/  
    <project_root>/setup_files/markers_and_bone_markers_in_bodies.xml  
    <project_root>/simulations/<player_id>/mri/landmarks.mrk.json  
    <project_root>/simulations/<player_id>/<trial>/scaled_model.osim

Subject anthropometry is read from ``players.json`` instead of being  
hard-coded — the central fix versus the original pipeline.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/config.py#L193)</sub>

<a id="personalisationconfigto_dict"></a>

### `PersonalisationConfig.to_dict`

```python
PersonalisationConfig.to_dict() -> dict
```

**returns** `dict`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/tps/config.py#L246)</sub>
