from app.schemas import ColumnProfile


def build_facts(profile: ColumnProfile) -> dict:
    """
    Converts a ColumnProfile into a flat dict of values that YAML rule
    conditions can reference by name. Every key here is a name a
    condition string is allowed to use, e.g. "missing_pct > 30".

    None values are converted to 0 or False rather than left as None,
    because simple_eval doesn't handle comparisons against None
    gracefully (e.g. "skewness > 1" would error if skewness is None).
    A rule that only makes sense when a stat exists should be scoped
    with applies_to instead of relying on None-checks in the condition.
    """
    return {
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
    }