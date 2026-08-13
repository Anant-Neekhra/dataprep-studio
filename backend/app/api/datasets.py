import io

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile
from scipy.stats import kurtosis as scipy_stats_kurtosis
from scipy.stats import skew as scipy_stats_skew
from typing import Literal

from app.rule_engine.engine import evaluate_dataset_rules, evaluate_rules
from app.rule_engine.facts import build_dataset_facts, build_facts
from app.schemas import (
    BoxPlotData,
    ColumnTypeInfo,
    CompareStrategiesRequest,
    CompareStrategiesResponse,
    DatasetList,
    DatasetOverview,
    DatasetProfile,
    DatasetSummary,
    DuplicateColumnPair,
    DuplicateColumnsPreview,
    DuplicateRowsPreview,
    ImputePreviewResponse,
    ImputeRequest,
    Recommendation,
    RemoveDuplicateColumnsRequest,
    RemoveDuplicateRowsRequest,
    ScatterData,
    TypeOverrideRequest,
    UploadResponse,
    DtypeConversionPreview,
    DtypeConversionRequest,
    DistributionAnalysis, 
    HistogramData, 
    NormalityTestResult, 
    TransformPreview, 
    TransformRequest,
    OutlierDetectionResult, 
    OutlierTreatmentRequest,
    CorrelationMatrix, 
    CorrelationPair, 
    HighCorrelationPairs,
    CategoryFrequency, 
    MultiLabelProfile,
    FeatureInspectorReport,
    EncodingRequest, 
    ScalingRequest,
    VersionHistory, 
    VersionInfo
)
from app.services.imputation_service import compare_strategies, impute_column_in_dataframe, preview_imputation
from app.services.dataset_service import compute_overview, get_effective_type, drop_column
from app.services.profiling_service import compute_profile, profile_column
from app.storage import dataset_store
from app.services.quality_service import (
    detect_duplicate_columns,
    detect_duplicate_rows,
    remove_duplicate_columns,
    remove_duplicate_rows,
)
from app.services.datatype_service import convert_column_dtype, summarize_dtype_conversion
from app.services.distribution_service import (
    apply_transform,
    compute_histogram_bins,
    normality_test,
)
from app.services.outlier_service import cap_outliers, detect_outliers, remove_outliers
from app.services.correlation_service import (
    compute_categorical_correlation_matrix,
    compute_numeric_correlation_matrix,
    detect_high_correlation_pairs,
)
from app.services.categorical_service import (
    compute_category_frequencies,
    detect_multi_label_delimiter,
    profile_multi_label_column,
)
from app.services.profiling_service import compute_entropy
from app.services.encoding_service import (
    binary_encode,
    frequency_encode,
    label_encode,
    multi_label_binarize,
    one_hot_encode,
    ordinal_encode,
)
from app.services.scaling_service import apply_scaling
from app.services.categorical_service import detect_multi_label_delimiter

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

@router.get("/{dataset_id}/columns/{column}/distribution", response_model=DistributionAnalysis)
def get_column_distribution(dataset_id: str, column: str) -> DistributionAnalysis:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    series = df[column]
    if not pd.api.types.is_numeric_dtype(series):
        raise HTTPException(
            status_code=400, detail="Distribution analysis requires a numeric column."
        )

    non_null = series.dropna()
    skewness = float(scipy_stats_skew(non_null)) if len(non_null) >= 3 else None
    kurtosis = float(scipy_stats_kurtosis(non_null)) if len(non_null) >= 3 else None

    hist = compute_histogram_bins(series)
    norm_result = normality_test(series)

    return DistributionAnalysis(
        column=column,
        skewness=skewness,
        kurtosis=kurtosis,
        histogram=HistogramData(**hist),
        normality_test=NormalityTestResult(**norm_result),
    )


