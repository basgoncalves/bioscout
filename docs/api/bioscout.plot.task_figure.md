# `bioscout.plot.task_figure`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/task_figure.py)

Vertical trial figures with the TASK on top.

Every per-trial figure with a handful of time-series panels uses the same  
layout, so they can be read against each other:

    row 0   the posed skeleton (both legs) at the foot-strike / foot-off events,  
            each pose centred (on the pelvis) above its event line, with the GRF  
            of each loaded plate drawn as an arrow from its COP  
    row 1   vertical GRF of both feet, stance shaded, events dashed and named  
    rows    the figure's own panels, one per row, sharing the time axis, with  
            the same event lines

    from bioscout.plot.task_figure import TaskStrip  
    ts = TaskStrip(trial_folder)                      # 3_iterations/<it>/<trial>  
    ts.figure([dict(draw=lambda ax: ax.plot(...), title="..."), ...],  
              out="...png", legend=[Line2D handles])

Without a model (session.yaml -> iteration ``model_scaled``) or its Geometry  
the pose row is left out; without ``2_experimental/<trial>/grf.mot`` the GRF  
row is left out. The panels are always drawn. Used by kinematics_moments,  
residuals, _ik_marker_errors_plot, muscle_moments_<side>, muscle_groups and  
jrf_<origin> and emg_processing (bioscout.plot.emg_figure); figures with many  
panels (inverse_dynamics, muscle_individual) keep their grids.

## Contents

- class [`TaskStrip`](#taskstrip) — The task context of one trial (window, GRF, events, poses), drawn on top of any stack of time-series panels by :meth:`figure`.
  - [`TaskStrip.figure`](#taskstripfigure) — Draw ``rows`` under the pose strip and the vGRF row and save ``out``.
- [`read_sto`](#read_sto) — (DataFrame, in_degrees) of an OpenSim .sto/.mot.
- [`model_for`](#model_for) — The iteration's scaled model, from session.yaml (bioscout >= 3.0 layout).
- [`events_from_grf`](#events_from_grf) — [(name, time)] foot strike / foot off of each foot inside [t0, t1].
- [`grf_vectors`](#grf_vectors) — (time, [(side, F (n,3) N, COP (n,3) m), ...]) from grf.mot, ground frame.
- [`strip_for`](#strip_for) — TaskStrip or None (never raises) -- for figure code with a grid fallback.

<a id="taskstrip"></a>

## class `TaskStrip`

```python
TaskStrip(trial, t_range=None, poses=True, n_min_poses=3, log=print)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |
| `t_range` | – | `None` |
| `poses` | – | `True` |
| `n_min_poses` | – | `3` |
| `log` | – | `print` |

The task context of one trial (window, GRF, events, poses), drawn on top  
of any stack of time-series panels by :meth:`figure`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/task_figure.py#L165)</sub>

<a id="taskstripfigure"></a>

### `TaskStrip.figure`

```python
TaskStrip.figure(
    rows,
    out,
    legend=None,
    width=10.5,
    row_height=1.45,
    xlabel='time (s)',
    grf_row=True,
    dpi=150,
    legend_ncol=None,
    legend_loc='bottom'
)
```

| input | type | default |
|---|---|---|
| `rows` | – | required |
| `out` | – | required |
| `legend` | – | `None` |
| `width` | – | `10.5` |
| `row_height` | – | `1.45` |
| `xlabel` | – | `'time (s)'` |
| `grf_row` | – | `True` |
| `dpi` | – | `150` |
| `legend_ncol` | – | `None` |
| `legend_loc` | – | `'bottom'` |

Draw ``rows`` under the pose strip and the vGRF row and save ``out``.

rows    list of dicts: ``draw`` (callable(ax) -> None), optional  
        ``title`` (left-aligned), ``title_color``, ``height`` (relative,  
        default 1) and ``ylabel``. A row's draw() may add a twin axis.  
legend  list of matplotlib handles for a shared legend at the bottom,  
        or -- ``legend_loc="top"`` -- right-aligned just above the first  
        data row (under the vGRF row), without the GRF-at-COP entry.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/task_figure.py#L218)</sub>

### `read_sto`

```python
read_sto(path)
```

| input | type | default |
|---|---|---|
| `path` | – | required |

(DataFrame, in_degrees) of an OpenSim .sto/.mot.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/task_figure.py#L36)</sub>

### `model_for`

```python
model_for(trial: Path)
```

| input | type | default |
|---|---|---|
| `trial` | Path | required |

The iteration's scaled model, from session.yaml (bioscout >= 3.0 layout).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/task_figure.py#L46)</sub>

### `events_from_grf`

```python
events_from_grf(tg, vy_by_side, t0, t1, thr=20.0)
```

| input | type | default |
|---|---|---|
| `tg` | – | required |
| `vy_by_side` | – | required |
| `t0` | – | required |
| `t1` | – | required |
| `thr` | – | `20.0` |

[(name, time)] foot strike / foot off of each foot inside [t0, t1].

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/task_figure.py#L70)</sub>

### `grf_vectors`

```python
grf_vectors(trial: Path)
```

| input | type | default |
|---|---|---|
| `trial` | Path | required |

(time, [(side, F (n,3) N, COP (n,3) m), ...]) from grf.mot, ground frame.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/task_figure.py#L84)</sub>

### `strip_for`

```python
strip_for(trial, t_range=None, log=print)
```

| input | type | default |
|---|---|---|
| `trial` | – | required |
| `t_range` | – | `None` |
| `log` | – | `print` |

TaskStrip or None (never raises) -- for figure code with a grid fallback.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/task_figure.py#L347)</sub>
