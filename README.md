# FinDistill - Financial Data Distillation Engine (v11.5)

A high-performance FastAPI-based engine designed to distill complex financial documents (XBRL, XML, PDF, Images) into high-quality, English-only Chain-of-Thought (CoT) datasets for LLM fine-tuning and financial intelligence.

## 🚀 Key Features

- **Strict v11.5 Protocol**: 100% English-only outputs with a mandatory "Poison Pill" filter that halts the process if any non-English character is detected in the final output.
- **Self-Healing Financial Scaling**: Intelligently detects numerical scales (e.g., trillions vs. billions) and standardizes everything to Billions ($B).
- **Multi-Year Trend Analysis**: Automatically pairs Current Year (CY) and Prior Year (PY) data to calculate YoY growth with LaTeX formulas.
- **Unified Expert CoT**: Generates professional reasoning outputs following a mandatory 4-step structure: [Definition], [Synthesis], [Symbolic Reasoning], and [Professional Insight].
- **Multi-Format Export**: Supports JSONL (for SFT), Markdown (for RAG), Parquet (for Analytics), and HDF5 (for Research).

## 📁 Project Structure

```
project_1/
├── api/
│   ├── app.py               # FastAPI entry point (v11.5 Strict)
│   ├── services/
│   │   ├── xbrl_semantic_engine.py  # Core Distillation Engine
│   │   ├── ingestion.py      # File Processing & Routing
│   │   ├── normalizer.py     # Data Standardization
│   │   ├── exporter.py       # Multi-format Exporter
│   │   └── embedder.py       # Semantic Embedding Service
├── app/                      # Next.js Frontend (Next.js 14+)
│   ├── upload/               # File Upload Interface
│   └── history/              # Extraction History View
└── requirements.txt
```

## 🛠️ Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

Set your Gemini API key and Supabase credentials in a `.env` file:

```env
GEMINI_API_KEY="your-api-key"
SUPABASE_URL="your-supabase-url"
SUPABASE_ANON_KEY="your-anon-key"
```

### 3. Run Server

```bash
uvicorn api.app:app --host 0.0.0.0 --port 8000 --reload
```

## 📖 API Usage

### Endpoints

- `GET /api/health` - Check service status.
- `POST /api/extract` - Distill financial data from a document.
- `GET /api/history` - Retrieve extraction history.
- `GET /api/export/{format}/{doc_id}` - Export data in specific formats.

### Sample Response (JSONL Output)

```json
{
  "instruction": "Analyze the multi-year performance of Company X.",
  "input": "Company X 2024 Financial Data",
  "output": "[Definition]\nGrowth analysis...\n\n[Synthesis]\n- CY Revenue: $150.0B\n\n[Symbolic Reasoning]\n$$Growth = \\frac{CY-PY}{PY} \\times 100\\% = +25.00\\%$$\n\n[Professional Insight]\nAccelerated growth suggests..."
}
```

## 🧪 Verification

To verify the strict adherence to v11.5 standards, run:

```bash
python verify_v11_5_strict.py
```

## ⚠️ Safety Protocols

This project implements a **Strict Poison Pill Filter**.
If any Korean character is detected in the final generated JSONL dataset, the engine will raise `RuntimeError("KOREAN_DETECTED")` and abort the process to prevent data contamination.

## 📝 License

MIT License
