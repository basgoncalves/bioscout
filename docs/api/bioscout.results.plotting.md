# `bioscout.results.plotting`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/plotting.py)

Matplotlib for ResultSet.plot -- imported only when a plot is asked for.

## Contents

- class [`Plot`](#plot) — What ``ResultSet.plot`` returns: the figure, without a second copy in Jupyter.
- [`plot_resultset`](#plot_resultset) — 
- [`plot_resultsets`](#plot_resultsets) — Several result files (``session.results([...])``) in one go.
- [`plot_stack`](#plot_stack) — Stacked contributions, one axes per result file (an IAA target: a coordinate, center_of_mass_X/Y/Z, grf_<foot>_X/Y/Z). Positive parts stack above zero, negative below; black = their sum, dashed = measured.

<a id="plot"></a>

## class `Plot`

```python
Plot(fig)
```

| input | type | default |
|---|---|---|
| `fig` | – | required |

What ``ResultSet.plot`` returns: the figure, without a second copy in Jupyter.

plot() already displayed the figure; returning a bare Figure as the cell's  
last value would draw it again. This wrapper shows nothing as a value and  
forwards everything else to the figure (``p.savefig(...)``, ``p.axes``);  
``p.fig`` is the matplotlib Figure (``display(p.fig)`` shows it again).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/plotting.py#L20)</sub>

### `plot_resultset`

```python
plot_resultset(rs, var=None, by='iteration', mean=True, ncols=3, title=None, save=None)
```

| input | type | default |
|---|---|---|
| `rs` | – | required |
| `var` | – | `None` |
| `by` | – | `'iteration'` |
| `mean` | – | `True` |
| `ncols` | – | `3` |
| `title` | – | `None` |
| `save` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/plotting.py#L100)</sub>

### `plot_resultsets`

```python
plot_resultsets(
    rss,
    var=None,
    layout='figures',
    by='iteration',
    mean=True,
    ncols=3,
    title=None,
    save=None,
    **stack_kw
)
```

| input | type | default |
|---|---|---|
| `rss` | – | required |
| `var` | – | `None` |
| `layout` | – | `'figures'` |
| `by` | – | `'iteration'` |
| `mean` | – | `True` |
| `ncols` | – | `3` |
| `title` | – | `None` |
| `save` | – | `None` |
| `**stack_kw` | – | – |

Several result files (``session.results([...])``) in one go.

layout  "figures"  one figure per file (each like ResultSet.plot)  
        "rows"     one figure, a row per file, a column per channel  
        "overlay"  one axes per channel, a colour per file; a second file  
                   with another unit (N vs activation) gets its own y axis  
        "stack"    one axes per file, its channels stacked (IAA contributions;  
                   ``group``, ``top``, ``bw`` -- see plot_stack)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/plotting.py#L126)</sub>

### `plot_stack`

```python
plot_stack(rss, var=None, group=True, top=8, ncols=3, title=None, save=None, bw=None)
```

| input | type | default |
|---|---|---|
| `rss` | – | required |
| `var` | – | `None` |
| `group` | – | `True` |
| `top` | – | `8` |
| `ncols` | – | `3` |
| `title` | – | `None` |
| `save` | – | `None` |
| `bw` | – | `None` |

Stacked contributions, one axes per result file (an IAA target: a coordinate,  
center_of_mass_X/Y/Z, grf_<foot>_X/Y/Z). Positive parts stack above zero, negative  
below; black = their sum, dashed = measured.

var    channels to stack (glob; muscles, 'gravity', ...); default all  
group  True: sum muscles into groups per side (+ gravity, velocity, reserves)  
top    the largest ``top`` contributors per axes; the rest is one grey 'others'  
bw     body weight (N): GRF axes in BW

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/plotting.py#L332)</sub>
