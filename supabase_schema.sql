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
