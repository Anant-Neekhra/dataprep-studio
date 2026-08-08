from typing import Literal

import pandas as pd

NUMERIC_ONLY_STRATEGIES = {"mean", "median"}


def validate_strategy_for_column(series: pd.Series, strategy: str) -> None:
    """
    Raises ValueError with a clear message if the strategy doesn't make
    sense for this column's data type. Called before any imputation is
    attempted, so a bad combination fails cleanly instead of crashing
    deep inside pandas with a confusing TypeError.
    """
    is_numeric = pd.api.types.is_numeric_dtype(series)

    if strategy in NUMERIC_ONLY_STRATEGIES and not is_numeric:
        raise ValueError(
            f"'{strategy}' requires a numeric column, but this column is "
            f"'{series.dtype}'. Try 'mode', 'constant', or 'drop_rows' instead."
        )

ImputationStrategy = Literal[
    "mean", "median", "mode", "constant", "forward_fill", "backward_fill", "drop_rows"
]


def apply_imputation(
    series: pd.Series, strategy: ImputationStrategy, constant_value: str | None = None
) -> pd.Series:
    """
    Returns a NEW series with missing values handled according to
    strategy. Never mutates the input — callers decide whether to keep
    the result (apply) or just inspect it (preview).
    """
    if strategy == "mean":
        return series.fillna(series.mean())

    if strategy == "median":
        return series.fillna(series.median())

    if strategy == "mode":
        mode_result = series.mode()
        fill_value = mode_result.iloc[0] if not mode_result.empty else series
        return series.fillna(fill_value)

    if strategy == "constant":
        if constant_value is None:
            raise ValueError("constant_value is required for the 'constant' strategy")
        return series.fillna(constant_value)

    if strategy == "forward_fill":
        return series.ffill()

    if strategy == "backward_fill":
        return series.bfill()

    if strategy == "drop_rows":
        # Note: this doesn't change the SERIES length here, since a
        # series can't drop rows independently of the rest of the
        # DataFrame. This strategy is handled specially at the
        # DataFrame level — see impute_column_in_dataframe below.
        return series

    raise ValueError(f"Unknown imputation strategy: {strategy}")

def impute_column_in_dataframe(
    df: pd.DataFrame,
    column: str,
    strategy: ImputationStrategy,
    constant_value: str | None = None,
) -> pd.DataFrame:
    validate_strategy_for_column(df[column], strategy)

    new_df = df.copy()

    if strategy == "drop_rows":
        new_df = new_df.dropna(subset=[column])
    else:
        new_df[column] = apply_imputation(new_df[column], strategy, constant_value)

    return new_df

from app.schemas import ColumnStatsSummary


def summarize_column(series: pd.Series) -> ColumnStatsSummary:
    non_null = series.dropna()
    is_numeric = pd.api.types.is_numeric_dtype(series)

    return ColumnStatsSummary(
        mean=float(non_null.mean()) if is_numeric and len(non_null) else None,
        median=float(non_null.median()) if is_numeric and len(non_null) else None,
        std=float(non_null.std()) if is_numeric and len(non_null) > 1 else None,
        missing_count=int(series.isna().sum()),
        row_count=len(series),
    )


def preview_imputation(
    df: pd.DataFrame, column: str, strategy: ImputationStrategy, constant_value: str | None = None
) -> dict:
    before_series = df[column]
    after_df = impute_column_in_dataframe(df, column, strategy, constant_value)
    after_series = after_df[column]

    # Grab a small sample of rows that WERE missing, to show what they
    # became after imputation — this is more informative than a random
    # sample, since it directly shows the effect of the strategy.
    missing_mask = before_series.isna()
    sample_indices = before_series[missing_mask].index[:5]

    return {
        "before": summarize_column(before_series),
        "after": summarize_column(after_series),
        "sample_before": before_series.loc[sample_indices].fillna("NaN").tolist(),
        "sample_after": after_series.loc[sample_indices].tolist() if strategy != "drop_rows" else [],
    }


def compare_strategies(
    df: pd.DataFrame, column: str, strategy_a: ImputationStrategy, strategy_b: ImputationStrategy
) -> dict:
    before_series = df[column]
    after_a = impute_column_in_dataframe(df, column, strategy_a)[column]
    after_b = impute_column_in_dataframe(df, column, strategy_b)[column]

    return {
        "before": summarize_column(before_series),
        "after_a": summarize_column(after_a),
        "after_b": summarize_column(after_b),
    }