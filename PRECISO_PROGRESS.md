# Preciso Progress Report
Date: 2026-02-07

## Summary
- Implemented Kong Gateway configuration for AI Brain RAG/API rate limiting.
- Synced infra plan (Kong) with repo via `kong.yml`.
- Updated deploy docs with Kong usage.

## Changes
- Added `kong.yml` with key-auth + rate-limiting plugins for `/rag` and `/api/v1`.
- Added Kong notes in deployment guide.

## Files Updated / Added
- /Users/leesangmin/.openclaw/workspace/preciso/app/services/custom_fields.py
- /Users/leesangmin/.openclaw/workspace/preciso/docker-compose.onprem.yml
- /Users/leesangmin/.openclaw/workspace/preciso/.env.template
- /Users/leesangmin/.openclaw/workspace/preciso/launcher.sh
- /Users/leesangmin/.openclaw/workspace/preciso/launcher.bat
- /Users/leesangmin/.openclaw/workspace/preciso/README_DEPLOY.md
- /Users/leesangmin/.openclaw/workspace/preciso/kong.yml
- /Users/leesangmin/.openclaw/workspace/preciso/README_DEPLOY.md

## Tests
- Not run for Kong config (infra config only).

## Notes
- No `app/services/billing.py` exists in repo; no in-app rate limit logic found.
- Kong config assumes backend service `preciso-api:8000` and Redis at `redis:6379`.


---
Date: 2026-02-07

## Summary
- Added on-prem license validation, audit-trail auto-capture, and approval workflow endpoints.
- Implemented pgvector RAG schema + feedback tables with RPC helpers.
- Added embedding generation/storage and case-embedding search hook (optional env `CASE_RAG_ENABLED=1`).

## Changes
- Added audit logger with checksum chain and middleware (trace ID + audit capture).
- Added license guard middleware, license validation API, and export/feedback/approval endpoints.
- Added pgvector schema + license/audit/version tables in `supabase_ai_evolution.sql`.
- Extended DB clients with audit/embedding/feedback/license support.

## Files Updated / Added
- /Users/leesangmin/.openclaw/workspace/preciso/app/services/custom_fields.py
- /Users/leesangmin/.openclaw/workspace/preciso/docker-compose.onprem.yml
- /Users/leesangmin/.openclaw/workspace/preciso/.env.template
- /Users/leesangmin/.openclaw/workspace/preciso/launcher.sh
- /Users/leesangmin/.openclaw/workspace/preciso/launcher.bat
- /Users/leesangmin/.openclaw/workspace/preciso/README_DEPLOY.md
- /Users/leesangmin/.openclaw/workspace/preciso/app/services/audit_logger.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/middleware/audit.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/middleware/trace.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/middleware/license_guard.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/services/license_service.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/services/embedding_service.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/services/case_embedding_search.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/api/v1/license.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/api/v1/export.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/api/v1/feedback.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/api/v1/approval.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/db/client.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/db/supabase_db.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/db/registry.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/core/config.py
- /Users/leesangmin/.openclaw/workspace/preciso/app/main.py
- /Users/leesangmin/.openclaw/workspace/preciso/supabase_ai_evolution.sql
- /Users/leesangmin/.openclaw/workspace/preciso/.env.example
- /Users/leesangmin/.openclaw/workspace/preciso/tests/test_audit_logger.py

## Tests
- Added unit test for audit checksum chain.
- Full test suite not run; previous failures due to missing `dotenv` remain.


---
Date: 2026-02-07

## Summary
- Fixed case embedding search formatter and added python-dotenv to requirements.
- Full test suite passes in venv.

## Changes
- Rewrote CaseEmbeddingSearch formatter string to avoid syntax error.
- Added python-dotenv to requirements.txt.

## Files Updated / Added
- /Users/leesangmin/.openclaw/workspace/preciso/app/services/case_embedding_search.py
- /Users/leesangmin/.openclaw/workspace/preciso/requirements.txt

## Tests
- /Users/leesangmin/.openclaw/workspace/preciso/venv/bin/python -m pytest -q (pass with 3 warnings about return values in tests/test_phase2_integration.py)


---
Date: 2026-02-07

## Summary
- Cleared pytest warnings by converting Phase 2 integration tests to assertions.

## Changes
- Rewrote tests in tests/test_phase2_integration.py to avoid returning values.

## Files Updated / Added
- /Users/leesangmin/.openclaw/workspace/preciso/tests/test_phase2_integration.py

## Tests
- /Users/leesangmin/.openclaw/workspace/preciso/venv/bin/python -m pytest -q (pass, 0 warnings)
