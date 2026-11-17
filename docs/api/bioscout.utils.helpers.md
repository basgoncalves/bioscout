# `bioscout.utils.helpers`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/helpers.py)

Helper functions for batch processing pipeline

## Contents

- [`setup_logging`](#setup_logging) — Set up logging configuration for the batch pipeline.
- [`plot_motion_results`](#plot_motion_results) — Plot motion analysis results from OpenSim output file.
- [`check_cpu_temperature`](#check_cpu_temperature) — Check the CPU temperature and log a warning if it exceeds 80°C.

### `setup_logging`

```python
setup_logging(log_dir)
```

| input | type | default |
|---|---|---|
| `log_dir` | – | required |

Set up logging configuration for the batch pipeline.

  
**Args**

    log_dir: Directory for log files

  
**Returns**

    logger: Configured logger instance

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/helpers.py#L18)</sub>

### `plot_motion_results`

```python
plot_motion_results(trial_name, data_file, title, ylabel, results_dir, logger)
```

| input | type | default |
|---|---|---|
| `trial_name` | – | required |
| `data_file` | – | required |
| `title` | – | required |
| `ylabel` | – | required |
| `results_dir` | – | required |
| `logger` | – | required |

Plot motion analysis results from OpenSim output file.

  
**Args**

    trial_name: Name of the trial  
    data_file: Path to the data file (.mot or .sto)  
    title: Plot title  
    ylabel: Y-axis label  
    results_dir: Directory to save the plot  
    logger: Logger instance

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/helpers.py#L66)</sub>

### `check_cpu_temperature`

```python
check_cpu_temperature()
```

Check the CPU temperature and log a warning if it exceeds 80°C.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/helpers.py#L123)</sub>
