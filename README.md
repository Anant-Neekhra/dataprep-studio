# DataPrep Studio

An interactive, explainable data analysis and preprocessing workbench. Upload a CSV and get full profiling, data-quality detection, and preprocessing recommendations — every suggestion backed by a deterministic rule (not AI), with the reasoning, alternatives, and trade-offs shown before anything is applied. Every transformation is preview-then-apply, fully undoable, and exportable as CSV, Parquet, a reproducible pipeline definition, or a standalone Python script.

## What it does

- **Upload → Profile → Recommend → Apply**, with nothing changed silently
- **Human-in-the-loop column typing** — auto-detects numerical/categorical/datetime/id/text/multi-label columns, with a full override system for when auto-detection gets it wrong (e.g. an ID column that looks numeric)
- **A YAML-driven rule engine** (not a black box) covering missing values, duplicates, data quality issues, datatypes, distribution shape, outliers, multicollinearity, encoding, and scaling — every recommendation includes *why*, pros/cons, alternatives, and a documentation link
- **Preview → Apply → Undo/Redo** on every transformation, backed by full SQLite version history — nothing is ever destructive
- **"Why Not?" comparisons** — see two strategies (e.g. mean vs. median imputation) run side-by-side on your actual data before choosing
- **Pipeline reordering with real replay** — re-run every applied transformation from the original data in a new order
- **Five export formats**, including a Python script generator that reproduces your entire pipeline in plain pandas/numpy/scipy, independent of this app
- **A health-score Dashboard** that ties the whole session together, with a transparent, explainable scoring breakdown

## Architecture

NiceGUI (frontend, :8080) --HTTP--> FastAPI (backend, :8000) --> Pandas / Rule Engine / SQLite
Two independent services. The frontend is a thin client of a documented REST API (`/docs` for the full interactive spec) — the backend could serve a completely different frontend unchanged.

## Tech Stack

**Backend:** FastAPI, Pydantic, Pandas, NumPy, SciPy, Scikit-learn (preprocessing only), PyYAML, simpleeval, PyArrow, SQLite
**Frontend:** NiceGUI, Plotly
**Infra:** Docker, Docker Compose, GitHub Actions, Pytest, Ruff, Black

## Running locally (without Docker)

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

## Running with Docker

```bash
docker compose up --build
```
Frontend: `http://localhost:8080` · Backend: `http://localhost:8000/docs`

Data persists in a named Docker volume across container restarts.

## Running tests

```bash
cd backend
pytest -v
```

## Project status
It's a solo project — see the Progress Log below for the full build history, including real bugs found and fixed along the way. Test coverage currently focuses on the highest-risk service modules (imputation, outliers, pipeline replay); not yet exhaustive across every module.

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

### Day 13 — Feature Inspector (aggregation)
- `compute_entropy()`: Shannon entropy in bits — a new stat not previously computed, complements cardinality by capturing how evenly distributed a column's values are, not just how many distinct values exist
- `GET /columns/{column}/inspect` — a single composition endpoint pulling together: effective type (Day 3), full profile (Day 3), entropy (today), quality flags (Day 5), outlier summary via IQR (Day 10), top 5 correlated columns (Day 11), matching rule-engine recommendations (Day 4+), and a "possible transformations" list tailored to the column's effective type (numerical → distribution/outlier tools, categorical → encoding, multi_label → binarization, id → exclusion warning)
- Deliberately introduces almost no new detection logic — every number in the report is computed by an existing, previously-tested service function; today's work was composition, not detection
- Frontend Feature Inspector page: single-column deep-dive combining every card type built in prior days into one scrollable report
- Linked from the Column Types page
- Verified end to end: inspected a numeric column with missing values, outliers, and correlation — confirmed all sections populated correctly in one unified view

### Day 14 — Encoding Advisor + Scaling Advisor
- `services/encoding_service.py`: one-hot, label (deterministic alphabetical mapping), ordinal (user-specified order), frequency, binary (log2(n) columns instead of n), and **multi-label binarization** — the real applied version of what Day 12 only detected/profiled
- `services/scaling_service.py`: StandardScaler, MinMaxScaler, RobustScaler, MaxAbsScaler, Normalizer — all pure functions with input validation
- `knowledge_base/encoding.yaml`: cardinality-tiered recommendations (≤10 → one-hot, 11-50 → frequency/binary, >50 → flags possible misclassification as id/text), dedicated multi-label rule
- `knowledge_base/scaling.yaml`: rules based on skewness + outlier percentage (already-computed facts) — StandardScaler for clean normal data, RobustScaler when outliers are present, MinMaxScaler for bounded non-negative data
- Encoding/scaling apply endpoints only (no preview) — column-count-changing operations like one-hot/binary/multi-label would need a meaningfully different preview response shape; deferred as a possible future enhancement
- Frontend pages for both advisors, linked from Recommendation cards with `category == "encoding"` / `"scaling"`
- Verified end to end: one-hot encoding correctly expanded column count, multi-label binarization correctly expanded a genres-style column into per-label binary columns

