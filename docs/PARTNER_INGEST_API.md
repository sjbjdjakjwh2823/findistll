# Partner Ingest API (External Company Financial Data)

## Goal
Allow external companies/partners to push structured financial data into Preciso, so it can flow through:

`partner payload -> raw_documents -> UnifiedConversionEngine -> (Spokes/Exports) -> HITL/WS8`

## Auth
Header: `X-Partner-Api-Key`

Config:
- `PARTNER_AUTH_MODE`:
  - `open`: allow without key (dev only)
  - `env`: require `PARTNER_API_KEYS` allow-list
  - `db`: require DB-backed key registry (`partner_accounts` + `partner_api_keys`)
  - `env_or_db`: accept either
- `PARTNER_API_KEYS` (comma-separated)
  - legacy allow-list (no partner binding)
- `PARTNER_API_KEY_PEPPER` (optional)
  - improves API key hash security in DB mode

### DB-backed Registration (Recommended)
Create partner + one-time API key (admin-only):
- `POST /api/v1/admin/partners`
  - Requires `ADMIN_API_TOKEN` (header `X-Admin-Token`) or RBAC admin role when `RBAC_ENFORCED=1`.

Rotate key (admin-only):
- `POST /api/v1/admin/partners/{partner_id}/keys`

DB schema required:
- Apply `supabase_partner_registry.sql` (or re-run `supabase_bootstrap_preciso.sql`) to create:
  - `partner_accounts`
  - `partner_api_keys`

## Endpoint
`POST /api/v1/partners/financials`

### Request body
```json
{
  "partner_id": "acme-inc",
  "source": "partner",
  "document_type": "partner_financials",
  "ticker": "ACME",
  "payload": {
    "title": "ACME Q4 2024 Financials",
    "facts": [
      {
        "entity": "ACME",
        "metric": "Revenue",
        "period": "2024Q4",
        "period_norm": "2024Q4",
        "raw_value": "100000000",
        "normalized_value": "100000000",
        "unit": "currency",
        "currency": "USD",
        "evidence": {
          "document_id": "partner:acme:q4-2024",
          "page": 12,
          "section": "Income Statement",
          "snippet": "Total revenue ...",
          "method": "partner_api",
          "confidence": 0.9
        }
      }
    ],
    "tables": [],
    "metadata": {
      "company": "ACME",
      "fiscal_year": "2024"
    }
  }
}
```

### Response
```json
{
  "document_id": "uuid",
  "facts_count": 123,
  "needs_review": false,
  "message": "partner payload ingested"
}
```

## Storage / Lineage
Writes to `raw_documents`:
- `source`: request.source
- `ticker`: request.ticker
- `document_type`: request.document_type
- `raw_content`: updated to the **normalized** payload after conversion
- `metadata`: includes `partner_id`, `facts_count`, `needs_review`, `unified_summary`

## Quality Rules (enforced)
Conversion path uses `UnifiedConversionEngine` structured payload support:
- Facts get standardized with:
  - `raw_value` vs `normalized_value`
  - `evidence` (document/page/section/snippet/method/confidence)
  - `needs_review` if evidence missing or low confidence

## Next Step (Suggested)
Connect partner ingested documents to HITL queue and, on approval, generate WS8 Spoke A/B artifacts.

## Partner Document Access
List ingested docs for a partner:
- `GET /api/v1/partners/documents?partner_id=...`

Fetch a specific ingested doc:
- `GET /api/v1/partners/documents/{document_id}?partner_id=...`
