# Preciso Production Hardening Checklist

## Scope
- Security controls, operations readiness, performance verification, compliance artifacts, and release gating.

## Phase 0: Baseline
- Define SLO/SLA, RTO/RPO, data retention, and audit requirements.
- Capture architecture baseline (API, workers, DB, gateway, tenant boundaries).
- Create risk register with mitigation owners.

## Phase 1: Security
- Verify RBAC enforcement paths and negative tests.
- Validate tenant isolation paths (request headers + DB scoping).
- Standardize secret management (replace ad-hoc env usage with a single secret source).
- Define audit event schema and retention.

## Phase 2: Operations
- Add pre-deploy checks: migrations, smoke tests, rollback plan.
- Establish backup/restore drill cadence and tracking.
- Configure monitoring for error rate, latency, queue depth, and approval delays.

## Phase 3: Performance
- Load test retrieval, approvals, multi-agent pipeline, workers.
- Tune DB indexes and slow queries.
- Establish performance regression gates.
- Enable RAG cache in prod (`RAG_CACHE_ENABLED=1`) with Redis configured.
- Set RAG quality gates (`RAG_MIN_SIM`, `RAG_MIN_KEYWORD_SIM`) and document defaults.

## Phase 4: Compliance
- Produce audit evidence bundle (RBAC, approvals, diffs, logs).
- Verify audit log immutability and chain validation.
- Maintain monthly compliance report template.

## Phase 5: Release Gates
- E2E regression for critical workflows.
- Canary and staged rollout criteria.
- UAT signoff checklist and Go/No-Go decision.
