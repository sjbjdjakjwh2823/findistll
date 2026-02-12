-- Preciso RLS Policies (tenant isolation)
-- Requires Supabase auth JWT with tenant_id claim.

-- Helper function
CREATE OR REPLACE FUNCTION public.current_tenant_id()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT COALESCE(
    nullif(current_setting('request.jwt.claims', true), '')::jsonb->>'tenant_id',
    'public'
  );
$$;

-- Enable RLS
ALTER TABLE IF EXISTS public.cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.case_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS public.audit_events ENABLE ROW LEVEL SECURITY;

-- Policies (tenant match)
DROP POLICY IF EXISTS tenant_isolation_cases ON public.cases;
CREATE POLICY tenant_isolation_cases
ON public.cases
USING (tenant_id = public.current_tenant_id())
WITH CHECK (tenant_id = public.current_tenant_id());

DROP POLICY IF EXISTS tenant_isolation_documents ON public.documents;
CREATE POLICY tenant_isolation_documents
ON public.documents
USING (tenant_id = public.current_tenant_id())
WITH CHECK (tenant_id = public.current_tenant_id());

DROP POLICY IF EXISTS tenant_isolation_case_embeddings ON public.case_embeddings;
CREATE POLICY tenant_isolation_case_embeddings
ON public.case_embeddings
USING (tenant_id = public.current_tenant_id())
WITH CHECK (tenant_id = public.current_tenant_id());

DROP POLICY IF EXISTS tenant_isolation_audit_logs ON public.audit_logs;
CREATE POLICY tenant_isolation_audit_logs
ON public.audit_logs
USING (tenant_id = public.current_tenant_id())
WITH CHECK (tenant_id = public.current_tenant_id());

DROP POLICY IF EXISTS tenant_isolation_audit_events ON public.audit_events;
CREATE POLICY tenant_isolation_audit_events
ON public.audit_events
USING (tenant_id = public.current_tenant_id())
WITH CHECK (tenant_id = public.current_tenant_id());
