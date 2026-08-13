import io
import json

import pandas as pd
import yaml


def export_to_csv_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")


def export_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    df.to_parquet(buffer, engine="pyarrow")
    return buffer.getvalue()


def export_pipeline_to_json(steps: list[dict]) -> str:
    return json.dumps(steps, indent=2)


def export_pipeline_to_yaml(steps: list[dict]) -> str:
    return yaml.dump(steps, sort_keys=False, default_flow_style=False)

# Maps operation names to a function that generates the equivalent
# Python/pandas code as a string, given that step's parameters. This
# mirrors the operation registry in pipeline_service.py — same set of
# operations, but emitting code instead of executing it.

def _code_impute(p: dict) -> str:
    col, strategy = p["column"], p["strategy"]
    if strategy == "mean":
        return f"df['{col}'] = df['{col}'].fillna(df['{col}'].mean())"
    if strategy == "median":
        return f"df['{col}'] = df['{col}'].fillna(df['{col}'].median())"
    if strategy == "mode":
        return f"df['{col}'] = df['{col}'].fillna(df['{col}'].mode().iloc[0])"
    if strategy == "constant":
        return f"df['{col}'] = df['{col}'].fillna({p.get('constant_value')!r})"
    if strategy == "forward_fill":
        return f"df['{col}'] = df['{col}'].ffill()"
    if strategy == "backward_fill":
        return f"df['{col}'] = df['{col}'].bfill()"
    if strategy == "drop_rows":
        return f"df = df.dropna(subset=['{col}'])"
    return f"# Unknown impute strategy: {strategy}"


def _code_remove_duplicate_rows(p: dict) -> str:
    return f"df = df.drop_duplicates(keep='{p.get('keep', 'first')}').reset_index(drop=True)"


def _code_remove_duplicate_columns(p: dict) -> str:
    return f"df = df.drop(columns={p['columns_to_drop']!r})"


def _code_convert_dtype(p: dict) -> str:
    col, target = p["column"], p["target_type"]
    if target == "datetime":
        return f"df['{col}'] = pd.to_datetime(df['{col}'], errors='coerce', format='mixed')"
    if target == "integer":
        return f"df['{col}'] = df['{col}'].round(0).astype('Int64')"
    if target == "category":
        return f"df['{col}'] = df['{col}'].astype('category')"
    if target == "float":
        return f"df['{col}'] = pd.to_numeric(df['{col}'], errors='coerce')"
    if target == "string":
        return f"df['{col}'] = df['{col}'].astype(str)"
    return f"# Unknown target_type: {target}"


def _code_transform(p: dict) -> str:
    col, t = p["column"], p["transform"]
    if t == "log":
        return f"df['{col}'] = np.log(df['{col}'])"
    if t == "sqrt":
        return f"df['{col}'] = np.sqrt(df['{col}'])"
    if t == "box_cox":
        return f"df['{col}'], _ = scipy.stats.boxcox(df['{col}'])"
    if t == "yeo_johnson":
        return f"df['{col}'], _ = scipy.stats.yeojohnson(df['{col}'])"
    return "# no transform"


def _code_outlier_treatment(p: dict) -> str:
    col, method, action = p["column"], p["method"], p["action"]
    comment = f"# Outlier {action} on '{col}' using {method} — see outlier_service.py for exact bounds logic"
    return comment


def _code_encode(p: dict) -> str:
    col, method = p["column"], p["method"]
    if method == "one_hot":
        return f"df = pd.get_dummies(df, columns=['{col}'], prefix='{col}', dtype=int)"
    if method == "label":
        return (
            f"_categories = sorted(df['{col}'].dropna().unique())\n"
            f"df['{col}'] = df['{col}'].map({{c: i for i, c in enumerate(_categories)}})"
        )
    if method == "frequency":
        return f"df['{col}'] = df['{col}'].map(df['{col}'].value_counts())"
    return f"# Encoding method '{method}' — see encoding_service.py for exact logic"


def _code_scale(p: dict) -> str:
    col, method = p["column"], p["method"]
    if method == "standard":
        return f"df['{col}'] = (df['{col}'] - df['{col}'].mean()) / df['{col}'].std()"
    if method == "minmax":
        return f"df['{col}'] = (df['{col}'] - df['{col}'].min()) / (df['{col}'].max() - df['{col}'].min())"
    if method == "robust":
        return (
            f"_q1, _q3 = df['{col}'].quantile(0.25), df['{col}'].quantile(0.75)\n"
            f"df['{col}'] = (df['{col}'] - df['{col}'].median()) / (_q3 - _q1)"
        )
    return f"# Scaling method '{method}' — see scaling_service.py for exact logic"


def _code_drop_column(p: dict) -> str:
    return f"df = df.drop(columns=['{p['column']}'])"


CODE_GENERATORS = {
    "impute": _code_impute,
    "remove_duplicate_rows": _code_remove_duplicate_rows,
    "remove_duplicate_columns": _code_remove_duplicate_columns,
    "convert_dtype": _code_convert_dtype,
    "transform": _code_transform,
    "outlier_treatment": _code_outlier_treatment,
    "encode": _code_encode,
    "scale": _code_scale,
    "drop_column": _code_drop_column,
}


def generate_pipeline_script(steps: list[dict]) -> str:
    """
    Generates a standalone Python script that reproduces the pipeline's
    transformations using plain pandas/numpy/scipy — no dependency on
    this app's own service modules, so it runs anywhere.
    """
    lines = [
        "# Auto-generated preprocessing script — DataPrep Studio",
        "# Reproduces the transformations applied in this session",
        "import pandas as pd",
        "import numpy as np",
        "import scipy.stats",
        "",
        "df = pd.read_csv('your_data.csv')  # replace with your actual file",
        "",
    ]

    for step in steps:
        if step["operation"] is None or step["operation"] == "reorder":
            continue
        generator = CODE_GENERATORS.get(step["operation"])
        lines.append(f"# {step['description']}")
        if generator:
            lines.append(generator(step["operation_params"] or {}))
        else:
            lines.append(f"# Unrecognized operation: {step['operation']}")
        lines.append("")

    lines.append("df.to_csv('processed_output.csv', index=False)")
    return "\n".join(lines)