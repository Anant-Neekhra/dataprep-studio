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