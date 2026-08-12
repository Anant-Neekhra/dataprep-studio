import pandas as pd


def one_hot_encode(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Returns a NEW DataFrame with the column replaced by one binary column per category."""
    dummies = pd.get_dummies(df[column], prefix=column, dtype=int)
    new_df = df.drop(columns=[column])
    return pd.concat([new_df, dummies], axis=1)


def label_encode(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Returns a NEW DataFrame with categories mapped to integer codes
    (alphabetically ordered for determinism — re-running this on the
    same data always produces the same mapping).
    """
    new_df = df.copy()
    categories = sorted(new_df[column].dropna().unique())
    mapping = {cat: i for i, cat in enumerate(categories)}
    new_df[column] = new_df[column].map(mapping)
    return new_df


def ordinal_encode(df: pd.DataFrame, column: str, order: list[str]) -> pd.DataFrame:
    """
    Like label_encode, but the caller specifies the category order
    explicitly (e.g. "Low" < "Medium" < "High") rather than alphabetical
    — ordinal encoding is only meaningful when order carries real
    information, which the tool can't infer on its own.
    """
    new_df = df.copy()
    mapping = {cat: i for i, cat in enumerate(order)}
    new_df[column] = new_df[column].map(mapping)
    return new_df


def frequency_encode(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Returns a NEW DataFrame with each category replaced by its frequency count."""
    new_df = df.copy()
    freq_map = new_df[column].value_counts()
    new_df[column] = new_df[column].map(freq_map)
    return new_df


def binary_encode(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Encodes categories as binary digit columns — more compact than
    one-hot for higher-cardinality columns (log2(n) columns instead of
    n), at the cost of the encoding no longer being human-interpretable
    per column.
    """
    new_df = df.copy()
    categories = sorted(new_df[column].dropna().unique())
    mapping = {cat: i for i, cat in enumerate(categories)}
    codes = new_df[column].map(mapping)

    n_bits = max(1, (len(categories) - 1).bit_length())
    for bit in range(n_bits):
        new_df[f"{column}_bin_{bit}"] = codes.apply(
            lambda x: (int(x) >> bit) & 1 if pd.notna(x) else None
        )
    new_df = new_df.drop(columns=[column])
    return new_df


def multi_label_binarize(df: pd.DataFrame, column: str, delimiter: str) -> pd.DataFrame:
    """
    Returns a NEW DataFrame with a multi-label column (e.g. genres)
    expanded into one binary column per distinct label — this is the
    real applied version of what Day 12 only detected and profiled.
    """
    new_df = df.copy()
    non_null = new_df[column].dropna().astype(str)
    all_labels = sorted(non_null.str.split(delimiter).explode().str.strip().unique())

    for label in all_labels:
        if label == "":
            continue
        col_name = f"{column}_{label}"
        new_df[col_name] = new_df[column].apply(
            lambda x: int(label in [t.strip() for t in str(x).split(delimiter)]) if pd.notna(x) else 0
        )

    new_df = new_df.drop(columns=[column])
    return new_df