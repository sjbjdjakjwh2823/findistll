# FinDistill v28.0 - Project Briefing

## 1. Project Overview
Successfully integrated the **FinDistill v28.0** crypto and macro data pipeline into `project_1`. This system is designed to run 24/7 on a HuggingFace Space, producing high-quality financial datasets (JSONL, Parquet, Graph Triplets) with automated correlations and AI reasoning.

## 2. Key Components Created

### A. The Core Factory (`project_1/main_factory.py`)
- **FastAPI Server**: Runs on port **7860**.
- **Scheduler**: Automatically triggers the ETL pipeline every **60 minutes**.
- **Endpoints**:
  - `GET /`: System status check.
  - `GET /health`: Health check for database and services.
  - `POST /trigger`: Manual pipeline trigger.
  - `GET /logs`: View system logs.

### B. Ingestors (`project_1/ingestors/`)
- **`financial.py`**: Legacy parser for PDF, Excel, HTML, XBRL financial statements.
- **`market.py`**: 
  - `CryptoIngestor`: Fetches real-time OHLCV for BTC, ETH, SOL, XRP via `ccxt`. Includes **Stablecoin Peg Detection**.
  - `MacroIngestor`: Fetches Treasury Yields (^TNX), Gold (GC=F) via `yfinance`.
  - `NewsIngestor`: Injects simulated news metadata for correlation analysis.

### C. Spoke Engines (`project_1/spokes/engines.py`)
- **Spoke A (AI Tuning)**: Generates `crypto_cot_strategy.jsonl` with **Chain-of-Thought** reasoning (Context -> Data -> Peg Check -> Strategy).
- **Spoke B (Quant)**: Generates `crypto_quant_data.parquet` with Z-Ordering and **Year/Month Partitioning**.
- **Spoke C (RAG)**: Generates `crypto_news_context.json` linking news headlines to price actions.
- **Spoke D (Correlation Graph)**: Generates `crypto_macro_graph.json` implementing the **"Spoke ABCD Correlation"** logic:
  - `BTC` <-> `Nasdaq_100` (Positive Correlation)
  - `US10Y` -> `Crypto_Market` (Inverse Impact)
  - `News Event` -> `Entity` (Mentions)

### D. Data Persistence (`project_1/database/manager.py`)
- **DuckDB**: Local caching of raw market data to support query speed and persistence.
- **Bulk Upsert**: Optimized for high-throughput writing.

### E. HuggingFace Integration (`project_1/api/services/hf_integration.py`)
- **Auto-Push**: Uploads the `final_output/` directory to the HF Hub dataset automatically after each cycle.

## 3. How to Run
1. **Start Server**:
   ```bash
   python project_1/main_factory.py
   ```
2. **Manual Trigger**:
   ```bash
   curl -X POST http://localhost:7860/trigger
   ```

## 4. Verification Results
- **Pipeline Execution**: Validated via `project_1/run_crypto_engine.py`.
- **Output Quality**: Checked JSONL and Graph outputs; correlations and CoT logic are correctly generated.
- **Dependencies**: All required packages (`ccxt`, `yfinance`, `duckdb`, `fastapi`, `polars`) are installed.

## 5. Next Steps
- Set `HF_TOKEN` and `HF_REPO_ID` in the environment variables to enable actual pushing to the Hub.
- Deploy the `project_1` folder to a HuggingFace Space.
