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

LogicalType = Literal["numerical", "categorical", "boolean", "datetime", "text", "id", "mixed"]

ALLOWED_LOGICAL_TYPES: list[str] = [
    "numerical", "categorical", "boolean", "datetime", "text", "id", "mixed"
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