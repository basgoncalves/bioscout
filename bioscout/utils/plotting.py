"""
bioscout.utils.plotting — figure/axis helpers (layout, saving, interactive
export). Extracted from utils/__init__.py.

Depends only on os/webbrowser/numpy/matplotlib (+ optional scipy/plotly/tkinter
imported lazily inside the functions that use them). No bioscout-global state.
"""
import os
import webbrowser

import numpy as np
import matplotlib.pyplot as plt


def save_fig(fig, save_path):
    """Saves the figure to the specified path."""
    if not os.path.exists(os.path.dirname(save_path)):
        os.makedirs(os.path.dirname(save_path))
    fig.savefig(save_path, bbox_inches='tight')
    print(f"Figure saved to {save_path}")


def get_screen_size():
    try:
        import tkinter as tk
        root = tk.Tk()
        width = root.winfo_screenwidth()
        height = root.winfo_screenheight()
        root.destroy()
        return width, height
    except Exception as e:
        print(f"Error getting screen size: {e}")
        return None


def calculate_nRows_nCols(n_subplots):
    """Number of (rows, cols) for a grid that fits n_subplots."""
    ncols = int(np.ceil(np.sqrt(n_subplots)))
    nrows = int(np.ceil(n_subplots / ncols))
    while (nrows - 1) * ncols >= n_subplots:
        nrows -= 1
    return nrows, ncols


def figure_suplots_grid(n_subplots, fig_size=(12, 8)):
    """Create a figure with a grid of subplots sized for n_subplots."""
    nrows, ncols = calculate_nRows_nCols(n_subplots)
    fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=fig_size)
    axes = axes.flatten()  # Flatten in case of multiple rows/columns
    return fig, axes


def mmfn(fig: plt.Figure, n_rows: int, n_cols: int):
    '''make my figure nice

    - remove x-tick labels from all but last row
    - remove title from all but first row
    - if an ax is empty (no data), remove ax
    - y labels only on first column
    '''
    axes = fig.get_axes()
    if len(axes) != n_rows * n_cols:
        raise ValueError(f'Number of axes ({len(axes)}) does not match n_rows * n_cols ({n_rows * n_cols})')

    for idx, ax in enumerate(axes):
        row = idx // n_cols
        col = idx % n_cols

        # Remove x-tick labels from all but last row
        if row < n_rows - 1:
            ax.set_xticklabels([])
            ax.set_xlabel('')

        # Y labels only on first column
        if col > 0:
            ax.set_yticklabels([])
            ax.set_ylabel('')

    # delete empty axes
    axes_to_delete = []
    for idx, ax in enumerate(axes):
        if not ax.has_data():
            axes_to_delete.append(idx)

    for idx in reversed(axes_to_delete):  # delete from the end to avoid index shift
        fig.delaxes(axes[idx])

    plt.tight_layout()
    return fig


def plot_mean_error_shade(ax: plt.Axes, df_list: list, xcol: str, ycol: str, color: str, label: str = ''):
    '''Plot mean and error shade for a list of dataframes.'''
    from bioscout.utils.shared import get_mean_across_trial_dfs  # lazy: avoids circular import
    df_mean = get_mean_across_trial_dfs(df_list, mode='mean')
    df_error = get_mean_across_trial_dfs(df_list, mode='stdev')

    ax.plot(df_mean[xcol], df_mean[ycol], color=color, label=label)
    ax.fill_between(df_mean[xcol],
                    df_mean[ycol] - df_error[ycol],
                    df_mean[ycol] + df_error[ycol],
                    color=color, alpha=0.3)
    return ax


def add_picture_to_ax(ax: plt.Axes, image_path: str, scale: float = 1.0):
    from scipy.ndimage import zoom

    if os.path.exists(image_path):
        img = plt.imread(image_path)
        ax.imshow(img)
        # Scale image if needed
        if scale != 1.0:
            img = zoom(img, (scale, scale, 1), order=1)
        ax.imshow(img)
        ax.axis('off')
    else:
        print(f"Warning: Image file not found at {image_path}. Adding task name text instead.")
        ax.text(0.5, 0.5, "Image not found", ha='center', va='center', fontsize=12)
        ax.axis('off')


def convert_to_interactive_fig(fig: plt.Figure, html_path: str, launch_browser: bool = True):
    """
    Convert Matplotlib figure to Plotly and:
    1) show each legend label only once
    2) toggle all traces with that label across all subplots
    3) order legend labels alphabetically
    """
    import plotly.io as pio
    import plotly.tools as tls

    plotly_fig = tls.mpl_to_plotly(fig)

    # Keep suptitle if present
    if fig._suptitle is not None:
        plotly_fig.update_layout(title=fig._suptitle.get_text(), title_x=0.5)

    # Ensure all traces have a name
    for trace in plotly_fig.data:
        if not trace.name:
            trace.name = "Unnamed"

    # Sort traces alphabetically by label
    sorted_traces = sorted(plotly_fig.data, key=lambda t: t.name.lower())

    # Merge repeated legend labels and link traces by legendgroup
    seen = set()
    for trace in sorted_traces:
        name = trace.name
        trace.legendgroup = name
        trace.showlegend = name not in seen
        seen.add(name)

    # Apply sorted order back to figure
    plotly_fig.data = tuple(sorted_traces)

    # Clicking one legend item toggles the whole group (all subplots)
    plotly_fig.update_layout(
        legend=dict(groupclick="togglegroup", traceorder="normal")
    )

    pio.write_html(plotly_fig, file=html_path, full_html=True, auto_open=False)
    print(f"Interactive plot saved: {html_path}")

    if launch_browser:
        webbrowser.open("file://" + os.path.abspath(html_path))


__all__ = [
    "save_fig", "get_screen_size", "calculate_nRows_nCols",
    "figure_suplots_grid", "mmfn", "plot_mean_error_shade",
    "add_picture_to_ax", "convert_to_interactive_fig",
]
