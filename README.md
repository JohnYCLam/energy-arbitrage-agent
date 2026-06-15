markdown_v2 = """# Portfolio Project Plan: Autonomous Microgrid Energy Arbitrage Agent

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
  * `/api/v1/map-data` for recent NEM regional price/demand time-series
  * Data pipeline is DataFrame-first internally, JSON at API boundary for frontend consumption.
* **API Clients Completed:**
  * `src/api_clients/pricing_api.py` returns DataFrames for market/network/regional demand use cases.
  * `src/api_clients/open_meteo.py` supports both raw payload and standardized DataFrame helper.
* **Frontend Completed (`frontend/v1_observability`):**
  * React + Vite + TypeScript + ECharts app scaffolded and connected to backend APIs.
  * Multi-region line chart with controls: metric toggle (`price`/`demand`), region visibility, highlight region, manual refresh.
  * Real Australia map view (state polygons) with timeline slider and playback controls (run/pause/stop).
  * Right-side collapsible filter panel and latest data timestamp display.

### Phase 2: Forecasting Model & The Predictive Overlay
**Description:** Building the predictive engine and overlaying its accuracy against baselines on the dashboard.
* **Backend Outcomes:** * A trained deep learning model generating a 24-hour multi-variate forecast.
  * **Note:** Use advanced architectures like xLSTM (configured explicitly *without* the deprecated `backend` argument) or Temporal Fusion Transformers (TFT).
  * SHAP integration for Explainable AI (XAI) feature importance.
* **Frontend Outcomes (UI Stage 2):** * A "Look-Ahead" toggle added to the dashboard.
  * The chart now overlays four distinct paths: The Model's Forecast, the Actual Spot Price, a Naive Baseline (persistence), and the Industry Norm (Default Market Offer).
* **Language / Stack:** Python, PyTorch / Darts, SHAP.

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
│   ├── settings.yaml           # House parameters (battery capacity, location)
│   └── prompt_templates/       # Agent persona and constraints
│
├── data/
│   ├── raw/                    # Raw JSON/CSV dumps
│   └── processed/              # Cleaned datasets
│
├── infrastructure/
│   └── cloudformation.yaml     # AWS IaC template (deployed via console)
│
├── notebooks/                  
│   ├── 01_data_exploration.ipynb
│   ├── 02_xlstm_forecasting.ipynb  # xLSTM setup (no backend arg)
│   └── 03_agent_reasoning.ipynb
│
├── src/                        # Modularized Python Backend
│   ├── models/                 # PyTorch/xLSTM architectures
│   ├── agent/                  # LLM orchestration and tools
│   ├── api_clients/
│   │   ├── open_meteo.py
│   │   ├── pricing_api.py
│   │   └── testing.py
│   ├── fetch_weather_history.py
│   └── main.py                 # FastAPI app
│
├── frontend/                   # Progressive Web Visualization
│   └── v1_observability/       # Implemented: map + time-series dashboard
│   │   ├── src/
│   │   │   ├── api/
│   │   │   │   └── mapData.ts
│   │   │   ├── components/
│   │   │   │   ├── MapDataLineChart.tsx
│   │   │   │   └── MapDataRegionMap.tsx
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
├── tests/                      # Planned pytest suite
├── GEMINI.md                   # Optional AI workflow notes
├── environment.yaml            # Conda environment spec
├── .env.example                # API keys template
├── .gitignore
└── README.md
```