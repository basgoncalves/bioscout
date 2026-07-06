"""
bioscout.utils.stats — small, dependency-free numeric helpers used across the
analysis pipeline (curve agreement metrics). Extracted from utils/__init__.py
so the statistics live in one obvious place.

Pure numpy/pandas; no bioscout/OpenSim dependencies.

Statistical Parametric Mapping (SPM) helpers wrap the optional third-party
``spm1d`` package (https://spm1d.org). ``spm1d`` is imported lazily so the rest
of this module keeps working without it; install with ``pip install spm1d`` to
use the ``spm_*`` functions.
"""
import numpy as np
import pandas as pd


def _require_spm1d():
    """Lazily import spm1d, raising a helpful error if it is missing."""
    try:
        import spm1d  # noqa: F401
    except ImportError as exc:  # pragma: no cover - env dependent
        raise ImportError(
            "spm1d is required for statistical parametric mapping. "
            "Install it with `pip install spm1d`."
        ) from exc
    return spm1d


def rsquared(y_true, y_pred):
    """R-squared between true and predicted values.

    Args:
        y_true (array-like): The true values.
        y_pred (array-like): The predicted values.
    """
    r = np.corrcoef(y_true, y_pred)[0, 1]
    return r ** 2


def rmse(y_true, y_pred):
    """Root Mean Square Error between true and predicted values.

    Args:
        y_true (array-like): The true values.
        y_pred (array-like): The predicted values.
    """
    return np.sqrt(np.mean((y_true - y_pred) ** 2))


def compare_curves(dataFrame1, dataFrame2, mapping=None):
    """RMSE and R-squared over the common columns of two DataFrames.

    mapping: dict
        A dictionary mapping column names from dataFrame1 to dataFrame2.
    """
    if mapping is None:
        common_columns = dataFrame1.columns.intersection(dataFrame2.columns)
        mapping = dict(common_columns.to_series())
    else:
        common_columns = list(mapping.keys())

    results = pd.DataFrame(columns=['RMSE', 'R2'], index=common_columns)
    for col in common_columns:
        mapped_col = mapping.get(col, col)
        y_true_col = dataFrame1[mapped_col].values
        y_pred_col = dataFrame2[col].values
        rmse_value = rmse(y_true_col, y_pred_col)
        r2_value = rsquared(y_true_col, y_pred_col)
        results.loc[col] = [rmse_value, r2_value]

    return results


def sum3d(df, columns):
    """Euclidean magnitude of three DataFrame columns (e.g. X/Y/Z)."""
    x = df[columns[0]]
    y = df[columns[1]]
    z = df[columns[2]]
    return np.sqrt(x ** 2 + y ** 2 + z ** 2)


# ---------------------------------------------------------------------------
# Statistical Parametric Mapping (SPM) — 1D waveform statistics via spm1d
# ---------------------------------------------------------------------------
#
# SPM treats each subject/trial as a continuous 1D curve (e.g. a joint angle,
# moment, or muscle force normalised to 0-100% of a task) and tests for
# differences at every point of the curve while controlling for the multiple
# comparisons across the whole waveform (random field theory). This is the
# appropriate tool for comparing biomechanical time-series between conditions
# or groups, instead of collapsing curves to a single scalar (e.g. peak).
#
# Convention: each input is a 2D array (n_curves, n_nodes) — one row per
# subject/trial, one column per time-normalised point. DataFrames are accepted
# and converted with columns = time nodes.


def _as_curve_array(data):
    """Coerce array-like / DataFrame to a 2D (n_curves, n_nodes) float array."""
    if isinstance(data, (pd.DataFrame, pd.Series)):
        data = data.values
    arr = np.asarray(data, dtype=float)
    if arr.ndim == 1:
        arr = arr[np.newaxis, :]
    if arr.ndim != 2:
        raise ValueError(
            f"Expected 1D or 2D curve data (n_curves, n_nodes), got shape {arr.shape}."
        )
    return arr


