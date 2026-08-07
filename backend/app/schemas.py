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