import io

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile

from app.rule_engine.engine import evaluate_dataset_rules, evaluate_rules
from app.rule_engine.facts import build_dataset_facts, build_facts
from app.schemas import (
    ColumnTypeInfo,
    DatasetOverview,
    DatasetProfile,
    Recommendation,
    TypeOverrideRequest,
    UploadResponse,
)
from app.services.dataset_service import compute_overview, get_effective_type
from app.services.profiling_service import compute_profile, profile_column
from app.storage import dataset_store

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