# Phase 0 Kickoff (WS0 + WS1)

Date: 2026-02-12

## Goal
Stabilize "single-tenant central engine" operations:
- All major paths create/update `pipeline_jobs` consistently with a traceable `job_id`.
- Queue reliability is deterministic: idempotency, lease/reclaim, DLQ.
- Heavy RAG can run async (queue/worker) behind a feature flag (default off).

## Home
`/Users/leesangmin/.openclaw/workspace/preciso`

## Workstreams (Parallel)
### WS-PQ (Worker 1: Pipeline/Queue/API)
- Branch: `ws/pipeline-queue` (worktree `.worktrees/ws-pipeline-queue`)
- Scope:
  - pipeline job standardization API
  - RAG async mode (heavy query only first)
  - queue reliability + DLQ operations
- Owned files: see `AGENTS/WORKER_1_PIPELINE_QUEUE_API.md`

### WS-DQ (Worker 2: Data Quality)
- Branch: `ws/data-quality` (worktree `.worktrees/ws-data-quality`)
- Scope (Phase 0 prep + Phase 3 groundwork):
  - deterministic OCR fallback order + `needs_review` routing plumbing
  - numeric preservation checks extension (no behavior change unless behind flag)
- Owned files: see `AGENTS/WORKER_2_DATAFORGE_FINDISTILL_QUALITY.md`

### WS-MLOPS (Worker 3: Training/UI)
- Branch: `ws/mlops-training-ui` (worktree `.worktrees/ws-mlops-training-ui`)
- Scope (Phase 0 prep + Phase 2 groundwork):
  - refactor training execution into job semantics (API surface stays stable behind flag)
  - UI: clarify Auto vs Batch training flow (no breaking changes)
- Owned files: see `AGENTS/WORKER_3_MLOPS_TRAINING_UI.md`

## Shared Contracts (Conductor-Only)
- `app/services/types.py`
- `app/core/auth.py`
- `app/core/rbac.py`
- `app/models/schemas.py`
- `supabase_all_in_one_safe.sql`
- `supabase_migration_safe.sql`

Workers must propose changes, Conductor applies.

## Feature Flag Rule
All big behavior changes must be behind flags (default off). Propose names; Conductor adds them to `app/services/feature_flags.py`.

## Definition of Done (Phase 0)
- `job_id` is:
  - returned in responses where a job is created
  - searchable in logs/audit events
- Worker crash/restart does not permanently strand jobs:
  - stale reclaim works
  - DLQ exists + retry path exists
- Async heavy RAG mode works end-to-end with queue/worker (flag off by default)

## Tests (Minimum)
- Add at least 1 test per workstream:
  - pipeline job transitions (PQ)
  - OCR fallback order or numeric preservation (DQ)
  - training job submission -> status transition (MLOPS)

