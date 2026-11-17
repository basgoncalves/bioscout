# `bioscout.results`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/__init__.py)

bioscout.results — load, analyse, plot and export simulation results.

From a session, iteration or project (all the same call)::

    sess = PROJECT.session("K2L", "11_03_24")  
    sess.results()                                       # what is on disk (no file read)  
    sess.results.files                                   # every file kind, its aliases and unit

    f = sess.results("so_forces", trial="Gehen_01", iteration="gpkv4", var=["vasmed_r", "soleus_r"])  
    f.df                                                 # time | vasmed_r | soleus_r (+ ID columns)  
    f.plot()

    f = sess.results("so_forces", trial="Gehen*", var="*_r", window="cycle")   # many at once  
    f.mean("iteration").plot()  
    f.to_bw().peak()

    r = sess.results(["ik", "id", "jcf_so"], trial="Gehen_01")                 # several files  
    r["joint_angles"].plot(var="*_r")

Without bioscout objects::

    from bioscout import results  
    results.load(r"C:/.../simulations/K2L/11_03_24", "ik")     # a session folder  
    results.load(r"C:/.../ExampleData", "ik", subject="K2L")   # or a project

Layers (each extensible on its own):

    kinds      file kind registry       -> register_file(...)  
    scan       which sessions/files exist  
    windows    trial / cycle / stance cutting + time normalisation  
    load       read + cut -> ResultSet  
    resultset  ResultSet + actions      -> @action  
    export     CSVs for Excel/JASP/R    (``bioscout project results``)

## Available as `bioscout.results.<name>`

- [`bioscout.results.export_results`](bioscout.results.export.md#export_results) — from `bioscout.results.export`
- [`bioscout.results.FILES`](bioscout.results.kinds.md#files) — from `bioscout.results.kinds`
- [`bioscout.results.register_file`](bioscout.results.kinds.md#register_file) — from `bioscout.results.kinds`
- [`bioscout.results.read_storage`](bioscout.results.io.md#read_storage) — from `bioscout.results.io`
- [`bioscout.results.ACTIONS`](bioscout.results.resultset.md#actions) — from `bioscout.results.resultset`
- [`bioscout.results.ResultSet`](bioscout.results.resultset.md#resultset) — from `bioscout.results.resultset`
- [`bioscout.results.ResultSets`](bioscout.results.resultset.md#resultsets) — from `bioscout.results.resultset`
- [`bioscout.results.action`](bioscout.results.resultset.md#action) — from `bioscout.results.resultset`
- [`bioscout.results.find_sessions`](bioscout.results.scan.md#find_sessions) — from `bioscout.results.scan`
- [`bioscout.results.ID_COLS`](bioscout.results.windows.md#id_cols) — from `bioscout.results.windows`

## Contents

- class [`Results`](#results) — ``session.results`` / ``iteration.results`` / ``project.results``.
  - [`Results.plot_iaa`](#resultsplot_iaa) — The IAA summary, 3 x 3, contributions stacked (positive up, negative down; black = sum, dashed = measured):
  - [`Results.files`](#resultsfiles) — 
  - [`Results.available`](#resultsavailable) — 
- [`files`](#files) — The file kinds as a table: name, aliases, unit, description.
- [`load`](#load) — ``path`` = a session folder (holds session.yaml) or a project folder. ``file=None`` -> availability table; otherwise see :meth:`Results.__call__`.

<a id="results"></a>

## class `Results`

```python
Results(infos, **fixed)
```

| input | type | default |
|---|---|---|
| `infos` | – | required |
| `**fixed` | – | – |

``session.results`` / ``iteration.results`` / ``project.results``.

Call it to load; nothing is read until you do. Fixed filters (the  
iteration of an Iteration, the subject/session of a Session) are applied  
on every call.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/__init__.py#L67)</sub>

<a id="resultsplot_iaa"></a>

### `Results.plot_iaa`

```python
Results.plot_iaa(
    trial=None,
    iteration=None,
    side='r',
    engine='opensim',
    group=True,
    top=8,
    bw=None,
    window='trial',
    title=None,
    save=None,
    **kw
)
```

| input | type | default |
|---|---|---|
| `trial` | – | `None` |
| `iteration` | – | `None` |
| `side` | – | `'r'` |
| `engine` | – | `'opensim'` |
| `group` | – | `True` |
| `top` | – | `8` |
| `bw` | – | `None` |
| `window` | – | `'trial'` |
| `title` | – | `None` |
| `save` | – | `None` |
| `**kw` | – | – |

The IAA summary, 3 x 3, contributions stacked (positive up, negative down;  
black = sum, dashed = measured):

  row 1  centre-of-mass acceleration  X, Y, Z            (IAA)  
  row 2  ground reaction force under the ``side`` foot  X, Y, Z   (IAA)  
  row 3  sagittal hip / knee / ankle moments on ``side``: each muscle's SO  
         force x moment arm (muscle_moments_so), dashed = inverse dynamics

``engine`` "opensim" | "pyosim"; ``bw`` body weight in N (GRF in BW, moments in  
N*m/kg); ``group`` muscles into groups (False: individual muscles).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/__init__.py#L111)</sub>

<a id="resultsfiles"></a>

### `Results.files`

```python
Results.files()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/__init__.py#L165)</sub>

<a id="resultsavailable"></a>

### `Results.available`

```python
Results.available(**kw)
```

| input | type | default |
|---|---|---|
| `**kw` | – | – |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/__init__.py#L168)</sub>

### `files`

```python
files()
```

The file kinds as a table: name, aliases, unit, description.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/__init__.py#L56)</sub>

### `load`

```python
load(path, file=None, subject=None, session=None, **kw)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `file` | – | `None` |
| `subject` | – | `None` |
| `session` | – | `None` |
| `**kw` | – | – |

``path`` = a session folder (holds session.yaml) or a project folder.  
``file=None`` -> availability table; otherwise see :meth:`Results.__call__`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/__init__.py#L61)</sub>
