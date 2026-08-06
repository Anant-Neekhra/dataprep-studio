import pandas as pd

from app.schemas import DatasetOverview, FeatureTypeBreakdown


def classify_dtype(series: pd.Series) -> str:
    """
    Buckets a pandas Series into one of our feature type categories.
    This is intentionally simple for Day 2 — the real Datatype Analyzer
    (Day 8) will do smarter detection (e.g. sniffing date-like strings).
    """
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numerical"
    if pd.api.types.is_categorical_dtype(series):
        return "categorical"

    # Object dtype columns could be text or low-cardinality categories.
    # Rule of thumb: if fewer than 5% of values are unique, treat it as
    # categorical; otherwise treat it as free text.
    if series.dtype == object:
        unique_ratio = series.nunique(dropna=True) / max(len(series), 1)
        return "categorical" if unique_ratio < 0.05 else "text"

    return "mixed"


def compute_overview(dataset_id: str, filename: str, df: pd.DataFrame) -> DatasetOverview:
    feature_types = {
        "numerical": 0,
        "categorical": 0,
        "boolean": 0,
        "datetime": 0,
        "text": 0,
        "mixed": 0,
    }
    for column in df.columns:
        category = classify_dtype(df[column])
        feature_types[category] += 1

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