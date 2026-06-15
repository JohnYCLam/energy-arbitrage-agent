# Project: Autonomous Microgrid Energy Arbitrage Agent

## System Directives
You are acting as a senior AI engineering pair programmer. Your goal is to help me build an event-driven, serverless agentic system for energy arbitrage. Prioritize clean, object-oriented Python, robust error handling, and explainable ML models. 

Always design with the end goal in mind: this project will be presented as a professional portfolio piece. Ensure logs, outputs, and return values consistently surface measurable achievements (e.g., benchmarked percentage savings vs. baselines).

## Tech Stack & Core Libraries
* **Backend:** Python 3.10+, Pytest
* **ML/Forecasting:** PyTorch, Darts (for xLSTM/TFT), SHAP
* **Agentic Framework:** LangChain, LangGraph, Anthropic/OpenAI APIs
* **Data:** Pandas, Open-Meteo API, Amber Electric API / OpenNEM
* **Cloud (Target):** AWS Lambda, EventBridge, DynamoDB, CloudFormation

## Architectural & Coding Constraints

### 1. Model & Data Rules
* **xLSTM Implementation:** When writing or refactoring xLSTM code, **never** use or pass the `backend` argument in the configuration. It has been removed in the latest library update and will throw a `TypeError`.
* **Explainability:** Model interpretability is a hard requirement. Always integrate SHAP values to explain feature importance for the forecasting pipeline.
* **Timezone Strictness:** The system operates in the Australian National Electricity Market (NEM). All temporal data ingestion and processing must explicitly handle AEST/AEDT (Melbourne) conversions and missing intervals.

### 2. Infrastructure & Deployment Rules
* **Serverless First:** Design all backend Python functions (`src/`) so they can easily be wrapped in AWS Lambda handlers later. Keep dependencies lightweight.
* **Infrastructure as Code:** All AWS architecture must be defined in `cloudformation.yaml`. 
* **Deployment Method:** Target **console-based deployment** for CloudFormation. Do not generate or suggest AWS CLI deployment scripts; I will upload the templates manually via the AWS Console.

### 3. Workflow & Output Rules
* **No Unsolicited Re-writes:** Only modify the specific files or functions I ask you to. Do not re-write entire classes unless requested.
* **Documentation:** Use standard Python docstrings for all functions. 
* **Agent Traceability:** When building the LangGraph components, ensure the `Thought -> Tool Call -> Action` loops are highly visible and easy to stream to a frontend console.