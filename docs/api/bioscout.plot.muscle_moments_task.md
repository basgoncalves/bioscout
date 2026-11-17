# `bioscout.plot.muscle_moments_task`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/muscle_moments_task.py)

Muscle vs ID moments in the context of the task: poses, GRF and joint angles.

``static_optimisation/muscle_moments_<side>.png`` -- one figure per leg, in the  
vertical task layout of :mod:`bioscout.plot.task_figure` (poses and vGRF on  
top), then one row per reserved coordinate of that leg:

    stacked muscle-group moments (force x moment arm, groups/colours as in  
    contributions_so.png) + reserve (hatched), summing to the ID moment (black),  
    in N·m, left axis; joint angle (grey dotted, right axis)  
    title: RMSE(muscles, ID) and peak |reserve|, both in % of the ID moment's  
    RANGE (the numbers in muscle_moments.csv); green < 5 %, orange < 10 %, red

Trial data only: the point is to see WHEN in the task each reserve works.

    python -m bioscout.plot.muscle_moments_task <trial folder> [--sides r l]

Called after SO by ``Analyse.plot_muscle_moments`` (via  
``bioscout.simulate.so_files.plot_muscle_moments``).

## Contents

- [`muscle_moments`](#muscle_moments) — Draw muscle_moments_<side>.png for ``trial`` (a 3_iterations/<it>/<trial> folder). Returns the list of figure paths.
- [`main`](#main) — 

### `muscle_moments`

```python
muscle_moments(trial, sides=None, out_dir=None, log=print, strip=None)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |
| `sides` | – | `None` |
| `out_dir` | – | `None` |
| `log` | – | `print` |
| `strip` | – | `None` |

Draw muscle_moments_<side>.png for ``trial`` (a 3_iterations/<it>/<trial>  
folder). Returns the list of figure paths.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/muscle_moments_task.py#L82)</sub>

### `main`

```python
main(argv=None)
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/muscle_moments_task.py#L186)</sub>