**Bug found and fixed:** `profile_column()` trusted `effective_type == "numerical"` without checking whether the column's actual underlying values could support numeric math. Manually overriding a column's logical type (Day 3 feature) to "numerical" doesn't convert the underlying string data — a real-world dataset (`anime.csv`, `episodes` column containing literal `"Unknown"` strings mixed with numeric-looking strings) triggered a 500 error on `/recommendations` when scipy tried to compute skewness on string data. Fixed by requiring both `effective_type == "numerical"` AND `pd.api.types.is_numeric_dtype(series)` before attempting numeric stats — a type/data mismatch now gracefully falls back to mode-only profiling instead of crashing. Root cause resolved by using the Datatype Analyzer (`pd.to_numeric(errors="coerce")`) to properly convert the column, correctly surfacing "Unknown" values as missing data to be handled through the normal Missing Value Engine.

### Day 15 — Feature Engineering Suggestions + Visualization Center
- `knowledge_base/feature_engineering.yaml`: explanation-only rules (never auto-applied, per the project's original scope) — date feature extraction, age/duration calculation, text length extraction, binning suggestions, cyclic encoding (with an explicit false-positive warning in its own `disadvantages` field, since the heuristic can't truly know if a value range is genuinely cyclical)
- No new service layer needed — these rules reuse existing facts (`unique_count`, `minimum`, `maximum`) computed in prior days, reinforcing that the facts pipeline built early was general enough to support new rule categories with zero code changes
- Two new backend endpoints (`/visualize/scatter`, `/visualize/boxplot`); bar/pie/count charts reuse the existing `category-frequencies` endpoint from Day 12, and histograms reuse Day 9's distribution endpoint — most of today's chart data plumbing already existed
- Visualization Center frontend page: tabbed interface (Scatter, Box Plot, Bar Chart, Pie Chart), each tab includes "when to use / what to observe" guidance text per the project's original spec
- Linked from the Column Types page

**UX fix:** cross-page navigation had grown inconsistent — links to Correlation, Categorical Analysis, Feature Inspector, and Visualization Center were scattered ad-hoc across different pages as they were built, with some pages missing links others had. Added a single `dataset_nav_links()` helper rendering a consistent set of links, applied to the two main hub pages (Column Types, Recommendations) rather than every page, keeping navigation predictable without cluttering every module page with a full link list.

