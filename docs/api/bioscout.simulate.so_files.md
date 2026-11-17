# `bioscout.simulate.so_files`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_files.py)

Static-optimisation output names, in ONE place.

The SO folder (``<trial>/static_optimisation/``) already says what its files  
are, so they carry no ``SO_`` prefix (changed 2026-10-01):

    StaticOptimization_force.sto        was SO_StaticOptimization_force.sto  
    StaticOptimization_activation.sto   was SO_StaticOptimization_activation.sto  
    StaticOptimization_controls.xml     was SO_StaticOptimization_controls.xml  
    muscle_individual.png               was SO_results.png  
    muscle_groups.png                   was SO_muscle_groups.png  
    muscle_moments_<side>.png / muscle_moments.csv  
                                        replace SO_reserves_inspection.png / .csv  
                                        (task layout, bioscout.plot.muscle_moments_task;  
                                        the grid muscle_moments.png and  
                                        muscle_moments_task_<side>.png are gone)

OpenSim's AnalyzeTool still writes ``<toolname>_StaticOptimization_*``; the SO  
stage renames them straight after the run (:func:`migrate_dir`). Folders from  
before the change are renamed the first time a trial is opened, and every reader  
goes through :func:`pick`, which falls back to the legacy name, so old sessions  
keep working without a migration step. :func:`migrate` renames a whole tree.

Light on purpose: numpy/pandas/matplotlib only, no OpenSim.

## Contents

- [`pick`](#pick) — ``path`` if it exists, else its legacy/current twin if THAT exists, else ``path``.
- [`migrate_dir`](#migrate_dir) — Rename legacy outputs in ONE static_optimisation folder to the current names.
- [`migrate`](#migrate) — migrate_dir() on every ``static_optimisation`` folder under ``root``.
- [`moment_table`](#moment_table) — Per reserved coordinate: ID range, peak reserve, RMSE(muscles, ID) -- the last two also in % of the ID moment's RANGE over the window (never of its instantaneous value, which blows up at every zero crossing; the old SO_reserves_inspection read a 0.5 N·m reserve as 476 %). SO enforces ID = muscles + reserve at every frame, so RMSE(muscles, ID) = RMS(reserve). Same numbers as bioscout.plot.summary's ``moment_RMSE_pct``.
- [`plot_muscle_moments`](#plot_muscle_moments) — ID moment vs the moment the muscles carry, per reserved coordinate.
- [`tidy`](#tidy) — migrate() a tree (removing obsolete outputs), then (re)draw muscle_moments_<side>.png (+ .csv) in every static_optimisation folder that has a force file and an ID next door.

### `pick`

```python
pick(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

``path`` if it exists, else its legacy/current twin if THAT exists, else ``path``.

Use for every READ of an SO output, so sessions written before the rename  
still resolve. Writers use the current names.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_files.py#L51)</sub>

### `migrate_dir`

```python
migrate_dir(so_dir, remove_obsolete=False, dry=False)
```

| input | type | default |
|---|---|---|
| `so_dir` | – | required |
| `remove_obsolete` | – | `False` |
| `dry` | – | `False` |

Rename legacy outputs in ONE static_optimisation folder to the current names.

A legacy file replaces a current one only if it is newer (OpenSim has just  
written it); an older legacy file next to a current one is stale and is  
removed. Returns [(old, new), ...].

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_files.py#L67)</sub>

### `migrate`

```python
migrate(root, remove_obsolete=False, dry=False, log=print)
```

| input | type | default |
|---|---|---|
| `root` | – | required |
| `remove_obsolete` | – | `False` |
| `dry` | – | `False` |
| `log` | – | `print` |

migrate_dir() on every ``static_optimisation`` folder under ``root``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_files.py#L104)</sub>

### `moment_table`

```python
moment_table(so_forces, id_file, t_range=None, order=None)
```

| input | type | default |
|---|---|---|
| `so_forces` | – | required |
| `id_file` | – | required |
| `t_range` | – | `None` |
| `order` | – | `None` |

Per reserved coordinate: ID range, peak reserve, RMSE(muscles, ID) -- the  
last two also in % of the ID moment's RANGE over the window (never of its  
instantaneous value, which blows up at every zero crossing; the old  
SO_reserves_inspection read a 0.5 N·m reserve as 476 %). SO enforces  
ID = muscles + reserve at every frame, so RMSE(muscles, ID) = RMS(reserve).  
Same numbers as bioscout.plot.summary's ``moment_RMSE_pct``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_files.py#L126)</sub>

### `plot_muscle_moments`

```python
plot_muscle_moments(so_forces, id_file, out_dir=None, t_range=None, order=None, log=print)
```

| input | type | default |
|---|---|---|
| `so_forces` | – | required |
| `id_file` | – | required |
| `out_dir` | – | `None` |
| `t_range` | – | `None` |
| `order` | – | `None` |
| `log` | – | `print` |

ID moment vs the moment the muscles carry, per reserved coordinate.

Writes ``muscle_moments.csv`` (:func:`moment_table`) and, per leg,  
``muscle_moments_<side>.png`` in the vertical task layout (poses + vGRF on  
top, one row per coordinate; bioscout.plot.muscle_moments_task) to  
``out_dir`` (default: the force file's folder). Returns (fig_paths, rows).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_files.py#L163)</sub>

### `tidy`

```python
tidy(root, plots=True, log=print)
```

| input | type | default |
|---|---|---|
| `root` | – | required |
| `plots` | – | `True` |
| `log` | – | `print` |

migrate() a tree (removing obsolete outputs), then (re)draw muscle_moments_<side>.png  
(+ .csv) in every static_optimisation folder that has a force file and an ID next door.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/simulate/so_files.py#L198)</sub>
