"use client";

import React, { useEffect, useState } from "react";
import type { JsonRecord } from "@/lib/types";

const API_BASE = "/api/proxy";

type Check = { key: string; ok: boolean; severity: string; message: string; fix: string };
type StatusResponse = {
  checks?: Check[];
  blockers?: Check[];
  warnings?: Check[];
  [key: string]: unknown;
};

export default function SetupWizardPage() {
  const [mode, setMode] = useState<"cloud" | "onprem" | "hybrid">("cloud");
  const [adminToken, setAdminToken] = useState("");
  const [supabaseUrl, setSupabaseUrl] = useState("");
  const [supabaseKey, setSupabaseKey] = useState("");
  const [dbUrl, setDbUrl] = useState("");
  const [redisUrl, setRedisUrl] = useState("");
  const [publicDomain, setPublicDomain] = useState("");
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [statusErr, setStatusErr] = useState<string | null>(null);
  const [validateOut, setValidateOut] = useState<JsonRecord | null>(null);
  const [validateErr, setValidateErr] = useState<string | null>(null);
  const [pipelineOut, setPipelineOut] = useState<JsonRecord | null>(null);
  const [pipelineErr, setPipelineErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    setAdminToken("");
  }, []);

  const adminHeaders = {
    "Content-Type": "application/json",
    ...(adminToken ? { "X-Admin-Token": adminToken } : {}),
    "X-Preciso-User-Role": "admin",
    "X-Preciso-User-Id": "setup",
  };

  const runStatus = async () => {
    setStatusErr(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/status`);
      const data = await res.json();
      setStatus((data || null) as StatusResponse | null);
    } catch (e: unknown) {
      setStatusErr(e instanceof Error ? e.message : String(e));
    }
  };

  const runValidate = async () => {
    setValidateErr(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/connectivity/validate`, {
        method: "POST",
        headers: adminHeaders,
        body: JSON.stringify({
          supabase_url: supabaseUrl || undefined,
          supabase_service_role_key: supabaseKey || undefined,
          db_url: dbUrl || undefined,
          redis_url: redisUrl || undefined,
          http_url: API_BASE || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setValidateOut(data);
    } catch (e: unknown) {
      setValidateErr(e instanceof Error ? e.message : String(e));
    }
  };

  const runPipelineStatus = async () => {
    setPipelineErr(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/pipeline/tenant-status`, {
        headers: adminHeaders,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setPipelineOut(data);
    } catch (e: unknown) {
      setPipelineErr(e instanceof Error ? e.message : String(e));
    }
  };

  const checks: Check[] = status?.checks || [];
  const dbBackend =
    mode === "onprem" ? "postgres" : mode === "cloud" ? "supabase" : "supabase";

  const envSnippet = [
    "APP_ENV=prod",
    "RBAC_ENFORCED=1",
    "TENANT_HEADER_REQUIRED=1",
    `PUBLIC_DOMAIN=${publicDomain || "your-domain.com"}`,
    `REDIS_URL=${redisUrl || "redis://redis:6379"}`,
    `DB_BACKEND=${dbBackend}`,
    dbBackend === "supabase" ? `SUPABASE_URL=${supabaseUrl || "https://your-project.supabase.co"}` : "",
    dbBackend === "supabase" ? `SUPABASE_SERVICE_ROLE_KEY=${supabaseKey || "YOUR_SERVICE_ROLE_KEY"}` : "",
    dbBackend === "postgres" ? `DATABASE_URL=${dbUrl || "postgresql://user:pass@host:5432/preciso"}` : "",
    adminToken ? `ADMIN_API_TOKEN=${adminToken}` : "ADMIN_API_TOKEN=",
  ]
    .filter(Boolean)
    .join("\n");

  const copySnippet = async () => {
    try {
      await navigator.clipboard.writeText(envSnippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <div className="max-w-5xl mx-auto px-6 py-10 space-y-8">
        <header>
          <h1 className="text-2xl font-semibold">Setup Wizard</h1>
          <p className="text-sm text-neutral-400">
            30분 내 온보딩: 배포 모드 → 연결 → Preflight → 스키마 → 샘플 → Spokes → 승인 → Export
          </p>
        </header>

        <section className="rounded-xl border border-white/10 bg-white/5 p-5 space-y-3">
          <h2 className="text-lg font-semibold">Step 1. Deployment Mode</h2>
          <div className="flex flex-wrap gap-2">
            {[
              { key: "cloud", label: "Cloud (Supabase)" },
              { key: "onprem", label: "On-prem (Postgres)" },
              { key: "hybrid", label: "Hybrid" },
            ].map((m) => (
              <button
                key={m.key}
                onClick={() => setMode(m.key as "cloud" | "onprem" | "hybrid")}
                className={`px-3 py-2 rounded-lg border text-sm ${
                  mode === m.key
                    ? "border-emerald-500/50 bg-emerald-500/10"
                    : "border-white/10 bg-white/5"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-white/10 bg-white/5 p-5 space-y-4">
          <h2 className="text-lg font-semibold">Step 2. Connection Inputs</h2>
          <p className="text-xs text-neutral-400">
            Secrets are not stored in the browser. Use env snippets for production.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <input
              className="bg-black/40 border border-white/10 rounded-lg p-2 text-xs"
              placeholder="ADMIN_API_TOKEN (optional)"
              value={adminToken}
              onChange={(e) => setAdminToken(e.target.value)}
            />
            <input
              className="bg-black/40 border border-white/10 rounded-lg p-2 text-xs"
              placeholder="PUBLIC_DOMAIN"
              value={publicDomain}
              onChange={(e) => setPublicDomain(e.target.value)}
            />
            <input
              className="bg-black/40 border border-white/10 rounded-lg p-2 text-xs"
              placeholder="SUPABASE_URL"
              value={supabaseUrl}
              onChange={(e) => setSupabaseUrl(e.target.value)}
            />
            <input
              className="bg-black/40 border border-white/10 rounded-lg p-2 text-xs"
              placeholder="SUPABASE_SERVICE_ROLE_KEY"
              value={supabaseKey}
              onChange={(e) => setSupabaseKey(e.target.value)}
            />
            <input
              className="bg-black/40 border border-white/10 rounded-lg p-2 text-xs"
              placeholder="DATABASE_URL (Postgres)"
              value={dbUrl}
              onChange={(e) => setDbUrl(e.target.value)}
            />
            <input
              className="bg-black/40 border border-white/10 rounded-lg p-2 text-xs"
              placeholder="REDIS_URL"
              value={redisUrl}
              onChange={(e) => setRedisUrl(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-neutral-400">Generated .env snippet</span>
              <button
                onClick={copySnippet}
                className="px-2 py-1 rounded-md border border-white/10 bg-white/10 text-xs"
              >
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <pre className="text-xs text-neutral-300 bg-black/40 p-3 rounded-lg overflow-auto">
{envSnippet}
            </pre>
          </div>
        </section>

        <section className="rounded-xl border border-white/10 bg-white/5 p-5 space-y-3">
          <h2 className="text-lg font-semibold">Step 3. Preflight</h2>
          <div className="flex gap-2">
            <button
              onClick={runStatus}
              className="px-3 py-2 rounded-lg bg-white/10 border border-white/10 text-sm"
            >
              Check /api/v1/status
            </button>
            <button
              onClick={runValidate}
              className="px-3 py-2 rounded-lg bg-emerald-500/20 border border-emerald-500/30 text-sm"
            >
              Validate Connectivity
            </button>
          </div>
          {statusErr && <div className="text-sm text-red-400">{statusErr}</div>}
          {status && (
            <div className="text-xs text-neutral-300 space-y-1">
              <div>Blockers: {status.blockers?.length || 0}</div>
              <div>Warnings: {status.warnings?.length || 0}</div>
            </div>
          )}
          {checks.length > 0 && (
            <div className="mt-2 space-y-1 text-xs">
              {checks.map((c) => (
                <div key={c.key} className="flex items-start gap-2">
                  <span className={c.ok ? "text-emerald-400" : "text-amber-400"}>
                    {c.ok ? "OK" : "WARN"}
                  </span>
                  <span className="text-neutral-300">{c.message}</span>
                  {!c.ok && <span className="text-neutral-500">Fix: {c.fix}</span>}
                </div>
              ))}
            </div>
          )}
          {validateErr && <div className="text-sm text-red-400">{validateErr}</div>}
          {validateOut && (
            <pre className="text-xs text-neutral-300 bg-black/40 p-3 rounded-lg overflow-auto">
{JSON.stringify(validateOut, null, 2)}
            </pre>
          )}
        </section>

        <section className="rounded-xl border border-white/10 bg-white/5 p-5 space-y-2">
          <h2 className="text-lg font-semibold">Step 4. Schema Apply</h2>
          <p className="text-xs text-neutral-400">
            Apply SQL: `supabase_bootstrap_preciso.sql`, `supabase_spokes.sql`, `supabase_rbac.sql`,
            `supabase_partner_registry.sql`, `supabase_integration_secrets.sql`,
            `supabase_enterprise_collab.sql`.
          </p>
        </section>

        <section className="rounded-xl border border-white/10 bg-white/5 p-5 space-y-2">
          <h2 className="text-lg font-semibold">Step 5. Sample Ingest</h2>
          <p className="text-xs text-neutral-400">
            Upload a document or call `/api/v1/partners/financials` to generate spokes.
          </p>
        </section>

        <section className="rounded-xl border border-white/10 bg-white/5 p-5 space-y-2">
          <h2 className="text-lg font-semibold">Step 6–8. Spokes → Approval → Export</h2>
          <p className="text-xs text-neutral-400">
            Verify Spokes A/B/C/D, approve once, then export case bundle.
          </p>
          <div className="pt-2">
            <button
              onClick={runPipelineStatus}
              className="px-3 py-2 rounded-lg bg-fuchsia-500/20 border border-fuchsia-500/30 text-sm"
            >
              Check Tenant Pipeline Status
            </button>
          </div>
          {pipelineErr && <div className="text-sm text-red-400">{pipelineErr}</div>}
          {pipelineOut && (
            <pre className="text-xs text-neutral-300 bg-black/40 p-3 rounded-lg overflow-auto">
{JSON.stringify(pipelineOut, null, 2)}
            </pre>
          )}
        </section>
      </div>
    </div>
  );
}
