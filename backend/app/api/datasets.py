import io

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile

from app.rule_engine.engine import evaluate_dataset_rules, evaluate_rules
from app.rule_engine.facts import build_dataset_facts, build_facts
from app.schemas import (
    ColumnTypeInfo,
    CompareStrategiesRequest,
    CompareStrategiesResponse,
    DatasetOverview,
    DatasetProfile,
    DuplicateColumnPair,
    DuplicateColumnsPreview,
    DuplicateRowsPreview,
    ImputePreviewResponse,
    ImputeRequest,
    Recommendation,
    RemoveDuplicateColumnsRequest,
    RemoveDuplicateRowsRequest,
    TypeOverrideRequest,
    UploadResponse,
    DtypeConversionPreview,
    DtypeConversionRequest,
)
from app.services.imputation_service import compare_strategies, impute_column_in_dataframe, preview_imputation
from app.services.dataset_service import compute_overview, get_effective_type
from app.services.profiling_service import compute_profile, profile_column
from app.storage import dataset_store
from app.services.quality_service import (
    detect_duplicate_columns,
    detect_duplicate_rows,
    remove_duplicate_columns,
    remove_duplicate_rows,
)
from app.services.datatype_service import convert_column_dtype, summarize_dtype_conversion

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _get_df_or_404(dataset_id: str) -> pd.DataFrame:
    df = dataset_store.get(dataset_id)
    if df is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    return df


