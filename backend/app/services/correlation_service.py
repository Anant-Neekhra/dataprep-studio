import numpy as np
import pandas as pd
from scipy import stats as scipy_stats


def compute_numeric_correlation_matrix(df: pd.DataFrame, method: str = "pearson") -> dict:
    """
    Returns a correlation matrix for all numerical columns using
    pearson, spearman, or kendall. Pearson measures linear
    relationships; Spearman/Kendall measure monotonic relationships and
    are more robust to outliers and non-linear (but still monotonic)
    relationships.
    """
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.shape[1] < 2:
        return {"columns": list(numeric_df.columns), "matrix": []}

    corr = numeric_df.corr(method=method)
    return {
        "columns": corr.columns.tolist(),
        "matrix": corr.round(3).values.tolist(),
    }


def cramers_v(x: pd.Series, y: pd.Series) -> float:
    """
    Cramér's V measures association strength between two categorical
    variables, based on the chi-squared statistic. Returns a value from
    0 (no association) to 1 (perfect association) — this makes it
    comparable in spirit to a correlation coefficient, even though the
    underlying math is different (chi-squared, not covariance).
    """
    confusion_matrix = pd.crosstab(x, y)
    if confusion_matrix.size == 0:
        return 0.0

    chi2 = scipy_stats.chi2_contingency(confusion_matrix)[0]
    n = confusion_matrix.sum().sum()
    if n == 0:
        return 0.0

    phi2 = chi2 / n
    r, k = confusion_matrix.shape
    # Bias correction (Bergsma 2013) — the raw Cramér's V is known to
    # be biased upward on small samples, this correction reduces that.
    phi2_corr = max(0, phi2 - ((k - 1) * (r - 1)) / (n - 1))
    r_corr = r - ((r - 1) ** 2) / (n - 1)
    k_corr = k - ((k - 1) ** 2) / (n - 1)
    denominator = min((k_corr - 1), (r_corr - 1))

    if denominator <= 0:
        return 0.0

    return float(np.sqrt(phi2_corr / denominator))


def compute_categorical_correlation_matrix(df: pd.DataFrame, categorical_columns: list[str]) -> dict:
    """Returns a Cramér's V matrix across the given categorical columns."""
    if len(categorical_columns) < 2:
        return {"columns": categorical_columns, "matrix": []}

    n = len(categorical_columns)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i == j:
                matrix[i][j] = 1.0
            elif j > i:
                v = cramers_v(df[categorical_columns[i]], df[categorical_columns[j]])
                matrix[i][j] = round(v, 3)
                matrix[j][i] = round(v, 3)

    return {"columns": categorical_columns, "matrix": matrix}


def detect_high_correlation_pairs(
    columns: list[str], matrix: list[list[float]], threshold: float = 0.8
) -> list[dict]:
    """
    Scans a correlation/association matrix for pairs above threshold
    (in absolute value), excluding the diagonal. Used both for numeric
    (Pearson/Spearman/Kendall, which can be negative) and categorical
    (Cramér's V, always 0-1) matrices.
    """
    pairs = []
    n = len(columns)
    for i in range(n):
        for j in range(i + 1, n):
            value = matrix[i][j]
            if abs(value) >= threshold:
                pairs.append(
                    {"column_a": columns[i], "column_b": columns[j], "correlation": value}
                )
    return pairs