# `bioscout.utils.plotting`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/plotting.py)

bioscout.utils.plotting — figure/axis helpers (layout, saving, interactive  
export). Extracted from utils/__init__.py.

Depends only on os/webbrowser/numpy/matplotlib (+ optional scipy/plotly/tkinter  
imported lazily inside the functions that use them). No bioscout-global state.

## Contents

- [`save_fig`](#save_fig) — Saves the figure to the specified path.
- [`get_screen_size`](#get_screen_size) — 
- [`calculate_nRows_nCols`](#calculate_nrows_ncols) — Number of (rows, cols) for a grid that fits n_subplots.
- [`figure_suplots_grid`](#figure_suplots_grid) — Create a figure with a grid of subplots sized for n_subplots.
- [`mmfn`](#mmfn) — make my figure nice
- [`plot_mean_error_shade`](#plot_mean_error_shade) — Plot mean and error shade for a list of dataframes.
- [`add_picture_to_ax`](#add_picture_to_ax) — 
- [`convert_to_interactive_fig`](#convert_to_interactive_fig) — Convert Matplotlib figure to Plotly and: 1) show each legend label only once 2) toggle all traces with that label across all subplots 3) order legend labels alphabetically

### `save_fig`

```python
save_fig(fig, save_path)
```

| input | type | default |
|---|---|---|
| `fig` | – | required |
| `save_path` | – | required |

Saves the figure to the specified path.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/plotting.py#L15)</sub>

### `get_screen_size`

```python
get_screen_size()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/plotting.py#L23)</sub>

### `calculate_nRows_nCols`

```python
calculate_nRows_nCols(n_subplots)
```

| input | type | default |
|---|---|---|
| `n_subplots` | – | required |

Number of (rows, cols) for a grid that fits n_subplots.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/plotting.py#L36)</sub>

### `figure_suplots_grid`

```python
figure_suplots_grid(n_subplots, fig_size=(12, 8))
```

| input | type | default |
|---|---|---|
| `n_subplots` | – | required |
| `fig_size` | – | `(12, 8)` |

Create a figure with a grid of subplots sized for n_subplots.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/plotting.py#L45)</sub>

### `mmfn`

```python
mmfn(fig: plt.Figure, n_rows: int, n_cols: int)
```

| input | type | default |
|---|---|---|
| `fig` | plt.Figure | required |
| `n_rows` | int | required |
| `n_cols` | int | required |

make my figure nice

- remove x-tick labels from all but last row  
- remove title from all but first row  
- if an ax is empty (no data), remove ax  
- y labels only on first column

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/plotting.py#L53)</sub>

### `plot_mean_error_shade`

```python
plot_mean_error_shade(
    ax: plt.Axes,
    df_list: list,
    xcol: str,
    ycol: str,
    color: str,
    label: str = ''
)
```

| input | type | default |
|---|---|---|
| `ax` | plt.Axes | required |
| `df_list` | list | required |
| `xcol` | str | required |
| `ycol` | str | required |
| `color` | str | required |
| `label` | str | `''` |

Plot mean and error shade for a list of dataframes.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/plotting.py#L92)</sub>

### `add_picture_to_ax`

```python
add_picture_to_ax(ax: plt.Axes, image_path: str, scale: float = 1.0)
```

| input | type | default |
|---|---|---|
| `ax` | plt.Axes | required |
| `image_path` | str | required |
| `scale` | float | `1.0` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/plotting.py#L106)</sub>

### `convert_to_interactive_fig`

```python
convert_to_interactive_fig(fig: plt.Figure, html_path: str, launch_browser: bool = True)
```

| input | type | default |
|---|---|---|
| `fig` | plt.Figure | required |
| `html_path` | str | required |
| `launch_browser` | bool | `True` |

Convert Matplotlib figure to Plotly and:  
1) show each legend label only once  
2) toggle all traces with that label across all subplots  
3) order legend labels alphabetically

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/plotting.py#L123)</sub>