@router.post("/{dataset_id}/columns/{column}/transform/preview", response_model=TransformPreview)
def preview_transform(
    dataset_id: str, column: str, body: TransformRequest
) -> TransformPreview:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    before_series = df[column]
    before_non_null = before_series.dropna()
    before_skew = float(scipy_stats_skew(before_non_null)) if len(before_non_null) >= 3 else None

    try:
        after_series = apply_transform(before_series, body.transform)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    after_non_null = after_series.dropna()
    after_skew = float(scipy_stats_skew(after_non_null)) if len(after_non_null) >= 3 else None

    return TransformPreview(
        column=column,
        transform=body.transform,
        before_skewness=before_skew,
        after_skewness=after_skew,
        before_histogram=HistogramData(**compute_histogram_bins(before_series)),
        after_histogram=HistogramData(**compute_histogram_bins(after_series)),
    )


@router.post("/{dataset_id}/columns/{column}/transform/apply", response_model=DatasetOverview)
def apply_column_transform(
    dataset_id: str, column: str, body: TransformRequest
) -> DatasetOverview:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    try:
        new_df = df.copy()
        new_df[column] = apply_transform(df[column], body.transform)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    dataset_store.update(dataset_id, new_df)

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)

@router.delete("/{dataset_id}/columns/{column}", response_model=DatasetOverview)
def delete_column(dataset_id: str, column: str) -> DatasetOverview:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    new_df = drop_column(df, column)
    dataset_store.update(dataset_id, new_df)

    # Column overrides for a dropped column are stale — clean up so they
    # don't linger and cause confusion if a future column happens to
    # share the same name.
    dataset_store.clear_override(dataset_id, column)

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)

@router.get("/{dataset_id}/columns/{column}/outliers", response_model=OutlierDetectionResult)
def get_column_outliers(
    dataset_id: str, column: str, method: Literal["iqr", "zscore", "modified_zscore"] = "iqr"
) -> OutlierDetectionResult:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    if not pd.api.types.is_numeric_dtype(df[column]):
        raise HTTPException(status_code=400, detail="Outlier detection requires a numeric column.")

    result = detect_outliers(df[column], method)
    return OutlierDetectionResult(column=column, method=method, **result)


@router.post("/{dataset_id}/columns/{column}/outliers/apply", response_model=DatasetOverview)
def apply_outlier_treatment(
    dataset_id: str, column: str, body: OutlierTreatmentRequest
) -> DatasetOverview:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    if not pd.api.types.is_numeric_dtype(df[column]):
        raise HTTPException(status_code=400, detail="Outlier treatment requires a numeric column.")

    if body.action == "remove":
        new_df = remove_outliers(df, column, body.method)
    else:
        new_df = cap_outliers(df, column, body.method)

    dataset_store.update(dataset_id, new_df)

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)

@router.get("/{dataset_id}/correlation", response_model=CorrelationMatrix)
def get_correlation_matrix(
    dataset_id: str, method: Literal["pearson", "spearman", "kendall"] = "pearson"
) -> CorrelationMatrix:
    df = _get_df_or_404(dataset_id)
    result = compute_numeric_correlation_matrix(df, method=method)
    return CorrelationMatrix(columns=result["columns"], matrix=result["matrix"], method=method)


@router.get("/{dataset_id}/correlation/high-pairs", response_model=HighCorrelationPairs)
def get_high_correlation_pairs(dataset_id: str, threshold: float = 0.8) -> HighCorrelationPairs:
    df = _get_df_or_404(dataset_id)
    result = compute_numeric_correlation_matrix(df, method="pearson")
    pairs = detect_high_correlation_pairs(result["columns"], result["matrix"], threshold=threshold)
    return HighCorrelationPairs(
        pairs=[CorrelationPair(**p) for p in pairs], threshold=threshold
    )

@router.get("/{dataset_id}/columns/{column}/category-frequencies", response_model=CategoryFrequency)
def get_category_frequencies(dataset_id: str, column: str) -> CategoryFrequency:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    result = compute_category_frequencies(df[column])
    return CategoryFrequency(**result)


