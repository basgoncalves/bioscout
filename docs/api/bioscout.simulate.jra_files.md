# `bioscout.simulate.jra_files`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/jra_files.py)

Joint-reaction (contact-force) output names, in ONE place.

The folder (``<trial>/joint_contact_forces/``) already says what its files are,  
so they are named by the ORIGIN of the muscle forces only (changed 2026-10-01):

    output_so.sto                       was Analyse_JRA_ReactionLoads_SO.sto  
    output_ceinms.sto                   was Analyse_JRA_ReactionLoads_CEINMS.sto  
    output_ml.sto                       was Analyse_JRA_ReactionLoads_ML.sto  
    jrf_so.png                          was JRA_SO.png (now the vertical task layout)  
    jrf_so_vs_ceinms.png                was JRA_SO_vs_CEINMS.png  
    jrf_<origin>_coverage_<plane>.png   was JRA_<ORIGIN>_coverage_<plane>.png

Every reader goes through :func:`pick`, which falls back to the legacy name, so  
old sessions keep working; :func:`migrate_dir` / :func:`migrate` rename them.  
Light on purpose: no OpenSim, no matplotlib.

## Contents

- [`output`](#output) — ``output_<origin>.sto`` (origin: SO, CEINMS, ML, ...).
- [`figure`](#figure) — ``jrf_so.png``, ``jrf_so_vs_ceinms.png``, ...
- [`coverage`](#coverage) — 
- [`current_name`](#current_name) — Current name for a legacy file name, or None.
- [`legacy_name`](#legacy_name) — Legacy name for a current OUTPUT name (``output_so.sto`` -> ``Analyse_JRA_ReactionLoads_SO.sto``), or None.
- [`pick`](#pick) — ``path`` if it exists, else its legacy/current twin if THAT exists, else ``path``. Use for every READ of a JRA output.
- [`migrate_dir`](#migrate_dir) — Rename legacy outputs in ONE joint_contact_forces folder. A legacy file replaces a current one only if it is newer; an older legacy copy is stale and removed. Returns [(old, new), ...].
- [`migrate`](#migrate) — migrate_dir() on every ``joint_contact_forces`` folder under ``root``.

### `output`

```python
output(origin)
```

| input | type | default |
|---|---|---|
| `origin` | – | required |

``output_<origin>.sto`` (origin: SO, CEINMS, ML, ...).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/jra_files.py#L25)</sub>

### `figure`

```python
figure(*origins)
```

| input | type | default |
|---|---|---|
| `*origins` | – | – |

``jrf_so.png``, ``jrf_so_vs_ceinms.png``, ...

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/jra_files.py#L30)</sub>

### `coverage`

```python
coverage(origin, plane)
```

| input | type | default |
|---|---|---|
| `origin` | – | required |
| `plane` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/jra_files.py#L35)</sub>

### `current_name`

```python
current_name(legacy)
```

| input | type | default |
|---|---|---|
| `legacy` | – | required |

Current name for a legacy file name, or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/jra_files.py#L51)</sub>

### `legacy_name`

```python
legacy_name(current)
```

| input | type | default |
|---|---|---|
| `current` | – | required |

Legacy name for a current OUTPUT name (``output_so.sto`` ->  
``Analyse_JRA_ReactionLoads_SO.sto``), or None.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/jra_files.py#L60)</sub>

### `pick`

```python
pick(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

``path`` if it exists, else its legacy/current twin if THAT exists, else  
``path``. Use for every READ of a JRA output.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/jra_files.py#L67)</sub>

### `migrate_dir`

```python
migrate_dir(jcf_dir, dry=False)
```

| input | type | default |
|---|---|---|
| `jcf_dir` | – | required |
| `dry` | – | `False` |

Rename legacy outputs in ONE joint_contact_forces folder. A legacy file  
replaces a current one only if it is newer; an older legacy copy is stale and  
removed. Returns [(old, new), ...].

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/jra_files.py#L80)</sub>

### `migrate`

```python
migrate(root, dry=False, log=print)
```

| input | type | default |
|---|---|---|
| `root` | – | required |
| `dry` | – | `False` |
| `log` | – | `print` |

migrate_dir() on every ``joint_contact_forces`` folder under ``root``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/jra_files.py#L106)</sub>
