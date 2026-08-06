import uuid

import pandas as pd


class DatasetStore:
    """
    Holds uploaded datasets in memory while the app is running, keyed by
    a generated dataset_id. This is intentionally simple for now — later
    (Day 15, History Manager) we'll back this with SQLite so versions
    persist across restarts. For Day 2, in-memory is enough to prove the
    upload -> overview flow end to end.
    """

    def __init__(self):
        self._datasets: dict[str, dict] = {}

    def add(self, filename: str, df: pd.DataFrame) -> str:
        dataset_id = str(uuid.uuid4())
        self._datasets[dataset_id] = {
            "filename": filename,
            "df": df,
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


# A single shared instance — every request handler imports this same
# object, so data uploaded in one request is visible in the next.
dataset_store = DatasetStore()