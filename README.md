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

### Day 4 — Rule Engine + Knowledge Base
- Designed the YAML rule schema: `id`, `category`, `severity` (low/medium/high), `applies_to` (effective type), `condition` (safe expression string), `recommendation`, `reason`, `advantages`, `disadvantages`, `alternatives`, `docs_url`
- Built `knowledge_base/missing_values.yaml` — 7 rules covering low/moderate/high/very-high missingness for both numerical and categorical columns
- Rule engine (`rule_engine/engine.py`): loads all YAML files in `knowledge_base/` at startup, evaluates conditions safely via `simpleeval` (no `eval()`, no arbitrary code execution) against a per-column facts dict
- `rule_engine/facts.py`: bridges `ColumnProfile` → flat facts dict rule conditions can reference
- `GET /datasets/{id}/recommendations`: runs every column through effective-type detection (Day 3) → profiling (Day 3) → rule evaluation (today), returns all matched recommendations across the dataset
- Reusable **Recommendation Card** component in the frontend (`ui.expansion`): shows column + recommendation + severity/category collapsed by default, expands to reveal reason/advantages/disadvantages/alternatives/docs link — this component will be reused for every future module (missing values, outliers, encoding, scaling, etc.)
- Also refined ID-column heuristic from Day 3 to add a word-count signal, correctly distinguishing single-token IDs from near-unique free-text columns
- Verified end-to-end: uploaded a dataset

### Day 5 — Data Quality Module
- Quality detectors (`services/quality_service.py`): whitespace issues, case inconsistency, constant columns, low-variance columns, duplicate rows, duplicate column pairs
- Extended `build_facts()` to accept the raw column series (optional) and compute quality signals alongside existing profiling stats
- New `build_dataset_facts()` — facts scoped to the whole dataset rather than one column, for issues like duplicate rows/columns where no single column is responsible
- Rule engine extended with `applies_to: dataset` support — a separate `evaluate_dataset_rules()` path, explicitly excluded from per-column evaluation
- `knowledge_base/quality.yaml` — whitespace, case inconsistency, constant/low-variance column rules
- `knowledge_base/duplicates.yaml` — duplicate row (tiered by %) and duplicate column rules
- `/datasets/{id}/recommendations` now merges column-level and dataset-level recommendations into one list
- No new frontend work required — the existing Recommendation Card page from Day 4 renders all of today's new rule types automatically, confirming the architecture decision to build that component generically was the right call
- Verified: whitespace/case-inconsistency correctly flagged on a test categorical column, duplicate row detection confirmed on a dataset with repeated records

### Day 6 — Missing Value Engine ("Preview → Apply" + "Why Not?" simulation)
- `DatasetStore.update()` — allows a dataset's working DataFrame to be replaced after a transformation is applied
- `services/imputation_service.py`: pure functions for mean/median/mode/constant/forward-fill/backward-fill/drop-rows strategies, kept side-effect-free (return new Series/DataFrames rather than mutating in place)
- **Strategy validation**: `validate_strategy_for_column()` rejects numeric-only strategies (mean/median) on non-numeric columns with a clear message, instead of letting pandas throw a raw `TypeError` deep in the call stack
- Three endpoints per column: `/impute/preview` (before/after stats + sample values, no mutation), `/impute/apply` (actually updates the stored dataset), `/impute/compare` (runs two strategies side by side on the same original data — powers the "Why Not?" feature)
- All three endpoints properly catch `ValueError` and return clean `400` responses with actionable messages instead of crashing
- Frontend Missing Value Engine page: column dropdown (populated from real column names, replacing an earlier free-text input that was error-prone), strategy picker, Preview/Apply buttons, and a "Why Not?" comparison panel showing two strategies' effects side by side on real data
- Linked directly from Recommendation cards with `category == "missing_values"`

**Bugs found and fixed during testing:**
- `missing_values.yaml` had no rules for `applies_to: text` — a real dataset (Titanic) has a high-cardinality-but-not-unique text column (`Cabin`, 77% missing) that fell through the cracks between "categorical" and "numerical" rules. Added dedicated text-column missing-value rules.
- Free-text column-name input was replaced with a dropdown populated from `/column-types`, eliminating a class of typo/empty-input bugs
- Added `try/except` around all `.json()` calls on error responses in the frontend, so a malformed or empty error body shows a clean message instead of crashing the whole page
- Confirmed that `uvicorn --reload` wipes the in-memory `DatasetStore` on every backend code change — a known limitation until Day 16's SQLite-backed History Manager
- Verified end to end: previewed and applied `constant` imputation on `Cabin`, confirmed dataset-wide missing % dropped, confirmed the corresponding recommendation card disappeared from the Recommendations page after the fix

