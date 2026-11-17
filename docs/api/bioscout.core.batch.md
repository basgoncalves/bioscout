# `bioscout.core.batch`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/batch.py)

Fire a multi-subject analysis into the background and give the shell back.

    bioscout run 009 010 011 --iteration gpk --trial Run_baseline1,SJ1

prints the header and the log paths, then returns immediately: one detached  
worker runs the stages for each subject in turn, writing each subject's output  
to its own log. Nothing is streamed to the terminal, because a run of this  
length outlives the terminal it was started from -- the logs are the record.

    bioscout run --status          what is running, what finished, how long  
    bioscout run --status JOB_ID   the stage-by-stage detail of one job

Implementation note: the worker is this same module re-invoked with --worker,  
detached from the launching shell (``start_new_session`` on POSIX,  
DETACHED_PROCESS on Windows), so closing the terminal does not kill the run.

## Contents

- [`build_parser`](#build_parser) — 
- [`main`](#main) — 

### `build_parser`

```python
build_parser() -> argparse.ArgumentParser
```

**returns** `argparse.ArgumentParser`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/batch.py#L146)</sub>

### `main`

```python
main(argv=None) -> int
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

**returns** `int`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/core/batch.py#L169)</sub>
