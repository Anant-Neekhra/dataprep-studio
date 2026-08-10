import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


def normality_test(series: pd.Series) -> dict:
    """
    Shapiro-Wilk test for normality. Returns the test statistic and
    p-value. A small p-value (typically < 0.05) means the data is
    unlikely to be normally distributed. Shapiro-Wilk is reliable up to
    a few thousand rows; beyond that we sample, since the test becomes
    overly sensitive to tiny deviations from normality on huge datasets.
    """
    non_null = series.dropna()
    if len(non_null) < 3:
        return {"statistic": None, "p_value": None, "is_normal": None}

    sample = non_null.sample(min(len(non_null), 5000), random_state=42)
    statistic, p_value = scipy_stats.shapiro(sample)

    return {
        "statistic": float(statistic),
        "p_value": float(p_value),
        "is_normal": bool(p_value > 0.05),
    }


def compute_histogram_bins(series: pd.Series, bins: int = 30) -> dict:
    """Returns bin edges and counts, ready for a frontend chart."""
    non_null = series.dropna()
    counts, bin_edges = np.histogram(non_null, bins=bins)
    return {
        "bin_edges": [round(float(e), 4) for e in bin_edges],
        "counts": [int(c) for c in counts],
    }


def apply_transform(series: pd.Series, transform: str) -> pd.Series:
    """
    Returns a NEW series with the transform applied. All transforms
    require positive values except Yeo-Johnson, which is designed to
    handle zero and negative values too — that's specifically why it
    exists as an alternative to Box-Cox.
    """
    non_null_min = series.dropna().min() if series.notna().any() else None

    if transform == "none":
        return series

    if transform == "log":
        if non_null_min is not None and non_null_min <= 0:
            raise ValueError(
                "Log transform requires all values to be positive. "
                "This column contains zero or negative values — try Yeo-Johnson instead."
            )
        return np.log(series)

    if transform == "sqrt":
        if non_null_min is not None and non_null_min < 0:
            raise ValueError(
                "Square root transform requires all values to be non-negative. "
                "This column contains negative values — try Yeo-Johnson instead."
            )
        return np.sqrt(series)

    if transform == "box_cox":
        if non_null_min is not None and non_null_min <= 0:
            raise ValueError(
                "Box-Cox transform requires all values to be positive. "
                "This column contains zero or negative values — try Yeo-Johnson instead."
            )
        non_null = series.dropna()
        transformed_values, _ = scipy_stats.boxcox(non_null)
        result = series.copy().astype(float)
        result.loc[non_null.index] = transformed_values
        return result

    if transform == "yeo_johnson":
        non_null = series.dropna()
        transformed_values, _ = scipy_stats.yeojohnson(non_null)
        result = series.copy().astype(float)
        result.loc[non_null.index] = transformed_values
        return result

    raise ValueError(f"Unknown transform: {transform}")