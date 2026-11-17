# `bioscout.devtools.bench`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py)

Overnight pipeline benchmark: where does the time go, and what scales?

    python -m bioscout.devtools.bench --smoke      # ~2 min: does every stage run?  
    python -m bioscout.devtools.bench              # the overnight run (8 h budget)

Runs on COPIES of example_data/orthoload (Walking_01, iteration gpk), so your  
example data is never touched. Four tests, in this order, each with a share of  
the time budget (time a test does not use passes on to the next):

  stages    each stage timed on its own, --reps times (scale, IK, ID, MA, SO,  
            muscle moments, JRA, mew, JCF contributions)          -> which stage is slow  
  profile   one chain under cProfile; time split into OpenSim / bioscout /  
            matplotlib / pandas / numpy / file I/O per stage       -> why it is slow  
  soak      the IK..mew chain repeated in ONE process; memory, handles,  
            open figures and time per round                         -> leaks / slow-down  
  parallel  N copies of the trial run with 1, 2, 4 ... processes, plus the  
            JCF-contributions n_jobs sweep                          -> does parallel pay

Everything lands in example_data/_bench/<date_time>/ (gitignored):  
  STATUS.md        rewritten after every unit -- open it to see where the run is  
  SUMMARY.md       the morning read (rewritten after every test, so a crash  
                   still leaves the part that finished)  
  stage_times.csv  one row per timed stage, every test  
  parallel.csv     one row per worker count  
  profile/         <stage>.prof (snakeviz-able) + <stage>_top.txt  
  run.log          everything the pipeline printed

Ctrl+C stops cleanly and still writes SUMMARY.md.

## Contents

- class [`Runner`](#runner) — Opens the session once; runs one stage at a time on one trial.
  - [`Runner.it`](#runnerit) — 
  - [`Runner.run`](#runnerrun) — -> dict row (wall/cpu/open/status/error + process stats).
- class [`Bench`](#bench) — 
  - [`Bench.event`](#benchevent) — 
  - [`Bench.record`](#benchrecord) — 
  - [`Bench.write_status`](#benchwrite_status) — 
  - [`Bench.time_left`](#benchtime_left) — 
  - [`Bench.copy`](#benchcopy) — 
  - [`Bench.runner`](#benchrunner) — 
  - [`Bench.test_stages`](#benchtest_stages) — Each stage on its own, --reps rounds. Scale runs on its own copy (rescaling rewrites model_scaled, which every other stage reads).
  - [`Bench.test_profile`](#benchtest_profile) — 
  - [`Bench.test_soak`](#benchtest_soak) — 
  - [`Bench.test_parallel`](#benchtest_parallel) — 
  - [`Bench.run`](#benchrun) — 
  - [`Bench.write_header`](#benchwrite_header) — 
  - [`Bench.write_summary`](#benchwrite_summary) — 
- [`main`](#main) — 

<a id="runner"></a>

## class `Runner`

```python
Runner(project, session, iteration, trial, log_path, fake=False)
```

| input | type | default |
|---|---|---|
| `project` | – | required |
| `session` | – | required |
| `iteration` | – | required |
| `trial` | – | required |
| `log_path` | – | required |
| `fake` | – | `False` |

Opens the session once; runs one stage at a time on one trial.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L174)</sub>

<a id="runnerit"></a>

### `Runner.it`

```python
Runner.it()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L186)</sub>

<a id="runnerrun"></a>

### `Runner.run`

```python
Runner.run(stage, n_jobs=None, profiler=None)
```

| input | type | default |
|---|---|---|
| `stage` | – | required |
| `n_jobs` | – | `None` |
| `profiler` | – | `None` |

-> dict row (wall/cpu/open/status/error + process stats).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L272)</sub>

<a id="bench"></a>

## class `Bench`

```python
Bench(a)
```

| input | type | default |
|---|---|---|
| `a` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L349)</sub>

<a id="benchevent"></a>

### `Bench.event`

```python
Bench.event(msg)
```

| input | type | default |
|---|---|---|
| `msg` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L393)</sub>

<a id="benchrecord"></a>

### `Bench.record`

```python
Bench.record(test, row, round_=None, workers=None, job=None)
```

| input | type | default |
|---|---|---|
| `test` | – | required |
| `row` | – | required |
| `round_` | – | `None` |
| `workers` | – | `None` |
| `job` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L400)</sub>

<a id="benchwrite_status"></a>

### `Bench.write_status`

```python
Bench.write_status()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L415)</sub>

<a id="benchtime_left"></a>

### `Bench.time_left`

```python
Bench.time_left()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L429)</sub>

<a id="benchcopy"></a>

### `Bench.copy`

```python
Bench.copy(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L432)</sub>

<a id="benchrunner"></a>

### `Bench.runner`

```python
Bench.runner(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L438)</sub>

<a id="benchtest_stages"></a>

### `Bench.test_stages`

```python
Bench.test_stages(deadline)
```

| input | type | default |
|---|---|---|
| `deadline` | – | required |

Each stage on its own, --reps rounds. Scale runs on its own copy  
(rescaling rewrites model_scaled, which every other stage reads).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L444)</sub>

<a id="benchtest_profile"></a>

### `Bench.test_profile`

```python
Bench.test_profile(deadline)
```

| input | type | default |
|---|---|---|
| `deadline` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L457)</sub>

<a id="benchtest_soak"></a>

### `Bench.test_soak`

```python
Bench.test_soak(deadline)
```

| input | type | default |
|---|---|---|
| `deadline` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L480)</sub>

<a id="benchtest_parallel"></a>

### `Bench.test_parallel`

```python
Bench.test_parallel(deadline)
```

| input | type | default |
|---|---|---|
| `deadline` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L490)</sub>

<a id="benchrun"></a>

### `Bench.run`

```python
Bench.run()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L580)</sub>

<a id="benchwrite_header"></a>

### `Bench.write_header`

```python
Bench.write_header()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L607)</sub>

<a id="benchwrite_summary"></a>

### `Bench.write_summary`

```python
Bench.write_summary()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L636)</sub>

### `main`

```python
main(argv=None)
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/devtools/bench.py#L815)</sub>
