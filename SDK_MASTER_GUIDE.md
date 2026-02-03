# Preciso SDK Master Guide

This guide explains the Preciso Mixboard and how to use the SDK to build secure financial applications. The SDK is designed for enterprise-grade data integrity, traceability, and decision support.

## Preciso Mixboard: 4 Tracks

The Mixboard is a four-track workflow. Each track can be used independently, or chained end-to-end.

1) Distill Track
- Purpose: Extract structured facts from source documents with pixel lineage and self-reflection metadata.
- Core API: PrecisoToolkit.distill_document
- Output: Facts, summaries, and lineage metadata for downstream use.

2) Oracle Track
- Purpose: Simulate causal impacts and regime shifts using the extracted graph or external causal graphs.
- Core API: PrecisoToolkit.predict_impact
- Output: Impact forecasts, regime shifts, and action triggers.

3) Decision Track
- Purpose: Generate analyst-critic-strategist consensus and turn insights into recommended actions.
- Core API: PrecisoToolkit.generate_strategy
- Output: Recommendation, rationale, and suggested actions.

4) Sovereign Proof Track
- Purpose: Validate integrity and external data claims without revealing raw data.
- Core APIs:
  - PrecisoToolkit.verify_integrity
  - PrecisoToolkit.verify_external_data
- Output: Tamper-evident audit verification and ZKP-based external data verification.

## Quick Start

```python
from app.services.toolkit import PrecisoToolkit

sdk = PrecisoToolkit()

# 1) Distill
with open("annual_report.pdf", "rb") as f:
    distill = await sdk.distill_document(
        file_bytes=f.read(),
        filename="annual_report.pdf",
        mime_type="application/pdf",
    )

# 2) Oracle
impact = sdk.predict_impact(
    node_id="revenue",
    delta=0.05,
    causal_graph=[],
)

# 3) Decision
decision = await sdk.generate_strategy(distill)

# 4) Sovereign Proof
audit_ok = sdk.verify_integrity([])
```

## ZKP Verification (External Data)

Use ZKP verification when a provider supplies a Circom/SnarkJS proof that a dataset meets accounting constraints without exposing the raw numbers.

```python
proof = {
    "pi_a": ["1", "2"],
    "pi_b": [["3", "4"], ["5", "6"]],
    "pi_c": ["7", "8"],
    "protocol": "groth16",
}
public_signals = ["signal_1", "signal_2"]
verification_key = {
    "protocol": "groth16",
    "circuit_id": "acct_rules_v1",
    "vk_hash": "expected_vk_hash",
}

result = sdk.verify_external_data(
    provider_id="acme_data",
    proof=proof,
    public_signals=public_signals,
    verification_key=verification_key,
    scheme="groth16",
)

if not result["verified"]:
    raise RuntimeError("ZKP verification failed")
```

## Building Secure Financial Apps

Recommended flow for secure, auditable applications:

1) Ingest documents and distill facts with lineage (Distill Track).
2) Run causal simulations and stress tests (Oracle Track).
3) Produce decision-ready guidance and action sets (Decision Track).
4) Verify audit trails and external data claims (Sovereign Proof Track).

This flow allows apps to stay explainable, tamper-evident, and compliant while protecting sensitive source data.

## Notes for Advanced Integrations

- If you need ontology graph construction, integrate SpokesEngine directly alongside the Distill Track outputs.
- The Sovereign Proof Track can be used independently for data providers that only send proofs and public signals.
- All verification outputs include deterministic hashes for traceability without persisting raw data.
