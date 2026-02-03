# Preciso B2B SDK Document (Draft v0.1)

Welcome to the Preciso Sovereign Intelligence SDK. This guide helps developers integrate Preciso's high-precision financial data refinement and causal inference engines into their own enterprise workflows.

---

## 🚀 Getting Started

### Installation
```bash
pip install preciso-toolkit
```

### Quick Start: Data Distillation
Transform messy PDFs into audit-ready 3D knowledge graphs with pixel-level lineage.

```python
from preciso import PrecisoToolkit

client = PrecisoToolkit(api_key="your_sovereign_key")

with open("annual_report.pdf", "rb") as f:
    result = await client.distill_document(
        file_bytes=f.read(),
        filename="report.pdf",
        mime_type="application/pdf"
    )

print(f"Extracted {len(result['facts'])} facts with 99.9% confidence.")
```

---

## 🔮 Core Engines

### 1. Preciso Distill
- **Agentic Reflection**: Each fact is self-critiqued 3 times by independent agents.
- **Pixel Lineage**: Every number includes exact X/Y coordinates for 100% traceability.

### 2. Preciso Oracle
- **Causal Discovery**: Differentiates between mere correlation and true causal drivers using PC/NOTEARS algorithms.
- **What-if Simulation**:
```python
# Simulate effect of 10% oil price hike on airline margins
impact = client.predict_impact(
    node_id="brent_crude",
    delta=10.0,
    causal_graph=current_ontology
)
```

### 3. Preciso Sovereign Vault
- **Merkle Chaining**: Every action is cryptographically linked to the previous one.
- **Integrity Check**:
```python
is_valid = client.verify_integrity(audit_trail)
if not is_valid:
    raise SecurityAlert("Data tampering detected!")
```

---

## 🎨 Enterprise UI Integration (React)
Import our high-density Foundry-style components directly into your application.

```jsx
import { KnowledgeGraph3D, LineageViewer } from '@preciso/ui-react';

function Dashboard() {
  return (
    <div className="sharp-dark-theme">
      <KnowledgeGraph3D data={apiData} />
      <LineageViewer fileUrl={pdfUrl} highlight={selectedFact.anchor} />
    </div>
  );
}
```

---
*Preciso: Data Integrity for the Sovereign Enterprise.*
