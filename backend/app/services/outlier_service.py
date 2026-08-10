import numpy as np
import pandas as pd


def detect_outliers_iqr(series: pd.Series, multiplier: float = 1.5) -> pd.Series:
    """
    Returns a boolean mask (True = outlier) using the IQR method.
    Points beyond Q1 - multiplier*IQR or Q3 + multiplier*IQR are flagged.
    This method is robust to skewed distributions since it's based on
    quartiles, not the mean.
    """
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - multiplier * iqr
    upper_bound = q3 + multiplier * iqr
    return (series < lower_bound) | (series > upper_bound)


def detect_outliers_zscore(series: pd.Series, threshold: float = 3.0) -> pd.Series:
    """
    Returns a boolean mask using standard Z-score. Assumes roughly
    normal data — sensitive to the mean/std being pulled by the
    outliers themselves, which is why Modified Z-score often works
    better on real-world skewed data.
    """
    mean = series.mean()
    std = series.std()
    if std == 0 or pd.isna(std):
        return pd.Series([False] * len(series), index=series.index)
    z_scores = (series - mean) / std
    return z_scores.abs() > threshold


def detect_outliers_modified_zscore(series: pd.Series, threshold: float = 3.5) -> pd.Series:
    """
    Uses median and MAD (median absolute deviation) instead of mean/std,
    making it robust to the outliers it's trying to detect — a classic
    chicken-and-egg problem with standard Z-score that this avoids.
    """
    median = series.median()
    mad = (series - median).abs().median()
    if mad == 0 or pd.isna(mad):
        return pd.Series([False] * len(series), index=series.index)
    modified_z = 0.6745 * (series - median) / mad
    return modified_z.abs() > threshold


OUTLIER_METHODS = {
    "iqr": detect_outliers_iqr,
    "zscore": detect_outliers_zscore,
    "modified_zscore": detect_outliers_modified_zscore,
}


def detect_outliers(series: pd.Series, method: str) -> dict:
    if method not in OUTLIER_METHODS:
        raise ValueError(f"Unknown outlier method: {method}")

    non_null = series.dropna()
    mask = OUTLIER_METHODS[method](non_null)

    outlier_indices = non_null[mask].index
    return {
        "outlier_count": int(mask.sum()),
        "outlier_percentage": round((mask.sum() / len(non_null)) * 100, 2) if len(non_null) else 0.0,
        "outlier_values": non_null[mask].tolist()[:20],  # cap sample size
        "outlier_indices": outlier_indices.tolist()[:20],
    }


def remove_outliers(df: pd.DataFrame, column: str, method: str) -> pd.DataFrame:
    """Returns a NEW DataFrame with outlier rows removed based on one column."""
    series = df[column].dropna()
    mask = OUTLIER_METHODS[method](series)
    outlier_indices = series[mask].index
    return df.drop(index=outlier_indices).reset_index(drop=True)


def cap_outliers(df: pd.DataFrame, column: str, method: str) -> pd.DataFrame:
    """
    Returns a NEW DataFrame with outliers capped (winsorized) to the
    nearest boundary instead of removed — preserves row count, which
    matters if other columns in the same row hold valuable data.
    """
    new_df = df.copy()
    series = new_df[column]

    if method == "iqr":
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
    else:
        # For zscore/modified_zscore, cap at the equivalent of the
        # threshold boundary using mean/std or median/MAD respectively.
        if method == "zscore":
            center, spread, threshold = series.mean(), series.std(), 3.0
        else:
            center = series.median()
            spread = (series - center).abs().median() / 0.6745
            threshold = 3.5
        lower_bound = center - threshold * spread
        upper_bound = center + threshold * spread

    new_df[column] = series.clip(lower=lower_bound, upper=upper_bound)
    return new_df