import pandas as pd

from app.schemas import ColumnProfile
from app.services.quality_service import (
    has_case_inconsistency,
    has_whitespace_issues,
    is_constant_column,
    is_low_variance_column,
)
from app.services.datatype_service import (
    detect_category_dtype_beneficial,
    detect_datetime_convertible,
    detect_int_convertible,
)
from app.services.outlier_service import detect_outliers_iqr
from app.services.quality_service import detect_duplicate_columns, detect_duplicate_rows
from app.services.correlation_service import compute_numeric_correlation_matrix, detect_high_correlation_pairs

def build_facts(profile: ColumnProfile, series: pd.Series | None = None) -> dict:
    facts = {
        "missing_pct": profile.missing_percentage,
        "missing_count": profile.missing_count,
        "unique_count": profile.unique_count,
        "cardinality_ratio": profile.cardinality_ratio,
        "count": profile.count,
        "mean": profile.mean or 0,
        "median": profile.median or 0,
        "std": profile.std or 0,
        "variance": profile.variance or 0,
        "minimum": profile.minimum or 0,
        "maximum": profile.maximum or 0,
        "range": profile.range or 0,
        "skewness": profile.skewness or 0,
        "kurtosis": profile.kurtosis or 0,
        "has_whitespace": False,
        "has_case_inconsistency": False,
        "is_constant": False,
        "is_low_variance": False,
        "is_datetime_convertible": False,
        "is_int_convertible": False,
        "is_category_beneficial": False,
        "outlier_pct": 0.0,
    }

    if series is not None:
        facts["has_whitespace"] = has_whitespace_issues(series)
        facts["has_case_inconsistency"] = has_case_inconsistency(series)
        facts["is_constant"] = is_constant_column(series)
        facts["is_low_variance"] = is_low_variance_column(series, profile.cardinality_ratio)
        facts["is_datetime_convertible"] = detect_datetime_convertible(series)
        facts["is_int_convertible"] = detect_int_convertible(series)
        facts["is_category_beneficial"] = detect_category_dtype_beneficial(
            series, profile.cardinality_ratio
        )
        if pd.api.types.is_numeric_dtype(series):
            non_null = series.dropna()
            if len(non_null) > 0:
                mask = detect_outliers_iqr(non_null)
                facts["outlier_pct"] = round((mask.sum() / len(non_null)) * 100, 2)

    return facts


def build_dataset_facts(df: pd.DataFrame) -> dict:
    from app.services.quality_service import detect_duplicate_columns, detect_duplicate_rows

    dup_rows = detect_duplicate_rows(df)
    dup_columns = detect_duplicate_columns(df)

    corr_result = compute_numeric_correlation_matrix(df, method="pearson")
    high_corr_pairs = detect_high_correlation_pairs(
        corr_result["columns"], corr_result["matrix"], threshold=0.8
    )

    return {
        "duplicate_row_pct": dup_rows["percentage"],
        "duplicate_row_count": dup_rows["count"],
        "duplicate_column_count": len(dup_columns),
        "high_correlation_pair_count": len(high_corr_pairs),
    }