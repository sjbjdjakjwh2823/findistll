# SDK UI (Partner Ingest) Guide

## Goal
Provide an operator-friendly UI to:
- Register partner accounts and issue/rotate API keys
- Submit partner financial payloads (structured facts/tables)
- Verify that ingested partner data is visible downstream (raw_documents -> HITL -> WS8)

## UI
Path: `/sdkui` (Next.js)

## Backend Endpoints
- Public config: `GET /api/v1/config/public`
- Admin partner registry:
  - `POST /api/v1/admin/partners`
  - `POST /api/v1/admin/partners/{partner_id}/keys`
  - `GET /api/v1/admin/partners`
  - `GET /api/v1/admin/partners/{partner_id}/keys`
- Partner ingest + retrieval:
  - `POST /api/v1/partners/financials`
  - `GET /api/v1/partners/documents?partner_id=...`
  - `GET /api/v1/partners/documents/{document_id}?partner_id=...`

## Auth
Recommended production settings:
- `PARTNER_AUTH_MODE=db`
- `ADMIN_API_TOKEN=<random>` (required unless `RBAC_ENFORCED=1` and you provide RBAC headers)

## Pipeline Consumption
1. Partner pushes payload
2. Stored in `raw_documents` with metadata `{ partner_id, converted, facts_count, needs_review }`
3. If `needs_review=true`, route to DataForge review
4. Approved records feed WS8:
  - Spoke A JSONL (SFT)
  - Spoke B Parquet facts/features (quant + numeric ground truth)
  - Spoke C evidence chunks (RAG)

