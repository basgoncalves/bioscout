# `bioscout.plot.tidy`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/tidy.py)

bioscout.plot.tidy — the one table shape every bioscout figure understands.

WHY A TABLE AND NOT A FOLDER WALK  
    Three projects have now grown their own version of the same figure  
    (``FAIS/code/figure_muscle_work.py``, ``FAIS/code/results.py``,  
    ``Powerlifting/results.py``) and each one re-walked ``simulations/`` in its  
    own way. The drawing was never the hard part; agreeing on where the numbers  
    come from was. So the plotting layer here reads exactly one thing — a LONG  
    ("tidy") table, one row per number — and knows nothing about disks,  
    sessions or file layouts.

    That is what makes it generic. A bioscout project builds the table with  
    :func:`bioscout.plot.work_table`; a project with data from anywhere else  
    builds the same columns however it likes, and every figure works unchanged.

THE SHAPE  
    One row per number. One column, ``Value``, holds it. Everything else is a  
    KEY that describes that number:

        Value     the number                                       (required)  
        Channel   what is being ranked / plotted — a muscle group  (usual item)  
        Task      running, cutting, squat …  
        Condition pre-fatigue / post-fatigue, control/patient, …  
        Subject Session Iteration Trial Side Algo Model Variable Metric

    None of the key columns are required and none are special-cased: you tell a  
    figure which column to compare across and which to facet by, and any column  
    present can play either role. ``Variable``/``Metric`` are the convention for  
    "which quantity is this" (``work`` / ``work_J``) so several quantities can  
    share one table — that is how the FAIS and Powerlifting master tables are  
    already built, and both drop straight in.

TIME SERIES LIVE HERE TOO  
    Add an ``x`` column (``Percent``, ``Time``, whatever you name it) and each  
    row becomes one sample of a curve rather than one summary number. The same  
    selection machinery then feeds the curve renderer. No second schema.

## Contents

- [`read`](#read) — Anything you might have -> a tidy DataFrame.
- [`from_mapping`](#from_mapping) — A nested dict -> a tidy table, for when the numbers are already in hand.
- [`select`](#select) — Filter rows. Each value may be a scalar, a list/tuple/set of allowed values, or a callable predicate::
- [`levels`](#levels) — The distinct values of ``col``, in ``order`` if given (unknown names in ``order`` are dropped, values missing from it are appended in the order they appear — so a partial order is a nudge, not a filter).
- [`cells`](#cells) — The table, reduced to what a comparison figure actually draws.
- [`counts`](#counts) — ``{(facet, compare): n}`` — how many distinct ``over`` values back each panel. Figures print this as ``n=…``; a panel drawn from one trial and a panel drawn from twelve should not look identical.
- [`group_channels`](#group_channels) — Collapse individual muscles into functional groups.

### `read`

```python
read(source, **filters)
```

| input | type | default |
|---|---|---|
| `source` | – | required |
| `**filters` | – | – |

Anything you might have -> a tidy DataFrame.

Accepts a DataFrame (returned as-is), a path to a ``.csv`` / ``.csv.gz``,  
a list of row-dicts, or a nested dict (see :func:`from_mapping`).  
``**filters`` are applied through :func:`select` on the way out, so  
``read(master, Variable="work", Algo="SO")`` is the whole preamble of every  
figure in one line.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/tidy.py#L56)</sub>

### `from_mapping`

```python
from_mapping(data, levels=None, item='Channel', value=VALUE)
```

| input | type | default |
|---|---|---|
| `data` | – | required |
| `levels` | – | `None` |
| `item` | – | `'Channel'` |
| `value` | – | `VALUE` |

A nested dict -> a tidy table, for when the numbers are already in hand.

Depth decides the columns, so all three of these work::

    {"Vasti": 12.0, "Hamstrings": 9.1}                     -> Channel, Value  
    {"pre": {...}, "post": {...}}                -> Condition, Channel, Value  
    {"run": {"pre": {...}, "post": {...}}} -> Task, Condition, Channel, Value

``levels`` names the outer levels explicitly (outermost first) when the  
defaults — ``("Task", "Condition")`` — are not what they are.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/tidy.py#L88)</sub>

### `select`

```python
select(df, **filters)
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `**filters` | – | – |

Filter rows. Each value may be a scalar, a list/tuple/set of allowed  
values, or a callable predicate::

    select(df, Variable="work", Algo=["SO", "CEINMS"],  
           Side=lambda s: str(s).endswith("_r"))

An unknown column raises rather than being ignored: a filter that silently  
does nothing is a figure that quietly plots the wrong rows.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/tidy.py#L129)</sub>

### `levels`

```python
levels(df, col, order=None)
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `col` | – | required |
| `order` | – | `None` |

The distinct values of ``col``, in ``order`` if given (unknown names in  
``order`` are dropped, values missing from it are appended in the order  
they appear — so a partial order is a nudge, not a filter).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/tidy.py#L154)</sub>

### `cells`

```python
cells(
    df,
    compare,
    item='Channel',
    value=VALUE,
    facet=None,
    agg='mean',
    compare_order=None,
    facet_order=None
)
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `compare` | – | required |
| `item` | – | `'Channel'` |
| `value` | – | `VALUE` |
| `facet` | – | `None` |
| `agg` | – | `'mean'` |
| `compare_order` | – | `None` |
| `facet_order` | – | `None` |

The table, reduced to what a comparison figure actually draws.

-> ``{facet_value: [(compare_label, {item: number}), ...]}``, columns in  
``compare_order``, rows in ``facet_order``. With no ``facet``, the single  
key is ``None``.

``agg`` collapses everything the figure is NOT splitting on (trials, sides,  
repetitions, subjects) — ``"mean"`` by default, because the question a rank  
figure asks is about the condition, not about one trial. Pass ``"sum"`` for  
quantities that add across limbs, or any name pandas' ``groupby`` accepts.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/tidy.py#L165)</sub>

### `counts`

```python
counts(df, compare, facet=None, over='Trial')
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `compare` | – | required |
| `facet` | – | `None` |
| `over` | – | `'Trial'` |

``{(facet, compare): n}`` — how many distinct ``over`` values back each  
panel. Figures print this as ``n=…``; a panel drawn from one trial and a  
panel drawn from twelve should not look identical.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/tidy.py#L199)</sub>

### `group_channels`

```python
group_channels(
    df,
    mapping,
    item='Channel',
    value=VALUE,
    agg='sum',
    keep_unmapped=False,
    strip_side=True
)
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `mapping` | – | required |
| `item` | – | `'Channel'` |
| `value` | – | `VALUE` |
| `agg` | – | `'sum'` |
| `keep_unmapped` | – | `False` |
| `strip_side` | – | `True` |

Collapse individual muscles into functional groups.

Ranking raw muscle names lets a three-compartment gluteus maximus be beaten  
by an intact peroneus longus purely because its force was split three ways  
— an artefact of the model's discretisation, not a statement about the leg.  
``mapping`` is ``{group: (member, ...)}``; unmapped channels are dropped  
unless ``keep_unmapped``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/tidy.py#L213)</sub>
