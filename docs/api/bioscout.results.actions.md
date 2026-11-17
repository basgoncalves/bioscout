# `bioscout.results.actions`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/actions.py)

Built-in ResultSet actions. Each is a plain function ``f(rs, ...)``  
registered with :func:`bioscout.results.action` -- copy one to write your own.

## Contents

- [`to_bw`](#to_bw) — Divide every channel by body weight (session.yaml body_mass * 9.81) of each curve's own session.
- [`mean`](#mean) — Mean curve per group (``by`` = ID column(s)); the other ID columns become 'mean' (or 'sd' with ``sd=True``). Needs a shared x: use a normalised window (window='cycle'/'stance', or normalise=True).
- [`peak`](#peak) — One row per curve, one column per channel: 'max', 'min' or 'abs' peak.
- [`at`](#at) — Value of every channel at x (percent or seconds), one row per curve.
- [`stats`](#stats) — max / min / mean of every curve and channel, long format.
- [`plot`](#plot) — One subplot per channel; one line (mean +- SD when several curves) per ``by`` group (mean +- SD only on time-normalised data). Shown inline in a notebook, once; written only when ``save=`` is given. Returns a Plot: ``p.savefig(...)``, ``p.axes``, ``p.fig`` (the matplotlib Figure).

### `to_bw`

```python
to_bw(rs: ResultSet) -> ResultSet
```

| input | type | default |
|---|---|---|
| `rs` | ResultSet | required |

**returns** `ResultSet`

Divide every channel by body weight (session.yaml body_mass * 9.81) of  
each curve's own session.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/actions.py#L22)</sub>

### `mean`

```python
mean(rs: ResultSet, by='iteration', sd=False) -> ResultSet
```

| input | type | default |
|---|---|---|
| `rs` | ResultSet | required |
| `by` | – | `'iteration'` |
| `sd` | – | `False` |

**returns** `ResultSet`

Mean curve per group (``by`` = ID column(s)); the other ID columns become  
'mean' (or 'sd' with ``sd=True``). Needs a shared x: use a normalised  
window (window='cycle'/'stance', or normalise=True).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/actions.py#L36)</sub>

### `peak`

```python
peak(rs: ResultSet, how='max') -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `rs` | ResultSet | required |
| `how` | – | `'max'` |

**returns** `pd.DataFrame`

One row per curve, one column per channel: 'max', 'min' or 'abs' peak.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/actions.py#L64)</sub>

### `at`

```python
at(rs: ResultSet, x: float) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `rs` | ResultSet | required |
| `x` | float | required |

**returns** `pd.DataFrame`

Value of every channel at x (percent or seconds), one row per curve.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/actions.py#L72)</sub>

### `stats`

```python
stats(rs: ResultSet) -> pd.DataFrame
```

| input | type | default |
|---|---|---|
| `rs` | ResultSet | required |

**returns** `pd.DataFrame`

max / min / mean of every curve and channel, long format.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/actions.py#L82)</sub>

### `plot`

```python
plot(
    rs: ResultSet,
    var=None,
    by='iteration',
    mean=True,
    ncols=3,
    title=None,
    save=None,
    **where
)
```

| input | type | default |
|---|---|---|
| `rs` | ResultSet | required |
| `var` | – | `None` |
| `by` | – | `'iteration'` |
| `mean` | – | `True` |
| `ncols` | – | `3` |
| `title` | – | `None` |
| `save` | – | `None` |
| `**where` | – | – |

One subplot per channel; one line (mean +- SD when several curves) per  
``by`` group (mean +- SD only on time-normalised data). Shown inline in a  
notebook, once; written only when ``save=`` is given. Returns a Plot:  
``p.savefig(...)``, ``p.axes``, ``p.fig`` (the matplotlib Figure).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/results/actions.py#L90)</sub>
