# Worker 3 - MLOps/Training/Models UI (WS4/WS5)

## Mission
Make approval->training "non-dev operable":
- Training must be a job (queue/worker), not a local thread spawn in API process
- Job status/logs/artifacts visible and consistent with pipeline_jobs
- Serving model selection + rollback UX clarity (single serving model)

Source of truth:
- `PLANS/Preciso_Enterprise_NonDev_Central_RAG_LLM_Master_Plan_v1.md` (Phase 2)

## Worktree + Branch
- Worktree: `.worktrees/ws-mlops-training-ui`
- Branch: `ws/mlops-training-ui`

## Owned Files (You Can Edit)
- `app/api/v1/training.py`
- `app/api/v1/mlflow_api.py`
- `app/services/training_service.py`
- `app/services/mlflow_service.py`
- `web/app/mlops/**`
- `web/app/settings/**`
- `web/app/ops-console/**`
- `web/app/logs/**`
- `web/app/setup/**`
- `tests/test_*training*`, `tests/test_*mlflow*`

## Do Not Touch (Conductor-Only Contracts)
- `app/services/types.py`
- `app/core/auth.py`
- `app/core/rbac.py`
- `app/models/schemas.py`
- `supabase_all_in_one_safe.sql`
- `supabase_migration_safe.sql`

## Feature Flags
Any change that affects job execution path must be behind a flag (default off).
Propose flag names; Conductor adds them centrally.

## Execution Template (Fill This Before Coding)
- Goal:
- Home: `.worktrees/ws-mlops-training-ui`
- Files to edit (owned only):
- DB migration required: yes/no (if yes, propose to Conductor; do not edit shared SQL here)
- Tests add/update:
- Rollback plan: feature flag off, or revert commit(s)

## Deliverables (Incremental)
1. Training job structure:
   - enqueue training job
   - worker consumes and updates status
2. UI improvements:
   - "Auto vs Batch" split is obvious
   - show last run status and how to rollback

## Tests
- Add at least 1 test covering:
  - training job submission -> status transition (mock worker)

## Local Commands
- `pytest -q tests/test_*training*`
- `cd web && npm run lint` (if you edit UI)

## Hand-off To Conductor (What To Write)
When you're ready to merge, provide:
- New UI routes/components you touched
- Any API behavior changes (flagged) and how to roll back
- Any shared-contract change proposals (do not implement them here)
