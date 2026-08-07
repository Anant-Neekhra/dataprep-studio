import pandas as pd
from scipy import stats as scipy_stats

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

    # Compute numeric stats only when the EFFECTIVE type is numerical —
    # this is the whole point of the override system. A column pandas
    # sees as int64 but the user (or our ID heuristic) has marked as
    # "id" should never get a mean/std/skewness computed on it, since
    # those numbers would be meaningless (or actively misleading).
    if effective_type == "numerical":
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
        # id / categorical / text / boolean / datetime / mixed all fall
        # here — mode is still meaningful ("most common value"), but no
        # mean/std/skew, since those don't mean anything for these types.
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