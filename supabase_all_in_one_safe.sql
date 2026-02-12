-- Preciso Supabase All-in-One Safe Bootstrap
-- Purpose: initialize an empty Supabase project with all tables/RPC needed by Preciso
-- Policy: idempotent, no DO/BEGIN blocks, safe to rerun.

create extension if not exists pgcrypto;
create extension if not exists pg_trgm;
create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- Core domain
-- ---------------------------------------------------------------------------
create table if not exists cases (
  id uuid primary key default gen_random_uuid(),
  case_id text unique,
  title text,
  status text default 'created',
  distill jsonb,
  decision jsonb,
  metadata jsonb default '{}'::jsonb,
  tenant_id text not null default 'public',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  doc_id text unique,
  case_id text,
  filename text,
  mime_type text,
  source text,
  payload jsonb default '{}'::jsonb,
  tenant_id text not null default 'public',
  created_at timestamptz not null default now()
);

create table if not exists raw_documents (
  id uuid primary key default gen_random_uuid(),
  doc_id text,
  source text,
  ticker text,
  document_type text,
  document_date date,
  raw_content jsonb default '{}'::jsonb,
  file_hash text,
  file_path text,
  processing_status text default 'pending',
  processing_error text,
  metadata jsonb default '{}'::jsonb,
  tenant_id text not null default 'public',
  ingested_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_raw_documents_file_hash_tenant
  on raw_documents(tenant_id, file_hash)
  where file_hash is not null;
create index if not exists idx_raw_documents_tenant_ingested
  on raw_documents(tenant_id, ingested_at desc);

create table if not exists spoke_c_rag_context (
  id uuid primary key default gen_random_uuid(),
  chunk_id text unique,
  entity text,
  period text,
  source text,
  text_content text,
  keywords jsonb default '[]'::jsonb,
  metadata jsonb default '{}'::jsonb,
  tenant_id text not null default 'public',
  created_at timestamptz not null default now()
);
create index if not exists idx_spoke_c_tenant_created on spoke_c_rag_context(tenant_id, created_at desc);
create index if not exists idx_spoke_c_text_trgm on spoke_c_rag_context using gin (text_content gin_trgm_ops);
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='spoke_c_rag_context' AND column_name='keywords' AND data_type='jsonb'
  ) THEN
    EXECUTE 'create index if not exists idx_spoke_c_keywords_gin on spoke_c_rag_context using gin (keywords jsonb_path_ops)';
  ELSIF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='spoke_c_rag_context' AND column_name='keywords' AND data_type='ARRAY'
  ) THEN
    EXECUTE 'create index if not exists idx_spoke_c_keywords_gin on spoke_c_rag_context using gin (keywords)';
  END IF;
END $$;
create index if not exists idx_spoke_c_entity_period on spoke_c_rag_context(tenant_id, entity, period);

create table if not exists spoke_d_graph (
  id uuid primary key default gen_random_uuid(),
  head_node text,
  relation text,
  tail_node text,
  properties jsonb default '{}'::jsonb,
  tenant_id text not null default 'public',
  created_at timestamptz not null default now()
);
create index if not exists idx_spoke_d_tenant_head on spoke_d_graph(tenant_id, head_node);
create index if not exists idx_spoke_d_tenant_tail on spoke_d_graph(tenant_id, tail_node);

