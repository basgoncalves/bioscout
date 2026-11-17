# `bioscout.model.inspect.multi_model`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/multi_model.py)

Compare SEVERAL models against each other and against the literature.

    python -m bioscout.model.inspect compare-models \  
        --models a.osim b.osim c.osim --out report/

Everything else in this package inspects ONE model and writes one folder next  
to it. That is the wrong shape for the question people actually ask -- "is this  
model better than the one we published?" -- which needs every curve on the same  
axes, scored against the same studies, in one place.

WHAT IT WRITES

    discontinuity.csv                 model x muscle x coordinate, flagged or not  
    moment_arm_curves.csv             long format: coordinate, model, muscle,  
                                      angle_deg, moment_arm_mm, source  
    validation_rmse.csv               model x muscle x study: rmse_cm, pct_within_sd  
    fig01_<coord>_vs_literature.png   one coordinate, in detail  
    fig02_moment_arms_all_coordinates.png   every coordinate, models overlaid  
    fig03_validate_<coord>.png        per moment DOF: panels of muscle x study

BOTH HALVES, ON PURPOSE  
    The discontinuity screen and the literature comparison answer different  
    questions and disagree usefully. A path can be perfectly smooth and 20 mm  
    from every published curve, or sit inside the SD band and still step 6 mm  
    between two frames. Reporting one without the other is how a model gets  
    called "validated" on the half that happened to pass.

SIGNS AND UNITS  
    The corpus is SIGNED and in CENTIMETRES, using the models' own convention.  
    Curves are plotted signed with a zero line, because a moment arm crossing  
    zero is a muscle reversing its action -- the single most important thing a  
    plot of this kind can show, and invisible if magnitudes are used.

## Contents

- [`model_styles`](#model_styles) — {label: (colour, linestyle)} — one hue per family, style within it.
- [`screen_discontinuity`](#screen_discontinuity) — {label: set(flagged muscles)} plus a csv. The original screen, per model.
- [`compare_models`](#compare_models) — The whole report. Returns the list of files written.
- [`main`](#main) — 

### `model_styles`

```python
model_styles(labels)
```

| input | type | default |
|---|---|---|
| `labels` | – | required |

{label: (colour, linestyle)} — one hue per family, style within it.

A family the map does not know (Hagen, say) keeps the old behaviour: a  
colour off MODEL_COLORS, solid. The named families' hues are removed from  
that pool first, so an unnamed model can never come out the same green as  
Catelli in one figure and something else in the next.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/multi_model.py#L100)</sub>

### `screen_discontinuity`

```python
screen_discontinuity(models, coords=None, n=80, out_dir=None, detect=None)
```

| input | type | default |
|---|---|---|
| `models` | – | required |
| `coords` | – | `None` |
| `n` | – | `80` |
| `out_dir` | – | `None` |
| `detect` | – | `None` |

{label: set(flagged muscles)} plus a csv. The original screen, per model.

`detect` is forwarded to `detect_discontinuities` (min_jump_m, k_d2,  
k_local, k_global, win). Exposed because the default 1 mm floor is a  
judgement about what counts as a jump, not a constant of nature -- a  
generic and a scaled model do not deserve the same threshold.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/multi_model.py#L133)</sub>

### `compare_models`

```python
compare_models(
    models,
    out_dir,
    literature_csv=None,
    side='_r',
    n=60,
    coords=None,
    focus='knee_angle',
    discontinuity=True,
    detect=None,
    dpi=110,
    grids=True,
    fibre=True
)
```

| input | type | default |
|---|---|---|
| `models` | – | required |
| `out_dir` | – | required |
| `literature_csv` | – | `None` |
| `side` | – | `'_r'` |
| `n` | – | `60` |
| `coords` | – | `None` |
| `focus` | – | `'knee_angle'` |
| `discontinuity` | – | `True` |
| `detect` | – | `None` |
| `dpi` | – | `110` |
| `grids` | – | `True` |
| `fibre` | – | `True` |

The whole report. Returns the list of files written.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/multi_model.py#L324)</sub>

### `main`

```python
main(argv=None)
```

| input | type | default |
|---|---|---|
| `argv` | – | `None` |

_No docstring._

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/model/inspect/multi_model.py#L453)</sub>
