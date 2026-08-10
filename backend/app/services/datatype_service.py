import pandas as pd


def detect_datetime_convertible(series: pd.Series, threshold: float = 0.9) -> bool:
    """
    True if at least `threshold` fraction of non-null values in an
    object column can be parsed as dates. Using a threshold rather than
    100% because a handful of genuinely malformed entries shouldn't
    block a real recommendation — those rows would just become NaT
    (pandas' "missing datetime") after conversion, visible via the
    normal missing-value tools afterward.
    """
    if series.dtype != object:
        return False

    non_null = series.dropna()
    if len(non_null) == 0:
        return False

    sample = non_null.head(200)  # sampling keeps this fast on large datasets
    parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
    success_ratio = parsed.notna().sum() / len(sample)

    return success_ratio >= threshold


def detect_int_convertible(series: pd.Series) -> bool:
    """
    True if a float column's non-null values are all whole numbers
    (e.g. 25.0, 30.0, 42.0) — meaning it's likely stored as float only
    because of missing values (pandas upcasts int columns with NaN to
    float) or an unnecessary export format choice.
    """
    if not pd.api.types.is_float_dtype(series):
        return False

    non_null = series.dropna()
    if len(non_null) == 0:
        return False

    return bool((non_null == non_null.round(0)).all())


def detect_category_dtype_beneficial(series: pd.Series, cardinality_ratio: float) -> bool:
    """
    True if converting an object column to pandas' 'category' dtype
    would meaningfully save memory — low cardinality relative to row
    count means many repeated strings, which category dtype stores far
    more efficiently than plain object.
    """
    if series.dtype != object:
        return False
    return cardinality_ratio < 0.5

def convert_column_dtype(df: pd.DataFrame, column: str, target_type: str) -> pd.DataFrame:
    """
    Returns a NEW DataFrame with one column converted to target_type.
    Supported: "datetime", "integer", "category", "float", "string"
    """
    new_df = df.copy()
    series = new_df[column]

    if target_type == "datetime":
        new_df[column] = pd.to_datetime(series, errors="coerce", format="mixed")

    elif target_type == "integer":
        if series.isna().any():
            # Nullable Int64 (capital I) tolerates missing values;
            # standard int64 does not.
            new_df[column] = series.round(0).astype("Int64")
        else:
            new_df[column] = series.round(0).astype("int64")

    elif target_type == "category":
        new_df[column] = series.astype("category")

    elif target_type == "float":
        new_df[column] = pd.to_numeric(series, errors="coerce")

    elif target_type == "string":
        new_df[column] = series.astype(str)

    else:
        raise ValueError(f"Unsupported target_type: {target_type}")

    return new_df


def summarize_dtype_conversion(df: pd.DataFrame, column: str, target_type: str) -> dict:
    """
    Preview info: what the dtype would become, how many values would
    fail to convert (become missing), and a small before/after sample.
    """
    before_dtype = str(df[column].dtype)
    before_missing = int(df[column].isna().sum())

    converted_df = convert_column_dtype(df, column, target_type)
    after_dtype = str(converted_df[column].dtype)
    after_missing = int(converted_df[column].isna().sum())

    sample_indices = df[column].dropna().head(5).index

    return {
        "before_dtype": before_dtype,
        "after_dtype": after_dtype,
        "before_missing": before_missing,
        "after_missing": after_missing,
        "newly_invalid_count": after_missing - before_missing,
        "sample_before": df[column].loc[sample_indices].tolist(),
        "sample_after": converted_df[column].loc[sample_indices].tolist(),
    }