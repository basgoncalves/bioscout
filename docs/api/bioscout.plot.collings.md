# `bioscout.plot.collings`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py)

Collings-style rank-shift figures for muscle force.

    python -m bioscout --collings <session path>  
    python -m bioscout --collings <session path> --skip gpk_mri lernagopal  
    python -m bioscout --collings <session path> --trial Walking_03 --metric impulse

After Collings et al. (2025), Med Sci Sports Exerc — "Comparison of exercise  
ranking from highest to lowest based on peak normalized muscle force and peak  
normalized EMG amplitude". Their figure ranks a list of exercises twice, once  
by each measure, and draws a connector between the two rankings so the  
DISAGREEMENT is the thing you read, not either ranking on its own.

WHAT IS BORROWED, AND WHAT IS NOT  
    Borrowed: the paired ranked-bar layout, the connectors, and — the part that  
    makes it legible — COLOUR ANCHORED ON THE FIRST COLUMN. Each item is  
    coloured by its rank in the leftmost panel and keeps that colour in every  
    panel to its right. A dark bar sitting low on the right is then instantly  
    "this one dropped", with no need to trace a line.

    Not borrowed: their columns are two MEASURES of the same exercises (force  
    vs EMG) on one model. Here the columns are usually MODELS or CALIBRATION  
    VARIANTS of the same muscles. The grammar is identical; the question is  
    not. Do not describe output from this function as a replication of  
    Collings et al.

WHY COLOUR-BY-FIRST-COLUMN AND NOT A FIXED PALETTE  
    A fixed per-muscle palette is comparable across figures but throws away the  
    light-to-dark gradient, and it is the gradient that carries the signal: in  
    the anchored scheme the leftmost panel is always a clean dark-to-pale ramp,  
    so ANY colour disorder further right is a re-ranking. With a fixed palette  
    every panel looks equally shuffled and you are back to tracing lines.

THE ARROW CONVENTION IS THE PAPER'S, AND IT IS EASY TO INVERT BY ACCIDENT  
    An arrow runs from an item's rank in one column to its rank in the column  
    IMMEDIATELY RIGHT of it.

        blue   ranked HIGHER by the right-hand column  (it over-rates this one)  
        red    ranked LOWER  by the right-hand column  (it under-rates it)  
        grey   no change  
        dotted it left the top-N entirely

    Collings phrase this as "red = underestimated, blue = overestimated by  
    EMG", EMG being their right-hand column. Same rule, stated by position so  
    it stays correct when the columns are models rather than measures.

## Contents