@router.get("/{dataset_id}/columns/{column}/multi-label-profile", response_model=MultiLabelProfile)
def get_multi_label_profile(dataset_id: str, column: str) -> MultiLabelProfile:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    delimiter = detect_multi_label_delimiter(df[column])
    if delimiter is None:
        raise HTTPException(
            status_code=400,
            detail="Could not detect a consistent delimiter — this may not be a multi-label column.",
        )

    result = profile_multi_label_column(df[column], delimiter)
    return MultiLabelProfile(column=column, **result)

@router.get("/{dataset_id}/columns/{column}/inspect", response_model=FeatureInspectorReport)
def inspect_column(dataset_id: str, column: str) -> FeatureInspectorReport:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    overrides = dataset_store.get_overrides(dataset_id)
    series = df[column]

    detected, effective, is_overridden = get_effective_type(series, column, overrides)
    profile = profile_column(series, column, effective)
    facts = build_facts(profile, series=series)

    quality_flags = {
        "has_whitespace": facts["has_whitespace"],
        "has_case_inconsistency": facts["has_case_inconsistency"],
        "is_constant": facts["is_constant"],
        "is_low_variance": facts["is_low_variance"],
    }

    outlier_summary = None
    top_correlated = []
    possible_transformations = []

    if effective == "numerical":
        outlier_result = detect_outliers(series, "iqr")
        outlier_summary = {
            "outlier_count": outlier_result["outlier_count"],
            "outlier_percentage": outlier_result["outlier_percentage"],
        }

        corr_result = compute_numeric_correlation_matrix(df, method="pearson")
        if column in corr_result["columns"]:
            idx = corr_result["columns"].index(column)
            other_correlations = [
                {"column": other_col, "correlation": corr_result["matrix"][idx][j]}
                for j, other_col in enumerate(corr_result["columns"])
                if other_col != column
            ]
            other_correlations.sort(key=lambda x: abs(x["correlation"]), reverse=True)
            top_correlated = other_correlations[:5]

        if facts["skewness"] and abs(facts["skewness"]) > 0.5:
            possible_transformations.append("log/sqrt/Box-Cox/Yeo-Johnson transform (see Distribution Analysis)")
        if facts["outlier_pct"] > 1:
            possible_transformations.append("Outlier treatment — cap or remove (see Outlier Analysis)")

    elif effective == "categorical":
        possible_transformations.append("Encoding — one-hot, label, or ordinal (see Encoding Advisor, coming Day 14)")

    elif effective == "multi_label":
        possible_transformations.append("Multi-label binarization (see Encoding Advisor, coming Day 14)")

    elif effective == "id":
        possible_transformations.append("Consider excluding from feature set — likely carries no predictive signal")

    recommendations = evaluate_rules(column, effective, facts)

    return FeatureInspectorReport(
        column=column,
        pandas_dtype=str(series.dtype),
        detected_type=detected,
        effective_type=effective,
        is_overridden=is_overridden,
        memory_usage_bytes=int(series.memory_usage(deep=True)),
        profile=profile,
        entropy=compute_entropy(series),
        quality_flags=quality_flags,
        outlier_summary=outlier_summary,
        top_correlated_columns=top_correlated,
        recommendations=recommendations,
        possible_transformations=possible_transformations,
    )

@router.post("/{dataset_id}/columns/{column}/encode/apply", response_model=DatasetOverview)
def apply_encoding(dataset_id: str, column: str, body: EncodingRequest) -> DatasetOverview:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    try:
        if body.method == "one_hot":
            new_df = one_hot_encode(df, column)
        elif body.method == "label":
            new_df = label_encode(df, column)
        elif body.method == "ordinal":
            if not body.order:
                raise ValueError("Ordinal encoding requires an 'order' list of categories.")
            new_df = ordinal_encode(df, column, body.order)
        elif body.method == "frequency":
            new_df = frequency_encode(df, column)
        elif body.method == "binary":
            new_df = binary_encode(df, column)
        elif body.method == "multi_label":
            delimiter = body.delimiter or detect_multi_label_delimiter(df[column])
            if delimiter is None:
                raise ValueError("Could not detect a delimiter for multi-label binarization.")
            new_df = multi_label_binarize(df, column, delimiter)
        else:
            raise ValueError(f"Unknown encoding method: {body.method}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    dataset_store.update(dataset_id, new_df)

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)


