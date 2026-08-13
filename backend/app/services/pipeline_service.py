import pandas as pd

from app.services.imputation_service import impute_column_in_dataframe
from app.services.quality_service import remove_duplicate_rows, remove_duplicate_columns
from app.services.datatype_service import convert_column_dtype
from app.services.distribution_service import apply_transform
from app.services.outlier_service import remove_outliers, cap_outliers
from app.services.encoding_service import (
    one_hot_encode, label_encode, ordinal_encode,
    frequency_encode, binary_encode, multi_label_binarize,
)
from app.services.scaling_service import apply_scaling
from app.services.dataset_service import drop_column


def execute_operation(df: pd.DataFrame, operation: str, params: dict) -> pd.DataFrame:
    """
    Executes a single named operation against a DataFrame, returning a
    NEW DataFrame. This is the single source of truth mapping an
    operation name (as stored in dataset_versions.operation) to the
    actual service function that performs it — used both for replaying
    a pipeline from scratch and, indirectly, for generating equivalent
    Python code (see pipeline_export_service.py).
    """
    if operation == "impute":
        return impute_column_in_dataframe(
            df, params["column"], params["strategy"], params.get("constant_value")
        )

    if operation == "remove_duplicate_rows":
        return remove_duplicate_rows(df, keep=params.get("keep", "first"))

    if operation == "remove_duplicate_columns":
        return remove_duplicate_columns(df, params["columns_to_drop"])

    if operation == "convert_dtype":
        return convert_column_dtype(df, params["column"], params["target_type"])

    if operation == "transform":
        new_df = df.copy()
        new_df[params["column"]] = apply_transform(df[params["column"]], params["transform"])
        return new_df

    if operation == "outlier_treatment":
        if params["action"] == "remove":
            return remove_outliers(df, params["column"], params["method"])
        return cap_outliers(df, params["column"], params["method"])

    if operation == "encode":
        method = params["method"]
        column = params["column"]
        if method == "one_hot":
            return one_hot_encode(df, column)
        if method == "label":
            return label_encode(df, column)
        if method == "ordinal":
            return ordinal_encode(df, column, params["order"])
        if method == "frequency":
            return frequency_encode(df, column)
        if method == "binary":
            return binary_encode(df, column)
        if method == "multi_label":
            return multi_label_binarize(df, column, params["delimiter"])
        raise ValueError(f"Unknown encoding method: {method}")

    if operation == "scale":
        return apply_scaling(df, params["column"], params["method"])

    if operation == "drop_column":
        return drop_column(df, params["column"])

    raise ValueError(f"Unknown operation: {operation}")


def replay_pipeline(original_df: pd.DataFrame, steps: list[dict]) -> pd.DataFrame:
    """
    Re-executes a list of {operation, operation_params} steps against
    the ORIGINAL data, in order. This is what powers reordering (apply
    the same steps in a new order) and serves as a correctness check
    for the export feature (if replay produces the same result as the
    live current version, we know the recorded steps are complete).
    """
    df = original_df.copy()
    for step in steps:
        if step["operation"] is None:
            continue  # defensive: skip any legacy/malformed entries
        df = execute_operation(df, step["operation"], step["operation_params"] or {})
    return df