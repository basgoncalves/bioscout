"""
bioscout.utils.stats — small, dependency-free numeric helpers used across the
analysis pipeline (curve agreement metrics). Extracted from utils/__init__.py
so the statistics live in one obvious place.

Pure numpy/pandas; no bioscout/OpenSim dependencies.
"""
import numpy as np
import pandas as pd


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


__all__ = ["rsquared", "rmse", "compare_curves", "sum3d"]
