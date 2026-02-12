# Partner Registry + SDK UI (Implementation Report)

## What Shipped
- DB-backed Partner Registry:
  - Tables: `partner_accounts`, `partner_api_keys` (hash-only keys)
  - Admin API to register partners and issue/rotate keys
- Partner Ingest API:
  - `POST /api/v1/partners/financials` now supports DB auth (partner-bound)
  - Adds lineage metadata: `partner_account_id`, `partner_key_id`
  - Adds partner document access:
    - `GET /api/v1/partners/documents?partner_id=...`
    - `GET /api/v1/partners/documents/{document_id}?partner_id=...`
- Public config endpoint:
  - `GET /api/v1/config/public`
- Next.js `sdkui`:
  - `/sdkui` shows config + partner registration + ingest test + docs listing + pipeline explanation
- External API Key Registration (Admin):
  - Encrypted secret storage (`integration_secrets`)
  - Admin API to set/list/revoke/test provider keys
  - Market data fetchers use registered keys when env keys are missing
- Python SDK (v1):
  - `sdk/preciso_v1_client.py` (minimal client for /api/v1)

## DB Migration
- Apply `supabase_partner_registry.sql` (or re-run `supabase_bootstrap_preciso.sql`).
- Apply `supabase_integration_secrets.sql` (or re-run `supabase_bootstrap_preciso.sql`).

## Env
- `PARTNER_AUTH_MODE` (`open|env|db|env_or_db`)
- `PARTNER_API_KEYS` (legacy allow-list)
- `PARTNER_API_KEY_PEPPER` (optional)
- `ADMIN_API_TOKEN` (admin protection)
- `INTEGRATION_KEYS_MASTER_KEY` (required for encrypted external key storage)

## Tests
- `pytest -q` (36 tests)
- `npm run build` under `web/`
