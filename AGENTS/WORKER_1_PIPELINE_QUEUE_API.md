# Worker 1 - Pipeline/Queue/API (WS0/WS1 + Async RAG option)

## Mission
Deliver Phase 0 stability:
- Pipeline job standardization across ingest/rag/approval/train/export
- Queue/worker reliability (idempotency, lease, reclaim, DLQ)
- RAG async option design ("heavy query" only first)

Source of truth:
- `PLANS/Preciso_Enterprise_NonDev_Central_RAG_LLM_Master_Plan_v1.md` (Phase 0 + Immediate Next Step)

## Worktree + Branch
- Worktree: `.worktrees/ws-pipeline-queue`
- Branch: `ws/pipeline-queue`

## Owned Files (You Can Edit)
- `app/api/v1/pipeline.py`
- `app/api/v1/rag.py`
- `app/api/v1/ingest.py`
- `app/services/task_queue.py`
- `app/services/enterprise_collab.py`
- `app/services/metrics_logger.py`
- `app/middleware/` (non-contract)
- `tests/test_*pipeline*`, `tests/test_*queue*`

## Do Not Touch (Conductor-Only Contracts)
- `app/services/types.py`
- `app/core/auth.py`
- `app/core/rbac.py`
- `app/models/schemas.py`
- `supabase_all_in_one_safe.sql`
- `supabase_migration_safe.sql`

If you must change them, write a proposal to Conductor instead.

## Non-Negotiables
- No synchronous heavy RAG in API path if it can DOS the server: prefer async behind a flag.
- Every pipeline job must have deterministic `job_id` propagation and audit linkage.
- No silent failures: surface error class + retry guidance.

## Execution Template (Fill This Before Coding)
- Goal:
- Home: `.worktrees/ws-pipeline-queue`
- Files to edit (owned only):
- DB migration required: yes/no (if yes, propose to Conductor; do not edit shared SQL here)
- Tests add/update:
- Rollback plan: feature flag off, or revert commit(s)

## Feature Flags
Any behavior change that alters execution path must be behind a flag (default off).
Propose new flag names; Conductor will add them to `app/services/feature_flags.py`.

## Deliverables (Incremental)
1. Minimal job_id propagation contract:
   - Response includes `job_id`
   - Logs include `job_id` (trace)
2. Async RAG mode:
   - `mode=sync|async` (async only for heavy queries initially)
   - Async returns job_id + status endpoint
3. DLQ UX hooks:
   - pipeline API supports retry/cancel where safe

## Tests
- Add/extend at least 1 test proving:
  - `pipeline_jobs` state transitions (pending->processing->completed/failed)
  - job_id returned and searchable

## Local Commands
- `pytest -q tests/test_*pipeline*`
- `pytest -q tests/test_*rag*` (if you touch rag path)

## Hand-off To Conductor (What To Write)
When you're ready to merge, provide:
- Summary of behavior changes
- New endpoints/params (if any)
- Feature flag name(s) and default state
- Any shared-contract change proposals (do not implement them here)
