# DataPrep Studio

An interactive, explainable data analysis and preprocessing workbench. Upload a dataset, and instead of black-box AutoML, get transparent, rule-based recommendations for every cleaning and preparation step — with the reasoning, alternatives, and trade-offs always shown before anything is applied.

## Architecture

Two independent services. The frontend is a thin client of a documented REST API.

## Tech Stack

**Backend:** FastAPI, Pydantic, Pandas, NumPy, SciPy, Scikit-learn, PyYAML, PyArrow
**Frontend:** NiceGUI, Plotly
**Storage:** SQLite (history/versioning), Parquet/CSV (export)
**Infra:** Docker, Docker Compose, GitHub Actions, Pytest, Ruff, Black

## Running locally

**Backend:**
```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
API docs at `http://localhost:8000/docs`

**Frontend** (in a second terminal):
```bash
cd frontend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
App at `http://localhost:8080`

## Progress Log

### Day 1 — Foundation
- FastAPI backend skeleton with a `/health` endpoint (Pydantic response model, CORS configured for the frontend origin)
- NiceGUI frontend skeleton that calls the backend `/health` endpoint on load and displays live connection status
- Confirmed end-to-end: frontend successfully reaches backend over HTTP, green "Connected" status shown
- Separate virtual environments for backend and frontend, `.gitignore` configured

### Day 2 — Dataset Upload & Overview
- `POST /datasets/upload` endpoint: accepts CSV files, parses with Pandas, validates (rejects non-CSV, empty files, unparseable files with proper 400 errors), stores in-memory keyed by a generated `dataset_id`
- `GET /datasets/{id}/overview` endpoint: returns rows, columns, memory usage, missing value %, duplicate row count, feature type breakdown (numerical/categorical/boolean/datetime/text/mixed), and per-column dtypes
- In-memory `DatasetStore` (Day 15 will migrate this to SQLite for persistence across restarts)
- NiceGUI Upload page (`/upload`): file picker → calls upload endpoint → calls overview endpoint → renders stats cards, feature type breakdown, and a column dtype table
- Confirmed end-to-end with a real CSV: correct row/column counts, missing %, and dtype detection

### Day 3 — Data Profiling Engine + Human-in-the-Loop Type Override
- Per-column profiling: count, mean, median, mode, std, variance, min/max, quartiles, range, skewness, kurtosis, missing %, unique count, cardinality ratio (`GET /datasets/{id}/profile`)
- Numeric stats computed only for columns whose **effective type** is `numerical` — prevents meaningless mean/std/skewness on ID-like columns that pandas parses as int64
- **Logical type override system**: separates pandas dtype (fixed) from logical/semantic type (auto-detected, user-overridable)
  - Heuristic auto-detection of ID-like columns (name pattern matching + high-cardinality check)
  - `GET /datasets/{id}/column-types` — detected vs effective type per column
  - `PUT /datasets/{id}/columns/{column}/type` — override a column's logical type
  - `DELETE /datasets/{id}/columns/{column}/type` — revert to auto-detection
  - Overrides propagate through both Overview and Profile endpoints automatically
- NiceGUI Column Type Review page: dropdown per column to override type, shows "Detected → Overridden" state, Apply/Reset buttons wired to the override endpoints
- Verified: ID-like column auto-detected correctly, overriding a numeric column to `id` correctly nulls out its mean/std/skewness in the profile response, reset restores auto-detection