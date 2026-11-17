# `bioscout.plot`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/__init__.py)

bioscout.plot — project-independent comparison figures.

    import bioscout as bs

    fig = (bs.plot(df)                       # or bs.plot.compare(df)  
             .where(Variable="muscle_work_total", Algo="SO")  
             .compare("Condition", order=["pre-fatigue", "post-fatigue"])  
             .facet("Task", icons=TASK_ICONS)  
             .group(bs.plot.MUSCLE_GROUPS)  
             .top(8)  
             .title("total muscle work ranks")  
             .save("results/group/work_ranks.png"))

Three layers, each usable on its own:

``bioscout.plot.work``     .sto files  -> muscle work numbers  (:func:`work_table`)  
``bioscout.plot.tidy``     numbers     -> one long table       (:func:`read`)  
``bioscout.plot.compare``  table       -> a figure             (:class:`Compare`)

The middle layer is the contract. A bioscout session goes through all three; a  
project whose numbers came from anywhere else builds the table itself and uses  
the last one. Nothing in here reads a project ``settings.py`` — the house style  
lives in :mod:`bioscout.plot.config` and a notebook overrides it at run time  
with :func:`configure`.

Quick tour, no data required::

    bs.plot.demo().show()

## Available as `bioscout.plot.<name>`

- [`bioscout.plot.Compare`](bioscout.plot.compare.md#compare) — from `bioscout.plot.compare`
- [`bioscout.plot.PlotConfig`](bioscout.plot.config.md#plotconfig) — from `bioscout.plot.config`
- [`bioscout.plot.configure`](bioscout.plot.config.md#configure) — from `bioscout.plot.config`
- [`bioscout.plot.reset`](bioscout.plot.config.md#reset) — from `bioscout.plot.config`
- [`bioscout.plot.resolve`](bioscout.plot.config.md#resolve) — from `bioscout.plot.config`
- [`bioscout.plot.settings`](bioscout.plot.config.md#settings) — from `bioscout.plot.config`
- [`bioscout.plot.using`](bioscout.plot.config.md#using) — from `bioscout.plot.config`
- [`bioscout.plot.KEYS`](bioscout.plot.tidy.md#keys) — from `bioscout.plot.tidy`
- [`bioscout.plot.VALUE`](bioscout.plot.tidy.md#value) — from `bioscout.plot.tidy`
- [`bioscout.plot.cells`](bioscout.plot.tidy.md#cells) — from `bioscout.plot.tidy`
- [`bioscout.plot.counts`](bioscout.plot.tidy.md#counts) — from `bioscout.plot.tidy`
- [`bioscout.plot.from_mapping`](bioscout.plot.tidy.md#from_mapping) — from `bioscout.plot.tidy`
- [`bioscout.plot.group_channels`](bioscout.plot.tidy.md#group_channels) — from `bioscout.plot.tidy`
- [`bioscout.plot.levels`](bioscout.plot.tidy.md#levels) — from `bioscout.plot.tidy`
- [`bioscout.plot.read`](bioscout.plot.tidy.md#read) — from `bioscout.plot.tidy`
- [`bioscout.plot.select`](bioscout.plot.tidy.md#select) — from `bioscout.plot.tidy`
- [`bioscout.plot.MUSCLE_GROUPS`](bioscout.plot.work.md#muscle_groups) — from `bioscout.plot.work`
- [`bioscout.plot.MUSCLE_GROUPS_SPLIT`](bioscout.plot.work.md#muscle_groups_split) — from `bioscout.plot.work`
- [`bioscout.plot.PHASES`](bioscout.plot.work.md#phases) — from `bioscout.plot.work`
- [`bioscout.plot.find_trials`](bioscout.plot.work.md#find_trials) — from `bioscout.plot.work`
- [`bioscout.plot.group_of`](bioscout.plot.work.md#group_of) — from `bioscout.plot.work`
- [`bioscout.plot.muscle_work`](bioscout.plot.work.md#muscle_work) — from `bioscout.plot.work`
- [`bioscout.plot.read_sto`](bioscout.plot.work.md#read_sto) — from `bioscout.plot.work`
- [`bioscout.plot.session_records`](bioscout.plot.work.md#session_records) — from `bioscout.plot.work`
- [`bioscout.plot.trial_inputs`](bioscout.plot.work.md#trial_inputs) — from `bioscout.plot.work`
- [`bioscout.plot.work_table`](bioscout.plot.work.md#work_table) — from `bioscout.plot.work`

## Contents

- [`compare`](#compare) — Start a comparison figure from a tidy table (DataFrame, CSV path, list of dicts or nested dict). Extra keywords filter rows immediately::
- [`work_ranks`](#work_ranks) — The ranked muscle-work figure, in one call.
- [`curves`](#curves) — Mean ± SD waveforms, same selection grammar as :func:`work_ranks`.
- [`demo`](#demo) — A synthetic table wired into a finished figure — for checking the install, and for seeing the layout before you have your own numbers.

### `compare`

```python
compare(data=None, **filters)
```

| input | type | default |
|---|---|---|
| `data` | – | `None` |
| `**filters` | – | – |

Start a comparison figure from a tidy table (DataFrame, CSV path,  
list of dicts or nested dict). Extra keywords filter rows immediately::

    bs.plot.compare("results/master_results.csv", Variable="work")

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/__init__.py#L58)</sub>

### `work_ranks`

```python
work_ranks(
    source,
    compare_by='Condition',
    facet_by='Task',
    where=None,
    group=MUSCLE_GROUPS,
    title=None,
    save=None,
    icons=None,
    order=None,
    facet_order=None,
    **style
)
```

| input | type | default |
|---|---|---|
| `source` | – | required |
| `compare_by` | – | `'Condition'` |
| `facet_by` | – | `'Task'` |
| `where` | – | `None` |
| `group` | – | `MUSCLE_GROUPS` |
| `title` | – | `None` |
| `save` | – | `None` |
| `icons` | – | `None` |
| `order` | – | `None` |
| `facet_order` | – | `None` |
| `**style` | – | – |

The ranked muscle-work figure, in one call.

``source`` is a tidy table — usually one built by :func:`work_table`. This  
is a thin convenience over the builder; reach for the builder the moment  
you want anything it does not expose::

    bs.plot.work_ranks(rows, compare_by="Condition", facet_by="Task",  
                       where={"Algo": "SO"}, top=8,  
                       save="results/group/work_ranks.png")

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/__init__.py#L67)</sub>

### `curves`

```python
curves(source, compare_by, facet_by=None, x='Percent', **kw)
```

| input | type | default |
|---|---|---|
| `source` | – | required |
| `compare_by` | – | required |
| `facet_by` | – | `None` |
| `x` | – | `'Percent'` |
| `**kw` | – | – |

Mean ± SD waveforms, same selection grammar as :func:`work_ranks`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/__init__.py#L97)</sub>

### `demo`

```python
demo(seed=0)
```

| input | type | default |
|---|---|---|
| `seed` | – | `0` |

A synthetic table wired into a finished figure — for checking the  
install, and for seeing the layout before you have your own numbers.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/__init__.py#L105)</sub>
