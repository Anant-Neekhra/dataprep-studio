import re

import pandas as pd

from app.schemas import DatasetOverview, FeatureTypeBreakdown


ID_NAME_PATTERN = re.compile(r"(^id$|_id$|^id_|uuid|guid)", re.IGNORECASE)


def looks_like_id_column(series: pd.Series, column_name: str) -> bool:
    """
    Heuristic ID detection — not perfect, which is exactly why we let the
    user override it rather than trusting this blindly. Two signals:
      1. Name strongly suggests an identifier (e.g. "user_id", "uuid")
      2. Values are unique (or near-unique) AND look sequential/random
         rather than measuring anything — i.e. very high cardinality
         relative to row count, on an int or string column.
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return False

    name_suggests_id = bool(ID_NAME_PATTERN.search(str(column_name)))
    cardinality_ratio = non_null.nunique() / len(non_null)
    near_unique = cardinality_ratio > 0.95

    is_int_or_string = pd.api.types.is_integer_dtype(series) or series.dtype == object

    return is_int_or_string and near_unique and (name_suggests_id or cardinality_ratio == 1.0)


def classify_dtype(series: pd.Series, column_name: str | None = None) -> str:
    """
    Auto-detects a logical type for a column. This is a *suggestion* —
    the user can always override it via the type-override endpoints.
    Order matters: we check for ID-likeness before falling through to
    numerical, since an int64 "user_id" column would otherwise be
    classified as numerical and get meaningless mean/std computed on it.
    """
    name = column_name if column_name is not None else series.name

    if looks_like_id_column(series, name):
        return "id"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numerical"
    if pd.api.types.is_categorical_dtype(series):
        return "categorical"

    if series.dtype == object:
        unique_ratio = series.nunique(dropna=True) / max(len(series), 1)
        return "categorical" if unique_ratio < 0.05 else "text"

    return "mixed"


def get_effective_type(
    series: pd.Series, column_name: str, overrides: dict[str, str]
) -> tuple[str, str, bool]:
    """
    Returns (detected_type, effective_type, is_overridden).
    effective_type is what the rest of the app should actually use.
    """
    detected = classify_dtype(series, column_name)
    if column_name in overrides:
        return detected, overrides[column_name], True
    return detected, detected, False


def compute_overview(
    dataset_id: str, filename: str, df: pd.DataFrame, overrides: dict[str, str] | None = None
) -> DatasetOverview:
    overrides = overrides or {}
    feature_types = {
        "numerical": 0, "categorical": 0, "boolean": 0,
        "datetime": 0, "text": 0, "id": 0, "mixed": 0,
    }
    for column in df.columns:
        _, effective_type, _ = get_effective_type(df[column], column, overrides)
        feature_types[effective_type] += 1

    total_cells = df.shape[0] * df.shape[1]
    missing_total = int(df.isna().sum().sum())

    return DatasetOverview(
        dataset_id=dataset_id,
        filename=filename,
        rows=df.shape[0],
        columns=df.shape[1],
        memory_usage_bytes=int(df.memory_usage(deep=True).sum()),
        missing_values_total=missing_total,
        missing_percentage=round((missing_total / total_cells) * 100, 2) if total_cells else 0.0,
        duplicate_rows=int(df.duplicated().sum()),
        feature_types=FeatureTypeBreakdown(**feature_types),
        dtypes={col: str(dtype) for col, dtype in df.dtypes.items()},
    )