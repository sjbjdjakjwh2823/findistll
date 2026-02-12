# Architecture Baseline (Preciso)

## Components
- API (FastAPI)
- Worker (background processing)
- DB (Supabase/Postgres)
- Gateway (Kong + Nginx)
- Multi-tenant context

## Data Flow
- Ingest → Distill → RAG/Graph → Decision → Audit → Approval → Indexing