- [`muscle_label`](#muscle_label) — 
- [`work_group`](#work_group) — 
- [`group_values`](#group_values) — {group: value} for one force table.
- [`iterations_root`](#iterations_root) — 
- [`find_iterations`](#find_iterations) — 
- [`find_trials`](#find_trials) — 
- [`ceinms_forces`](#ceinms_forces) — The CEINMS execution force file, newest Execution_* wins.
- [`so_forces`](#so_forces) — 
- [`rank_colours`](#rank_colours) — The colour map `rank_shift_axes` would anchor on `vals`. -> {item: rgba}
- [`rank_shift_axes`](#rank_shift_axes) — Draw one Collings-style row.
- [`rank_shift_figure`](#rank_shift_figure) — 
- [`collings_session`](#collings_session) — One rank-shift figure per trial: columns are static opt, then each model iteration. Returns the list of files written.

### `muscle_label`

```python
muscle_label(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L116)</sub>

### `work_group`

```python
work_group(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L125)</sub>

### `group_values`

```python
group_values(h, R, metric='peak', side='_r', allowed=None)
```

| input | type | default |
|---|---|---|
| `h` | – | required |
| `R` | – | required |
| `metric` | – | `'peak'` |
| `side` | – | `'_r'` |
| `allowed` | – | `None` |

{group: value} for one force table.

metric='peak'    the maximum over time of the group's SUMMED force. Summed  
                 before the max, not after: three muscles peaking at  
                 different instants are not a group that peaked three  
                 times. This is the Collings measure.  
metric='impulse' time-integral of that same summed force.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L130)</sub>

### `iterations_root`

```python
iterations_root(session)
```

| input | type | default |
|---|---|---|
| `session` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L161)</sub>

### `find_iterations`

```python
find_iterations(session, skip=())
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `skip` | – | `()` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L166)</sub>

### `find_trials`

```python
find_trials(session, iteration)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `iteration` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L182)</sub>

### `ceinms_forces`

```python
ceinms_forces(session, iteration, trial)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `iteration` | – | required |
| `trial` | – | required |

The CEINMS execution force file, newest Execution_* wins.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L192)</sub>

### `so_forces`

```python
so_forces(session, iteration, trial)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `iteration` | – | required |
| `trial` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L201)</sub>

### `rank_colours`

```python
rank_colours(vals, top=12)
```

| input | type | default |
|---|---|---|
| `vals` | – | required |
| `top` | – | `12` |

The colour map `rank_shift_axes` would anchor on `vals`. -> {item: rgba}

Exposed so a caller drawing SEVERAL rows can anchor them all on one panel.  
Stacked rows each anchored on their own leftmost column are internally  
consistent but not comparable BETWEEN rows: a muscle is dark in one row and  
pale in the other purely because the two rows rank it differently, which is  
exactly the comparison the reader is trying to make by eye.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L275)</sub>

### `rank_shift_axes`

```python
rank_shift_axes(
    fig,
    axes,
    columns,
    top=12,
    xlabel='% of the top group',
    label_fs=7.5,
    tick_fs=7.0,
    title_fs=9.0,
    colour=None,
    measured=(),
    measured_colour='#c1272d'
)
```

| input | type | default |
|---|---|---|
| `fig` | – | required |
| `axes` | – | required |
| `columns` | – | required |
| `top` | – | `12` |
| `xlabel` | – | `'% of the top group'` |
| `label_fs` | – | `7.5` |
| `tick_fs` | – | `7.0` |
| `title_fs` | – | `9.0` |
| `colour` | – | `None` |
| `measured` | – | `()` |
| `measured_colour` | – | `'#c1272d'` |

Draw one Collings-style row.

`columns` is an ordered list of (title, {item: value}). COLOUR IS ANCHORED  
ON columns[0]: every item takes the colour of its rank there and keeps it  
all the way right. An item absent from column 0 — it can happen, a muscle  
with no force in the reference — falls back to neutral grey rather than  
being given a rank it never had.

The three font sizes are ARGUMENTS because this function is also embedded  
as one row of a taller grid (results.py's supplementary rank figures stack  
a static-optimisation row over a CEINMS row, at a larger print size). The  
obvious alternative — let the caller restyle the text afterwards — breaks  
the label-fits-inside test below, which is decided at draw time from  
`label_fs`: bump the font after the fact and the longest in-bar labels  
overrun their bars. Pass the size in and the fit follows it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L290)</sub>

### `rank_shift_figure`

```python
rank_shift_figure(
    columns,
    path,
    title='',
    subtitle='',
    top=12,
    xlabel='% of the top group'
)
```

| input | type | default |
|---|---|---|
| `columns` | – | required |
| `path` | – | required |
| `title` | – | `''` |
| `subtitle` | – | `''` |
| `top` | – | `12` |
| `xlabel` | – | `'% of the top group'` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L410)</sub>

### `collings_session`

```python
collings_session(
    session,
    skip=(),
    trials=None,
    iterations=None,
    metric='peak',
    side='_r',
    top=12,
    out_dir=None,
    include_so=True,
    log=print
)
```

| input | type | default |
|---|---|---|
| `session` | – | required |
| `skip` | – | `()` |
| `trials` | – | `None` |
| `iterations` | – | `None` |
| `metric` | – | `'peak'` |
| `side` | – | `'_r'` |
| `top` | – | `12` |
| `out_dir` | – | `None` |
| `include_so` | – | `True` |
| `log` | – | `print` |

One rank-shift figure per trial: columns are static opt, then each  
model iteration. Returns the list of files written.

`include_so` puts static optimisation FIRST on purpose. It uses no EMG, so  
it is identical whatever the EMG-informed columns do, and it is the only  
no-EMG reference available — which makes it the right thing to anchor the  
colours on. Without it the leftmost column is just whichever model sorted  
first alphabetically, and the whole colour scheme inherits that accident.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/collings.py#L442)</sub>