@router.post("/{dataset_id}/columns/{column}/scale/apply", response_model=DatasetOverview)
def apply_column_scaling(dataset_id: str, column: str, body: ScalingRequest) -> DatasetOverview:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    try:
        new_df = apply_scaling(df, column, body.method)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    dataset_store.update(dataset_id, new_df)

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)

@router.get("/{dataset_id}/visualize/scatter", response_model=ScatterData)
def get_scatter_data(dataset_id: str, x_column: str, y_column: str) -> ScatterData:
    df = _get_df_or_404(dataset_id)
    for col in (x_column, y_column):
        if col not in df.columns:
            raise HTTPException(status_code=404, detail=f"Column '{col}' not found.")

    subset = df[[x_column, y_column]].dropna()
    # Cap sample size — scatter plots with tens of thousands of points
    # render slowly and add little visual value beyond a few thousand.
    if len(subset) > 3000:
        subset = subset.sample(3000, random_state=42)

    return ScatterData(
        x_values=subset[x_column].tolist(),
        y_values=subset[y_column].tolist(),
        x_column=x_column,
        y_column=y_column,
    )


@router.get("/{dataset_id}/visualize/boxplot", response_model=BoxPlotData)
def get_boxplot_data(dataset_id: str, column: str) -> BoxPlotData:
    df = _get_df_or_404(dataset_id)
    if column not in df.columns:
        raise HTTPException(status_code=404, detail=f"Column '{column}' not found.")

    series = df[column].dropna()
    if not pd.api.types.is_numeric_dtype(series):
        raise HTTPException(status_code=400, detail="Box plot requires a numeric column.")

    return BoxPlotData(
        column=column,
        values=series.tolist()[:3000],
        q1=float(series.quantile(0.25)),
        median=float(series.median()),
        q3=float(series.quantile(0.75)),
        minimum=float(series.min()),
        maximum=float(series.max()),
    )

@router.get("/{dataset_id}/history", response_model=VersionHistory)
def get_dataset_history(dataset_id: str) -> VersionHistory:
    if not dataset_store.exists(dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found.")

    history = dataset_store.get_history(dataset_id)
    return VersionHistory(
        dataset_id=dataset_id,
        versions=[VersionInfo(**v) for v in history],
    )


@router.post("/{dataset_id}/undo", response_model=DatasetOverview)
def undo_last_change(dataset_id: str) -> DatasetOverview:
    if not dataset_store.exists(dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found.")

    try:
        new_df = dataset_store.undo(dataset_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)


@router.post("/{dataset_id}/redo", response_model=DatasetOverview)
def redo_last_change(dataset_id: str) -> DatasetOverview:
    if not dataset_store.exists(dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found.")

    try:
        new_df = dataset_store.redo(dataset_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)


@router.post("/{dataset_id}/restore/{version_num}", response_model=DatasetOverview)
def restore_dataset_version(dataset_id: str, version_num: int) -> DatasetOverview:
    if not dataset_store.exists(dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found.")

    try:
        new_df = dataset_store.restore(dataset_id, version_num)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    filename = dataset_store.get_filename(dataset_id)
    overrides = dataset_store.get_overrides(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=new_df, overrides=overrides)

@router.get("", response_model=DatasetList)
def list_all_datasets() -> DatasetList:
    datasets = dataset_store.list_datasets()
    return DatasetList(datasets=[DatasetSummary(**d) for d in datasets])

@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: str) -> dict:
    if not dataset_store.exists(dataset_id):
        raise HTTPException(status_code=404, detail="Dataset not found.")

    dataset_store.delete_dataset(dataset_id)
    return {"message": f"Dataset {dataset_id} deleted."}