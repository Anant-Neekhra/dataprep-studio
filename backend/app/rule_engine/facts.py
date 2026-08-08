import pandas as pd

from app.schemas import ColumnProfile
from app.services.quality_service import (
    has_case_inconsistency,
    has_whitespace_issues,
    is_constant_column,
    is_low_variance_column,
)


def build_facts(profile: ColumnProfile, series: pd.Series | None = None) -> dict:
    """
    Converts a ColumnProfile (+ optionally the raw series, for quality
    checks that need actual values rather than just precomputed stats)
    into a flat dict of values YAML rule conditions can reference.
    """
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
        # Quality signals default to False if we don't have the raw
        # series (facts should still be usable without it).
        "has_whitespace": False,
        "has_case_inconsistency": False,
        "is_constant": False,
        "is_low_variance": False,
    }

    if series is not None:
        facts["has_whitespace"] = has_whitespace_issues(series)
        facts["has_case_inconsistency"] = has_case_inconsistency(series)
        facts["is_constant"] = is_constant_column(series)
        facts["is_low_variance"] = is_low_variance_column(series, profile.cardinality_ratio)

    return facts


def build_dataset_facts(df: pd.DataFrame) -> dict:
    """
    Facts about the dataset as a whole, not any single column — used for
    rules like duplicate row/column detection where no one column is
    responsible for the issue.
    """
    from app.services.quality_service import detect_duplicate_columns, detect_duplicate_rows

    dup_rows = detect_duplicate_rows(df)
    dup_columns = detect_duplicate_columns(df)

    return {
        "duplicate_row_pct": dup_rows["percentage"],
        "duplicate_row_count": dup_rows["count"],
        "duplicate_column_count": len(dup_columns),
    }