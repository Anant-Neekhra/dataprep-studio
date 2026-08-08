import uuid

import pandas as pd


class DatasetStore:
    def __init__(self):
        self._datasets: dict[str, dict] = {}

    def add(self, filename: str, df: pd.DataFrame) -> str:
        dataset_id = str(uuid.uuid4())
        self._datasets[dataset_id] = {
            "filename": filename,
            "df": df,
            "type_overrides": {},  # column_name -> logical type string
        }
        return dataset_id

    def get(self, dataset_id: str) -> pd.DataFrame | None:
        entry = self._datasets.get(dataset_id)
        return entry["df"] if entry else None

    def get_filename(self, dataset_id: str) -> str | None:
        entry = self._datasets.get(dataset_id)
        return entry["filename"] if entry else None

    def exists(self, dataset_id: str) -> bool:
        return dataset_id in self._datasets

    def get_overrides(self, dataset_id: str) -> dict[str, str]:
        entry = self._datasets.get(dataset_id)
        return entry["type_overrides"] if entry else {}

    def set_override(self, dataset_id: str, column: str, logical_type: str) -> None:
        entry = self._datasets.get(dataset_id)
        if entry is None:
            raise KeyError(f"Dataset {dataset_id} not found")
        if column not in entry["df"].columns:
            raise KeyError(f"Column {column} not found in dataset {dataset_id}")
        entry["type_overrides"][column] = logical_type

    def clear_override(self, dataset_id: str, column: str) -> None:
        entry = self._datasets.get(dataset_id)
        if entry:
            entry["type_overrides"].pop(column, None)

    def update(self, dataset_id: str, df: pd.DataFrame) -> None:
        entry = self._datasets.get(dataset_id)
        if entry is None:
            raise KeyError(f"Dataset {dataset_id} not found")
        entry["df"] = df


dataset_store = DatasetStore()