@router.post("/upload", response_model=UploadResponse)
async def upload_dataset(file: UploadFile) -> UploadResponse:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported right now.")

    raw_bytes = await file.read()

    try:
        df = pd.read_csv(io.BytesIO(raw_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded CSV has no rows.")

    dataset_id = dataset_store.add(filename=file.filename, df=df)

    return UploadResponse(
        dataset_id=dataset_id,
        filename=file.filename,
        rows=df.shape[0],
        columns=df.shape[1],
    )


@router.get("/{dataset_id}/overview", response_model=DatasetOverview)
def get_dataset_overview(dataset_id: str) -> DatasetOverview:
    df = _get_df_or_404(dataset_id)
    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=df, overrides=overrides)


@router.get("/{dataset_id}/profile", response_model=DatasetProfile)
def get_dataset_profile(dataset_id: str) -> DatasetProfile:
    df = _get_df_or_404(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_profile(dataset_id=dataset_id, df=df, overrides=overrides)


@router.get("/{dataset_id}/column-types", response_model=list[ColumnTypeInfo])
def get_column_types(dataset_id: str) -> list[ColumnTypeInfo]:
    df = _get_df_or_404(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)

    results = []
    for col in df.columns:
        detected, effective, is_overridden = get_effective_type(df[col], col, overrides)
        results.append(
            ColumnTypeInfo(
                column=col,
                pandas_dtype=str(df[col].dtype),
                detected_type=detected,
                effective_type=effective,
                is_overridden=is_overridden,
            )
        )
    return results


@router.put("/{dataset_id}/columns/{column}/type", response_model=ColumnTypeInfo)
def override_column_type(
    dataset_id: str, column: str, body: TypeOverrideRequest
) -> ColumnTypeInfo:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    dataset_store.set_override(dataset_id, column, body.logical_type)

    overrides = dataset_store.get_overrides(dataset_id)
    detected, effective, is_overridden = get_effective_type(df[column], column, overrides)
    return ColumnTypeInfo(
        column=column,
        pandas_dtype=str(df[column].dtype),
        detected_type=detected,
        effective_type=effective,
        is_overridden=is_overridden,
    )


@router.delete("/{dataset_id}/columns/{column}/type", response_model=ColumnTypeInfo)
def clear_column_type_override(dataset_id: str, column: str) -> ColumnTypeInfo:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    dataset_store.clear_override(dataset_id, column)

    overrides = dataset_store.get_overrides(dataset_id)
    detected, effective, is_overridden = get_effective_type(df[column], column, overrides)
    return ColumnTypeInfo(
        column=column,
        pandas_dtype=str(df[column].dtype),
        detected_type=detected,
        effective_type=effective,
        is_overridden=is_overridden,
    )

@router.get("/{dataset_id}/recommendations", response_model=list[Recommendation])
def get_recommendations(dataset_id: str) -> list[Recommendation]:
    df = _get_df_or_404(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)

    all_recommendations = []

    # Column-level recommendations (missing values, quality issues, etc.)
    for col in df.columns:
        _, effective_type, _ = get_effective_type(df[col], col, overrides)
        profile = profile_column(df[col], col, effective_type)
        facts = build_facts(profile, series=df[col])
        recommendations = evaluate_rules(col, effective_type, facts)
        all_recommendations.extend(recommendations)

    # Dataset-level recommendations (duplicate rows/columns)
    dataset_facts = build_dataset_facts(df)
    all_recommendations.extend(evaluate_dataset_rules(dataset_facts))

    return all_recommendations

@router.post("/{dataset_id}/columns/{column}/impute/preview", response_model=ImputePreviewResponse)
def preview_column_imputation(
    dataset_id: str, column: str, body: ImputeRequest
) -> ImputePreviewResponse:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    try:
        result = preview_imputation(df, column, body.strategy, body.constant_value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ImputePreviewResponse(
        column=column,
        strategy=body.strategy,
        before=result["before"],
        after=result["after"],
        sample_before=result["sample_before"],
        sample_after=result["sample_after"],
    )


@router.post("/{dataset_id}/columns/{column}/impute/apply", response_model=DatasetOverview)
def apply_column_imputation(
    dataset_id: str, column: str, body: ImputeRequest
) -> DatasetOverview:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    try:
        new_df = impute_column_in_dataframe(df, column, body.strategy, body.constant_value)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    dataset_store.update(dataset_id, new_df)

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)


@router.post("/{dataset_id}/columns/{column}/impute/compare", response_model=CompareStrategiesResponse)
def compare_imputation_strategies(
    dataset_id: str, column: str, body: CompareStrategiesRequest
) -> CompareStrategiesResponse:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    try:
        result = compare_strategies(df, column, body.strategy_a, body.strategy_b)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CompareStrategiesResponse(
        column=column,
        strategy_a=body.strategy_a,
        strategy_b=body.strategy_b,
        before=result["before"],
        after_a=result["after_a"],
        after_b=result["after_b"],
    )

@router.get("/{dataset_id}/duplicates/rows/preview", response_model=DuplicateRowsPreview)
def preview_duplicate_rows(dataset_id: str) -> DuplicateRowsPreview:
    df = _get_df_or_404(dataset_id)
    dup_info = detect_duplicate_rows(df)

    duplicate_rows = df[df.duplicated(keep="first")]
    sample = duplicate_rows.head(5).to_dict(orient="records")

    return DuplicateRowsPreview(
        duplicate_count=dup_info["count"],
        duplicate_percentage=dup_info["percentage"],
        rows_after_removal=len(df) - dup_info["count"],
        sample_duplicate_rows=sample,
    )


@router.post("/{dataset_id}/duplicates/rows/apply", response_model=DatasetOverview)
def apply_remove_duplicate_rows(
    dataset_id: str, body: RemoveDuplicateRowsRequest
) -> DatasetOverview:
    df = _get_df_or_404(dataset_id)
    new_df = remove_duplicate_rows(df, keep=body.keep)
    dataset_store.update(dataset_id, new_df)

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)


@router.get("/{dataset_id}/duplicates/columns/preview", response_model=DuplicateColumnsPreview)
def preview_duplicate_columns(dataset_id: str) -> DuplicateColumnsPreview:
    df = _get_df_or_404(dataset_id)
    pairs = detect_duplicate_columns(df)
    return DuplicateColumnsPreview(
        pairs=[DuplicateColumnPair(column_a=a, column_b=b) for a, b in pairs]
    )


@router.post("/{dataset_id}/duplicates/columns/apply", response_model=DatasetOverview)
def apply_remove_duplicate_columns(
    dataset_id: str, body: RemoveDuplicateColumnsRequest
) -> DatasetOverview:
    df = _get_df_or_404(dataset_id)

    missing = [c for c in body.columns_to_drop if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Column(s) not found: {missing}")

    new_df = remove_duplicate_columns(df, body.columns_to_drop)
    dataset_store.update(dataset_id, new_df)

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)

@router.post("/{dataset_id}/columns/{column}/convert/preview", response_model=DtypeConversionPreview)
def preview_dtype_conversion(
    dataset_id: str, column: str, body: DtypeConversionRequest
) -> DtypeConversionPreview:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    try:
        result = summarize_dtype_conversion(df, column, body.target_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return DtypeConversionPreview(column=column, **result)


@router.post("/{dataset_id}/columns/{column}/convert/apply", response_model=DatasetOverview)
def apply_dtype_conversion(
    dataset_id: str, column: str, body: DtypeConversionRequest
) -> DatasetOverview:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    try:
        new_df = convert_column_dtype(df, column, body.target_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    dataset_store.update(dataset_id, new_df)

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)