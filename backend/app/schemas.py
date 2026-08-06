from pydantic import BaseModel


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