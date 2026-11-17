# `bioscout.plot.compare`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py)

bioscout.plot.compare — one comparison figure, any two things.

The figure this generalises has been rebuilt three times in three projects, and  
each time the only thing that really changed was WHAT the two columns were:

    Powerlifting   columns = generic models,   rows = algorithm  
    FAIS (subject) columns = task,             rows = pre- / post-fatigue  
    FAIS (group)   columns = pre- / post-,     rows = task

So the columns and the rows are arguments, not code::

    import bioscout as bs

    (bs.plot.compare("results/master_results.csv")  
        .where(Variable="muscle_work_total", Algo="SO")  
        .compare("Condition", order=["pre-fatigue", "post-fatigue"])  
        .facet("Task")  
        .top(8)  
        .title("total muscle work ranks")  
        .save("results/group/work_ranks.png"))

Swap ``.compare("Condition")`` for ``.compare("Task")`` and the same table  
answers "which muscles change between TASKS" instead. Swap it for  
``.compare("Algo")`` and it answers "does the algorithm reorder the leg".  
Nothing about the figure is specific to fatigue, to tasks, or to muscle work —  
it ranks whatever is in the ``Channel`` column by whatever is in ``Value``.

TWO RENDERERS ON ONE SELECTION  
    ``.ranks()``   ranked horizontal bars, colour anchored on the first column  
    ``.curves()``  mean ± SD waveforms, one line per compared level

    Both read the same tidy table and the same ``.where/.compare/.facet``  
    selection, which is the point: the pipeline from data to figure is written  
    once.

READING A RANK FIGURE  
    Bar colour is the item's rank in the FIRST compared column, carried into  
    every column to its right. The left panel is therefore always a clean  
    dark-to-pale ramp by construction, and ANY colour disorder further right is  
    a re-ranking — no tracing of lines required. ▲/▼ after a label gives the  
    places gained or lost, and ``style="connector"`` draws the arrows from  
    Collings et al. (2025) instead (see ``bioscout.plot.collings`` for the  
    fixed published layout).

    With ``normalise="reference"`` (the default) every panel in a row is scaled  
    to the leader of the first column, so a panel that shrinks did less work  
    and a bar may legitimately pass 100 %. ``normalise="panel"`` scales each  
    panel to its own leader: that is a pure ranking with the magnitudes thrown  
    away, which is sometimes what you want and is never what you want by  
    accident.

## Contents

