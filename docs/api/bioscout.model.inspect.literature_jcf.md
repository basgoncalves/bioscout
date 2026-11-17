# `bioscout.model.inspect.literature_jcf`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/literature_jcf.py)

Literature joint-contact-force / muscle-force curves for validation overlays.

Reads the tidy long-form ``literature/literature_curves.csv`` (digitized from  
Bergmann 2001, Giarmatzis 2015, Hoang, Pandy 2021) and exposes helpers to:

  * pull a study's mean / band (lower-upper) waveform for a given variable,  
    entity (joint or muscle group) and condition, and  
  * overlay those bands onto an existing matplotlib axis -- e.g. the pipeline's  
    joint-contact-force figure -- by mapping % gait cycle onto the plotted  
    time window.

All y-values are returned in **multiples of body weight (xBW)** so they line up  
with a model joint-reaction resultant normalized to body weight. Sources stored  
in ``%BW`` are divided by 100; ``normalized`` muscle forces are left as-is.

CSV columns: source, variable, entity, condition, series, x, y, x_unit, y_unit  
  variable : "hip_contact_force" | "muscle_force"  
  entity   : "hip" | muscle group (GAS, GMAX, GMED, HAMS, IP, RF, SOL, VAS)  
  series   : "mean" | "lower" | "upper" | "curve" | "peak"  
  x        : % gait cycle (0-100)

## Contents

- [`variable_for_entity`](#variable_for_entity) — CSV ``variable`` name for a joint entity (default ``<entity>_contact_force``).
- [`load_curves`](#load_curves) — Load the literature curves CSV into a DataFrame (xBW-normalized ``y_xbw``).
- [`available`](#available) — Summarize what is in the CSV: {variable: {entity: {source: [conditions]}}}.
- [`get_series`](#get_series) — Return {(source, condition): {series_name: (x, y_xbw)}} matching the filters.
- [`overlay_joint_contact_force`](#overlay_joint_contact_force) — Overlay literature contact-force bands on an existing axis.
- [`plot_jcf_validation`](#plot_jcf_validation) — Standalone literature joint-contact-force reference figure.

### `variable_for_entity`

```python
variable_for_entity(entity)
```

| input | type | default |
|---|---|---|
| `entity` | – | required |

CSV ``variable`` name for a joint entity (default ``<entity>_contact_force``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/literature_jcf.py#L71)</sub>

### `load_curves`

```python
load_curves(csv_path=None)
```

| input | type | default |
|---|---|---|
| `csv_path` | – | `None` |

Load the literature curves CSV into a DataFrame (xBW-normalized ``y_xbw``).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/literature_jcf.py#L84)</sub>

### `available`

```python
available(df=None)
```

| input | type | default |
|---|---|---|
| `df` | – | `None` |

Summarize what is in the CSV: {variable: {entity: {source: [conditions]}}}.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/literature_jcf.py#L100)</sub>

### `get_series`

```python
get_series(df, variable, entity, source=None, condition=None)
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `variable` | – | required |
| `entity` | – | required |
| `source` | – | `None` |
| `condition` | – | `None` |

Return {(source, condition): {series_name: (x, y_xbw)}} matching the filters.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/literature_jcf.py#L110)</sub>

### `overlay_joint_contact_force`

```python
overlay_joint_contact_force(
    ax,
    entity='hip',
    df=None,
    sources=None,
    condition=None,
    gait_window=None,
    stance_window=None,
    bands=True,
    label_prefix='',
    central=True,
    band_alpha=0.15,
    line_alpha=0.6,
    line_width=1.8
)
```

| input | type | default |
|---|---|---|
| `ax` | – | required |
| `entity` | – | `'hip'` |
| `df` | – | `None` |
| `sources` | – | `None` |
| `condition` | – | `None` |
| `gait_window` | – | `None` |
| `stance_window` | – | `None` |
| `bands` | – | `True` |
| `label_prefix` | – | `''` |
| `central` | – | `True` |
| `band_alpha` | – | `0.15` |
| `line_alpha` | – | `0.6` |
| `line_width` | – | `1.8` |

Overlay literature contact-force bands on an existing axis.

  
**Parameters**

ax : matplotlib axis whose x-axis is TIME (seconds) over one motion cycle.  
entity : joint entity to overlay (default "hip").  
df : pre-loaded DataFrame (loaded from bundle if None).  
sources : list of study names to include; None -> the walking defaults.  
condition : force a specific condition; None -> per-source walking default.  
gait_window : (t0, t1) time window that maps to 0-100 % gait cycle;  
    None -> the axis' current x-limits.  
bands : draw lower-upper (or mean +/- ) shaded band when available.  
central : draw the central (mean/curve) line. Set False to show only the  
    shaded band (cleaner overlay). Sources with no band fall back to a  
    faint central line so they are not lost.  
band_alpha : transparency of the shaded band.

Returns the list of study labels drawn (for legend handling upstream).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/literature_jcf.py#L139)</sub>

### `plot_jcf_validation`

```python
plot_jcf_validation(
    out_path,
    entity='hip',
    model=None,
    df=None,
    sources=None,
    condition=None,
    title=None
)
```

| input | type | default |
|---|---|---|
| `out_path` | – | required |
| `entity` | – | `'hip'` |
| `model` | – | `None` |
| `df` | – | `None` |
| `sources` | – | `None` |
| `condition` | – | `None` |
| `title` | – | `None` |

Standalone literature joint-contact-force reference figure.

Independent of the pipeline: plots the literature bands (xBW vs % gait cycle)  
for ``entity`` and, if given, overlays a model resultant.

  
**Parameters**

out_path : where to save the PNG.  
model : optional ``(x_pct, y_xbw)`` model curve already expressed in  
    % gait cycle and multiples of body weight.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/literature_jcf.py#L225)</sub>