create table if not exists ai_training_sets (
  id uuid primary key default gen_random_uuid(),
  metadata jsonb default '{}'::jsonb,
  input_features jsonb default '{}'::jsonb,
  reasoning_chain text,
  output_narrative text,
  training_prompt text,
  tenant_id text not null default 'public',
  created_at timestamptz not null default now()
);
create index if not exists idx_ai_training_sets_tenant_created on ai_training_sets(tenant_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Embeddings / retrieval
-- ---------------------------------------------------------------------------
create table if not exists embeddings_finance (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  metadata jsonb default '{}'::jsonb,
  embedding vector(384),
  tenant_id text not null default 'public',
  created_at timestamptz not null default now()
);
create index if not exists idx_embeddings_finance_tenant_created on embeddings_finance(tenant_id, created_at desc);

create table if not exists case_embeddings (
  id uuid primary key default gen_random_uuid(),
  case_id uuid,
  section_type text,
  chunk_type text,
  chunk_id text,
  content text not null,
  embedding vector(384),
  company text,
  industry text,
  severity text,
  period text,
  approval_status text,
  approved_at timestamptz,
  approved_by text,
  metadata jsonb default '{}'::jsonb,
  tenant_id text not null default 'public',
  created_at timestamptz not null default now()
);
create index if not exists idx_case_embeddings_tenant_created on case_embeddings(tenant_id, created_at desc);
create index if not exists idx_case_embeddings_chunk_id on case_embeddings(chunk_id);
create index if not exists idx_case_embeddings_content_trgm on case_embeddings using gin (content gin_trgm_ops);
create index if not exists idx_case_embeddings_embedding on case_embeddings using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- ---------------------------------------------------------------------------
-- Feedback / audit
-- ---------------------------------------------------------------------------
create table if not exists evidence_feedback (
  id uuid primary key default gen_random_uuid(),
  case_id text,
  evidence_id text,
  user_id text,
  feedback_type text,
  score numeric,
  comments text,
  metadata jsonb default '{}'::jsonb,
  tenant_id text not null default 'public',
  created_at timestamptz not null default now()
);
create index if not exists idx_evidence_feedback_tenant_case on evidence_feedback(tenant_id, case_id, created_at desc);

create table if not exists audit_events (
  id uuid primary key default gen_random_uuid(),
  event_type text not null,
  case_id uuid,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_audit_events_type_created on audit_events(event_type, created_at desc);

create table if not exists audit_logs (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  user_id text,
  action text,
  target_type text,
  target_id text,
  detail jsonb default '{}'::jsonb,
  timestamp timestamptz,
  actor_type text,
  actor_id text,
  action_type text,
  entity_type text,
  entity_id text,
  details jsonb default '{}'::jsonb,
  is_immutable boolean default true,
  created_at timestamptz not null default now()
);
create index if not exists idx_audit_logs_tenant_created on audit_logs(tenant_id, created_at desc);
create index if not exists idx_audit_logs_actor on audit_logs(tenant_id, actor_id, actor_type);
create index if not exists idx_audit_logs_entity on audit_logs(tenant_id, entity_id, entity_type);

create table if not exists ops_audit_logs (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  level text default 'info',
  event_type text,
  message text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_ops_audit_logs_tenant_created on ops_audit_logs(tenant_id, created_at desc);

-- ---------------------------------------------------------------------------
-- WS8 spoke artifacts
-- ---------------------------------------------------------------------------
create table if not exists dataset_versions (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  name text,
  status text default 'active',
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  sealed_at timestamptz
);
create index if not exists idx_dataset_versions_tenant_created on dataset_versions(tenant_id, created_at desc);

create table if not exists spoke_a_samples (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  dataset_version_id uuid,
  sample_key text,
  instruction text,
  input text,
  output text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create unique index if not exists idx_spoke_a_samples_tenant_key on spoke_a_samples(tenant_id, sample_key);
create index if not exists idx_spoke_a_samples_dataset on spoke_a_samples(dataset_version_id);

create table if not exists spoke_b_artifacts (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  doc_id text,
  kind text,
  artifact jsonb default '{}'::jsonb,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_spoke_b_artifacts_tenant_doc_kind on spoke_b_artifacts(tenant_id, doc_id, kind);

-- ---------------------------------------------------------------------------
-- Evaluation / quality
-- ---------------------------------------------------------------------------
create table if not exists prompt_templates (
  id uuid primary key default gen_random_uuid(),
  template_type text not null,
  version text default 'v1',
  prompt text not null,
  is_active boolean not null default true,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_prompt_templates_type_active on prompt_templates(template_type, is_active);

create table if not exists generated_samples (
  id uuid primary key default gen_random_uuid(),
  raw_document_id uuid,
  template_type text,
  template_version text,
  generated_content jsonb default '{}'::jsonb,
  model_used text,
  model_params jsonb default '{}'::jsonb,
  confidence_score numeric,
  token_usage jsonb default '{}'::jsonb,
  generation_time_ms int,
  review_status text default 'pending',
  priority_score numeric default 0.5,
  created_at timestamptz not null default now()
);
create index if not exists idx_generated_samples_template_status on generated_samples(template_type, review_status);

create table if not exists gold_standard_cases (
  id uuid primary key default gen_random_uuid(),
  title text,
  prompt text,
  expected_output text,
  validation_score numeric default 0,
  use_for_training boolean default true,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists eval_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  run_name text,
  status text default 'pending',
  score numeric,
  details jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists data_quality_scores (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  doc_id text,
  source text,
  score numeric,
  metrics jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_data_quality_scores_tenant_doc on data_quality_scores(tenant_id, doc_id, created_at desc);

create table if not exists dataforge_metrics (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  metric_name text not null,
  metric_value numeric,
  tags jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists perf_metrics (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  metric_name text not null,
  metric_value numeric,
  tags jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists selfcheck_samples (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  case_id text,
  sample jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists snorkel_aggregated_facts (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  doc_id text,
  fact jsonb default '{}'::jsonb,
  confidence numeric,
  created_at timestamptz not null default now()
);

create table if not exists labeling_function_profiles (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  name text,
  config jsonb default '{}'::jsonb,
  active boolean default true,
  created_at timestamptz not null default now()
);

create table if not exists labeling_function_results (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  profile_id uuid,
  doc_id text,
  result jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists annotator_stats (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  user_id text,
  stats jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists human_annotations (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  user_id text,
  sample_id text,
  annotation jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Graph/ontology/ops
-- ---------------------------------------------------------------------------
create table if not exists ontology_nodes (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  name text,
  node_type text,
  properties jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists causal_nodes (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  name text,
  node_type text,
  properties jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists causal_edges (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  source_node_id uuid,
  target_node_id uuid,
  relation text,
  weight numeric,
  properties jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists kg_entities (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  name text,
  entity_type text,
  properties jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists kg_relationships (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  source_entity_id uuid,
  target_entity_id uuid,
  relation_type text,
  weight numeric,
  properties jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_kg_relationships_source on kg_relationships(source_entity_id);
create index if not exists idx_kg_relationships_target on kg_relationships(target_entity_id);

create table if not exists ops_entities (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  name text,
  entity_type text,
  properties jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_ops_entities_tenant_name on ops_entities(tenant_id, name);

create table if not exists ops_relationships (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  source_entity_id uuid,
  target_entity_id uuid,
  relation_type text,
  weight numeric,
  properties jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists ops_cases (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  case_id text,
  status text,
  payload jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists ops_case_state_history (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  case_id text,
  from_state text,
  to_state text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Auth/license/partners
-- ---------------------------------------------------------------------------
create table if not exists licenses (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  license_key text unique,
  user_id text,
  status text default 'active',
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists license_activations (
  id uuid primary key default gen_random_uuid(),
  license_id uuid,
  device_fingerprint text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists license_checks (
  id uuid primary key default gen_random_uuid(),
  license_id uuid,
  device_fingerprint text,
  result text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists partner_accounts (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  partner_code text unique,
  name text,
  status text default 'active',
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists partner_api_keys (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  partner_id uuid,
  key_prefix text,
  key_hash text unique,
  status text default 'active',
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists integration_secrets (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  provider text not null,
  secret_name text not null,
  encrypted_value text not null,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique (tenant_id, provider, secret_name)
);

-- ---------------------------------------------------------------------------
-- Enterprise collaboration / pipeline manager
-- ---------------------------------------------------------------------------
create table if not exists org_users (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  rbac_user_id text,
  display_name text,
  email text,
  status text default 'active',
  created_at timestamptz not null default now()
);
create unique index if not exists idx_org_users_tenant_email on org_users(tenant_id, email);

create table if not exists collab_contacts (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  requester_user_id text,
  target_user_id text,
  status text not null default 'pending',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_collab_contacts_tenant_status on collab_contacts(tenant_id, status, created_at desc);

create table if not exists collab_invites (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  code text not null,
  requester_user_id text not null,
  target_user_id text,
  status text not null default 'pending',
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, code)
);
create index if not exists idx_collab_invites_tenant_code on collab_invites(tenant_id, code);

create table if not exists collab_teams (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  name text not null,
  owner_user_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_collab_teams_tenant_name on collab_teams(tenant_id, name);

create table if not exists collab_team_members (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  team_id uuid,
  user_id text,
  role text default 'member',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create unique index if not exists idx_collab_team_members_unique on collab_team_members(tenant_id, team_id, user_id);

create table if not exists collab_spaces (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  type text not null default 'personal',
  owner_user_id text,
  team_id uuid,
  name text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_collab_spaces_tenant_type on collab_spaces(tenant_id, type);

create table if not exists collab_files (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  space_id uuid,
  owner_user_id text,
  doc_id text,
  version int default 1,
  visibility text default 'private',
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_collab_files_tenant_space on collab_files(tenant_id, space_id, created_at desc);

create table if not exists collab_file_acl (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  file_id uuid,
  principal_type text not null,
  principal_id text,
  permission text not null default 'read',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_collab_file_acl_tenant_file on collab_file_acl(tenant_id, file_id);

create table if not exists collab_transfers (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  sender_user_id text,
  receiver_user_id text,
  file_id uuid,
  message text,
  status text default 'sent',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_collab_transfers_tenant_receiver on collab_transfers(tenant_id, receiver_user_id, created_at desc);

create table if not exists tenant_pipeline_profiles (
  tenant_id text primary key,
  rag_profile_json jsonb default '{}'::jsonb,
  llm_profile_json jsonb default '{}'::jsonb,
  rate_limits_json jsonb default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists tenant_pipeline_quotas (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null,
  user_id text not null,
  day date not null default current_date,
  rag_queries int not null default 0,
  llm_tokens bigint not null default 0,
  ingest_docs int not null default 0,
  created_at timestamptz not null default now(),
  unique (tenant_id, user_id, day)
);

create table if not exists pipeline_jobs (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  user_id text,
  job_type text not null,
  priority int not null default 50,
  status text not null default 'queued',
  input_ref jsonb default '{}'::jsonb,
  output_ref jsonb default '{}'::jsonb,
  error text,
  created_at timestamptz not null default now(),
  started_at timestamptz,
  finished_at timestamptz
);
create index if not exists idx_pipeline_jobs_tenant_status_priority
  on pipeline_jobs(tenant_id, status, priority, created_at);

create table if not exists ai_brain_traces (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default 'public',
  case_id text,
  trace jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- Column backfill (handles existing tables missing columns)
-- ---------------------------------------------------------------------------

alter table if exists cases
  add column if not exists case_id text,
  add column if not exists title text,
  add column if not exists status text,
  add column if not exists distill jsonb,
  add column if not exists decision jsonb,
  add column if not exists metadata jsonb,
  add column if not exists tenant_id text,
  add column if not exists created_at timestamptz,
  add column if not exists updated_at timestamptz;

alter table if exists documents
  add column if not exists doc_id text,
  add column if not exists case_id text,
  add column if not exists filename text,
  add column if not exists mime_type text,
  add column if not exists source text,
  add column if not exists payload jsonb,
  add column if not exists tenant_id text,
  add column if not exists created_at timestamptz;

alter table if exists raw_documents
  add column if not exists doc_id text,
  add column if not exists source text,
  add column if not exists ticker text,
  add column if not exists document_type text,
  add column if not exists document_date date,
  add column if not exists raw_content jsonb,
  add column if not exists file_hash text,
  add column if not exists file_path text,
  add column if not exists processing_status text,
  add column if not exists processing_error text,
  add column if not exists metadata jsonb,
  add column if not exists tenant_id text,
  add column if not exists ingested_at timestamptz,
  add column if not exists created_at timestamptz,
  add column if not exists updated_at timestamptz;

alter table if exists spoke_c_rag_context
  add column if not exists chunk_id text,
  add column if not exists entity text,
  add column if not exists period text,
  add column if not exists source text,
  add column if not exists text_content text,
  add column if not exists keywords jsonb,
  add column if not exists metadata jsonb,
  add column if not exists tenant_id text,
  add column if not exists created_at timestamptz;

alter table if exists spoke_d_graph
  add column if not exists head_node text,
  add column if not exists relation text,
  add column if not exists tail_node text,
  add column if not exists properties jsonb,
  add column if not exists tenant_id text,
  add column if not exists created_at timestamptz;

alter table if exists embeddings_finance
  add column if not exists content text,
  add column if not exists metadata jsonb,
  add column if not exists embedding vector(384),
  add column if not exists tenant_id text,
  add column if not exists created_at timestamptz;

alter table if exists case_embeddings
  add column if not exists case_id uuid,
  add column if not exists section_type text,
  add column if not exists chunk_type text,
  add column if not exists chunk_id text,
  add column if not exists content text,
  add column if not exists embedding vector(384),
  add column if not exists company text,
  add column if not exists industry text,
  add column if not exists severity text,
  add column if not exists period text,
  add column if not exists approval_status text,
  add column if not exists approved_at timestamptz,
  add column if not exists approved_by text,
  add column if not exists metadata jsonb,
  add column if not exists tenant_id text,
  add column if not exists created_at timestamptz;

alter table if exists evidence_feedback
  add column if not exists case_id text,
  add column if not exists evidence_id text,
  add column if not exists user_id text,
  add column if not exists feedback_type text,
  add column if not exists score numeric,
  add column if not exists comments text,
  add column if not exists metadata jsonb,
  add column if not exists tenant_id text,
  add column if not exists created_at timestamptz;

alter table if exists audit_events
  add column if not exists event_type text,
  add column if not exists case_id uuid,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists audit_logs
  add column if not exists tenant_id text,
  add column if not exists user_id text,
  add column if not exists action text,
  add column if not exists target_type text,
  add column if not exists target_id text,
  add column if not exists detail jsonb,
  add column if not exists timestamp timestamptz,
  add column if not exists actor_type text,
  add column if not exists actor_id text,
  add column if not exists action_type text,
  add column if not exists entity_type text,
  add column if not exists entity_id text,
  add column if not exists details jsonb,
  add column if not exists is_immutable boolean,
  add column if not exists created_at timestamptz;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='audit_logs' AND column_name='actor_id'
  ) THEN
    ALTER TABLE audit_logs
      ALTER COLUMN actor_id TYPE text USING actor_id::text;
  END IF;
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='audit_logs' AND column_name='entity_id'
  ) THEN
    ALTER TABLE audit_logs
      ALTER COLUMN entity_id TYPE text USING entity_id::text;
  END IF;
END $$;

alter table if exists ops_audit_logs
  add column if not exists tenant_id text,
  add column if not exists level text,
  add column if not exists event_type text,
  add column if not exists message text,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists dataset_versions
  add column if not exists tenant_id text,
  add column if not exists name text,
  add column if not exists status text,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz,
  add column if not exists sealed_at timestamptz;

alter table if exists spoke_a_samples
  add column if not exists tenant_id text,
  add column if not exists dataset_version_id uuid,
  add column if not exists sample_key text,
  add column if not exists instruction text,
  add column if not exists input text,
  add column if not exists output text,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists spoke_b_artifacts
  add column if not exists tenant_id text,
  add column if not exists doc_id text,
  add column if not exists kind text,
  add column if not exists artifact jsonb,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists prompt_templates
  add column if not exists template_type text,
  add column if not exists version text,
  add column if not exists prompt text,
  add column if not exists is_active boolean,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists generated_samples
  add column if not exists raw_document_id uuid,
  add column if not exists template_type text,
  add column if not exists template_version text,
  add column if not exists generated_content jsonb,
  add column if not exists model_used text,
  add column if not exists model_params jsonb,
  add column if not exists confidence_score numeric,
  add column if not exists token_usage jsonb,
  add column if not exists generation_time_ms int,
  add column if not exists review_status text,
  add column if not exists priority_score numeric,
  add column if not exists created_at timestamptz;

alter table if exists eval_runs
  add column if not exists tenant_id text,
  add column if not exists run_name text,
  add column if not exists status text,
  add column if not exists score numeric,
  add column if not exists details jsonb,
  add column if not exists created_at timestamptz;

alter table if exists data_quality_scores
  add column if not exists tenant_id text,
  add column if not exists doc_id text,
  add column if not exists source text,
  add column if not exists score numeric,
  add column if not exists metrics jsonb,
  add column if not exists created_at timestamptz;

alter table if exists dataforge_metrics
  add column if not exists tenant_id text,
  add column if not exists metric_name text,
  add column if not exists metric_value numeric,
  add column if not exists tags jsonb,
  add column if not exists created_at timestamptz;

alter table if exists perf_metrics
  add column if not exists tenant_id text,
  add column if not exists metric_name text,
  add column if not exists metric_value numeric,
  add column if not exists tags jsonb,
  add column if not exists created_at timestamptz;

alter table if exists selfcheck_samples
  add column if not exists tenant_id text,
  add column if not exists case_id text,
  add column if not exists sample jsonb,
  add column if not exists created_at timestamptz;

alter table if exists snorkel_aggregated_facts
  add column if not exists tenant_id text,
  add column if not exists doc_id text,
  add column if not exists fact jsonb,
  add column if not exists confidence numeric,
  add column if not exists created_at timestamptz;

alter table if exists labeling_function_profiles
  add column if not exists tenant_id text,
  add column if not exists name text,
  add column if not exists config jsonb,
  add column if not exists active boolean,
  add column if not exists created_at timestamptz;

alter table if exists labeling_function_results
  add column if not exists tenant_id text,
  add column if not exists profile_id uuid,
  add column if not exists doc_id text,
  add column if not exists result jsonb,
  add column if not exists created_at timestamptz;

alter table if exists annotator_stats
  add column if not exists tenant_id text,
  add column if not exists user_id text,
  add column if not exists stats jsonb,
  add column if not exists created_at timestamptz;

alter table if exists human_annotations
  add column if not exists tenant_id text,
  add column if not exists user_id text,
  add column if not exists sample_id text,
  add column if not exists annotation jsonb,
  add column if not exists created_at timestamptz;

alter table if exists ontology_nodes
  add column if not exists tenant_id text,
  add column if not exists name text,
  add column if not exists node_type text,
  add column if not exists properties jsonb,
  add column if not exists created_at timestamptz;

alter table if exists causal_nodes
  add column if not exists tenant_id text,
  add column if not exists name text,
  add column if not exists node_type text,
  add column if not exists properties jsonb,
  add column if not exists created_at timestamptz;

alter table if exists causal_edges
  add column if not exists tenant_id text,
  add column if not exists source_node_id uuid,
  add column if not exists target_node_id uuid,
  add column if not exists relation text,
  add column if not exists weight numeric,
  add column if not exists properties jsonb,
  add column if not exists created_at timestamptz;

alter table if exists kg_entities
  add column if not exists tenant_id text,
  add column if not exists name text,
  add column if not exists entity_type text,
  add column if not exists properties jsonb,
  add column if not exists created_at timestamptz;

alter table if exists kg_relationships
  add column if not exists tenant_id text,
  add column if not exists source_entity_id uuid,
  add column if not exists target_entity_id uuid,
  add column if not exists relation_type text,
  add column if not exists weight numeric,
  add column if not exists properties jsonb,
  add column if not exists created_at timestamptz;

alter table if exists ops_entities
  add column if not exists tenant_id text,
  add column if not exists name text,
  add column if not exists entity_type text,
  add column if not exists properties jsonb,
  add column if not exists created_at timestamptz;

alter table if exists ops_relationships
  add column if not exists tenant_id text,
  add column if not exists source_entity_id uuid,
  add column if not exists target_entity_id uuid,
  add column if not exists relation_type text,
  add column if not exists weight numeric,
  add column if not exists properties jsonb,
  add column if not exists created_at timestamptz;

alter table if exists ops_cases
  add column if not exists tenant_id text,
  add column if not exists case_id text,
  add column if not exists status text,
  add column if not exists payload jsonb,
  add column if not exists created_at timestamptz;

alter table if exists ops_case_state_history
  add column if not exists tenant_id text,
  add column if not exists case_id text,
  add column if not exists from_state text,
  add column if not exists to_state text,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists licenses
  add column if not exists tenant_id text,
  add column if not exists license_key text,
  add column if not exists user_id text,
  add column if not exists status text,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists license_activations
  add column if not exists license_id uuid,
  add column if not exists device_fingerprint text,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists license_checks
  add column if not exists license_id uuid,
  add column if not exists device_fingerprint text,
  add column if not exists result text,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists partner_accounts
  add column if not exists tenant_id text,
  add column if not exists partner_code text,
  add column if not exists name text,
  add column if not exists status text,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists partner_api_keys
  add column if not exists tenant_id text,
  add column if not exists partner_id uuid,
  add column if not exists key_prefix text,
  add column if not exists key_hash text,
  add column if not exists status text,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists integration_secrets
  add column if not exists tenant_id text,
  add column if not exists provider text,
  add column if not exists secret_name text,
  add column if not exists encrypted_value text,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz;

alter table if exists org_users
  add column if not exists tenant_id text,
  add column if not exists rbac_user_id text,
  add column if not exists display_name text,
  add column if not exists email text,
  add column if not exists status text,
  add column if not exists created_at timestamptz;

alter table if exists collab_contacts
  add column if not exists tenant_id text,
  add column if not exists requester_user_id text,
  add column if not exists target_user_id text,
  add column if not exists status text,
  add column if not exists created_at timestamptz,
  add column if not exists updated_at timestamptz;

alter table if exists collab_teams
  add column if not exists tenant_id text,
  add column if not exists name text,
  add column if not exists owner_user_id text,
  add column if not exists created_at timestamptz,
  add column if not exists updated_at timestamptz;

alter table if exists collab_team_members
  add column if not exists tenant_id text,
  add column if not exists team_id uuid,
  add column if not exists user_id text,
  add column if not exists role text,
  add column if not exists created_at timestamptz,
  add column if not exists updated_at timestamptz;

alter table if exists collab_spaces
  add column if not exists tenant_id text,
  add column if not exists type text,
  add column if not exists owner_user_id text,
  add column if not exists team_id uuid,
  add column if not exists name text,
  add column if not exists created_at timestamptz,
  add column if not exists updated_at timestamptz;

alter table if exists collab_files
  add column if not exists tenant_id text,
  add column if not exists space_id uuid,
  add column if not exists owner_user_id text,
  add column if not exists doc_id text,
  add column if not exists version int,
  add column if not exists visibility text,
  add column if not exists metadata jsonb,
  add column if not exists created_at timestamptz,
  add column if not exists updated_at timestamptz;

alter table if exists collab_file_acl
  add column if not exists tenant_id text,
  add column if not exists file_id uuid,
  add column if not exists principal_type text,
  add column if not exists principal_id text,
  add column if not exists permission text,
  add column if not exists created_at timestamptz,
  add column if not exists updated_at timestamptz;

alter table if exists collab_transfers
  add column if not exists tenant_id text,
  add column if not exists sender_user_id text,
  add column if not exists receiver_user_id text,
  add column if not exists file_id uuid,
  add column if not exists message text,
  add column if not exists status text,
  add column if not exists created_at timestamptz,
  add column if not exists updated_at timestamptz;

alter table if exists tenant_pipeline_profiles
  add column if not exists rag_profile_json jsonb,
  add column if not exists llm_profile_json jsonb,
  add column if not exists rate_limits_json jsonb,
  add column if not exists updated_at timestamptz;

alter table if exists tenant_pipeline_quotas
  add column if not exists tenant_id text,
  add column if not exists user_id text,
  add column if not exists day date,
  add column if not exists rag_queries int,
  add column if not exists llm_tokens bigint,
  add column if not exists ingest_docs int,
  add column if not exists created_at timestamptz;

alter table if exists pipeline_jobs
  add column if not exists tenant_id text,
  add column if not exists user_id text,
  add column if not exists job_type text,
  add column if not exists priority int,
  add column if not exists status text,
  add column if not exists input_ref jsonb,
  add column if not exists output_ref jsonb,
  add column if not exists error text,
  add column if not exists created_at timestamptz,
  add column if not exists updated_at timestamptz,
  add column if not exists started_at timestamptz,
  add column if not exists finished_at timestamptz;

alter table if exists ai_brain_traces
  add column if not exists tenant_id text,
  add column if not exists case_id text,
  add column if not exists trace jsonb,
  add column if not exists created_at timestamptz;

-- ---------------------------------------------------------------------------
-- RPC functions required by current code
-- ---------------------------------------------------------------------------

DO $$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT n.nspname, p.proname, p.oid::regprocedure AS sig
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname IN ('match_embeddings', 'match_case_embeddings', 'feedback_summary')
  LOOP
    EXECUTE format('drop function if exists %s cascade', r.sig);
  END LOOP;
END $$;

drop function if exists match_embeddings(vector, float, integer);
create or replace function match_embeddings(
  query_embedding vector(384),
  match_threshold float default 0.5,
  match_count int default 10
)
returns table (
  id uuid,
  content text,
  metadata jsonb,
  similarity float
)
language sql
stable
as $$
  select
    e.id,
    e.content,
    e.metadata,
    1 - (e.embedding <=> query_embedding) as similarity
  from embeddings_finance e
  where e.embedding is not null
    and (1 - (e.embedding <=> query_embedding)) >= match_threshold
    and e.tenant_id = coalesce(current_setting('request.jwt.claim.tenant_id', true), e.tenant_id)
  order by e.embedding <=> query_embedding
  limit match_count
$$;

drop function if exists match_case_embeddings(vector, integer, jsonb);
create or replace function match_case_embeddings(
  query_embedding vector(384),
  match_count int default 10,
  filters jsonb default '{}'::jsonb
)
returns table (
  id uuid,
  case_id uuid,
  chunk_id text,
  content text,
  metadata jsonb,
  similarity float
)
language sql
stable
as $$
  select
    ce.id,
    ce.case_id,
    ce.chunk_id,
    ce.content,
    ce.metadata,
    1 - (ce.embedding <=> query_embedding) as similarity
  from case_embeddings ce
  where ce.embedding is not null
    and (
      (filters ? 'tenant_id') is false
      or ce.tenant_id = (filters->>'tenant_id')
    )
    and (
      (filters ? 'company') is false
      or lower(coalesce(ce.company, '')) = lower(filters->>'company')
    )
    and (
      (filters ? 'company_in') is false
      or exists (
        select 1
        from jsonb_array_elements_text(filters->'company_in') as c(name)
        where lower(coalesce(ce.company, '')) = lower(c.name)
      )
    )
    and (
      (filters ? 'industry') is false
      or lower(coalesce(ce.industry, '')) = lower(filters->>'industry')
    )
    and (
      (filters ? 'severity') is false
      or lower(coalesce(ce.severity, '')) = lower(filters->>'severity')
    )
    and (
      (filters ? 'period') is false
      or lower(coalesce(ce.period, '')) = lower(filters->>'period')
    )
  order by ce.embedding <=> query_embedding
  limit match_count
$$;

create or replace function hybrid_case_search(
  query_embedding vector(384),
  query_text text,
  filters jsonb default '{}'::jsonb,
  match_count int default 10
)
returns table (
  id uuid,
  case_id uuid,
  chunk_id text,
  content text,
  metadata jsonb,
  similarity float,
  source text
)
language sql
stable
as $$
  with vec as (
    select
      ce.id,
      ce.case_id,
      ce.chunk_id,
      ce.content,
      ce.metadata,
      (1 - (ce.embedding <=> query_embedding))::float as similarity,
      'vector'::text as source
    from case_embeddings ce
    where ce.embedding is not null
      and (
        (filters ? 'tenant_id') is false
        or ce.tenant_id = (filters->>'tenant_id')
      )
      and (
        (filters ? 'owner_user_id') is false
        or coalesce(filters->>'owner_user_id','') = ''
        or coalesce(ce.metadata->>'owner_user_id','') = (filters->>'owner_user_id')
      )
      and (
        (filters ? 'doc_ids') is false
        or jsonb_typeof(filters->'doc_ids') <> 'array'
        or coalesce(ce.metadata->>'doc_id','') = any (array(select jsonb_array_elements_text(filters->'doc_ids')))
      )
    order by ce.embedding <=> query_embedding
    limit greatest(match_count, 1)
  ),
  kw as (
    select
      ce.id,
      ce.case_id,
      ce.chunk_id,
      ce.content,
      ce.metadata,
      0.35::float as similarity,
      'keyword'::text as source
    from case_embeddings ce
    where coalesce(query_text, '') <> ''
      and ce.content ilike ('%' || query_text || '%')
      and (
        (filters ? 'tenant_id') is false
        or ce.tenant_id = (filters->>'tenant_id')
      )
      and (
        (filters ? 'owner_user_id') is false
        or coalesce(filters->>'owner_user_id','') = ''
        or coalesce(ce.metadata->>'owner_user_id','') = (filters->>'owner_user_id')
      )
      and (
        (filters ? 'doc_ids') is false
        or jsonb_typeof(filters->'doc_ids') <> 'array'
        or coalesce(ce.metadata->>'doc_id','') = any (array(select jsonb_array_elements_text(filters->'doc_ids')))
      )
    order by ce.created_at desc
    limit greatest(match_count, 1)
  ),
  merged as (
    select * from vec
    union all
    select * from kw
  )
  select
    m.id,
    m.case_id,
    m.chunk_id,
    m.content,
    m.metadata,
    max(m.similarity)::float as similarity,
    min(m.source)::text as source
  from merged m
  group by m.id, m.case_id, m.chunk_id, m.content, m.metadata
  order by similarity desc
  limit greatest(match_count, 1)
$$;

-- ---------------------------------------------------------------------------
-- Console / Model Registry / Run Logs
-- ---------------------------------------------------------------------------
create table if not exists model_registry (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  provider text not null,
  base_url text,
  model text not null,
  purpose text default 'llm',
  is_default boolean default false,
  metadata jsonb default '{}'::jsonb,
  tenant_id text default coalesce(current_setting('request.jwt.claim.tenant_id', true), 'public'),
  created_at timestamptz default now()
);

create index if not exists model_registry_tenant_id_idx on model_registry(tenant_id);

create table if not exists llm_runs (
  id uuid primary key default gen_random_uuid(),
  user_id text,
  model_id uuid,
  model_name text,
  prompt text,
  response jsonb,
  tokens integer,
  latency_ms integer,
  status text default 'completed',
  metadata jsonb default '{}'::jsonb,
  tenant_id text default coalesce(current_setting('request.jwt.claim.tenant_id', true), 'public'),
  created_at timestamptz default now()
);

create index if not exists llm_runs_tenant_id_idx on llm_runs(tenant_id);

create table if not exists rag_runs (
  id uuid primary key default gen_random_uuid(),
  user_id text,
  query text,
  response jsonb,
  metrics jsonb default '{}'::jsonb,
  status text default 'completed',
  metadata jsonb default '{}'::jsonb,
  tenant_id text default coalesce(current_setting('request.jwt.claim.tenant_id', true), 'public'),
  created_at timestamptz default now()
);

create index if not exists rag_runs_tenant_id_idx on rag_runs(tenant_id);

create table if not exists rag_run_chunks (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references rag_runs(id) on delete cascade,
  chunk_id text,
  similarity numeric,
  metadata jsonb default '{}'::jsonb,
  tenant_id text default coalesce(current_setting('request.jwt.claim.tenant_id', true), 'public'),
  created_at timestamptz default now()
);

create index if not exists rag_run_chunks_tenant_id_idx on rag_run_chunks(tenant_id);
create index if not exists rag_run_chunks_run_id_idx on rag_run_chunks(run_id);

-- ---------------------------------------------------------------------------
-- Lakehouse / MLOps / Governance
-- ---------------------------------------------------------------------------
create table if not exists lakehouse_jobs (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default coalesce(current_setting('request.jwt.claim.tenant_id', true), 'public'),
  job_type text not null,
  priority text default 'normal',
  status text default 'queued',
  payload jsonb default '{}'::jsonb,
  dispatch_backend text default 'local',
  requested_by text,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);
create index if not exists lakehouse_jobs_tenant_created_idx on lakehouse_jobs(tenant_id, created_at desc);

create table if not exists lakehouse_table_versions (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default coalesce(current_setting('request.jwt.claim.tenant_id', true), 'public'),
  layer text not null,
  table_name text not null,
  table_fqn text not null,
  delta_version text not null,
  operation text not null,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);
create index if not exists lakehouse_table_versions_tenant_fqn_idx on lakehouse_table_versions(tenant_id, table_fqn, created_at desc);

create table if not exists dataset_mlflow_links (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default coalesce(current_setting('request.jwt.claim.tenant_id', true), 'public'),
  dataset_version_id uuid,
  mlflow_run_id text not null,
  model_name text,
  params jsonb default '{}'::jsonb,
  metrics jsonb default '{}'::jsonb,
  artifacts jsonb default '{}'::jsonb,
  status text default 'started',
  source text default 'stub',
  requested_by text,
  created_at timestamptz default now()
);
create index if not exists dataset_mlflow_links_tenant_created_idx on dataset_mlflow_links(tenant_id, created_at desc);
create index if not exists dataset_mlflow_links_run_idx on dataset_mlflow_links(mlflow_run_id);

create table if not exists governance_policies (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default coalesce(current_setting('request.jwt.claim.tenant_id', true), 'public'),
  domain text not null,
  principal text not null,
  role text not null,
  effect text default 'allow',
  rules jsonb default '{}'::jsonb,
  source text default 'db_only',
  requested_by text,
  created_at timestamptz default now()
);
create index if not exists governance_policies_tenant_domain_idx on governance_policies(tenant_id, domain, created_at desc);

create table if not exists governance_lineage_events (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null default coalesce(current_setting('request.jwt.claim.tenant_id', true), 'public'),
  source_type text not null,
  source_ref text not null,
  target_type text not null,
  target_ref text not null,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz default now()
);
create index if not exists governance_lineage_events_tenant_created_idx on governance_lineage_events(tenant_id, created_at desc);

drop function if exists feedback_summary(text);
create or replace function feedback_summary(case_id_in text)
returns table (
  total_feedback bigint,
  avg_score numeric,
  positives bigint,
  negatives bigint
)
language sql
stable
as $$
  select
    count(*)::bigint as total_feedback,
    avg(score)::numeric as avg_score,
    count(*) filter (where score >= 0.5)::bigint as positives,
    count(*) filter (where score < 0.5)::bigint as negatives
  from evidence_feedback
  where evidence_feedback.case_id::text = case_id_in
    and evidence_feedback.tenant_id = coalesce(current_setting('request.jwt.claim.tenant_id', true), evidence_feedback.tenant_id)
$$;

-- ---------------------------------------------------------------------------
-- Seed defaults (safe upsert/insert)
-- ---------------------------------------------------------------------------
insert into prompt_templates (template_type, version, prompt, is_active, metadata)
select 'summary', 'v1', 'Summarize key financial risks and evidence in JSON.', true, '{}'::jsonb
where not exists (
  select 1 from prompt_templates where template_type='summary' and is_active=true
);

insert into prompt_templates (template_type, version, prompt, is_active, metadata)
select 'risk_analysis', 'v1', 'Produce risk analysis with cause/effect chain and confidence in JSON.', true, '{}'::jsonb
where not exists (
  select 1 from prompt_templates where template_type='risk_analysis' and is_active=true
);

-- ---------------------------------------------------------------------------
-- Done
-- ---------------------------------------------------------------------------
select 'preciso supabase all-in-one bootstrap completed' as status;
