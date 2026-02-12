-- Preciso Supabase Migration (Safe / Idempotent)
-- Purpose:
-- 1) Align collaboration tables to use TEXT user ids (web NextAuth / header ids) instead of UUID.
-- 2) Add missing columns/indexes that code assumes exist.
--
-- Apply once per project (Supabase SQL editor). Safe to re-run.

do $$
declare
  ctype text;
begin
  -- Helper: convert a column to TEXT if it is UUID.
  -- Note: Postgres doesn't support "ALTER COLUMN IF EXISTS", so we guard via information_schema.

  -- collab_contacts
  select data_type into ctype from information_schema.columns
    where table_schema='public' and table_name='collab_contacts' and column_name='requester_user_id';
  if ctype = 'uuid' then
    execute 'alter table public.collab_contacts alter column requester_user_id type text using requester_user_id::text';
  end if;
  select data_type into ctype from information_schema.columns
    where table_schema='public' and table_name='collab_contacts' and column_name='target_user_id';
  if ctype = 'uuid' then
    execute 'alter table public.collab_contacts alter column target_user_id type text using target_user_id::text';
  end if;

  -- collab_teams
  select data_type into ctype from information_schema.columns
    where table_schema='public' and table_name='collab_teams' and column_name='owner_user_id';
  if ctype = 'uuid' then
    execute 'alter table public.collab_teams alter column owner_user_id type text using owner_user_id::text';
  end if;

  -- collab_team_members
  select data_type into ctype from information_schema.columns
    where table_schema='public' and table_name='collab_team_members' and column_name='user_id';
  if ctype = 'uuid' then
    execute 'alter table public.collab_team_members alter column user_id type text using user_id::text';
  end if;

  -- collab_spaces
  select data_type into ctype from information_schema.columns
    where table_schema='public' and table_name='collab_spaces' and column_name='owner_user_id';
  if ctype = 'uuid' then
    execute 'alter table public.collab_spaces alter column owner_user_id type text using owner_user_id::text';
  end if;

  -- collab_files
  select data_type into ctype from information_schema.columns
    where table_schema='public' and table_name='collab_files' and column_name='owner_user_id';
  if ctype = 'uuid' then
    execute 'alter table public.collab_files alter column owner_user_id type text using owner_user_id::text';
  end if;

  -- collab_file_acl (principal_id can be either user_id or team_id; keep TEXT)
  select data_type into ctype from information_schema.columns
    where table_schema='public' and table_name='collab_file_acl' and column_name='principal_id';
  if ctype = 'uuid' then
    execute 'alter table public.collab_file_acl alter column principal_id type text using principal_id::text';
  end if;

  -- collab_transfers
  select data_type into ctype from information_schema.columns
    where table_schema='public' and table_name='collab_transfers' and column_name='sender_user_id';
  if ctype = 'uuid' then
    execute 'alter table public.collab_transfers alter column sender_user_id type text using sender_user_id::text';
  end if;
  select data_type into ctype from information_schema.columns
    where table_schema='public' and table_name='collab_transfers' and column_name='receiver_user_id';
  if ctype = 'uuid' then
    execute 'alter table public.collab_transfers alter column receiver_user_id type text using receiver_user_id::text';
  end if;

  -- collab_invites
  if exists (select 1 from information_schema.tables where table_schema='public' and table_name='collab_invites') then
    select data_type into ctype from information_schema.columns
      where table_schema='public' and table_name='collab_invites' and column_name='created_by_user_id';
    if ctype = 'uuid' then
      execute 'alter table public.collab_invites alter column created_by_user_id type text using created_by_user_id::text';
    end if;
    select data_type into ctype from information_schema.columns
      where table_schema='public' and table_name='collab_invites' and column_name='accepted_by_user_id';
    if ctype = 'uuid' then
      execute 'alter table public.collab_invites alter column accepted_by_user_id type text using accepted_by_user_id::text';
    end if;
  end if;
end $$;

-- Ensure updated_at columns exist where code expects them (best-effort).
alter table public.collab_contacts add column if not exists updated_at timestamptz default now();
alter table public.collab_teams add column if not exists updated_at timestamptz default now();
alter table public.collab_team_members add column if not exists updated_at timestamptz default now();
alter table public.collab_spaces add column if not exists updated_at timestamptz default now();
alter table public.collab_files add column if not exists updated_at timestamptz default now();
alter table public.collab_file_acl add column if not exists updated_at timestamptz default now();
alter table public.collab_transfers add column if not exists updated_at timestamptz default now();
alter table public.collab_invites add column if not exists updated_at timestamptz default now();

-- Minimal indexes for tenant scoping performance.
create index if not exists idx_collab_contacts_tenant on public.collab_contacts(tenant_id);
create index if not exists idx_collab_teams_tenant on public.collab_teams(tenant_id);
create index if not exists idx_collab_team_members_tenant on public.collab_team_members(tenant_id);
create index if not exists idx_collab_spaces_tenant on public.collab_spaces(tenant_id);
create index if not exists idx_collab_files_tenant on public.collab_files(tenant_id);
create index if not exists idx_collab_file_acl_tenant on public.collab_file_acl(tenant_id);
create index if not exists idx_collab_transfers_tenant on public.collab_transfers(tenant_id);
create index if not exists idx_collab_invites_tenant on public.collab_invites(tenant_id);

-- Org directory for tenant role mapping (single role model).
create table if not exists public.org_users (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null,
  user_id text not null,
  email text,
  display_name text,
  role text not null default 'viewer',
  status text not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (tenant_id, user_id)
);
create index if not exists idx_org_users_tenant on public.org_users(tenant_id);
create index if not exists idx_org_users_user on public.org_users(tenant_id, user_id);
