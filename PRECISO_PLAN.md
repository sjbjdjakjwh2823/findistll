# Preciso Plan: FinRobot + FinDistill (Production-Ready)

## Goal
Integrate the existing FinDistill engine directly into FinRobot and use FinRobot's data-processing layer as the "brain" (decision + workflow). Deliver a Palantir-style web product that real users can use end-to-end (upload → evidence → decision → approval → audit).

## Assumptions
- FinDistill runs as-is (no logic rewrite), wrapped as an internal service.
- FinRobot is the orchestrator/brain that consumes FinDistill outputs.
- DB/infra credentials are stored in `C:\Users\Administrator\Desktop\중요.txt` and must be loaded via environment variables (never hard-coded).

## System Architecture (Front → Server → DB → Site)
### 1) Frontend (Palantir-like UX)
- Framework: Next.js (App Router) + Tailwind + data table/grid component.
- Layout:
  - Left nav: Cases, Evidence, Decisions, Audit, Admin.
  - Main panel: Case timeline + evidence viewer + decision composer.
  - Right panel: signal summary, approval status, audit log.
- Core Screens:
  - **Inbox**: assigned cases, status, SLA badges.
  - **Case Detail**: document preview, extracted facts, CoT (4 sections), signals, decision history.
  - **Evidence Viewer**: facts table + CoT markdown + source snippet anchoring.
  - **Decision Composer**: FinRobot suggestions + human edits + approval workflow.
  - **Audit Trail**: immutable log of evidence → decision → approvals.
- UX Requirements:
  - Dense, data-heavy panels, minimal chrome.
  - Clear authority/ownership markers (role badges).
  - Decision state machine visible at all times.

### 2) Backend Services
- **API Gateway (FastAPI)**
  - Auth, routing, RBAC, rate limits.
- **Distill Service (FinDistill)**
  - Existing extraction/normalization/CoT generation pipeline.
  - Exposes endpoints for `/extract`, `/export`, `/status`.
- **Robot Orchestrator (FinRobot Brain)**
  - Consumes FinDistill outputs (facts + CoT + metadata).
  - Runs reasoning pipeline to produce Decision + Action + Approval requests.
  - Stores decision artifacts and links them to evidence.
- **Background Workers**
  - Long-running PDF/XBRL processing, embedding, bulk exports.
  - Queue: Redis (or Supabase queue + cron).

### 3) Database / Storage
- Primary DB: Supabase Postgres (from 중요.txt)
- Storage:
  - Supabase Storage buckets (original docs, exports)
  - Optional: vector search (pgvector in Supabase or external Qdrant)
- Core Tables:
  - cases, documents, facts, signals, decisions, actions, approvals, comments, audit_events, users, roles
- Indexing:
  - case_id, company, period, status, severity

### 4) Public Site (Production)
- Domain + SSL
- Auth: Supabase Auth or external (Clerk/Okta)
- Observability: log aggregation + trace IDs
- RBAC enforcement end-to-end

## Data Flow (End-to-End)
1. User uploads document → `documents` record + file storage.
2. FinDistill extracts facts + CoT → stored in `facts` and `evidence` tables.
3. FinRobot consumes facts/CoT → generates decision recommendations.
4. User reviews/approves → status transitions recorded.
5. Audit log auto-captures every action.

## Server Requirements (MD Summary)
- Runtime:
  - Python 3.11+ (FastAPI, FinDistill)
  - Node 18+ (Next.js)
- Services:
  - Redis (queue/cache)
  - Supabase Postgres + Storage
- Optional:
  - Vector DB (pgvector/Qdrant)
  - Worker nodes for large PDF/XBRL batches
- Required ENV (values stored in 중요.txt):
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `SUPABASE_DB_URL`
  - `HF_TOKEN`
  - `HF_DATASET`
  - `CLOUDFLARE_TUNNEL_TOKEN` (if tunnel used)

## Implementation Plan (Phased)
### Phase 0: Setup (Week 1)
- Create `.env` from 중요.txt (no secrets in repo)
- Stand up DB schemas + storage buckets
- Baseline API skeleton

### Phase 1: Backend Core (Week 2–3)
- Wrap FinDistill as internal service
- Implement API endpoints:
  - `/cases`, `/cases/{id}/documents`, `/cases/{id}/distill`, `/cases/{id}/decide`
- Add background worker for extraction jobs

### Phase 2: FinRobot Brain (Week 3–4)
- Implement reasoning pipeline consuming facts + CoT
- Decision generation with evidence linkage
- Store outputs to decisions/actions/approvals

### Phase 3: Frontend (Week 4–5)
- Build Inbox, Case Detail, Evidence Viewer, Decision Composer, Audit
- Wire API integration
- RBAC-based UI gating

### Phase 4: QA + Hardening (Week 6)
- End-to-end tests (upload → decision)
- Security/RBAC tests
- Load tests on extraction + decision pipeline

### Phase 5: Deployment (Week 7)
- Frontend: Vercel (or Cloudflare Pages)
- Backend: Docker on VM or container platform
- Optional: Cloudflare Tunnel for restricted access

## Risks & Mitigations
- Long extraction time → async jobs + progress UI
- Decision quality variability → explainability + evidence anchoring
- Sensitive data → strict RBAC + audit log

## Next Actions
1. Confirm FinRobot interface contract for decisions/actions.
2. Approve DB schema and table names.
3. Approve UI screens and navigation layout.
