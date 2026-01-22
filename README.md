# FinDistill v27.0: Autonomous Financial Intelligence Engine

## Overview
FinDistill v27.0 is a state-of-the-art financial data processing engine designed to convert raw, conflicting, and chaotic financial data into AI-ready "Golden Datasets".

## Key Features
- **Recursive Conflict Resolution**: Automatically resolves data discrepancies between Tier 1 (PDF) and Tier 2 (CSV) sources.
- **Algebraic Recovery**: Restores missing financial items using accounting identities ($A=L+E$).
- **Self-Evolving Alpha**: Generates predictive signals using Fractional Differentiation and Meta-Labeling.
- **Execution Optimization**: Models slippage and latency to calculate realistic Net Alpha.
- **Auto-Tuning**: Automatically detects market regimes (High Volatility) and adjusts risk parameters.

## Architecture
- **Hub**: Core Math Engine (Polars LazyFrame, Zero-Copy)
- **Spoke A**: AI Tuning Data (Chain-of-Thought JSONL)
- **Spoke B**: Quant Data (Z-Ordered Parquet)
- **Spoke C**: RAG Data (Context Tree JSON)
- **Spoke D**: Risk Graph (Causal Triples JSON)

## Usage
```bash
python final_integrated_test.py
```

## Stack
- Python 3.12
- Polars, Numpy, Scipy, Statsmodels
- Vercel (Deployment) / Supabase (Storage)
