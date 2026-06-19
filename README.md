# Portfolio Project Plan: Autonomous Microgrid Energy Arbitrage Agent

## 1. Project Overview

**Objective:** To build an autonomous, serverless Agentic AI system that orchestrates a home battery storage strategy by analyzing real-time wholesale electricity prices, forecasting weather-dependent solar generation, and reasoning through physical battery constraints.

**Use Case:** Residential energy arbitrage for wholesale-exposed electricity customers (e.g., Amber Electric in Australia). The Agent acts as an automated energy broker, replacing brittle heuristic timers with dynamic, predictive reasoning to minimize retail costs and maximize grid export profits during market anomalies.

**Portfolio Impact (Measurable Achievements):** This project is designed to be presented on a resume as a series of measurable achievements, such as: *"Engineered a serverless AI agent reducing simulated annual energy costs by X% compared to baseline heuristics, utilizing xLSTM for 24-hour demand forecasting and LangGraph for autonomous execution."*

---

## 2. Progressive Execution Phases

This project follows an agile, progressively enhanced architecture where the frontend and backend evolve simultaneously.

### Phase 1: Data Ingestion & The Observability Foundation
**Description:** Sourcing the raw data and building the initial visual pipeline to prove the data engineering works.
* **Backend Outcomes:** * Clean, synchronized time-series datasets combining weather (Open-Meteo) and wholesale pricing (Amber API / OpenNEM).
  * Handling of Australian timezones (AEST/AEDT) and missing temporal data.
* **Frontend Outcomes (UI Stage 1):** * A geospatial map of the Australian National Electricity Market (NEM) regions showing live demand.
  * A time-series line chart tracking historical wholesale spot prices ($/MWh) alongside local solar irradiance.
* **Language / Stack:** Python, Pandas, Streamlit or React, Jupyter Notebooks for EDA.

**Phase 1 Progress Update (Implemented):**
* **Backend Completed:** FastAPI endpoints are live in `src/main.py`:
  * `/api/v1/market-data` for merged weather + market records
  * `/api/v1/map-data` for recent NEM regional price/demand time-series (sparse points forward-filled per region instead of zero-filled)
  * `/api/v1/victoria-data` for VIC1 energy plus weather across five representative Victorian locations
  * Data pipeline is DataFrame-first internally, JSON at API boundary for frontend consumption.
* **Timezone & Data Quality Handling:**
  * Weather and energy timestamps are standardized to `Australia/Melbourne` (energy is tz-aware AEST `+10:00`; weather is fetched in local time and localized to match).
  * Open-Meteo "latest 24 hours" clipping trims the archive API's future-dated, whole-day padding so data never extends past now.
* **Shared Configuration:**
  * `src/config/locations.py` defines `VICTORIA_WEATHER_LOCATIONS` (Melbourne, Mildura, Ararat, Bendigo, Traralgon) as the single source of truth, chosen to span demand, solar, and wind drivers across Victoria's renewable energy zones.
* **API Clients Completed:**
  * `src/api_clients/pricing_api.py` returns DataFrames for market/network/regional demand use cases.
  * `src/api_clients/open_meteo.py` supports raw payload, standardized DataFrame helper, latest-24h clipping, and batched multi-location fetch (one API call, tidy per-region rows).
* **Frontend Completed (`frontend/v1_observability`):**
  * React + Vite + TypeScript + ECharts app scaffolded and connected to backend APIs.
  * Two sections behind a top tab nav: **Overview** (default) and **Victoria**.
  * **Overview:** Multi-region line chart with controls (metric toggle `price`/`demand`, region visibility as buttons, highlight region, manual refresh) and a real Australia map view (state polygons) with timeline slider and playback controls (run/pause/stop).
  * **Victoria:** Combined energy + weather line chart with three filter groups (energy metrics, weather metrics, regions) and dual-axis support; small-multiple maps (Map A energy, Map B weather) rendering equal-size region bubbles over a neutral warm-gray Australia base map zoomed to Victoria, driven by a shared timeframe slider.
  * Right-side collapsible filter panel and latest data timestamp display on both sections.

*Overview section:*
![Line Chart View](docs/images/dashboard-line-chart.png)
![Map View](docs/images/dashboard-map-view.png)

