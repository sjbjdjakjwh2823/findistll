# FinDistill - Quickstart Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Install Dependencies (1 min)

```powershell
cd c:\Users\Administrator\Desktop\project_1
pip install -r requirements.txt
```

### Step 2: Set API Keys (30s)

```powershell
$env:GEMINI_API_KEY="your-gemini-api-key-here"
```

### Step 3: Run the Server (v11.5 Strict)

**Open Terminal 1:**

```powershell
cd c:\Users\Administrator\Desktop\project_1
uvicorn api.app:app --reload
```

✅ Once running, you will see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 4: Run Verification (3 mins)

**Open Terminal 2:**

```powershell
cd c:\Users\Administrator\Desktop\project_1
python verify_v11_5_strict.py
```

The verification script will:
1. Check Engine Operational Status ✅
2. Validate 4-Step CoT Structure ✅
3. Test Self-Healing trillion detection ✅
4. Test English Purity / Poison Pill Filter ✅
5. Test Integration with Ingestion Service ✅

---

## 📋 Execution Summary

### Terminal 1 (Server)
```powershell
cd c:\Users\Administrator\Desktop\project_1
$env:GEMINI_API_KEY="your-key"
uvicorn api.app:app --reload
```

### Terminal 2 (Verification)
```powershell
cd c:\Users\Administrator\Desktop\project_1
python verify_v11_5_strict.py
```

---

## 🎯 Browser Access

Access the following URLs after starting the server:

- **Swagger UI**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health
- **Extraction History**: http://localhost:8000/api/history

---

## 📁 Required Files

For production use, prepare financial documents in these formats:
- **XBRL/XML**: Instance files (multi-year paired)
- **PDF**: Balance sheets, Income statements
- **Excel/CSV**: Tabular financial data
- **Images**: High-resolution scans

---

## ✅ Success Indicators

Successful verification will output:
```
--- Testing Operational Status ---
V11.5 XML-TO-JSONL ENGINE: 100% OPERATIONAL
SUCCESS: Engine reported operational status.

PASS: Mandatory [Definition] block
PASS: Mandatory [Synthesis] block
PASS: Mandatory [Symbolic Reasoning] block
PASS: Mandatory [Professional Insight] block
PASS: LaTeX Growth formula present
PASS: No Korean detected
```

---

## 🐛 Troubleshooting

### "Connection Refused"
→ Ensure Terminal 1 is running and didn't crash.

### "KOREAN_DETECTED (Poison Pill)"
→ The engine detected non-English characters in the output. Check your source data or engine configuration. v11.5 is strictly English only.

---

## 📚 Resources

- Full Documentation: [README.md](README.md)
- Development Status: `api/services/xbrl_semantic_engine.py`
- Strict Verification: `verify_v11_5_strict.py`

---

## 🎉 Next Steps

1. ✅ Start the server
2. ✅ Run verification script
3. 📊 Upload real XBRL/PDF files
4. 🚀 Generate high-quality SFT datasets
