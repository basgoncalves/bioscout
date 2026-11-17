# `bioscout.model.opensim_base`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/opensim_base.py)

Low-level OpenSim wrapper plumbing shared by ``model/`` and ``simulate/``.

Loading a model, reading its assembly accuracy, and silencing OpenSim's logger  
are fundamentally about the MODEL, so they live here; ``bioscout.simulate``  
imports from this module and nothing here imports back from it.

Split out of the old ``bioscout/utils/openSim.py`` (docs/RESTRUCTURE_PLAN.md,  
stage 6) -- the code is unchanged, only its address.

## Contents

- [`load_model`](#load_model) — opensim.Model(path) with a relaxed assembly accuracy applied (see _assembly_accuracy). Use everywhere a model is loaded for a tool run.
- [`terminal_warnings`](#terminal_warnings) — Set OpenSim terminal warnings on or off.

### `load_model`

```python
load_model(path, accuracy=None)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `accuracy` | – | `None` |

opensim.Model(path) with a relaxed assembly accuracy applied (see  
_assembly_accuracy). Use everywhere a model is loaded for a tool run.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/opensim_base.py#L123)</sub>

### `terminal_warnings`

```python
terminal_warnings(mode='off')
```

| input | type | default |
|---|---|---|
| `mode` | – | `'off'` |

Set OpenSim terminal warnings on or off.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/opensim_base.py#L274)</sub>
