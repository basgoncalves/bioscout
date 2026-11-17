# `bioscout.utils.shared`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py)

bioscout.utils.shared — small, dependency-light helpers needed across several  
utils modules (analyse, analysis, emg, plotting, …).

Keeping them here (rather than in ``utils/__init__``) avoids import-order and  
circular-import headaches: every module can do ``from bioscout.utils import  
shared`` (or rely on the re-exports from ``utils/__init__``) without pulling in  
the whole package.

Functions that depend on project-level globals (CODE_DIR, PRINT_TERMINAL, …)  
read them lazily from ``bioscout.utils`` at call time, so they stay correct  
after ``bioscout.Project`` re-points those globals at the active project.

## Contents

- [`updir`](#updir) — Move up a directory path by a specified number of levels.
- [`print_to_log`](#print_to_log) — Print a message to the console and append it to the package log file.
- [`in_notebook`](#in_notebook) — True when stdout belongs to a Jupyter/IPython cell rather than a console.
- [`quiet_opensim`](#quiet_opensim) — Raise OpenSim's log level to quiet its C++ [info]/[warning] spam (missing display geometry, etc.). ``level`` defaults to ``settings.BatchSettings.opensim_log_level`` (e.g. "Error"). No-op if no level is configured or OpenSim isn't importable. Call this from any entry point that loads OpenSim models outside the logging pipeline (e.g. muscle_inspect).
- [`ensure_logging`](#ensure_logging) — Start file logging ONCE per process (idempotent).
- [`start_logging`](#start_logging) — Open a timestamped project log file, with a run heading.
- [`set_quiet_console`](#set_quiet_console) — 
- [`console_stream`](#console_stream) — The REAL terminal, even while a quiet tee / fd redirect is in place.
- [`stop_logging`](#stop_logging) — Close the current run log and give stdout/stderr back.
- [`capture_output`](#capture_output) — Copy ``print()`` output into the run log for the duration of a block.
- [`trial_type`](#trial_type) — Strip a trailing ``_<number>`` so reps of a task share a type.
- [`get_mean_across_trial_dfs`](#get_mean_across_trial_dfs) — Reduce a list of per-trial DataFrames across trials, aligned by row index.
- [`time_normalise_df`](#time_normalise_df) — Resample every column of ``df`` to 101 points over its time range.
- [`plot_style`](#plot_style) — Return ``{'color','ls','lw'}`` for a plot SOURCE. Merges the project's ``settings.PlottingSettings.sources[source]`` over ``DEFAULT_PLOT_STYLE``; the colour is normalised for matplotlib.
- [`side_color`](#side_color) — Body-side colour convention used across bioscout figures: right = blue, left = red. Accepts 'r'/'right'/'_r' or 'l'/'left'/'_l'.
- [`fig_size`](#fig_size) — Figure size (inches) for an ``nrows x ncols`` subplot grid, scaled by ``settings.PlottingSettings.scale_per_subplot`` = (row_mult, col_mult) and ``fig_scale``. Defaults to a sensible per-subplot size if unset.
- [`step_logs_on`](#step_logs_on) — 
- [`step_log`](#step_log) — Send everything printed inside the block to ``path`` (and to the terminal with --verbose) instead of the run log. Yields a dict filled on exit with ``warnings`` (lines with WARNING/Warning) and ``path`` (None when not redirected: library use, a nested step, or BIOSCOUT_STEP_LOGS=0).
- [`quiet_run`](#quiet_run) — Decorator for the long bioscout calls (scale_model, run): in a notebook or script, with ``log_terminal: false`` (``bioscout settings``), the call's output goes to the run log and the cell shows only the log path, warnings and errors. The streams are swapped only for the duration of the call, in the cell that makes it, and always restored. The CLI and nested calls are left alone; ``log_terminal: true`` prints everything as before.

### `updir`

```python
updir(path, levels=1)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `levels` | – | `1` |

Move up a directory path by a specified number of levels.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L29)</sub>

### `print_to_log`

```python
print_to_log(message, terminal=None, trial=None)
```

| input | type | default |
|---|---|---|
| `message` | – | required |
| `terminal` | – | `None` |
| `trial` | – | `None` |

Print a message to the console and append it to the package log file.

  
**Args**

    message (str): The message to print and log.  
    terminal (bool|None): Force console echo; ``None`` falls back to  
        ``utils.PRINT_TERMINAL``.  
    trial (str): Optional trial name shown before the message.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L36)</sub>

### `in_notebook`

```python
in_notebook()
```

True when stdout belongs to a Jupyter/IPython cell rather than a console.

``ipykernel`` in ``sys.modules`` is the cheap, dependency-free test: it is  
imported by the kernel itself and by nothing else. Used for two decisions in  
``start_logging`` — both about not stealing a notebook's own output.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L112)</sub>

### `quiet_opensim`

```python
quiet_opensim(level=None)
```

| input | type | default |
|---|---|---|
| `level` | – | `None` |

Raise OpenSim's log level to quiet its C++ [info]/[warning] spam (missing  
display geometry, etc.). ``level`` defaults to  
``settings.BatchSettings.opensim_log_level`` (e.g. "Error"). No-op if no level  
is configured or OpenSim isn't importable. Call this from any entry point that  
loads OpenSim models outside the logging pipeline (e.g. muscle_inspect).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L314)</sub>

### `ensure_logging`

```python
ensure_logging(name='bioscout', log_dir=None)
```

| input | type | default |
|---|---|---|
| `name` | – | `'bioscout'` |
| `log_dir` | – | `None` |

Start file logging ONCE per process (idempotent).

Called automatically whenever a Project or Analyse/Trial is created, so any  
bioscout run writes ``<project>/logs/bioscout_<timestamp>.log`` without the  
caller doing anything. No-op if logging was already started (e.g. an explicit  
``start_logging`` or the CLI). Returns the log handle, or None if already on.

Library use (notebook, script) opens the file but does NOT capture stdout —  
see ``start_logging(capture=...)``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L335)</sub>

### `start_logging`

```python
start_logging(name='run', log_dir=None, filename=None, append=False, capture=None)
```

| input | type | default |
|---|---|---|
| `name` | – | `'run'` |
| `log_dir` | – | `None` |
| `filename` | – | `None` |
| `append` | – | `False` |
| `capture` | – | `None` |

Open a timestamped project log file, with a run heading.

Every run writes to ``<log_dir>/bioscout_<YYYYmmdd_HHMMSS>.log`` — one naming  
scheme (``bioscout_…``) for all runs, with the timestamp in the filename so  
runs never collide, and a heading inside identifying what was done (``name``  
+ time + disclaimer)::

    from bioscout import utils  
    utils.start_logging("export Athlete_03_Cateli/25_03_31")

What goes into the file:

* always -- the heading, OpenSim's native C++ output and the completion  
  banner (both written when the process exits or :func:`stop_logging` runs);  
* ``print()`` output, but only while stdout/stderr are *captured*.

``capture`` decides whether ``sys.stdout``/``sys.stderr`` are teed into the  
file. ``None`` (the default) captures ONLY when bioscout's own CLI/GUI owns  
the process (see :func:`_console_owned`). Imported as a library -- a  
notebook, your own script -- bioscout leaves the streams alone, as a Python  
library should: replacing them silently changes where every other print in  
the session goes. Pass ``capture=True`` to opt in explicitly, or use  
:func:`capture_output` to capture just one block; :func:`stop_logging`  
puts the original streams back.

``log_dir`` defaults to ``<project>/logs`` (``utils.PROJECT_DIR``). Pass an  
explicit ``filename=`` to override, or ``append=True`` to append. Returns  
the open log file handle.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L456)</sub>

### `set_quiet_console`

```python
set_quiet_console(quiet=True)
```

| input | type | default |
|---|---|---|
| `quiet` | – | `True` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L628)</sub>

### `console_stream`

```python
console_stream()
```

The REAL terminal, even while a quiet tee / fd redirect is in place.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L672)</sub>

### `stop_logging`

```python
stop_logging()
```

Close the current run log and give stdout/stderr back.

Writes the completion banner (and OpenSim's native output) into the file  
and restores the streams if they were captured. Safe to call when logging  
never started. Afterwards the next ``Project``/``Session`` opens a fresh  
log.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L742)</sub>

### `capture_output`

```python
capture_output(name='block', log_dir=None)
```

| input | type | default |
|---|---|---|
| `name` | – | `'block'` |
| `log_dir` | – | `None` |

Copy ``print()`` output into the run log for the duration of a block.

For notebooks and scripts, where bioscout otherwise leaves stdout alone::

    from bioscout.utils import capture_output  
    with capture_output():  
        session.run()          # prints show in the cell AND in the log

Opens a log first if none is running. The streams are restored on exit,  
even on error, so the next cell behaves normally.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L762)</sub>

### `trial_type`

```python
trial_type(trial_name, pattern=DEFAULT_TRIAL_TYPE_PATTERN)
```

| input | type | default |
|---|---|---|
| `trial_name` | – | required |
| `pattern` | – | `DEFAULT_TRIAL_TYPE_PATTERN` |

Strip a trailing ``_<number>`` so reps of a task share a type.

``'Squat_35kg_02' -> 'Squat_35kg'``; names without a trailing number are  
returned unchanged.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L793)</sub>

### `get_mean_across_trial_dfs`

```python
get_mean_across_trial_dfs(df_list, mode='mean') -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `df_list` | – | required |
| `mode` | – | `'mean'` |

**returns** `pd.DataFrame`

Reduce a list of per-trial DataFrames across trials, aligned by row index.

``mode`` = 'mean' | 'median' | 'stdev'. Each input is one trial; the result  
is a single DataFrame of the per-row reduction (drops the internal trial id).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L803)</sub>

### `time_normalise_df`

```python
time_normalise_df(df, fs='')
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `fs` | – | `''` |

Resample every column of ``df`` to 101 points over its time range.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L827)</sub>

### `plot_style`

```python
plot_style(source)
```

| input | type | default |
|---|---|---|
| `source` | – | required |

Return ``{'color','ls','lw'}`` for a plot SOURCE. Merges the project's  
``settings.PlottingSettings.sources[source]`` over ``DEFAULT_PLOT_STYLE``;  
the colour is normalised for matplotlib.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L894)</sub>

### `side_color`

```python
side_color(side)
```

| input | type | default |
|---|---|---|
| `side` | – | required |

Body-side colour convention used across bioscout figures: right = blue,  
left = red. Accepts 'r'/'right'/'_r' or 'l'/'left'/'_l'.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L909)</sub>

### `fig_size`

```python
fig_size(nrows, ncols)
```

| input | type | default |
|---|---|---|
| `nrows` | – | required |
| `ncols` | – | required |

Figure size (inches) for an ``nrows x ncols`` subplot grid, scaled by  
``settings.PlottingSettings.scale_per_subplot`` = (row_mult, col_mult) and  
``fig_scale``. Defaults to a sensible per-subplot size if unset.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L920)</sub>

### `step_logs_on`

```python
step_logs_on()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L944)</sub>

### `step_log`

```python
step_log(path, label='')
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `label` | – | `''` |

Send everything printed inside the block to ``path`` (and to the terminal with  
--verbose) instead of the run log. Yields a dict filled on exit with  
``warnings`` (lines with WARNING/Warning) and ``path`` (None when not redirected:  
library use, a nested step, or BIOSCOUT_STEP_LOGS=0).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L950)</sub>

### `quiet_run`

```python
quiet_run(label)
```

| input | type | default |
|---|---|---|
| `label` | – | required |

Decorator for the long bioscout calls (scale_model, run): in a notebook  
or script, with ``log_terminal: false`` (``bioscout settings``), the call's  
output goes to the run log and the cell shows only the log path, warnings  
and errors. The streams are swapped only for the duration of the call, in  
the cell that makes it, and always restored. The CLI and nested calls are  
left alone; ``log_terminal: true`` prints everything as before.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/shared.py#L1061)</sub>
