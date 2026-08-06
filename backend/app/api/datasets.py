import io

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile

from app.schemas import DatasetOverview, UploadResponse
from app.services.dataset_service import compute_overview
from app.storage import dataset_store

router = APIRouter(prefix="/datasets", tags=["datasets"])


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
    df = dataset_store.get(dataset_id)
    if df is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")

    filename = dataset_store.get_filename(dataset_id)
    return compute_overview(dataset_id=dataset_id, filename=filename, df=df)