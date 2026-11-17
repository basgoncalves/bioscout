# `bioscout.model.inspect.paths`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/paths.py)

Locations of the literature data bundled with this package, and of the  
per-model report folders written next to a model on disk.

Keeping these here (rather than hard-coding ``"validation/..."`` relative to the  
current working directory, as the standalone scripts do) lets the module be  
imported and used from anywhere inside bioscout while still finding its data.

Two different things are called "validation" in this file and they are NOT  
related:

* ``PKG_DIR/validation/`` -- the literature CSVs shipped INSIDE the package.  
* ``validation_dir(model)`` -- ``<model_dir>/validation/<model_stem>/``, the  
  place every report ABOUT a model is written on the user's disk.

## Contents

- [`validation_dir`](#validation_dir) — Return the folder that reports about ``model_path`` should be written to.
- [`is_report_dir`](#is_report_dir) — True if ``name`` is a report folder rather than anything to scan for models.
- [`resolve_literature_csv`](#resolve_literature_csv) — Return an existing moment-arm CSV path.

### `validation_dir`

```python
validation_dir(model_path, kind=None, out=None, base=None)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |
| `kind` | – | `None` |
| `out` | – | `None` |
| `base` | – | `None` |

Return the folder that reports about ``model_path`` should be written to.

``<model_dir>/validation/<model_stem>/[<kind>/]``

So an iteration folder holds only models plus one ``validation/`` folder,  
and every report about a given model sits together under that model's name::

    cateli/  
        scaled.osim  
        scaled_opt_N10.osim  
        scaled_opt_N10_mvicx3.00.osim  
        validation/  
            scaled_opt_N10/                    <- moment arms, fibre, strength  
            scaled_opt_N10_mvicx3.00/  
                moment_arm_change/             <- kind="moment_arm_change"

Before 2.0.0b11 these were ``muscle_inspect_<stem>/`` and  
``moment_arm_change_<stem>/`` directly in the iteration folder. Old folders  
are not read by anything, so there is no fallback -- re-run the report.

  
**Parameters**

model_path : str  
    The model the report is about. Only its folder and stem are used; the  
    file does not have to exist.  
kind : str, optional  
    Sub-folder for a specific report type, e.g. ``"moment_arm_change"``.  
    Omit for the standard ``muscle_inspect`` outputs.  
out : str, optional  
    An explicit user-supplied output folder. When given it is returned  
    as-is (made absolute against the cwd), so ``--out`` always wins.  
base : str, optional  
    Override the model stem, for callers that already computed it.

  
**Returns**

str  
    Absolute path. The folder is NOT created -- callers do that.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/paths.py#L46)</sub>

### `is_report_dir`

```python
is_report_dir(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

True if ``name`` is a report folder rather than anything to scan for models.

Accepts a name or a path; matches the current ``validation/`` folder and the  
pre-2.0.0b11 ``muscle_inspect_*`` / ``moment_arm_change_*`` folders that may  
still be lying around in old sessions.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/paths.py#L97)</sub>

### `resolve_literature_csv`

```python
resolve_literature_csv(path=None)
```

| input | type | default |
|---|---|---|
| `path` | – | `None` |

Return an existing moment-arm CSV path.

Prefers an explicit ``path`` (absolute, or relative to cwd) when it exists;  
otherwise falls back to the CSV bundled with the package.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/paths.py#L108)</sub>