- class [`Compare`](#compare) — A comparison figure, built up a clause at a time.
  - [`Compare.data`](#comparedata) — Replace the table.
  - [`Compare.where`](#comparewhere) — Keep only matching rows. Scalars, lists and callables all work::
  - [`Compare.item`](#compareitem) — Which column names the things being ranked/drawn (default ``Channel``).
  - [`Compare.value`](#comparevalue) — Which column holds the number (default ``Value``).
  - [`Compare.group`](#comparegroup) — Collapse the item column into functional groups before ranking. ``mapping`` is ``{group: (member, ...)}`` — see :data:`bioscout.plot.MUSCLE_GROUPS`.
  - [`Compare.agg`](#compareagg) — How to collapse everything the figure is not splitting on — ``"mean"`` (default), ``"sum"``, ``"median"``, ``"max"``…
  - [`Compare.compare`](#comparecompare) — The column that becomes the panels side by side. ``order`` fixes their left-to-right order (and therefore which one anchors the colour); ``labels`` is an optional ``{value: heading}`` rename.
  - [`Compare.facet`](#comparefacet) — The column that becomes the stacked rows. ``icons`` may be a ``{value: image path}`` map or a callable, drawn in a strip on the left.
  - [`Compare.icons`](#compareicons) — Row icons: ``{facet value: image path}`` or a callable.
  - [`Compare.panels`](#comparepanels) — Curves only — the column that becomes the columns of panels (defaults to the item column, i.e. one panel per channel).
  - [`Compare.top`](#comparetop) — 
  - [`Compare.style`](#comparestyle) — ``"delta"`` (▲/▼ markers), ``"connector"`` (arrows), ``"both"``.
  - [`Compare.normalise`](#comparenormalise) — ``"reference"`` or ``"panel"`` — see the module docstring.
  - [`Compare.set`](#compareset) — Any :class:`bioscout.plot.PlotConfig` field, for this figure only::
  - [`Compare.title`](#comparetitle) — 
  - [`Compare.note`](#comparenote) — A footnote under the figure. ``None`` restores the default legend text, ``""`` removes it.
  - [`Compare.labels`](#comparelabels) — 
  - [`Compare.count_over`](#comparecount_over) — Print ``n=…`` on each panel, counting distinct values of ``col``. Off by default — but a panel drawn from one trial and a panel drawn from twelve should not look identical, so turn it on for anything anyone else will read.
  - [`Compare.ranks`](#compareranks) — Choose the ranked-bar renderer (and optionally set style keys).
  - [`Compare.curves`](#comparecurves) — Choose the mean ± SD waveform renderer. ``x`` names the column that holds the cycle axis (default ``Percent``); the data is expected to be time-normalised already — this draws what it is given.
  - [`Compare.draw`](#comparedraw) — Build the matplotlib Figure (cached; ``force=True`` redraws).
  - [`Compare.save`](#comparesave) — Draw if needed and write the file. Makes parent folders, honours ``save_pdf``, returns the path written.
  - [`Compare.show`](#compareshow) — 
  - [`Compare.close`](#compareclose) — 
  - [`Compare.table`](#comparetable) — The reduced numbers the figure will draw — ``{row: [(column, {item: value}), ...]}``. Print this when a panel looks wrong; it is much faster than reading the picture.

<a id="compare"></a>

## class `Compare`

```python
Compare(data=None, **filters)
```

| input | type | default |
|---|---|---|
| `data` | – | `None` |
| `**filters` | – | – |

A comparison figure, built up a clause at a time.

Every method returns a NEW ``Compare`` — chains are safe to branch::

    base = bs.plot.compare(df).facet("Task").top(8)  
    base.compare("Condition").save("by_fatigue.png")  
    base.compare("Algo").save("by_algorithm.png")

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L119)</sub>

<a id="comparedata"></a>

### `Compare.data`

```python
Compare.data(source, **filters)
```

| input | type | default |
|---|---|---|
| `source` | – | required |
| `**filters` | – | – |

Replace the table.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L174)</sub>

<a id="comparewhere"></a>

### `Compare.where`

```python
Compare.where(**filters)
```

| input | type | default |
|---|---|---|
| `**filters` | – | – |

Keep only matching rows. Scalars, lists and callables all work::

.where(Variable="muscle_work_total", Algo="SO",  
       Side=lambda s: s == "_r")

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L178)</sub>

<a id="compareitem"></a>

### `Compare.item`

```python
Compare.item(col)
```

| input | type | default |
|---|---|---|
| `col` | – | required |

Which column names the things being ranked/drawn (default  
``Channel``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L188)</sub>

<a id="comparevalue"></a>

### `Compare.value`

```python
Compare.value(col)
```

| input | type | default |
|---|---|---|
| `col` | – | required |

Which column holds the number (default ``Value``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L193)</sub>

<a id="comparegroup"></a>

### `Compare.group`

```python
Compare.group(mapping, keep_unmapped=False)
```

| input | type | default |
|---|---|---|
| `mapping` | – | required |
| `keep_unmapped` | – | `False` |

Collapse the item column into functional groups before ranking.  
``mapping`` is ``{group: (member, ...)}`` — see  
:data:`bioscout.plot.MUSCLE_GROUPS`.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L197)</sub>

<a id="compareagg"></a>

### `Compare.agg`

```python
Compare.agg(how)
```

| input | type | default |
|---|---|---|
| `how` | – | required |

How to collapse everything the figure is not splitting on —  
``"mean"`` (default), ``"sum"``, ``"median"``, ``"max"``…

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L203)</sub>

<a id="comparecompare"></a>

### `Compare.compare`

```python
Compare.compare(col, order=None, labels=None)
```

| input | type | default |
|---|---|---|
| `col` | – | required |
| `order` | – | `None` |
| `labels` | – | `None` |

The column that becomes the panels side by side. ``order`` fixes  
their left-to-right order (and therefore which one anchors the colour);  
``labels`` is an optional ``{value: heading}`` rename.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L209)</sub>

<a id="comparefacet"></a>

### `Compare.facet`

```python
Compare.facet(col, order=None, labels=None, icons=None)
```

| input | type | default |
|---|---|---|
| `col` | – | required |
| `order` | – | `None` |
| `labels` | – | `None` |
| `icons` | – | `None` |

The column that becomes the stacked rows. ``icons`` may be a  
``{value: image path}`` map or a callable, drawn in a strip on the  
left.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L216)</sub>

<a id="compareicons"></a>

### `Compare.icons`

```python
Compare.icons(mapping)
```

| input | type | default |
|---|---|---|
| `mapping` | – | required |

Row icons: ``{facet value: image path}`` or a callable.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L223)</sub>

<a id="comparepanels"></a>

### `Compare.panels`

```python
Compare.panels(col)
```

| input | type | default |
|---|---|---|
| `col` | – | required |

Curves only — the column that becomes the columns of panels  
(defaults to the item column, i.e. one panel per channel).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L227)</sub>

<a id="comparetop"></a>

### `Compare.top`

```python
Compare.top(n)
```

| input | type | default |
|---|---|---|
| `n` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L233)</sub>

<a id="comparestyle"></a>

### `Compare.style`

```python
Compare.style(name)
```

| input | type | default |
|---|---|---|
| `name` | – | required |

``"delta"`` (▲/▼ markers), ``"connector"`` (arrows), ``"both"``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L236)</sub>

<a id="comparenormalise"></a>

### `Compare.normalise`

```python
Compare.normalise(how)
```

| input | type | default |
|---|---|---|
| `how` | – | required |

``"reference"`` or ``"panel"`` — see the module docstring.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L240)</sub>

<a id="compareset"></a>

### `Compare.set`

```python
Compare.set(**kw)
```

| input | type | default |
|---|---|---|
| `**kw` | – | – |

Any :class:`bioscout.plot.PlotConfig` field, for this figure only::

.set(dpi=600, cmap="viridis", panel_w_in=4.2)

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L244)</sub>

<a id="comparetitle"></a>

### `Compare.title`

```python
Compare.title(text)
```

| input | type | default |
|---|---|---|
| `text` | – | required |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L252)</sub>

<a id="comparenote"></a>

### `Compare.note`

```python
Compare.note(text)
```

| input | type | default |
|---|---|---|
| `text` | – | required |

A footnote under the figure. ``None`` restores the default legend  
text, ``""`` removes it.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L255)</sub>

<a id="comparelabels"></a>

### `Compare.labels`

```python
Compare.labels(x=None, y=None)
```

| input | type | default |
|---|---|---|
| `x` | – | `None` |
| `y` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L260)</sub>

<a id="comparecount_over"></a>

### `Compare.count_over`

```python
Compare.count_over(col='Trial')
```

| input | type | default |
|---|---|---|
| `col` | – | `'Trial'` |

Print ``n=…`` on each panel, counting distinct values of ``col``.  
Off by default — but a panel drawn from one trial and a panel drawn  
from twelve should not look identical, so turn it on for anything  
anyone else will read.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L264)</sub>

<a id="compareranks"></a>

### `Compare.ranks`

```python
Compare.ranks(**kw)
```

| input | type | default |
|---|---|---|
| `**kw` | – | – |

Choose the ranked-bar renderer (and optionally set style keys).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L272)</sub>

<a id="comparecurves"></a>

### `Compare.curves`

```python
Compare.curves(x=None, **kw)
```

| input | type | default |
|---|---|---|
| `x` | – | `None` |
| `**kw` | – | – |

Choose the mean ± SD waveform renderer. ``x`` names the column that  
holds the cycle axis (default ``Percent``); the data is expected to be  
time-normalised already — this draws what it is given.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L277)</sub>

<a id="comparedraw"></a>

### `Compare.draw`

```python
Compare.draw(force=False)
```

| input | type | default |
|---|---|---|
| `force` | – | `False` |

Build the matplotlib Figure (cached; ``force=True`` redraws).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L289)</sub>

<a id="comparesave"></a>

### `Compare.save`

```python
Compare.save(path, **kw)
```

| input | type | default |
|---|---|---|
| `path` | – | required |
| `**kw` | – | – |

Draw if needed and write the file. Makes parent folders, honours  
``save_pdf``, returns the path written.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L306)</sub>

<a id="compareshow"></a>

### `Compare.show`

```python
Compare.show()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L324)</sub>

<a id="compareclose"></a>

### `Compare.close`

```python
Compare.close()
```

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L330)</sub>

<a id="comparetable"></a>

### `Compare.table`

```python
Compare.table()
```

The reduced numbers the figure will draw —  
``{row: [(column, {item: value}), ...]}``. Print this when a panel  
looks wrong; it is much faster than reading the picture.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/compare.py#L337)</sub>