*Victoria section:*
![Victoria Line Chart View](docs/images/dashboard-vic-line-chart.png)
![Victoria Map View](docs/images/dashboard-vic-map-view.png)
### Phase 2: Forecasting Model & The Predictive Overlay
**Description:** Building the predictive engine and overlaying its accuracy against baselines on the dashboard.
* **Backend Outcomes:** * A trained deep learning model generating a 24-hour multi-variate forecast.
  * **Note:** Use advanced architectures like xLSTM (configured explicitly *without* the deprecated `backend` argument) or Temporal Fusion Transformers (TFT).
  * SHAP integration for Explainable AI (XAI) feature importance.
* **Frontend Outcomes (UI Stage 2):** * A "Look-Ahead" toggle added to the dashboard.
  * The chart now overlays four distinct paths: The Model's Forecast, the Actual Spot Price, a Naive Baseline (persistence), and the Industry Norm (Default Market Offer).
* **Language / Stack:** Python, PyTorch / Darts, SHAP.

**Phase 2 Progress Update (In Progress):**

*Forecasting target (defined):*
  * Primary prediction: **VIC1 spot price** over the next **24 hours** at **15-minute** resolution (**96 steps**).
  * Strategy: **direct multi-step** forecasting (not autoregressive on price); no future price labels as model inputs.
  * Inputs: past market data (price, demand, renewables, interconnector flow) + weather covariates (linearly upsampled from hourly) + calendar features.
  * Baseline ladder: persistence → seasonal naive → XGBoost → TFT/xLSTM (deep models planned).

*Forecasting configuration & alignment (implemented):*
  * **`config/forecasting.yaml`** — single source of truth for grid interval, horizon, walk-forward windows, TFT hyperparameters, and region list. Change `interval_minutes` here (and in `config/settings.yaml`) to migrate resolution later without code edits.
  * **`src/config/forecasting.py`** — `ForecastingConfig` dataclass with derived values (`forecast_steps`, `input_chunk_length`, `pandas_freq`, `seasonal_naive_lag`).
  * **`src/models/align_timeseries.py`** — aligns 5-min energy (mean-aggregated) and hourly weather (time-interpolated, solar clipped ≥ 0) onto the modeling grid; adds calendar features; used by `main.py` and the price table builder.
  * **`src/main.py`** — refactored to load interval settings from config instead of hard-coded values.

*Price modeling table (implemented):*
  * **`src/build_price_training_table.py`** — merges aligned energy (VIC1 + NSW1 + SA1) with actual + forecast weather into a joint modeling CSV.
  * Example output: `data/processed/price_modeling_vic_730d.csv` (~70k rows × 83 columns, target `vic1_price`).

```bash
python src/build_price_training_table.py --days 730
```

*Baselines & walk-forward validation (implemented):*
  * **`src/models/baselines.py`** — persistence and seasonal-naive forecast functions.
  * **`src/evaluation/walk_forward.py`** — weekly-origin walk-forward harness with selection/holdout splits, per-fold MAE/RMSE, `collect_fold_predictions()`, and `consolidate_walk_forward_predictions()`.
  * **`src/evaluation/plotting.py`** — time-series and diagnostic plots (actual vs predicted over time, single 24h windows, scatter/MAE panels).
  * **`notebooks/02_xlstm_forecasting.ipynb`** — EDA, walk-forward baseline evaluation, XGBoost (or sklearn HGBR fallback) per-horizon tabular model, and **actual vs predicted time-series plots** for training and holdout.
  * **`tests/test_forecasting_config.py`** — unit tests for config loading and derived horizon/chunk lengths.

*Example walk-forward results (selection window, ~40 weekly origins):*

| Model | MAE ($/MWh) | RMSE ($/MWh) |
|-------|-------------|--------------|
| Seasonal naive | ~70 | ~124 |
| Persistence | ~128 | ~173 |

```bash
# Rebuild modeling table, run config tests, open forecasting notebook
python src/build_price_training_table.py --days 730
python -m pytest tests/test_forecasting_config.py -q
jupyter notebook notebooks/02_xlstm_forecasting.ipynb
```

