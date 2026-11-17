# `bioscout.plot.config`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/config.py)

bioscout.plot.config — figure settings that live IN bioscout, not in a project.

The rule this module exists to enforce: **a project should not need its own  
copy of anything to draw a figure.** Every knob has a defensible default here,  
and a notebook overrides the ones it cares about at run time::

    import bioscout as bs  
    bs.plot.configure(dpi=300, top=8, style="delta")

    with bs.plot.using(dpi=600, save_pdf=True):     # temporary, for one export  
        fig.save("results/figure_3.png")

Nothing reads a project ``settings.py``. If a project *wants* to pin its own  
look it does so by calling ``configure()`` once at the top of its script or  
notebook — which is the same mechanism, written down in the project rather than  
copied into it.

Precedence, lowest to highest:

1. the defaults in :class:`PlotConfig` below  
2. whatever ``configure()`` has been given in this process  
3. keyword arguments passed to the individual plotting call

so any single figure can always break the house style without changing it.

## Contents

- class [`PlotConfig`](#plotconfig) — Every knob the plotting layer has. All optional, all overridable.
  - [`PlotConfig.merged`](#plotconfigmerged) — A copy with ``kw`` applied. Unknown keys raise — a silently ignored ``dpi=600`` is a figure that went to a journal at 200 dpi.
- [`settings`](#settings) — The settings in force right now.
- [`configure`](#configure) — Change the house style for the rest of this process. Returns the new config so a notebook cell shows what it did.
- [`reset`](#reset) — Back to the bioscout defaults.
- [`using`](#using) — Temporary settings::
- [`resolve`](#resolve) — The active settings with per-call overrides applied. ``None`` values are dropped, so a plotting function can forward every one of its keyword arguments without having to know which were actually given.

<a id="plotconfig"></a>

## class `PlotConfig`

Every knob the plotting layer has. All optional, all overridable.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/config.py#L33)</sub>

<a id="plotconfigmerged"></a>

### `PlotConfig.merged`

```python
PlotConfig.merged(**kw)
```

| input | type | default |
|---|---|---|
| `**kw` | – | – |

A copy with ``kw`` applied. Unknown keys raise — a silently ignored  
``dpi=600`` is a figure that went to a journal at 200 dpi.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/config.py#L92)</sub>

### `settings`

```python
settings() -> PlotConfig
```

**returns** `PlotConfig`

The settings in force right now.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/config.py#L109)</sub>

### `configure`

```python
configure(**kw) -> PlotConfig
```

| input | type | default |
|---|---|---|
| `**kw` | – | – |

**returns** `PlotConfig`

Change the house style for the rest of this process. Returns the new  
config so a notebook cell shows what it did.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/config.py#L114)</sub>

### `reset`

```python
reset() -> PlotConfig
```

**returns** `PlotConfig`

Back to the bioscout defaults.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/config.py#L122)</sub>

### `using`

```python
using(**kw)
```

| input | type | default |
|---|---|---|
| `**kw` | – | – |

Temporary settings::

with bs.plot.using(dpi=600, save_pdf=True):  
    ...

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/config.py#L130)</sub>

### `resolve`

```python
resolve(**kw) -> PlotConfig
```

| input | type | default |
|---|---|---|
| `**kw` | – | – |

**returns** `PlotConfig`

The active settings with per-call overrides applied. ``None`` values are  
dropped, so a plotting function can forward every one of its keyword  
arguments without having to know which were actually given.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/plot/config.py#L145)</sub>
