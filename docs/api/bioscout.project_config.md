# `bioscout.project_config`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/project_config.py)

bioscout.project_config — lab facts as data (docs/IMPLEMENTATIONS §2.9).

Steps 1 + 2 of retiring the copied per-project ``settings.py``:

1. **The overlay** (:func:`overlay`, called once from ``utils/__init__``):  
   a small declarative ``project.yaml`` at the project root is applied ON TOP  
   of whatever settings module resolved — the project's legacy ``settings.py``  
   if it still exists, else bioscout's bundled template. The precedence every  
   consumer already sees through ``utils.settings`` therefore becomes::

       session.yaml  ->  project.yaml  ->  settings.py (legacy)  ->  bioscout defaults

   Nothing breaks on day one: no project.yaml means nothing changes (plus one  
   deprecation note when a legacy settings.py is carrying the load).

2. **The extractor** (:func:`init_project_yaml`, ``bioscout init --from-settings``):  
   writes project.yaml FROM an existing settings.py — the data attributes of  
   ``BatchSettings``/``CEINMSSettings`` that DIFFER from bioscout's bundled  
   defaults. Only deviations are written: the file stays short because the  
   defaults live in the package, versioned once.

Schema (version 1) — attribute names are used VERBATIM, which is what makes  
the extractor's round-trip exact::

    schema: 1  
    name: FAIS  
    log_type: minimal              # -> settings.LOG_TYPE  
    batch:                         # -> attributes set on BatchSettings  
      emg_sampling_freq: 2000  
      MUSCLE_GROUPS: {...}  
    ceinms:                        # -> attributes set on CEINMSSettings  
      calibration_trial_names: [SquatA1]  
    plot:                          # -> attributes set on PlottingSettings  
      dpi: 300  
    summary:                       # -> attributes set on SummarySettings  
      npts: 101

Deliberately NOT written by the extractor (they are not lab facts):  
run selection (``SUBJECTS``, ``sessions``, ``trial_list``, ``RUN_*``/``DO_*``  
flags, ``replace_existing``) — that belongs at the call site; and paths  
(``PROJECT_ROOT``, ``MODELS_DIR``, ...) — the folder convention IS the  
configuration.

Import-time dependencies: standard library only. PyYAML is imported lazily  
inside the functions that parse/write, so this module loads (and the rest of  
``bioscout.utils`` with it) even where yaml is missing.

## Contents

- [`find_project_yaml`](#find_project_yaml) — Path of the nearest ``project.yaml`` at or above ``start`` (default: cwd), or None. Walks at most ``_SEARCH_DEPTH`` levels so a stray file in ``C:\`` never captures every project on the machine.
- [`apply`](#apply) — Set ``data``'s sections onto ``base`` (a settings module or namespace). Returns the number of attributes applied.
- [`overlay`](#overlay) — Apply the nearest project.yaml on top of ``settings_obj`` and return the result. With no project.yaml this is a near no-op (one deprecation note when a legacy settings.py is the active configuration). Never raises: configuration loading must not be the thing that stops a run.
- [`extract`](#extract) — The project.yaml ``data`` dict for ``settings_module``: lab facts that DIFFER from ``baseline`` (default: bioscout's bundled template; with no baseline importable, every fact is included).
- [`init_project_yaml`](#init_project_yaml) — ``bioscout init --from-settings``: write ``<project_dir>/project.yaml`` from the project's settings.py. Returns a process exit code (0 written).

### `find_project_yaml`

```python
find_project_yaml(start=None)
```

| input | type | default |
|---|---|---|
| `start` | – | `None` |

Path of the nearest ``project.yaml`` at or above ``start`` (default:  
cwd), or None. Walks at most ``_SEARCH_DEPTH`` levels so a stray file in  
``C:\`` never captures every project on the machine.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/project_config.py#L89)</sub>

### `apply`

```python
apply(base, data, source='project.yaml')
```

| input | type | default |
|---|---|---|
| `base` | – | required |
| `data` | – | required |
| `source` | – | `'project.yaml'` |

Set ``data``'s sections onto ``base`` (a settings module or namespace).  
Returns the number of attributes applied.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/project_config.py#L134)</sub>

### `overlay`

```python
overlay(settings_obj, start=None)
```

| input | type | default |
|---|---|---|
| `settings_obj` | – | required |
| `start` | – | `None` |

Apply the nearest project.yaml on top of ``settings_obj`` and return  
the result. With no project.yaml this is a near no-op (one deprecation  
note when a legacy settings.py is the active configuration). Never raises:  
configuration loading must not be the thing that stops a run.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/project_config.py#L251)</sub>

### `extract`

```python
extract(settings_module, baseline=None)
```

| input | type | default |
|---|---|---|
| `settings_module` | – | required |
| `baseline` | – | `None` |

The project.yaml ``data`` dict for ``settings_module``: lab facts that  
DIFFER from ``baseline`` (default: bioscout's bundled template; with no  
baseline importable, every fact is included).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/project_config.py#L332)</sub>

### `init_project_yaml`

```python
init_project_yaml(project_dir='.', force=False, baseline=None)
```

| input | type | default |
|---|---|---|
| `project_dir` | – | `'.'` |
| `force` | – | `False` |
| `baseline` | – | `None` |

``bioscout init --from-settings``: write ``<project_dir>/project.yaml`` from the  
project's settings.py. Returns a process exit code (0 written).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/project_config.py#L367)</sub>
