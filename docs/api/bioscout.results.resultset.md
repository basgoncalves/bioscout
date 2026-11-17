# `bioscout.results.resultset`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py)

ResultSet: one result variable across any number of sessions, iterations,  
trials and cycles -- a DataFrame with a few helpers, extensible with actions.

    rs = sess.results("so_forces", trial="Gehen*", var="*_r")  
    rs.df                         # the data: ID columns + x ('time' or 'pct') + one column per channel  
    rs["vasmed_r"]                # x  x  curves  (one column per iteration/trial/cycle)  
    rs.where(iteration="gpkv4")   # filter (names, lists or globs on any ID column)  
    rs.to_bw().plot()             # actions chain

Add an action (in bioscout, a project, or a notebook)::

    from bioscout.results import action

    @action  
    def co_contraction(rs, a="vasmed_r", b="bflh_r"):  
        ...  
    rs.co_contraction()

## Contents

- class [`ResultSet`](#resultset) — 
  - [`ResultSet.x`](#resultsetx) — 'pct' for time-normalised data, else 'time'.
  - [`ResultSet.vars`](#resultsetvars) — 
  - [`ResultSet.ids`](#resultsetids) — One row per curve.
  - [`ResultSet.varying`](#resultsetvarying) — ID columns that differ between curves (what a legend needs).
  - [`ResultSet.info`](#resultsetinfo) — 
  - [`ResultSet.where`](#resultsetwhere) — Keep curves whose ID columns match (a name, list or glob each).
  - [`ResultSet.select`](#resultsetselect) — Keep channels (names or globs).
  - [`ResultSet.curves`](#resultsetcurves) — x as index, one column per curve (labelled by the ID columns that vary).
  - [`ResultSet.long`](#resultsetlong) — One value per row (ID columns, x, channel, value) -- bioscout.plot.tidy shape.
  - [`ResultSet.plot`](#resultsetplot) — One subplot per channel, one line per ``by`` group (mean +- SD on normalised data). Returns a Plot (``.savefig``, ``.axes``, ``.fig``). ``layout="stack"``: the channels stacked in one axes (IAA contributions).
  - [`ResultSet.mean`](#resultsetmean) — Mean (or SD) curve per ``by`` group.
  - [`ResultSet.to_bw`](#resultsetto_bw) — Every channel divided by its session's body weight.
  - [`ResultSet.peak`](#resultsetpeak) — One row per curve: 'max', 'min' or 'abs' peak of every channel.
  - [`ResultSet.at`](#resultsetat) — Every channel at x (percent or seconds), one row per curve.
  - [`ResultSet.stats`](#resultsetstats) — max / min / mean of every curve and channel.
  - [`ResultSet.actions`](#resultsetactions) — Every action and its first docstring line.
- class [`ResultSets`](#resultsets) — {variable: ResultSet}. Actions run on every member::
  - [`ResultSets.plot`](#resultsetsplot) — All files at once. ``layout``: "figures" (one per file), "rows" (one figure, a row per file) or "overlay" (one axes per channel, a colour per file; a different unit gets a second y axis)::
- [`action`](#action) — Register ``fn(rs, ...)`` as ``ResultSet.<name>(...)`` (and on ResultSets, where it runs on every member).

<a id="resultset"></a>

## class `ResultSet`

```python
ResultSet(
    df: pd.DataFrame,
    variable: str,
    infos=(),
    window='trial',
    index: Optional[pd.DataFrame] = None,
    errors=(),
    unit=None
)
```

| input | type | default |
|---|---|---|
| `df` | pd.DataFrame | required |
| `variable` | str | required |
| `infos` | – | `()` |
| `window` | – | `'trial'` |
| `index` | Optional[pd.DataFrame] | `None` |
| `errors` | – | `()` |
| `unit` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L48)</sub>

<a id="resultsetx"></a>

### `ResultSet.x`

```python
ResultSet.x() -> str
```

**returns** `str`

'pct' for time-normalised data, else 'time'.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L62)</sub>

<a id="resultsetvars"></a>

### `ResultSet.vars`

```python
ResultSet.vars() -> List[str]
```

**returns** `List[str]`

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L67)</sub>

<a id="resultsetids"></a>

### `ResultSet.ids`

```python
ResultSet.ids() -> pd.DataFrame
```

**returns** `pd.DataFrame`

One row per curve.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L71)</sub>

<a id="resultsetvarying"></a>

### `ResultSet.varying`

```python
ResultSet.varying() -> List[str]
```

**returns** `List[str]`

ID columns that differ between curves (what a legend needs).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L76)</sub>

<a id="resultsetinfo"></a>

### `ResultSet.info`

```python
ResultSet.info(subject, session)
```

| input | type | default |
|---|---|---|
| `subject` | – | required |
| `session` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L84)</sub>

<a id="resultsetwhere"></a>

### `ResultSet.where`

```python
ResultSet.where(**ids) -> 'ResultSet'
```

| input | type | default |
|---|---|---|
| `**ids` | – | – |

**returns** `'ResultSet'`

Keep curves whose ID columns match (a name, list or glob each).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L94)</sub>

<a id="resultsetselect"></a>

### `ResultSet.select`

```python
ResultSet.select(var) -> 'ResultSet'
```

| input | type | default |
|---|---|---|
| `var` | – | required |

**returns** `'ResultSet'`

Keep channels (names or globs).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L105)</sub>

<a id="resultsetcurves"></a>

### `ResultSet.curves`

```python
ResultSet.curves(var: str) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `var` | str | required |

**returns** `pd.DataFrame`

x as index, one column per curve (labelled by the ID columns that vary).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L120)</sub>

<a id="resultsetlong"></a>

### `ResultSet.long`

```python
ResultSet.long() -> pd.DataFrame
```

**returns** `pd.DataFrame`

One value per row (ID columns, x, channel, value) -- bioscout.plot.tidy shape.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L125)</sub>

<a id="resultsetplot"></a>

### `ResultSet.plot`

```python
ResultSet.plot(
    var=None,
    by='iteration',
    mean=True,
    ncols=3,
    title=None,
    save=None,
    layout=None,
    group=True,
    top=8,
    bw=None,
    **where
)
```

| input | type | default |
|---|---|---|
| `var` | – | `None` |
| `by` | – | `'iteration'` |
| `mean` | – | `True` |
| `ncols` | – | `3` |
| `title` | – | `None` |
| `save` | – | `None` |
| `layout` | – | `None` |
| `group` | – | `True` |
| `top` | – | `8` |
| `bw` | – | `None` |
| `**where` | – | – |

One subplot per channel, one line per ``by`` group (mean +- SD on  
normalised data). Returns a Plot (``.savefig``, ``.axes``, ``.fig``).  
``layout="stack"``: the channels stacked in one axes (IAA contributions).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L150)</sub>

<a id="resultsetmean"></a>

### `ResultSet.mean`

```python
ResultSet.mean(by='iteration', sd=False) -> 'ResultSet'
```

| input | type | default |
|---|---|---|
| `by` | – | `'iteration'` |
| `sd` | – | `False` |

**returns** `'ResultSet'`

Mean (or SD) curve per ``by`` group.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L163)</sub>

<a id="resultsetto_bw"></a>

### `ResultSet.to_bw`

```python
ResultSet.to_bw() -> 'ResultSet'
```

**returns** `'ResultSet'`

Every channel divided by its session's body weight.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L167)</sub>

<a id="resultsetpeak"></a>

### `ResultSet.peak`

```python
ResultSet.peak(how='max') -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `how` | – | `'max'` |

**returns** `pd.DataFrame`

One row per curve: 'max', 'min' or 'abs' peak of every channel.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L171)</sub>

<a id="resultsetat"></a>

### `ResultSet.at`

```python
ResultSet.at(x: float) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `x` | float | required |

**returns** `pd.DataFrame`

Every channel at x (percent or seconds), one row per curve.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L175)</sub>

<a id="resultsetstats"></a>

### `ResultSet.stats`

```python
ResultSet.stats() -> pd.DataFrame
```

**returns** `pd.DataFrame`

max / min / mean of every curve and channel.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L179)</sub>

<a id="resultsetactions"></a>

### `ResultSet.actions`

```python
ResultSet.actions()
```

Every action and its first docstring line.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L193)</sub>

<a id="resultsets"></a>

## class `ResultSets`(dict)

{variable: ResultSet}. Actions run on every member::

r = sess.results(["ik", "id"], trial="Gehen_01")  
r["joint_angles"].plot()  
r.to_bw()                   # -> ResultSets

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L198)</sub>

<a id="resultsetsplot"></a>

### `ResultSets.plot`

```python
ResultSets.plot(
    var=None,
    layout='figures',
    by='iteration',
    mean=True,
    ncols=3,
    title=None,
    save=None,
    group=True,
    top=8,
    bw=None,
    **where
)
```

| input | type | default |
|---|---|---|
| `var` | – | `None` |
| `layout` | – | `'figures'` |
| `by` | – | `'iteration'` |
| `mean` | – | `True` |
| `ncols` | – | `3` |
| `title` | – | `None` |
| `save` | – | `None` |
| `group` | – | `True` |
| `top` | – | `8` |
| `bw` | – | `None` |
| `**where` | – | – |

All files at once. ``layout``: "figures" (one per file), "rows" (one  
figure, a row per file) or "overlay" (one axes per channel, a colour per  
file; a different unit gets a second y axis)::

    r = sess.results(["so_forces", "so_activations"], trial="Walking_01")  
    r.plot(var="vasmed*", layout="overlay")

    iaa = sess.results("iaa_opensim/*_Y", trial="Walking_01")  
    iaa.plot(layout="stack")              # IAA: contributions stacked per target

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L213)</sub>

### `action`

```python
action(fn=None, name=None)
```

| input | type | default |
|---|---|---|
| `fn` | – | `None` |
| `name` | – | `None` |

Register ``fn(rs, ...)`` as ``ResultSet.<name>(...)`` (and on ResultSets,  
where it runs on every member).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/resultset.py#L39)</sub>
