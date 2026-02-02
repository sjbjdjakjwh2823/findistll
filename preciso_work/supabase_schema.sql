-- Supabase schema for Preciso (minimal)

create table if not exists public.cases (
  id uuid default gen_random_uuid() primary key,
  case_id text unique not null,
  title text,
  status text,
  distill jsonb,
  decision jsonb,
  created_at timestamptz default now()
);

create table if not exists public.documents (
  id uuid default gen_random_uuid() primary key,
  doc_id text unique not null,
  case_id text not null,
  filename text,
  mime_type text,
  source text,
  payload jsonb,
  created_at timestamptz default now()
);

create index if not exists idx_documents_case_id on public.documents(case_id);

-- Temporal KG edge support (Pillar 3 / TimeGate extension)
create table if not exists public.spoke_d_graph (
  id uuid default gen_random_uuid() primary key,
  case_id text,
  doc_id text,
  head_node text not null,
  relation text not null,
  tail_node text not null,
  properties jsonb,
  event_time timestamptz,
  valid_from timestamptz,
  valid_to timestamptz,
  observed_at timestamptz default now(),
  time_source text,
  time_granularity text,
  created_at timestamptz default now()
);

alter table if exists public.spoke_d_graph add column if not exists case_id text;
alter table if exists public.spoke_d_graph add column if not exists doc_id text;
alter table if exists public.spoke_d_graph add column if not exists event_time timestamptz;
alter table if exists public.spoke_d_graph add column if not exists valid_from timestamptz;
alter table if exists public.spoke_d_graph add column if not exists valid_to timestamptz;
alter table if exists public.spoke_d_graph add column if not exists observed_at timestamptz default now();
alter table if exists public.spoke_d_graph add column if not exists time_source text;
alter table if exists public.spoke_d_graph add column if not exists time_granularity text;

create index if not exists idx_spoke_d_graph_case_id on public.spoke_d_graph(case_id);
create index if not exists idx_spoke_d_graph_event_time on public.spoke_d_graph(event_time);
create index if not exists idx_spoke_d_graph_valid_window on public.spoke_d_graph(valid_from, valid_to);

-- Pipeline audit trail (Orchestrator v2)
create table if not exists public.audit_log (
  id uuid default gen_random_uuid() primary key,
  case_id text not null,
  event_type text not null,
  stage text not null,
  status text not null,
  payload jsonb,
  created_at timestamptz default now()
);

create index if not exists idx_audit_log_case_id on public.audit_log(case_id);
create index if not exists idx_audit_log_created_at on public.audit_log(created_at);