### Day 16 — History Manager (SQLite-backed storage, undo/redo/restore)
- **Major architectural change**: replaced the in-memory `DatasetStore` with a SQLite-backed store (`app/db.py`) — datasets now persist across backend restarts, permanently fixing the "stale dataset_id" issue hit repeatedly throughout Weeks 1-2
- DataFrames serialized as Parquet bytes (not pickle, for stability/safety; not CSV, to preserve dtypes correctly) and stored as BLOBs
- Three tables: `datasets` (metadata + current-version pointer), `dataset_versions` (every applied transformation as a full snapshot), `dataset_overrides` (Day 3's type overrides — deliberately kept separate from version history, since type overrides are a "lens" on the data rather than a data transformation, so undoing a transformation doesn't unexpectedly revert a column's type)
- `DatasetStore.update()` now creates a new version instead of overwriting, and correctly implements standard undo/redo-stack semantics: applying a new change while not at the latest version discards the old "future" versions
- New endpoints: `/history` (version list), `/undo`, `/redo`, `/restore/{version_num}`
- SQLite connections opened per-call rather than shared, since FastAPI runs sync endpoints in a thread pool and SQLite connections aren't thread-safe to share
- Frontend Version History page: full version list with descriptions/timestamps, current version highlighted, Undo/Redo buttons, Restore-to-any-version
- **Dataset list on the Upload page** (added after initial testing surfaced the gap): shows every previously uploaded dataset with version count (`v2/4`) and edited/unedited status, so datasets with duplicate filenames are distinguishable
- **Dataset deletion**: delete button per dataset in the list, cleans up all three tables (versions, overrides, metadata) to avoid orphaned rows
- Verified end to end: applied multiple transformations, confirmed full undo/redo/restore cycle works correctly, confirmed a dataset survives a full backend restart with all history intact, confirmed deleted datasets correctly 404 on old URLs

### Day 17 — Pipeline Builder (structured step tracking + ordered view)
- Extended `dataset_versions` table with `operation` (e.g. "impute", "drop_column") and `operation_params` (JSON-serialized parameters) — machine-readable step data alongside the existing human-readable `description`, needed for both today's pipeline view and Day 18's planned Python script export
- Updated `DatasetStore.update()` and `get_history()` to store/retrieve the new structured fields
- Wired structured operation data into all 9 apply-endpoints (impute, remove duplicate rows/columns, convert dtype, transform, outlier treatment, encode, scale, drop column) — each now records exactly what operation ran and with what parameters, not just a text description
- `GET /{id}/pipeline` — returns applied transformations in order (excludes the initial upload, version 1, since the pipeline shows what changed, not the starting point)
- Frontend Pipeline page: numbered, ordered list of every transformation applied to the dataset
- **Scope decision**: true drag-and-reorder-with-replay was deliberately deferred to Day 18, since it requires a "replay engine" (re-execute a list of operations against fresh data) that Day 18's Python script export needs identically — building it once, at the point where both features can share it, rather than duplicating the logic across two days
- Verified end to end: applied several different transformation types, confirmed `/history` correctly returns structured operation/params for each, confirmed the Pipeline page renders them in correct order

### Day 18 — Pipeline Replay Engine + Export Module
- `services/pipeline_service.py`: a single operation registry (`execute_operation`) mapping every operation name to its actual service function — one source of truth used by both pipeline reordering and (indirectly) script generation, avoiding logic duplicated across features
- `replay_pipeline()`: re-executes a list of recorded steps against the *original* uploaded data (version 1), enabling true reordering rather than just reading history
- `GET /pipeline/replay-check`: sanity-check endpoint comparing a full replay against the live current dataset — used to verify the operation registry completely and correctly mirrors every transformation the app can perform
- `POST /pipeline/reorder`: replays steps in a user-specified order; failures (e.g. encoding a column before its required dtype conversion) surface a clear, specific error rather than a stack trace
- Frontend Pipeline page: up/down reordering (chosen over full drag-and-drop after weighing implementation risk — NiceGUI has no built-in drag-reorder component, and a JS library integration was a larger investment than the up/down approach for the same functional outcome) with an explicit "Apply New Order" step that triggers the real backend replay
- `services/export_service.py`: CSV, Parquet, pipeline-as-JSON, pipeline-as-YAML, and a **Python script generator** — walks recorded pipeline steps and emits equivalent, dependency-free pandas/numpy/scipy code (outlier treatment steps emit an honest comment rather than inlined boundary-computation logic, since getting that subtly wrong would be worse than a disclosed limitation)
- Five export endpoints returning downloadable files via FastAPI `Response` with proper `Content-Disposition` headers
- Frontend Export page with direct download buttons for all five formats
- Verified end to end: replay-check confirmed exact match with live data, reordering correctly re-applied steps from scratch, all five export formats downloaded with correct content, generated Python script inspected and confirmed to accurately reproduce applied transformations

### Day 19 — Learning Mode
- Extended `Recommendation` schema with an optional `learning_content` field (concept, why it matters, math explanation, common mistakes, real-world example) — populated per-rule in YAML, `None` when absent
- Rule engine passes `learning_content` through in both `evaluate_rules` and `evaluate_dataset_rules`
- Global Learning Mode toggle using NiceGUI's `app.storage.user` (per-browser-session, persists across page navigation, never sent to the backend — purely a frontend display preference)
- Recommendation Card (built Day 4, reused ~15 times since) extended to conditionally render a "📚 Learn More" section when Learning Mode is on AND the specific rule has learning content — the same component handles both states without needing a separate "learning mode version"
- **Content coverage is intentionally partial**: 3 of ~40 rules across all knowledge_base YAML files currently have learning_content populated (missing values - moderate numerical, outliers - moderate, outliers - significant), proving the mechanism works correctly end to end. Filling in the remaining rules is pure content-writing, not engineering, and is left as incremental ongoing work rather than a blocker
- Verified end to end: toggle correctly persists across page navigation, learning content renders only for rules that have it, gracefully renders nothing for rules that don't (no errors, no empty sections)

### Day 20 — Dashboard + Health Score
- `services/health_service.py`: transparent, explainable 0-100 health score — starts at 100, subtracts capped penalties for missing data, duplicate rows, and severity-weighted active recommendations (directly tied to the same rule engine driving every other page, not a separate disconnected metric). Individual penalties are capped so no single dimension can single-handedly crater the score, keeping it meaningful as a genuine composite signal
- `GET /{id}/dashboard`: aggregates health score, dataset overview, last 5 version-history entries, pipeline step count, and top 5 highest-severity recommendations into one response — composition over new detection, same pattern as Day 13's Feature Inspector
- Frontend Dashboard page: health score with full breakdown (never a black-box number), overview stats, top recommendations with a link to the full list, recent changes with a link to full history
- **Dashboard promoted to the true landing page**: fresh uploads and the dataset list (Day 16) now route to Dashboard first, with Column Types as a secondary option — resolving the navigation gap flagged back on Day 9 and Day 15, now that persistent storage (Day 16) makes a real hub page worthwhile
- **Navigation consistency fix**: every module page's "back" link now points to Dashboard rather than Recommendations, since Dashboard's nav row gives one-click access to everywhere else — closes a real gap where users had no path back to Dashboard except returning to Upload first
- **Recommendations link visually highlighted** (bold, orange, ⚡) within the shared nav component, since it's the most likely next action after landing on Dashboard — the "see problems → go fix them" loop the whole app is built around
- Verified end to end: health score and breakdown reflect real dataset issues accurately, dashboard aggregation matches what's shown on individual pages (overview, history, recommendations), full navigation loop confirmed from any module page back to Dashboard