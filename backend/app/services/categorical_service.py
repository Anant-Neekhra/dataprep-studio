import pandas as pd

MULTI_LABEL_DELIMITERS = ["|", ",", ";", "/"]


def compute_category_frequencies(series: pd.Series, top_n: int = 20) -> dict:
    """Returns the most common values and their counts/percentages."""
    non_null = series.dropna()
    total = len(non_null)
    value_counts = non_null.value_counts().head(top_n)

    return {
        "categories": value_counts.index.astype(str).tolist(),
        "counts": value_counts.tolist(),
        "percentages": [round((c / total) * 100, 2) for c in value_counts.tolist()] if total else [],
        "total_unique": int(non_null.nunique()),
    }


def detect_multi_label_delimiter(series: pd.Series, min_split_ratio: float = 0.5) -> str | None:
    """
    Tries each candidate delimiter and checks whether splitting on it
    produces a small, repeating vocabulary (the signature of a
    multi-label column like "Action|Comedy|Drama") rather than just
    fragmenting unrelated text (like splitting an address on commas).

    Returns the best delimiter found, or None if this doesn't look like
    a multi-label column.
    """
    non_null = series.dropna().astype(str)
    if len(non_null) == 0:
        return None

    best_delimiter = None
    best_score = 0.0

    for delimiter in MULTI_LABEL_DELIMITERS:
        rows_with_delimiter = non_null.str.contains(delimiter, regex=False)
        split_ratio = rows_with_delimiter.mean()

        if split_ratio < min_split_ratio:
            continue

        all_tokens = non_null.str.split(delimiter).explode().str.strip()
        vocab_size = all_tokens.nunique()
        avg_tokens_per_row = all_tokens.shape[0] / len(non_null)

        # A genuine multi-label column has a SMALL, REPEATING vocabulary
        # (e.g. 15 genres across 1000 rows) — not a vocabulary that's
        # nearly as large as the token count (which would mean each
        # "token" is actually unique, like splitting free text or an
        # address on commas).
        repetition_ratio = 1 - (vocab_size / all_tokens.shape[0]) if all_tokens.shape[0] else 0

        if repetition_ratio > 0.5 and avg_tokens_per_row > 1.1:
            score = split_ratio * repetition_ratio
            if score > best_score:
                best_score = score
                best_delimiter = delimiter

    return best_delimiter


def profile_multi_label_column(series: pd.Series, delimiter: str) -> dict:
    """
    Token-level stats for a multi-label column — vocabulary size,
    average labels per row, and per-label frequency. Row-level stats
    like mean/std don't apply here since each row holds a SET of
    labels, not a single value.
    """
    non_null = series.dropna().astype(str)
    all_tokens = non_null.str.split(delimiter).explode().str.strip()
    all_tokens = all_tokens[all_tokens != ""]  # drop empty fragments from trailing delimiters

    label_counts = all_tokens.value_counts()
    tokens_per_row = non_null.str.split(delimiter).apply(len)

    return {
        "delimiter": delimiter,
        "vocabulary_size": int(label_counts.shape[0]),
        "avg_labels_per_row": round(float(tokens_per_row.mean()), 2),
        "label_frequencies": {
            str(k): int(v) for k, v in label_counts.head(20).items()
        },
    }