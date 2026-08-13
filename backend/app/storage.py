import uuid
from datetime import datetime, timezone

from app.db import bytes_to_dataframe, dataframe_to_bytes, get_connection
import pandas as pd


class DatasetStore:
    """
    SQLite-backed dataset store. Every applied transformation creates a
    NEW version row rather than overwriting — this is what makes
    undo/redo possible. `current_version` on the datasets table is the
    pointer that determines which version is "active" right now.
    """

    def add(self, filename: str, df: pd.DataFrame) -> str:
        dataset_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO datasets (dataset_id, filename, current_version, created_at) VALUES (?, ?, 1, ?)",
                (dataset_id, filename, now),
            )
            conn.execute(
                "INSERT INTO dataset_versions (dataset_id, version_num, description, timestamp, data) VALUES (?, 1, ?, ?, ?)",
                (dataset_id, "Initial upload", now, dataframe_to_bytes(df)),
            )
            conn.commit()
        finally:
            conn.close()

        return dataset_id

    def get(self, dataset_id: str) -> pd.DataFrame | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT current_version FROM datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
            if row is None:
                return None

            version_row = conn.execute(
                "SELECT data FROM dataset_versions WHERE dataset_id = ? AND version_num = ?",
                (dataset_id, row["current_version"]),
            ).fetchone()
            if version_row is None:
                return None

            return bytes_to_dataframe(version_row["data"])
        finally:
            conn.close()

    def get_filename(self, dataset_id: str) -> str | None:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT filename FROM datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
            return row["filename"] if row else None
        finally:
            conn.close()

    def exists(self, dataset_id: str) -> bool:
        return self.get_filename(dataset_id) is not None

    def update(self, dataset_id: str, df: pd.DataFrame, description: str = "Transformation applied") -> None:
        """
        Creates a NEW version rather than overwriting. If the current
        version isn't the latest one (i.e. the user has undone some
        steps and is now applying something new), every version AFTER
        the current one is deleted first — this is standard undo/redo
        behavior: making a new change from a "rewound" state discards
        the redo history, since it no longer makes sense.
        """
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT current_version FROM datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Dataset {dataset_id} not found")

            current_version = row["current_version"]

            conn.execute(
                "DELETE FROM dataset_versions WHERE dataset_id = ? AND version_num > ?",
                (dataset_id, current_version),
            )

            new_version = current_version + 1
            now = datetime.now(timezone.utc).isoformat()

            conn.execute(
                "INSERT INTO dataset_versions (dataset_id, version_num, description, timestamp, data) VALUES (?, ?, ?, ?, ?)",
                (dataset_id, new_version, description, now, dataframe_to_bytes(df)),
            )
            conn.execute(
                "UPDATE datasets SET current_version = ? WHERE dataset_id = ?",
                (new_version, dataset_id),
            )
            conn.commit()
        finally:
            conn.close()

    def undo(self, dataset_id: str) -> pd.DataFrame:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT current_version FROM datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Dataset {dataset_id} not found")

            current_version = row["current_version"]
            if current_version <= 1:
                raise ValueError("Already at the earliest version — nothing to undo.")

            new_version = current_version - 1
            conn.execute(
                "UPDATE datasets SET current_version = ? WHERE dataset_id = ?",
                (new_version, dataset_id),
            )
            conn.commit()
        finally:
            conn.close()

        return self.get(dataset_id)

    def redo(self, dataset_id: str) -> pd.DataFrame:
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT current_version FROM datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Dataset {dataset_id} not found")

            current_version = row["current_version"]
            max_row = conn.execute(
                "SELECT MAX(version_num) as max_v FROM dataset_versions WHERE dataset_id = ?",
                (dataset_id,),
            ).fetchone()
            max_version = max_row["max_v"]

            if current_version >= max_version:
                raise ValueError("Already at the latest version — nothing to redo.")

            new_version = current_version + 1
            conn.execute(
                "UPDATE datasets SET current_version = ? WHERE dataset_id = ?",
                (new_version, dataset_id),
            )
            conn.commit()
        finally:
            conn.close()

        return self.get(dataset_id)

    def restore(self, dataset_id: str, version_num: int) -> pd.DataFrame:
        conn = get_connection()
        try:
            exists = conn.execute(
                "SELECT 1 FROM dataset_versions WHERE dataset_id = ? AND version_num = ?",
                (dataset_id, version_num),
            ).fetchone()
            if exists is None:
                raise ValueError(f"Version {version_num} does not exist for this dataset.")

            conn.execute(
                "UPDATE datasets SET current_version = ? WHERE dataset_id = ?",
                (version_num, dataset_id),
            )
            conn.commit()
        finally:
            conn.close()

        return self.get(dataset_id)

    def get_history(self, dataset_id: str) -> list[dict]:
        conn = get_connection()
        try:
            current_row = conn.execute(
                "SELECT current_version FROM datasets WHERE dataset_id = ?", (dataset_id,)
            ).fetchone()
            current_version = current_row["current_version"] if current_row else None

            rows = conn.execute(
                "SELECT version_num, description, timestamp FROM dataset_versions "
                "WHERE dataset_id = ? ORDER BY version_num ASC",
                (dataset_id,),
            ).fetchall()

            return [
                {
                    "version_num": r["version_num"],
                    "description": r["description"],
                    "timestamp": r["timestamp"],
                    "is_current": r["version_num"] == current_version,
                }
                for r in rows
            ]
        finally:
            conn.close()

    # --- Type overrides: unchanged from before, still separate from versioning ---

    def get_overrides(self, dataset_id: str) -> dict[str, str]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT column, logical_type FROM dataset_overrides WHERE dataset_id = ?",
                (dataset_id,),
            ).fetchall()
            return {r["column"]: r["logical_type"] for r in rows}
        finally:
            conn.close()

    def set_override(self, dataset_id: str, column: str, logical_type: str) -> None:
        df = self.get(dataset_id)
        if df is None:
            raise KeyError(f"Dataset {dataset_id} not found")
        if column not in df.columns:
            raise KeyError(f"Column {column} not found in dataset {dataset_id}")

        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO dataset_overrides (dataset_id, column, logical_type) VALUES (?, ?, ?)",
                (dataset_id, column, logical_type),
            )
            conn.commit()
        finally:
            conn.close()

    def clear_override(self, dataset_id: str, column: str) -> None:
        conn = get_connection()
        try:
            conn.execute(
                "DELETE FROM dataset_overrides WHERE dataset_id = ? AND column = ?",
                (dataset_id, column),
            )
            conn.commit()
        finally:
            conn.close()

    def list_datasets(self) -> list[dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT dataset_id, filename, current_version, created_at FROM datasets ORDER BY created_at DESC"
            ).fetchall()

            results = []
            for r in rows:
                latest_version_row = conn.execute(
                    "SELECT MAX(version_num) as max_v FROM dataset_versions WHERE dataset_id = ?",
                    (r["dataset_id"],),
                ).fetchone()
                total_versions = latest_version_row["max_v"] if latest_version_row else 1

                results.append(
                    {
                        "dataset_id": r["dataset_id"],
                        "filename": r["filename"],
                        "created_at": r["created_at"],
                        "current_version": r["current_version"],
                        "total_versions": total_versions,
                    }
                )
            return results
        finally:
            conn.close()

    def delete_dataset(self, dataset_id: str) -> None:
        conn = get_connection()
        try:
            conn.execute("DELETE FROM dataset_versions WHERE dataset_id = ?", (dataset_id,))
            conn.execute("DELETE FROM dataset_overrides WHERE dataset_id = ?", (dataset_id,))
            conn.execute("DELETE FROM datasets WHERE dataset_id = ?", (dataset_id,))
            conn.commit()
        finally:
            conn.close()


dataset_store = DatasetStore()