# `bioscout.model.inspect.fl_fv_surface`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_surface.py)

Fibre operating point on the Hill force-length-velocity surface.

Generic, project-agnostic drawing code. Callers hand over already-reduced  
traces; nothing in here knows about sessions, tasks or models.

    from bioscout.model.inspect.fl_fv_surface import plot_fl_fv_surface

    panels = [dict(title="Squat 35kg", series=[  
        dict(name="cateli", ls="-",  marker="o",  
             data={"Vasti": dict(l=..., v=..., fn=..., wpos=.., wneg=..)}),  
        dict(name="gpk",    ls="--", marker="X", data={...}),  
    ])]  
    plot_fl_fv_surface(panels, groups, colors, "out.png")

WHAT THE SURFACE IS  
    f(l~, v~) = f_L(l~) . f_V(v~) at full activation, Thelen (2003) defaults --  
    the MODEL's capacity, not any one subject's. Height = the fraction of peak  
    isometric force a fibre can make at that normalised length and velocity.  
    Negative v~ is SHORTENING (OpenSim convention) and is plotted to the LEFT.

WHAT A TRACE IS  
    One muscle group over one movement cycle, force-weighted across its heads.  
    The marker sits at that group's instant of PEAK force.

## Contents

- [`hill_value`](#hill_value) — f_L(l~) . f_V(v~) at full activation -- Thelen 2003 defaults.
- [`hill_surface`](#hill_surface) — (l, v, L, V, S) -- the multiplier on a (l~, v~) grid.
- [`mask_out_of_domain`](#mask_out_of_domain) — NaN out samples off the plotted sheet -- a 3D axes does NOT clip.
- [`osim_muscle_params`](#osim_muscle_params) — {muscle: dict(f0, lopt, lts, pennation)} out of an .osim.
- [`rigid_tendon_states`](#rigid_tendon_states) — (l~, v~) from muscle-tendon length under a RIGID tendon assumption.
- [`force_weights`](#force_weights) — (weights, total force) for the heads of one group, per sample.
- [`weighted_group_trace`](#weighted_group_trace) — Force-weighted (l~, v~) of one group + its normalised force.
- [`finish_trace`](#finish_trace) — Mask, find the peak-force instant, and package one trace.
- [`plot_fl_fv_surface`](#plot_fl_fv_surface) — Draw a grid of 3D panels -- one ROW per algorithm, one COLUMN per task.

### `hill_value`

```python
hill_value(L, V, kshape=0.45, af=0.25, flen=1.4)
```

| input | type | default |
|---|---|---|
| `L` | – | required |
| `V` | – | required |
| `kshape` | – | `0.45` |
| `af` | – | `0.25` |
| `flen` | – | `1.4` |

f_L(l~) . f_V(v~) at full activation -- Thelen 2003 defaults.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_surface.py#L49)</sub>

### `hill_surface`

```python
hill_surface(nl=161, nv=161)
```

| input | type | default |
|---|---|---|
| `nl` | – | `161` |
| `nv` | – | `161` |

(l, v, L, V, S) -- the multiplier on a (l~, v~) grid.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_surface.py#L62)</sub>

### `mask_out_of_domain`

```python
mask_out_of_domain(L, V, where='')
```

| input | type | default |
|---|---|---|
| `L` | – | required |
| `V` | – | required |
| `where` | – | `''` |

NaN out samples off the plotted sheet -- a 3D axes does NOT clip.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_surface.py#L70)</sub>

### `osim_muscle_params`

```python
osim_muscle_params(model_path)
```

| input | type | default |
|---|---|---|
| `model_path` | – | required |

{muscle: dict(f0, lopt, lts, pennation)} out of an .osim.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_surface.py#L87)</sub>

### `rigid_tendon_states`

```python
rigid_tendon_states(t, lmt, par, vmax=VMAX_LOPT_PER_S)
```

| input | type | default |
|---|---|---|
| `t` | – | required |
| `lmt` | – | required |
| `par` | – | required |
| `vmax` | – | `VMAX_LOPT_PER_S` |

(l~, v~) from muscle-tendon length under a RIGID tendon assumption.

l_fibre = (l_MT - l_TS) / cos(pennation);  l~ = l_fibre / l_opt  
v~      = d(l~)/dt / vmax          (vmax in optimal fibre lengths per second)

Needed wherever OpenSim's MuscleAnalysis fibre output is degenerate (a  
constant fibre length means it never solved fibre equilibrium, and its  
velocity column is then the derivative of a flat line).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_surface.py#L109)</sub>

### `force_weights`

```python
force_weights(F)
```

| input | type | default |
|---|---|---|
| `F` | – | required |

(weights, total force) for the heads of one group, per sample.

Public so a caller can average a FURTHER per-head signal -- activation, say  
-- with exactly the weights the fibre state was averaged with.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_surface.py#L131)</sub>

### `weighted_group_trace`

```python
weighted_group_trace(F, L, V, F0)
```

| input | type | default |
|---|---|---|
| `F` | – | required |
| `L` | – | required |
| `V` | – | required |
| `F0` | – | required |

Force-weighted (l~, v~) of one group + its normalised force.

F/L/V are (n_heads, n_samples); F0 the summed peak isometric force.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_surface.py#L143)</sub>

### `finish_trace`

```python
finish_trace(l, v, fn, wpos=np.nan, wneg=np.nan, where='', act=None, **extra)
```

| input | type | default |
|---|---|---|
| `l` | – | required |
| `v` | – | required |
| `fn` | – | required |
| `wpos` | – | `np.nan` |
| `wneg` | – | `np.nan` |
| `where` | – | `''` |
| `act` | – | `None` |
| `**extra` | – | – |

Mask, find the peak-force instant, and package one trace.

Anything passed as **extra rides along on the trace -- e.g. `peak_bw=` for  
a second force scale the numbers block can rank and print.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_surface.py#L154)</sub>

### `plot_fl_fv_surface`

```python
plot_fl_fv_surface(
    rows,
    groups,
    colors,
    out_path,
    title='',
    footnote='',
    elev=26.0,
    azim=-122.0,
    dpi=200,
    panel_width=4.9,
    icon_for_panel=None,
    icon_h_in=0.62,
    header_icon=None,
    task_icon_scale=1.5,
    annot_for_panel=None,
    columns=DEFAULT_COLUMNS,
    rank_by=None,
    color_by='group',
    flag_pct=10.0,
    rows_are='group',
    style_by=None,
    legend_handles=None,
    table_fontsize=8.0,
    act_scale=True,
    save_pdf=False
)
```

| input | type | default |
|---|---|---|
| `rows` | – | required |
| `groups` | – | required |
| `colors` | – | required |
| `out_path` | – | required |
| `title` | – | `''` |
| `footnote` | – | `''` |
| `elev` | – | `26.0` |
| `azim` | – | `-122.0` |
| `dpi` | – | `200` |
| `panel_width` | – | `4.9` |
| `icon_for_panel` | – | `None` |
| `icon_h_in` | – | `0.62` |
| `header_icon` | – | `None` |
| `task_icon_scale` | – | `1.5` |
| `annot_for_panel` | – | `None` |
| `columns` | – | `DEFAULT_COLUMNS` |
| `rank_by` | – | `None` |
| `color_by` | – | `'group'` |
| `flag_pct` | – | `10.0` |
| `rows_are` | – | `'group'` |
| `style_by` | – | `None` |
| `legend_handles` | – | `None` |
| `table_fontsize` | – | `8.0` |
| `act_scale` | – | `True` |
| `save_pdf` | – | `False` |

Draw a grid of 3D panels -- one ROW per algorithm, one COLUMN per task.

rows            [dict(panels=[...], corner_icon=path|array)]. A bare list of  
                panels (no `panels` key) is taken as a single row, so the  
                one-row call still works unchanged.  
panels          [dict(title, series=[dict(name, ls, marker, data={group: trace})])]  
groups          ordered group names; colors {group: colour}  
title           figure heading, drawn top-left beside `header_icon` (or  
                centred if there is no icon); "" draws none  
header_icon     one pictogram (path or array) for the figure's top-left --  
                the muscle badge when a figure is one muscle group  
icon_for_panel  f(panel title) -> a pictogram path or array, above the TOP  
                row's panels only -- the columns are the same task throughout  
corner_icon     per row: the badge at the left of that row  
label           per row: the caption printed under that row's badge  
style_by        which dimension carries the STROKE; defaults to whichever  
                `color_by` does not use, but may be the same as `color_by`  
color_by        "group" -> colour is the muscle and stroke is the series;  
                "series" -> colour is the series (each needs a `color`) and  
                stroke is the muscle  
columns         [dict(key, head, fmt, cw)] for the numbers table  
rank_by         trace key to sort the numbers block by, largest first  
flag_pct        mark a cell `*` and bold it when the series disagree by  
                more than this % of their mean, `**` past 2.5x it; 0 off  
rows_are        "group" -> a table row is a muscle; "series" -> a table row  
                is a model, in its own colour (use with one muscle a figure)  
legend_handles  replace the auto identity block of the legend (use when one  
                series is a model x algorithm pair and the two read apart)  
act_scale       draw the activation key at the right of the panels

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/fl_fv_surface.py#L716)</sub>