def _run_inference(t, alpha, two_tailed):
    """Run SPM inference and return a tidy summary dict."""
    ti = t.inference(alpha, two_tailed=two_tailed, interp=True)

    def _cluster_summary(inf):
        clusters = []
        for c in getattr(inf, "clusters", []) or []:
            start, end = c.endpoints
            clusters.append({
                "start": float(start),
                "end": float(end),
                "p": float(getattr(c, "P", np.nan)),
            })
        return clusters

    if isinstance(ti, (list, tuple)):  # SnPM / list results
        summaries = [{
            "zstar": float(getattr(x, "zstar", np.nan)),
            "h0_rejected": bool(getattr(x, "h0reject", False)),
            "clusters": _cluster_summary(x),
        } for x in ti]
        return {"spm": t, "inference": ti, "results": summaries}

    return {
        "spm": t,
        "inference": ti,
        "alpha": alpha,
        "two_tailed": two_tailed,
        "zstar": float(getattr(ti, "zstar", np.nan)),
        "h0_rejected": bool(getattr(ti, "h0reject", False)),
        "clusters": _cluster_summary(ti),
    }


def spm_ttest2(group_a, group_b, alpha=0.05, two_tailed=True, equal_var=False):
    """Two-sample SPM t-test comparing two independent groups of 1D curves.

    Args:
        group_a, group_b: array-like/DataFrame, shape (n_curves, n_nodes).
        alpha (float): Significance level.
        two_tailed (bool): Two-tailed test if True.
        equal_var (bool): Assume equal variance (classic t) if True.

    Returns:
        dict with keys: spm, inference, zstar, h0_rejected, clusters
        (each cluster has start/end node indices and its p-value).
    """
    spm1d = _require_spm1d()
    a = _as_curve_array(group_a)
    b = _as_curve_array(group_b)
    t = spm1d.stats.ttest2(a, b, equal_var=equal_var)
    return _run_inference(t, alpha, two_tailed)


def spm_ttest_paired(group_a, group_b, alpha=0.05, two_tailed=True):
    """Paired SPM t-test for two matched conditions (same subjects)."""
    spm1d = _require_spm1d()
    a = _as_curve_array(group_a)
    b = _as_curve_array(group_b)
    t = spm1d.stats.ttest_paired(a, b)
    return _run_inference(t, alpha, two_tailed)


def spm_ttest(curves, mu=0.0, alpha=0.05, two_tailed=True):
    """One-sample SPM t-test against a datum curve/scalar ``mu``."""
    spm1d = _require_spm1d()
    y = _as_curve_array(curves)
    if np.isscalar(mu):
        mu_arr = mu
    else:
        mu_arr = np.asarray(mu, dtype=float)
    t = spm1d.stats.ttest(y, mu_arr)
    return _run_inference(t, alpha, two_tailed)


def spm_anova1(curves, groups, alpha=0.05):
    """One-way SPM ANOVA across >=2 independent groups of 1D curves.

    Args:
        curves: stacked array-like/DataFrame, shape (total_curves, n_nodes).
        groups: 1D array-like of group labels, length total_curves.
        alpha (float): Significance level.

    Returns:
        dict with keys: spm, inference, zstar, h0_rejected, clusters.
    """
    spm1d = _require_spm1d()
    y = _as_curve_array(curves)
    A = np.asarray(groups)
    f = spm1d.stats.anova1(y, A)
    return _run_inference(f, alpha, two_tailed=False)


def spm_plot(result, ax=None, **kwargs):
    """Plot an SPM inference result (the test statistic + threshold).

    Args:
        result: dict returned by one of the ``spm_*`` functions.
        ax: optional matplotlib Axes.

    Returns:
        The matplotlib Axes containing the plot.
    """
    import matplotlib.pyplot as plt

    inf = result.get("inference")
    if inf is None:
        raise ValueError("result has no 'inference'; pass output of an spm_* function.")
    if ax is not None:
        plt.sca(ax)
    inf.plot(**kwargs)
    try:
        inf.plot_threshold_label()
        inf.plot_p_values()
    except Exception:  # pragma: no cover - decoration is best-effort
        pass
    return plt.gca()


__all__ = [
    "rsquared",
    "rmse",
    "compare_curves",
    "sum3d",
    "spm_ttest",
    "spm_ttest2",
    "spm_ttest_paired",
    "spm_anova1",
    "spm_plot",
]
