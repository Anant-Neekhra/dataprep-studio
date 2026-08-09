import pandas as pd


def has_whitespace_issues(series: pd.Series) -> bool:
    """True if any string value has leading/trailing whitespace."""
    if series.dtype != object:
        return False
    non_null = series.dropna().astype(str)
    return bool((non_null != non_null.str.strip()).any())


def has_case_inconsistency(series: pd.Series) -> bool:
    """
    True if the same logical value appears with different casing,
    e.g. "Yes", "yes", "YES" all present as if they were distinct
    categories.
    """
    if series.dtype != object:
        return False
    non_null = series.dropna().astype(str).str.strip()
    if non_null.empty:
        return False
    original_unique = non_null.nunique()
    lowercased_unique = non_null.str.lower().nunique()
    return lowercased_unique < original_unique


def is_constant_column(series: pd.Series) -> bool:
    """True if the column has exactly one distinct non-null value."""
    return series.dropna().nunique() == 1


def is_low_variance_column(series: pd.Series, cardinality_ratio: float) -> bool:
    """
    Flags columns that technically have more than one value but are
    dominated by a single value — not constant, but close to it.
    Threshold: fewer than 1% of rows are distinct values, and more
    than one value exists (otherwise it's caught by is_constant instead).
    """
    unique_count = series.dropna().nunique()
    return 1 < unique_count and cardinality_ratio < 0.01


def detect_duplicate_rows(df: pd.DataFrame) -> dict:
    duplicate_count = int(df.duplicated().sum())
    total = len(df)
    return {
        "count": duplicate_count,
        "percentage": round((duplicate_count / total) * 100, 2) if total else 0.0,
    }


def detect_duplicate_columns(df: pd.DataFrame) -> list[tuple[str, str]]:
    """
    Returns pairs of column names that are exact duplicates of each
    other (identical values in every row).
    """
    duplicate_pairs = []
    columns = df.columns.tolist()
    for i, col_a in enumerate(columns):
        for col_b in columns[i + 1 :]:
            if df[col_a].equals(df[col_b]):
                duplicate_pairs.append((col_a, col_b))
    return duplicate_pairs

def remove_duplicate_rows(df: pd.DataFrame, keep: str = "first") -> pd.DataFrame:
    """
    Returns a NEW DataFrame with exact duplicate rows removed.
    keep: "first" keeps the first occurrence, "last" keeps the last.
    """
    return df.drop_duplicates(keep=keep).reset_index(drop=True)


def remove_duplicate_columns(df: pd.DataFrame, columns_to_drop: list[str]) -> pd.DataFrame:
    """
    Returns a NEW DataFrame with the specified columns removed. Used
    after detect_duplicate_columns identifies which columns are exact
    duplicates of another — the caller decides which one of each pair
    to actually drop (we don't guess, since the "right" one to keep
    might depend on naming/domain knowledge the tool doesn't have).
    """
    return df.drop(columns=columns_to_drop)