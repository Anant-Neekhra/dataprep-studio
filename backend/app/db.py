import sqlite3
from pathlib import Path
import io
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "Version_store" / "dataprep_studio.db"


def get_connection() -> sqlite3.Connection:
    """
    A new connection per call, rather than one shared connection — SQLite
    connections aren't safe to share across threads, and FastAPI can run
    request handlers in different threads (see the run_in_threadpool
    calls in your stack traces from earlier debugging sessions).
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets us access columns by name, not just index
    return conn


def init_db() -> None:
    """Creates tables if they don't already exist. Called once at app startup."""
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                current_version INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT NOT NULL,
                version_num INTEGER NOT NULL,
                description TEXT NOT NULL,
                operation TEXT,
                operation_params TEXT,
                timestamp TEXT NOT NULL,
                data BLOB NOT NULL,
                FOREIGN KEY (dataset_id) REFERENCES datasets (dataset_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dataset_overrides (
                dataset_id TEXT NOT NULL,
                column TEXT NOT NULL,
                logical_type TEXT NOT NULL,
                PRIMARY KEY (dataset_id, column)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def dataframe_to_bytes(df: pd.DataFrame) -> bytes:
    """
    Serializes a DataFrame to Parquet bytes for storage as a BLOB.
    Parquet preserves dtypes correctly (unlike CSV, which would turn
    everything back into strings on reload) — important since we've
    spent many days getting dtypes right (Day 8's Datatype Analyzer,
    Day 3's overrides).
    """
    buffer = io.BytesIO()
    df.to_parquet(buffer, engine="pyarrow")
    return buffer.getvalue()


def bytes_to_dataframe(data: bytes) -> pd.DataFrame:
    """Deserializes Parquet bytes back into a DataFrame."""
    buffer = io.BytesIO(data)
    return pd.read_parquet(buffer, engine="pyarrow")