*Historical training data pipelines (implemented):*
  * **Energy (`src/fetch_energy_history.py`):** Chunked 2-year backfill (default 7-day chunks), CLI (`--days`, `--chunk-days`, `--regions`), per-region validation, and CI-friendly exit codes. Pulls VIC1 + adjacent regions (NSW1, SA1) via `src/api_clients/pricing_api.py`.
  * **Energy client improvements (`src/api_clients/pricing_api.py`):** Date-range fetch methods, real `interconnector_flow_mw` from OpenElectricity `FLOW_IMPORTS`/`FLOW_EXPORTS`, and Melbourne-local datetime normalization for API compatibility.
  * **Actual weather (`src/fetch_weather_history.py`):** Chunked archive pulls with clip-to-now (avoids future-hour padding), multi-region support (`--all-vic-regions`), validation, and CLI exit codes.
  * **Forecast weather (`src/fetch_weather_forecast_history.py`):** Historical forecast backfill via Open-Meteo **Previous Runs API** (`--lead-days 1` ≈ 24h ahead) and live snapshot append mode (`--mode snapshot`). Supports all five VIC regions.
  * **Open-Meteo client (`src/api_clients/open_meteo.py`):** `get_historical_forecast_df()` (Previous Runs), `get_live_forecast_snapshot_df()` (live forecast API with `forecast_hours`), plus existing archive and multi-location helpers.
  * **Unified weather schema (`src/config/weather_schema.py`):** Canonical columns for actual + forecast rows (`region`, `timestamp`, `forecast_issue_time`, `lead_hours`, `record_type`, `source`, weather features). Shared chunking, clipping, validation, and location resolution.
  * **Modeling table builder (`src/build_weather_training_table.py`):** Merges aligned actual + forecast CSVs into `data/processed/weather_modeling_vic.csv` and reports the modeling overlap window.

*Raw datasets produced (example commands):*
```bash
python src/fetch_energy_history.py --days 730 --chunk-days 7
python src/fetch_weather_history.py --all-vic-regions --days 730 --chunk-days 30
python src/fetch_weather_forecast_history.py --mode historical --all-vic-regions --days 730 --chunk-days 30 --lead-days 1
python src/build_weather_training_table.py --days 730 --lead-days 1
```

*Key output files (`data/raw/` and `data/processed/`):*
  * `market_{REGION}_730d.csv` — energy actuals (5-min native), per NEM region
  * `weather_actual_vic_730d.csv` — actual weather, 5 VIC regions, hourly
  * `weather_forecast_history_vic_730d_lead1d.csv` — historical forecasts with issue-time semantics
  * `weather_forecast_snapshots_vic.csv` — append-only live forecast snapshots (snapshot mode)
  * `weather_modeling_vic.csv` — combined actual + forecast weather table
  * `price_modeling_vic_730d.csv` — joint energy + weather table for VIC1 price forecasting

*Still to do (core Phase 2 deliverables):*
  * Train/evaluate **TFT** and **xLSTM** price forecast models (Darts / PyTorch).
  * Walk-forward evaluation for XGBoost and deep models (notebook currently uses in-sample MAE per horizon for tabular model).
  * Arbitrage-relevant metrics (peak/trough slot MAE, simulated battery P&L).
  * SHAP feature importance for forecast explainability.
  * Frontend `v2_predictive` look-ahead overlay (model vs actual vs naive vs DMO reference).

### Phase 3: Autonomous Orchestrator & The Command Center
**Description:** Prototyping the cognitive agent that binds forecasts, live data, and physical constraints, making it visible to the user.
* **Backend Outcomes:** * A functioning agentic loop (Perception $\rightarrow$ Reasoning $\rightarrow$ Action) that invokes the forecasting model as a tool.
  * System prompts defining the mathematical objective function and battery state-of-charge limits.
* **Frontend Outcomes (UI Stage 3):** * An interactive **Agent Execution Trace** console streaming the agent's real-time inner monologue (`Thought` $\rightarrow$ `Tool Call` $\rightarrow$ `Action`).
  * A dynamic visual representing the battery's current State of Charge (SoC).
  * An active ROI scorecard tracking cumulative dollar savings vs. a standard heuristic.
* **Language / Stack:** Python, LangChain/LangGraph, OpenAI/Anthropic API.

### Phase 4: Backend Modularization & Testing
**Description:** Refactoring notebook experiments into a production-ready, object-oriented backend.
* **Outcomes:** * Clean codebase organized by domain (`api_clients`, `models`, `agent_core`).
  * Error handling for API rate limits and robust logging mechanisms.
