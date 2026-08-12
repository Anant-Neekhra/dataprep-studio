import pandas as pd
from scipy import stats as scipy_stats
import numpy as np

from app.schemas import ColumnProfile, DatasetProfile
from app.services.dataset_service import get_effective_type


def profile_column(series: pd.Series, column_name: str, effective_type: str) -> ColumnProfile:
    total = len(series)
    missing_count = int(series.isna().sum())
    non_null = series.dropna()
    unique_count = int(non_null.nunique())

    profile_data = {
        "column": column_name,
        "dtype": str(series.dtype),
        "count": int(non_null.shape[0]),
        "missing_count": missing_count,
        "missing_percentage": round((missing_count / total) * 100, 2) if total else 0.0,
        "unique_count": unique_count,
        "cardinality_ratio": round(unique_count / total, 4) if total else 0.0,
    }

    # Only attempt numeric stats if the effective type says numerical
    # AND the actual underlying data can support numeric operations.
    # These can disagree — e.g. a user overrides a column to
    # "numerical" on the Column Types page, but the real values are
    # still strings. Trusting effective_type alone here crashes on
    # scipy's mean/skew calculations; checking the real dtype too
    # makes this safe.
    is_actually_numeric = pd.api.types.is_numeric_dtype(series)

    if effective_type == "numerical" and is_actually_numeric:
        if len(non_null) >= 3:
            skewness = float(scipy_stats.skew(non_null))
            kurtosis = float(scipy_stats.kurtosis(non_null))
        else:
            skewness = None
            kurtosis = None

        mode_result = non_null.mode()
        q1 = float(non_null.quantile(0.25)) if len(non_null) else None
        q3 = float(non_null.quantile(0.75)) if len(non_null) else None

        profile_data.update(
            {
                "mean": float(non_null.mean()) if len(non_null) else None,
                "median": float(non_null.median()) if len(non_null) else None,
                "mode": float(mode_result.iloc[0]) if not mode_result.empty else None,
                "std": float(non_null.std()) if len(non_null) > 1 else None,
                "variance": float(non_null.var()) if len(non_null) > 1 else None,
                "minimum": float(non_null.min()) if len(non_null) else None,
                "maximum": float(non_null.max()) if len(non_null) else None,
                "q1": q1,
                "q3": q3,
                "range": float(non_null.max() - non_null.min()) if len(non_null) else None,
                "skewness": skewness,
                "kurtosis": kurtosis,
            }
        )
    else:
        mode_result = non_null.mode()
        profile_data["mode"] = str(mode_result.iloc[0]) if not mode_result.empty else None

    return ColumnProfile(**profile_data)


def compute_profile(
    dataset_id: str, df: pd.DataFrame, overrides: dict[str, str] | None = None
) -> DatasetProfile:
    overrides = overrides or {}
    columns = []
    for col in df.columns:
        _, effective_type, _ = get_effective_type(df[col], col, overrides)
        columns.append(profile_column(df[col], col, effective_type))
    return DatasetProfile(dataset_id=dataset_id, columns=columns)

def compute_entropy(series: pd.Series) -> float | None:
    """
    Shannon entropy, in bits — measures how 'spread out' a column's
    values are. Low entropy means one or few values dominate (e.g. a
    column that's 95% one category); high entropy means values are
    more evenly distributed. Useful as a quick signal alongside
    cardinality: two columns can have the same unique-value count but
    very different entropy if one is dominated by a single value.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return None

    value_counts = non_null.value_counts(normalize=True)
    entropy = -(value_counts * np.log2(value_counts)).sum()
    return round(float(entropy), 4)