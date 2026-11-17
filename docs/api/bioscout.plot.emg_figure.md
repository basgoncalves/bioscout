# `bioscout.plot.emg_figure`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/emg_figure.py)

emg_processing.png in the vertical task layout (vGRF on top).

    from bioscout.plot.emg_figure import emg_task_figure  
    emg_task_figure(exp_dir, out=exp_dir / "emg_processing.png")

``exp_dir`` is ``<session>/2_experimental/<trial>``. The figure is

    row 0   vertical GRF per foot, events dashed and named  
            (no poses / kinematics: EMG is processed at export, before IK)  
    rows    one row per EMG channel: filtered + normalised envelope (thick,  
            shaded) on the left axis, raw signal faint grey on a twin axis.

Each EMG channel is coloured by the SIDE of the muscles session.yaml's  
``emg_map`` assigns it (all ``*_r`` -> right red, all ``*_l`` -> left blue);  
a channel with no mapping, or mixed sides, is grey -- e.g. a reference  
electrode on the arm. The row title lists the model muscles it drives.

## Contents

- [`channel_side`](#channel_side) — 'r' / 'l' when every mapped muscle is on that side, else None. Without a mapping, fall back to a trailing _r/_l in the channel name.
- [`emg_task_figure`](#emg_task_figure) — Write emg_processing.png in the task layout. ``raw``/``norm`` are DataFrames (read from exp_dir/emg.mot and the best processed file when None). Returns the saved path.

### `channel_side`

```python
channel_side(channel: str, muscles) -> str | None
```

| input | type | default |
|---|---|---|
| `channel` | str | required |
| `muscles` | – | required |

**returns** `str \| None`

'r' / 'l' when every mapped muscle is on that side, else None. Without a  
mapping, fall back to a trailing _r/_l in the channel name.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/emg_figure.py#L50)</sub>

### `emg_task_figure`

```python
emg_task_figure(
    exp_dir,
    out=None,
    raw=None,
    norm=None,
    emg_map=None,
    norm_source=None,
    iteration=None,
    channels=None,
    log=print
)
```

| input | type | default |
|---|---|---|
| `exp_dir` | – | required |
| `out` | – | `None` |
| `raw` | – | `None` |
| `norm` | – | `None` |
| `emg_map` | – | `None` |
| `norm_source` | – | `None` |
| `iteration` | – | `None` |
| `channels` | – | `None` |
| `log` | – | `print` |

Write emg_processing.png in the task layout. ``raw``/``norm`` are  
DataFrames (read from exp_dir/emg.mot and the best processed file when  
None). Returns the saved path.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/emg_figure.py#L82)</sub>
