import numpy as np
import pandas as pd


def standard_scale(series: pd.Series) -> pd.Series:
    """(x - mean) / std — centers at 0, unit variance. Sensitive to outliers."""
    mean = series.mean()
    std = series.std()
    if std == 0 or pd.isna(std):
        return series - mean
    return (series - mean) / std


def minmax_scale(series: pd.Series) -> pd.Series:
    """(x - min) / (max - min) — rescales to [0, 1]. Very sensitive to outliers."""
    min_val = series.min()
    max_val = series.max()
    if max_val == min_val:
        return series * 0
    return (series - min_val) / (max_val - min_val)


def robust_scale(series: pd.Series) -> pd.Series:
    """
    (x - median) / IQR — uses median and interquartile range instead of
    mean/std, making it robust to outliers rather than distorted by
    them.
    """
    median = series.median()
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return series - median
    return (series - median) / iqr


def maxabs_scale(series: pd.Series) -> pd.Series:
    """x / max(|x|) — rescales to [-1, 1] without shifting/centering data, preserves sparsity (zeros stay zero)."""
    max_abs = series.abs().max()
    if max_abs == 0:
        return series
    return series / max_abs


def normalize_scale(series: pd.Series) -> pd.Series:
    """
    x / ||x|| (L2 norm) — scales values so the vector has unit length.
    Different in kind from the others: those scale each column
    independently based on its own stats; this scales relative to the
    magnitude of the whole vector, more common in text/vector contexts
    than typical tabular columns, but included since it's in scope.
    """
    norm = np.sqrt((series ** 2).sum())
    if norm == 0:
        return series
    return series / norm


SCALING_METHODS = {
    "standard": standard_scale,
    "minmax": minmax_scale,
    "robust": robust_scale,
    "maxabs": maxabs_scale,
    "normalize": normalize_scale,
}


def apply_scaling(df: pd.DataFrame, column: str, method: str) -> pd.DataFrame:
    if method not in SCALING_METHODS:
        raise ValueError(f"Unknown scaling method: {method}")

    if not pd.api.types.is_numeric_dtype(df[column]):
        raise ValueError(f"Scaling requires a numeric column, but '{column}' is {df[column].dtype}")

    new_df = df.copy()
    new_df[column] = SCALING_METHODS[method](new_df[column])
    return new_df