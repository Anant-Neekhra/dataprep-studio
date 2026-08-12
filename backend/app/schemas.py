from pydantic import BaseModel
from typing import Literal


class UploadResponse(BaseModel):
    dataset_id: str
    filename: str
    rows: int
    columns: int


class FeatureTypeBreakdown(BaseModel):
    numerical: int
    categorical: int
    boolean: int
    datetime: int
    text: int
    id: int
    multi_label: int
    mixed: int


class DatasetOverview(BaseModel):
    dataset_id: str
    filename: str
    rows: int
    columns: int
    memory_usage_bytes: int
    missing_values_total: int
    missing_percentage: float
    duplicate_rows: int
    feature_types: FeatureTypeBreakdown
    dtypes: dict[str, str]

class ColumnProfile(BaseModel):
    column: str
    dtype: str
    count: int
    missing_count: int
    missing_percentage: float
    unique_count: int
    cardinality_ratio: float

    # Numeric-only stats — None for non-numeric columns
    mean: float | None = None
    median: float | None = None
    mode: float | str | None = None
    std: float | None = None
    variance: float | None = None
    minimum: float | None = None
    maximum: float | None = None
    q1: float | None = None
    q3: float | None = None
    range: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None


class DatasetProfile(BaseModel):
    dataset_id: str
    columns: list[ColumnProfile]

LogicalType = Literal["numerical", "categorical", "boolean", "datetime", "text", "id", "multi_label", "mixed"]

ALLOWED_LOGICAL_TYPES: list[str] = [
    "numerical", "categorical", "boolean", "datetime", "text", "id", "multi_label", "mixed"
]


class TypeOverrideRequest(BaseModel):
    logical_type: LogicalType


class ColumnTypeInfo(BaseModel):
    column: str
    pandas_dtype: str
    detected_type: str      # what auto-detection would say
    effective_type: str     # what's actually being used (override if present)
    is_overridden: bool

class Recommendation(BaseModel):
    rule_id: str
    category: str
    severity: Literal["low", "medium", "high"]
    column: str
    recommendation: str
    reason: str
    advantages: list[str]
    disadvantages: list[str]
    alternatives: list[str]
    docs_url: str | None = None

class ImputeRequest(BaseModel):
    strategy: Literal["mean", "median", "mode", "constant", "forward_fill", "backward_fill", "drop_rows"]
    constant_value: str | None = None


class ColumnStatsSummary(BaseModel):
    """A lightweight before/after snapshot — not the full ColumnProfile,
    just the numbers that matter for judging an imputation's effect."""
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    missing_count: int
    row_count: int


class ImputePreviewResponse(BaseModel):
    column: str
    strategy: str
    before: ColumnStatsSummary
    after: ColumnStatsSummary
    sample_before: list  # a few original values, for visual comparison
    sample_after: list   # same rows, after imputation


class CompareStrategiesRequest(BaseModel):
    strategy_a: Literal["mean", "median", "mode", "constant", "forward_fill", "backward_fill", "drop_rows"]
    strategy_b: Literal["mean", "median", "mode", "constant", "forward_fill", "backward_fill", "drop_rows"]


class CompareStrategiesResponse(BaseModel):
    column: str
    strategy_a: str
    strategy_b: str
    before: ColumnStatsSummary
    after_a: ColumnStatsSummary
    after_b: ColumnStatsSummary

class DuplicateRowsPreview(BaseModel):
    duplicate_count: int
    duplicate_percentage: float
    rows_after_removal: int
    sample_duplicate_rows: list[dict]


class RemoveDuplicateRowsRequest(BaseModel):
    keep: Literal["first", "last"] = "first"


class DuplicateColumnPair(BaseModel):
    column_a: str
    column_b: str


class DuplicateColumnsPreview(BaseModel):
    pairs: list[DuplicateColumnPair]


class RemoveDuplicateColumnsRequest(BaseModel):
    columns_to_drop: list[str]

class DtypeConversionRequest(BaseModel):
    target_type: Literal["datetime", "integer", "category", "float", "string"]


class DtypeConversionPreview(BaseModel):
    column: str
    before_dtype: str
    after_dtype: str
    before_missing: int
    after_missing: int
    newly_invalid_count: int
    sample_before: list
    sample_after: list

class HistogramData(BaseModel):
    bin_edges: list[float]
    counts: list[int]


class NormalityTestResult(BaseModel):
    statistic: float | None
    p_value: float | None
    is_normal: bool | None


class DistributionAnalysis(BaseModel):
    column: str
    skewness: float | None
    kurtosis: float | None
    histogram: HistogramData
    normality_test: NormalityTestResult


class TransformRequest(BaseModel):
    transform: Literal["none", "log", "sqrt", "box_cox", "yeo_johnson"]


class TransformPreview(BaseModel):
    column: str
    transform: str
    before_skewness: float | None
    after_skewness: float | None
    before_histogram: HistogramData
    after_histogram: HistogramData

class OutlierDetectionResult(BaseModel):
    column: str
    method: str
    outlier_count: int
    outlier_percentage: float
    outlier_values: list
    outlier_indices: list[int]


class OutlierTreatmentRequest(BaseModel):
    method: Literal["iqr", "zscore", "modified_zscore"]
    action: Literal["remove", "cap"]

class CorrelationMatrix(BaseModel):
    columns: list[str]
    matrix: list[list[float]]
    method: str


class CorrelationPair(BaseModel):
    column_a: str
    column_b: str
    correlation: float


class HighCorrelationPairs(BaseModel):
    pairs: list[CorrelationPair]
    threshold: float

class CategoryFrequency(BaseModel):
    categories: list[str]
    counts: list[int]
    percentages: list[float]
    total_unique: int


class MultiLabelProfile(BaseModel):
    column: str
    delimiter: str
    vocabulary_size: int
    avg_labels_per_row: float
    label_frequencies: dict[str, int]

class FeatureInspectorReport(BaseModel):
    column: str
    pandas_dtype: str
    detected_type: str
    effective_type: str
    is_overridden: bool
    memory_usage_bytes: int
    profile: ColumnProfile
    entropy: float | None
    quality_flags: dict  # has_whitespace, has_case_inconsistency, is_constant, is_low_variance
    outlier_summary: dict | None  # None for non-numeric columns
    top_correlated_columns: list[dict]  # [{column, correlation}, ...], numeric only
    recommendations: list[Recommendation]
    possible_transformations: list[str]

class EncodingRequest(BaseModel):
    method: Literal["one_hot", "label", "ordinal", "frequency", "binary", "multi_label"]
    order: list[str] | None = None  # required only for ordinal
    delimiter: str | None = None    # required only for multi_label


class ScalingRequest(BaseModel):
    method: Literal["standard", "minmax", "robust", "maxabs", "normalize"]