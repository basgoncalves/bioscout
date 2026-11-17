# `bioscout.utils.stats`

[← API index](index.md) · [source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/stats.py)

bioscout.utils.stats — small, dependency-free numeric helpers used across the  
analysis pipeline (curve agreement metrics). Extracted from utils/__init__.py  
so the statistics live in one obvious place.

Pure numpy/pandas; no bioscout/OpenSim dependencies.

Statistical Parametric Mapping (SPM) helpers wrap the optional third-party  
``spm1d`` package (https://spm1d.org). ``spm1d`` is imported lazily so the rest  
of this module keeps working without it; install with ``pip install spm1d`` to  
use the ``spm_*`` functions.

## Contents

- [`rsquared`](#rsquared) — R-squared between true and predicted values.
- [`rmse`](#rmse) — Root Mean Square Error between true and predicted values.
- [`compare_curves`](#compare_curves) — RMSE and R-squared over the common columns of two DataFrames.
- [`sum3d`](#sum3d) — Euclidean magnitude of three DataFrame columns (e.g. X/Y/Z).
- [`spm_ttest2`](#spm_ttest2) — Two-sample SPM t-test comparing two independent groups of 1D curves.
- [`spm_ttest_paired`](#spm_ttest_paired) — Paired SPM t-test for two matched conditions (same subjects).
- [`spm_ttest`](#spm_ttest) — One-sample SPM t-test against a datum curve/scalar ``mu``.
- [`spm_anova1`](#spm_anova1) — One-way SPM ANOVA across >=2 independent groups of 1D curves.
- [`spm_plot`](#spm_plot) — Plot an SPM inference result (the test statistic + threshold).

### `rsquared`

```python
rsquared(y_true, y_pred)
```

| input | type | default |
|---|---|---|
| `y_true` | – | required |
| `y_pred` | – | required |

R-squared between true and predicted values.

  
**Args**

    y_true (array-like): The true values.  
    y_pred (array-like): The predicted values.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/stats.py#L29)</sub>

### `rmse`

```python
rmse(y_true, y_pred)
```

| input | type | default |
|---|---|---|
| `y_true` | – | required |
| `y_pred` | – | required |

Root Mean Square Error between true and predicted values.

  
**Args**

    y_true (array-like): The true values.  
    y_pred (array-like): The predicted values.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/stats.py#L40)</sub>

### `compare_curves`

```python
compare_curves(dataFrame1, dataFrame2, mapping=None)
```

| input | type | default |
|---|---|---|
| `dataFrame1` | – | required |
| `dataFrame2` | – | required |
| `mapping` | – | `None` |

RMSE and R-squared over the common columns of two DataFrames.

mapping: dict  
    A dictionary mapping column names from dataFrame1 to dataFrame2.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/stats.py#L50)</sub>

### `sum3d`

```python
sum3d(df, columns)
```

| input | type | default |
|---|---|---|
| `df` | – | required |
| `columns` | – | required |

Euclidean magnitude of three DataFrame columns (e.g. X/Y/Z).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/stats.py#L74)</sub>

### `spm_ttest2`

```python
spm_ttest2(group_a, group_b, alpha=0.05, two_tailed=True, equal_var=False)
```

| input | type | default |
|---|---|---|
| `group_a` | – | required |
| `group_b` | – | required |
| `alpha` | – | `0.05` |
| `two_tailed` | – | `True` |
| `equal_var` | – | `False` |

Two-sample SPM t-test comparing two independent groups of 1D curves.

  
**Args**

    group_a, group_b: array-like/DataFrame, shape (n_curves, n_nodes).  
    alpha (float): Significance level.  
    two_tailed (bool): Two-tailed test if True.  
    equal_var (bool): Assume equal variance (classic t) if True.

  
**Returns**

    dict with keys: spm, inference, zstar, h0_rejected, clusters  
    (each cluster has start/end node indices and its p-value).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/stats.py#L146)</sub>

### `spm_ttest_paired`

```python
spm_ttest_paired(group_a, group_b, alpha=0.05, two_tailed=True)
```

| input | type | default |
|---|---|---|
| `group_a` | – | required |
| `group_b` | – | required |
| `alpha` | – | `0.05` |
| `two_tailed` | – | `True` |

Paired SPM t-test for two matched conditions (same subjects).

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/stats.py#L166)</sub>

### `spm_ttest`

```python
spm_ttest(curves, mu=0.0, alpha=0.05, two_tailed=True)
```

| input | type | default |
|---|---|---|
| `curves` | – | required |
| `mu` | – | `0.0` |
| `alpha` | – | `0.05` |
| `two_tailed` | – | `True` |

One-sample SPM t-test against a datum curve/scalar ``mu``.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/stats.py#L175)</sub>

### `spm_anova1`

```python
spm_anova1(curves, groups, alpha=0.05)
```

| input | type | default |
|---|---|---|
| `curves` | – | required |
| `groups` | – | required |
| `alpha` | – | `0.05` |

One-way SPM ANOVA across >=2 independent groups of 1D curves.

  
**Args**

    curves: stacked array-like/DataFrame, shape (total_curves, n_nodes).  
    groups: 1D array-like of group labels, length total_curves.  
    alpha (float): Significance level.

  
**Returns**

    dict with keys: spm, inference, zstar, h0_rejected, clusters.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/stats.py#L187)</sub>

### `spm_plot`

```python
spm_plot(result, ax=None, **kwargs)
```

| input | type | default |
|---|---|---|
| `result` | – | required |
| `ax` | – | `None` |
| `**kwargs` | – | – |

Plot an SPM inference result (the test statistic + threshold).

  
**Args**

    result: dict returned by one of the ``spm_*`` functions.  
    ax: optional matplotlib Axes.

  
**Returns**

    The matplotlib Axes containing the plot.

<sub>[source](https://github.com/basgoncalves/bioscout/blob/main/bioscout/utils/stats.py#L205)</sub>