* **Language / Stack:** Python, Pytest.

### Phase 5: Serverless Cloud Deployment
**Description:** Moving the system to a fully autonomous, event-driven cloud architecture.
* **Outcomes:** * A serverless deployment running on a strict 30-minute cron schedule without manual intervention.
  * Infrastructure deployed and managed directly via **AWS CloudFormation (Console-based deployment)** for exact reproducibility.
* **Language / Stack:** AWS Lambda, Amazon EventBridge, Amazon DynamoDB, AWS CloudFormation.

---

## 3. Aligned Folder Structure (Current + Planned)
```text
energy-arbitrage/
│
├── config/
│   ├── settings.yaml           # House parameters (battery capacity, location, interval)
│   ├── forecasting.yaml        # Grid resolution, horizon, walk-forward, model hyperparams
│   └── prompt_templates/       # Agent persona and constraints
│
├── data/
│   ├── raw/                    # Raw JSON/CSV dumps
│   └── processed/              # Cleaned datasets
│
├── docs/
│   └── images/                 # README screenshots/assets
│       ├── dashboard-line-chart.png
│       └── dashboard-map-view.png
│
├── infrastructure/
│   └── cloudformation.yaml     # AWS IaC template (deployed via console)
│
├── notebooks/                  
│   ├── 01_data_exploration.ipynb
│   ├── 02_xlstm_forecasting.ipynb  # Baselines, walk-forward, XGBoost, forecast plots
│   └── 03_agent_reasoning.ipynb
│
├── scripts/                    # One-off utilities
│   └── generate_vic_regions.py # Builds Victoria sub-region polygons (Voronoi)
│
├── src/                        # Modularized Python Backend
│   ├── models/
│   │   ├── align_timeseries.py # Energy/weather alignment + calendar features
│   │   └── baselines.py        # Persistence + seasonal naive forecasters
│   ├── evaluation/
│   │   ├── walk_forward.py     # Walk-forward validation harness
│   │   └── plotting.py         # Actual vs predicted forecast plots
│   ├── agent/                  # LLM orchestration and tools
│   ├── config/
│   │   ├── locations.py        # VICTORIA_WEATHER_LOCATIONS constants
│   │   ├── forecasting.py      # ForecastingConfig loader + derived horizons
│   │   └── weather_schema.py   # Canonical weather export schema + validation helpers
│   ├── api_clients/
│   │   ├── open_meteo.py
│   │   ├── pricing_api.py
│   │   └── testing.py
│   ├── fetch_weather_history.py
│   ├── fetch_weather_forecast_history.py
│   ├── build_weather_training_table.py
│   ├── build_price_training_table.py
│   ├── fetch_energy_history.py
│   └── main.py                 # FastAPI app
│
├── frontend/                   # Progressive Web Visualization
│   └── v1_observability/       # Implemented: Overview + Victoria dashboard
│   │   ├── src/
│   │   │   ├── api/
│   │   │   │   ├── mapData.ts
│   │   │   │   └── victoriaData.ts
│   │   │   ├── assets/
│   │   │   │   └── vic_regions.geojson
│   │   │   ├── components/
│   │   │   │   ├── MapDataLineChart.tsx
│   │   │   │   ├── MapDataRegionMap.tsx
│   │   │   │   ├── OverviewSection.tsx
│   │   │   │   ├── VictoriaSection.tsx
│   │   │   │   ├── VictoriaLineChart.tsx
│   │   │   │   └── VictoriaRegionMap.tsx
│   │   │   ├── constants/
│   │   │   │   └── victoriaRegions.ts
│   │   │   ├── theme/
│   │   │   │   └── metricTheme.ts
│   │   │   ├── App.tsx
│   │   │   ├── App.css
│   │   │   ├── index.css
│   │   │   └── main.tsx
│   │   └── package.json
│   ├── v2_predictive/          # Forecast overlays
│   └── v3_command_center/      # Agent trace & ROI scorecard
│
├── tests/                      # Pytest suite
│   ├── conftest.py
│   └── test_forecasting_config.py
├── GEMINI.md                   # Optional AI workflow notes
├── environment.yaml            # Conda environment spec
├── .env.example                # API keys template
├── .gitignore
└── README.md
```