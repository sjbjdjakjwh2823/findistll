# FinDistill Testing Guide (v11.5 Strict)

## 🧪 How to Run Verification

### Prerequisites

1. **Install Dependencies**
```powershell
pip install -r requirements.txt
```

2. **Set Gemini API Key**
```powershell
$env:GEMINI_API_KEY="your-api-key-here"
```

3. **Prepare Test Documents**
- Have XBRL/XML or PDF files ready for testing.
- Example: `test_report.xml`, `company_audit.pdf`.

---

## 📝 Verification Workflow

### Step 1: Start the Server

**Terminal 1 (Server):**

```powershell
cd c:\Users\Administrator\Desktop\project_1
# Start the v11.5 Strict English API
uvicorn api.app:app --reload
```

Look for:
```
INFO:     Application startup complete.
```

---

### Step 2: Run the Strict Verification Script

**Terminal 2 (Testing):**

```powershell
cd c:\Users\Administrator\Desktop\project_1
# Run the core policy verification
python verify_v11_5_strict.py
```

---

## 📊 Verification Features

`verify_v11_5_strict.py` performs the following checks:

### 1. Operational Status
- Verifies the engine is initialized and ready.

### 2. 4-Step CoT Structure
- Enforces [Definition], [Synthesis], [Symbolic Reasoning], and [Professional Insight] blocks.

### 3. LaTeX Growth Formula
- Checks for correctly formatted LaTeX formulas in the output for YoY calculations.

### 4. Self-Healing Scaling
- Simulates trillion-scale input and verifies it's normalized to the Billions ($B) unit.

### 5. English Purity (Poison Pill)
- Injects Korean characters and verifies that the engine terminates with `RuntimeError("KOREAN_DETECTED")`.

### 6. Ingestion Integration
- Tests the full pipeline from `ingestion.py` through `XBRLSemanticEngine`.

---

## 🎯 Sample Output

### Success (Policy Compliant)

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

### Failure (Policy Violation - Korean Detected)

```
ERROR:api.services.xbrl_semantic_engine:POISON PILL TRIGGERED: Korean detected in output -> ...
Traceback (most recent call last):
  ...
RuntimeError: KOREAN_DETECTED
```

---

## 🔧 Manual API Testing

### cURL (v11.5 Protocol)

```bash
curl -X POST "http://localhost:8000/api/extract?export_format=jsonl" \
  -F "file=@financial_report.pdf" \
  -H "Authorization: Bearer your-token"
```

### Python Script

```python
import requests

url = "http://localhost:8000/api/extract"
headers = {"Authorization": "Bearer your-token"}

with open("report.pdf", "rb") as f:
    files = {"file": f}
    response = requests.post(url, files=files, headers=headers)
    print(response.json())
```

---

## ✅ v11.5 Strict Checklist

- [ ] Python 3.12+ installed
- [ ] Requirements.txt installed
- [ ] Gemini API Key set as Environment Variable
- [ ] **No Korean characters** in any prompts or logic
- [ ] Self-Healing Trillion detection active
- [ ] 4-Step CoT mandatory structure
- [ ] LaTeX YoY formulas required