### Day 7 — Duplicate Analysis (dedicated apply flow)
- `services/quality_service.py` extended: `remove_duplicate_rows()` (keep first/last), `remove_duplicate_columns()` (explicit column list — the tool never guesses which of two identical columns to drop, that's left to the user)
- Four new endpoints: `GET/POST .../duplicates/rows/preview|apply`, `GET/POST .../duplicates/columns/preview|apply`
- Row preview shows duplicate count/percentage, projected row count after removal, and a sample of the actual duplicate rows
- Column preview lists exact-duplicate column pairs; apply takes an explicit list of which columns to drop
- Frontend Duplicates

### Day 8 — Datatype Analyzer
- `services/datatype_service.py`: detectors for datetime-convertible text columns (sampled parsing, threshold-based), whole-number float columns worth converting to int, and low-cardinality object columns worth converting to `category` dtype for memory savings
- `convert_column_dtype()` supports datetime/integer/category/float/string targets; integer conversion uses pandas nullable `Int64` when missing values are present, since standard `int64` can't hold them
- `summarize_dtype_conversion()` powers the preview — explicitly surfaces `newly_invalid_count`, the number of values that would become missing after conversion (e.g. unparseable dates), so nothing changes silently
- `knowledge_base/datatypes.yaml`: object→datetime (both text and categorical), float→int, object→category rules
- Extended `build_facts()` with `is_datetime_convertible`, `is_int_convertible`, `is_category_beneficial`
- Two endpoints: `/columns/{column}/convert/preview` and `/convert/apply`
- Frontend Datatype Analyzer page: column + target-type dropdowns, preview shows before/after dtype and missing-value impact, Apply commits the conversion
- Linked from Recommendation cards with `category == "datatype"`
- Verified end to end: converted a text column to datetime, confirmed dtype change and newly-invalid count in preview matched expectations

### Day 9 — Distribution Analysis + Transform Recommendations
- `services/distribution_service.py`: Shapiro-Wilk normality test (sampled at 5000 rows for large datasets), histogram bin computation, and four transforms — log, sqrt, Box-Cox, Yeo-Johnson — each validating its own input range (e.g. log rejects non-positive values with a clear message pointing to Yeo-Johnson as an alternative)
- `knowledge_base/distribution.yaml`: skewness-based rules recommending log transform (high positive skew), sqrt (moderate positive skew), Yeo-Johnson (negative skew), or no transform (already near-symmetric)
- Three endpoints: `/columns/{column}/distribution` (stats + histogram + normality test), `/transform/preview`, `/transform/apply`
- Frontend Distribution Analysis page: first page using real Plotly charts (`ui.plotly`) — histogram auto-updates on column selection, transform preview shows side-by-side before/after histograms with skewness change
- Linked from Recommendation cards with `category == "distribution"`
- Verified end to end: log transform on a skewed column reduced skewness toward zero, confirmed visually in the before/after histograms

**UX fixes discovered through real testing:**
- Added `DELETE /datasets/{id}/columns/{column}` endpoint + "Drop Column" button on the Column Types page — a real functional gap where Data Quality recommendations suggested dropping constant/duplicate/low-variance columns but no UI action existed to actually do it
- Added a "Column Types & Drop Columns →" link on the Recommendations page — previously the only way back from Recommendations was to Upload, which meant losing access to the dataset entirely mid-session
- Re-confirmed the stale-`dataset_id`-after-backend-restart gotcha from Day 6 — noted as a known limitation until Day 16's SQLite-backed History Manager; a full persistent navigation bar is deferred to Day 13/20 as originally planned, since these smaller fixes solve the immediate friction without front-loading that work

### Day 10 — Outlier Analysis
- `services/outlier_service.py`: three detection methods — IQR (quartile-based, robust to skew), Z-score (assumes normality), Modified Z-score (median/MAD-based, robust to the outliers' own influence on the statistics — avoids the chicken-and-egg problem standard Z-score has)
- Two treatment options: `remove_outliers()` (drops flagged rows), `cap_outliers()` (winsorizes to the method's own boundary — keeps row count intact, useful when other columns in the same row still carry value)
- Cap boundaries are computed consistently with whichever method flagged the outliers, so detection and treatment never disagree on what counts as extreme
- Extended `build_facts()` with `outlier_pct` (IQR-based, used as the default trigger for rule matching)
- `knowledge_base/outliers.yaml`: moderate (1-5%) and significant (>5%) outlier rules
- `GET /columns/{column}/outliers?method=...` (detect), `POST .../outliers/apply` (treat)
- Frontend Outlier Analysis page: column + method dropdowns both auto-refresh results on change, Cap/Remove buttons with live outlier-count feedback after treatment
- Linked from Recommendation cards with `category == "outliers"`
- Verified end to end: compared outlier counts across all three methods on the same column, confirmed Cap reduced the outlier count on reload### Day 10 — Outlier Analysis
- `services/outlier_service.py`: three detection methods — IQR (quartile-based, robust to skew), Z-score (assumes normality), Modified Z-score (median/MAD-based, robust to the outliers' own influence on the statistics — avoids the chicken-and-egg problem standard Z-score has)
- Two treatment options: `remove_outliers()` (drops flagged rows), `cap_outliers()` (winsorizes to the method's own boundary — keeps row count intact, useful when other columns in the same row still carry value)
- Cap boundaries are computed consistently with whichever method flagged the outliers, so detection and treatment never disagree on what counts as extreme
- Extended `build_facts()` with `outlier_pct` (IQR-based, used as the default trigger for rule matching)
- `knowledge_base/outliers.yaml`: moderate (1-5%) and significant (>5%) outlier rules
- `GET /columns/{column}/outliers?method=...` (detect), `POST .../outliers/apply` (treat)
- Frontend Outlier Analysis page: column + method dropdowns both auto-refresh results on change, Cap/Remove buttons with live outlier-count feedback after treatment
- Linked from Recommendation cards with `category == "outliers"`
- Verified end to end: compared outlier counts across all three methods on the same column, confirmed Cap reduced the outlier count on reload

### Day 11 — Correlation Analysis + Multicollinearity Detection
- `services/correlation_service.py`: Pearson/Spearman/Kendall correlation matrices for numeric columns; Cramér's V (with Bergsma bias correction) for categorical association, implemented but not yet wired into the UI; `detect_high_correlation_pairs()` for threshold-based pair extraction
- Extended `build_dataset_facts()` with `high_correlation_pair_count` (fixed 0.8 threshold, used by the rule engine)
- `knowledge_base/correlation.yaml`: moderate (1-3 pairs) and significant (>3 pairs) multicollinearity rules, explaining why it matters for linear models specifically and noting tree-based models are largely unaffected
- Two endpoints: `/correlation` (matrix), `/correlation/high-pairs` (threshold-based pair list)
- Frontend Correlation Analysis page: interactive Plotly heatmap (red-blue diverging scale), method switcher, and a separate **user-adjustable exploration threshold** — intentionally decoupled from the rule engine's fixed 0.8 threshold, since the rule engine represents "what the app flags automatically" while this slider is for open-ended exploration at any sensitivity
- Page made reachable directly from Recommendations regardless of whether a multicollinearity card has fired, since correlation exploration is useful on its own, not just as a fix-this-problem destination

**Bug found and fixed:**
- Rapid threshold input changes (e.g. typing multiple digits quickly) fired overlapping async reload calls, causing duplicate heatmaps to render when responses arrived out of order. Fixed with a request-token pattern — each `load_correlation()` call tags itself with an incrementing ID and discards its own result if a newer call has since started, so only the most recent request ever renders. This is a reusable pattern for any future page with fast-changing inputs triggering async reloads.

### Day 12 — Categorical Analysis (including Multi-Label Detection)
- `services/categorical_service.py`: standard category frequency analysis (top-N values, counts, percentages), plus a **multi-label delimiter detector** — tries `|`, `,`, `;`, `/` as candidate delimiters and scores each by split coverage × vocabulary repetition, distinguishing genuine multi-label columns (e.g. "Action|Comedy|Drama" — few distinct tokens repeated often) from accidental delimiter matches (e.g. free text or addresses split on commas, where nearly every fragment is unique)
- New logical type: `multi_label`, added to `LogicalType`, `ALLOWED_LOGICAL_TYPES`, `FeatureTypeBreakdown`, and the Column Types override dropdown — fits directly into the detected/effective/overridden architecture built on Day 3
- `classify_dtype()` now checks for multi-label before falling through to the categorical/text split
- `profile_multi_label_column()`: token-level stats (vocabulary size, avg labels per row, per-label frequency) — deliberately different from row-level stats since each row holds a set of labels, not one value
- Two endpoints: `/category-frequencies` (standard categorical), `/multi-label-profile` (token-level)
- Frontend Categorical Analysis page: auto-detects whether the selected column is multi-label or standard categorical and renders the appropriate bar chart (label frequencies vs category frequencies); reused the request-token race-condition guard from Day 11 proactively
- Linked from the Column Types page (not tied to a specific recommendation, since categorical exploration is useful regardless of whether an issue was flagged)
- Verified end to end on a real multi-label test dataset (movie genres): correctly auto-detected as `multi_label`, correct delimiter identified, correct vocabulary size and per-label counts