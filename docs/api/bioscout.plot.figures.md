# `bioscout.plot.figures`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py)

bioscout.plot.figures - one catalogue for every plot in this project.

Every figure that lives in the powerlifting scripts (``results.py``,  
``calibration_figures.py``, ``manuscript.py``) and in bioscout itself  
(``simulate.ceinms.plot``, ``muscle_inspect``) is registered here ONCE, with the  
inputs it needs. Nothing is re-implemented: this module only knows how to find  
the builder, ask for its inputs and call it.

  
**Two ways to use it**

standalone::

    python -m bioscout.plot.figures                # menu, prompts for what it needs  
    python -m bioscout.plot.figures --list  
    python -m bioscout.plot.figures p04 p07jcf     # run these, prompt for inputs

inside bioscout / a notebook::

    from bioscout.plot import figures  
    figures.catalog()                          # -> list of Figure  
    figures.run("p04")                         # prompts for the missing inputs  
    figures.run("p04", trial="Squat_BW_01")    # nothing to prompt for  
    figures.menu()                             # the interactive menu

Anything you do not pass to ``run()`` is asked for with ``input()``; anything  
you do pass is used as-is, so the same registry works scripted and by hand.

## Contents

- class [`P`](#p) — One input a figure needs.
  - [`P.resolve`](#presolve) — 
- class [`Figure`](#figure) — 
- class [`Ctx`](#ctx) — sess / S / L / trials / tasks for one session - what results.run() builds.
- [`ask`](#ask) — Ask for one value. Returns `default` when there is no terminal.
- [`catalog`](#catalog) — 
- [`groups`](#groups) — 
- [`project_dir`](#project_dir) — Folder holding results.py / manuscript.py / calibration_figures.py.
- [`R`](#r) — 
- [`session_ctx`](#session_ctx) — 
- [`master`](#master) — {'curves','discrete','effects'} read from <project>/results/master_*.csv.
- [`run`](#run) — Run one figure. Missing inputs are prompted for.
- [`run_many`](#run_many) — 
- [`list_figures`](#list_figures) — 
- [`menu`](#menu) — Interactive picker: numbers, keys, a group name, or 'all'.
- [`main`](#main) — 

<a id="p"></a>

## class `P`

One input a figure needs.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L91)</sub>

<a id="presolve"></a>

### `P.resolve`

```python
P.resolve(state)
```

| input | type | default |
|---|---|---|
| `state` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L99)</sub>

<a id="figure"></a>

## class `Figure`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L105)</sub>

<a id="ctx"></a>

## class `Ctx`

```python
Ctx(session=None, subject=None, models=None)
```

| input | type | default |
|---|---|---|
| `session` | – | `None` |
| `subject` | – | `None` |
| `models` | – | `None` |

sess / S / L / trials / tasks for one session - what results.run() builds.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L190)</sub>

### `ask`

```python
ask(prompt, default=None, kind='text', choices=None)
```

| input | type | default |
|---|---|---|
| `prompt` | – | required |
| `default` | – | `None` |
| `kind` | – | `'text'` |
| `choices` | – | `None` |

Ask for one value. Returns `default` when there is no terminal.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L52)</sub>

### `catalog`

```python
catalog(group=None)
```

| input | type | default |
|---|---|---|
| `group` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L122)</sub>

### `groups`

```python
groups()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L126)</sub>

### `project_dir`

```python
project_dir(path=None)
```

| input | type | default |
|---|---|---|
| `path` | – | `None` |

Folder holding results.py / manuscript.py / calibration_figures.py.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L150)</sub>

### `R`

```python
R()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L182)</sub>

### `session_ctx`

```python
session_ctx(session=None, subject=None, models=None, reuse=True)
```

| input | type | default |
|---|---|---|
| `session` | – | `None` |
| `subject` | – | `None` |
| `models` | – | `None` |
| `reuse` | – | `True` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L223)</sub>

### `master`

```python
master(reload=False)
```

| input | type | default |
|---|---|---|
| `reload` | – | `False` |

{'curves','discrete','effects'} read from <project>/results/master_*.csv.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L253)</sub>

### `run`

```python
run(key, **kw)
```

| input | type | default |
|---|---|---|
| `key` | – | required |
| `**kw` | – | – |

Run one figure. Missing inputs are prompted for.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L589)</sub>

### `run_many`

```python
run_many(keys, **kw)
```

| input | type | default |
|---|---|---|
| `keys` | – | required |
| `**kw` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L608)</sub>

### `list_figures`

```python
list_figures(group=None)
```

| input | type | default |
|---|---|---|
| `group` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L618)</sub>

### `menu`

```python
menu()
```

Interactive picker: numbers, keys, a group name, or 'all'.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L626)</sub>

### `main`

```python
main(argv=None)
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/figures.py#L664)</sub>
