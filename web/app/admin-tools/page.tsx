"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";

const API_BASE = "/api/proxy";

type HttpMethod = "GET" | "POST" | "PATCH" | "DELETE";

const ENDPOINTS = [
  { label: "Approvals List", method: "GET", path: "/api/v1/approval/cases?limit=50" },
  { label: "Approval Detail", method: "GET", path: "/api/v1/approval/cases/{case_id}" },
  { label: "Export Case", method: "POST", path: "/api/v1/export/case" },
  { label: "Metrics Recent", method: "GET", path: "/api/v1/metrics/recent?limit=50" },
  { label: "Quality Gate Metrics", method: "GET", path: "/api/v1/metrics/quality?limit=500" },
  { label: "Market Quote", method: "GET", path: "/api/v1/market/quote?symbol=AAPL&ingest=false" },
  { label: "FMP Growth", method: "GET", path: "/api/v1/market/fmp/growth?symbol=AAPL&ingest=false" },
  { label: "SEC Filings", method: "GET", path: "/api/v1/market/sec/filings?symbol=AAPL&form_type=10-Q&limit=3&ingest=false" },
  { label: "Policy List", method: "GET", path: "/api/v1/policy/list" },
  { label: "License Status", method: "GET", path: "/api/v1/license/status" },
  { label: "Retention Jobs", method: "GET", path: "/api/v1/admin/retention/jobs" },
  { label: "Feedback Submit", method: "POST", path: "/api/v1/feedback/submit" },
  { label: "Extract (File URL)", method: "POST", path: "/api/v1/extract/url" },
  { label: "Generate (Template)", method: "POST", path: "/api/v1/generate" },
  { label: "Retrieval Test", method: "POST", path: "/api/v1/retrieval/query" },
  { label: "Multi-Agent Run", method: "POST", path: "/api/v1/multi-agent/run" },
  { label: "Datasets List", method: "GET", path: "/api/v1/datasets/list" },
];

export default function AdminToolsPage() {
  const [tenantId, setTenantId] = useState("public");
  const [userId, setUserId] = useState("admin");
  const [role, setRole] = useState("admin");
  const [adminToken, setAdminToken] = useState("");
  const [method, setMethod] = useState<HttpMethod>("GET");
  const [path, setPath] = useState("/api/v1/metrics/recent?limit=50");
  const [body, setBody] = useState('{"limit":50}');
  const [result, setResult] = useState<string>("Ready.");
  const [error, setError] = useState<string | null>(null);

  const headers = useMemo(
    () => ({
      "Content-Type": "application/json",
      "X-Tenant-Id": tenantId,
      "X-Preciso-User-Id": userId,
      "X-Preciso-User-Role": role,
      ...(adminToken ? { "X-Admin-Token": adminToken } : {}),
    }),
    [tenantId, userId, role, adminToken]
  );

  const run = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        method,
        headers,
        body: method === "GET" || method === "DELETE" ? undefined : body,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setResult(JSON.stringify(data, null, 2));
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setResult(JSON.stringify({ error: msg }, null, 2));
    }
  };

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <div className="mx-auto max-w-7xl px-6 py-8 space-y-6">
        <header className="rounded-xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold">Admin Tools</h1>
              <p className="text-sm text-neutral-400 mt-1">
                모든 API 기능을 웹에서 실행하기 위한 범용 콘솔입니다.
              </p>
            </div>
            <Link href="/ops-console" className="text-xs text-neutral-300 underline">Back to Ops</Link>
          </div>
        </header>

        <section className="rounded-xl border border-white/10 bg-white/5 p-4 grid grid-cols-1 md:grid-cols-5 gap-3">
          <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={tenantId} onChange={(e) => setTenantId(e.target.value)} placeholder="X-Tenant-Id" />
          <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={userId} onChange={(e) => setUserId(e.target.value)} placeholder="X-Preciso-User-Id" />
          <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={role} onChange={(e) => setRole(e.target.value)} placeholder="X-Preciso-User-Role" />
          <input className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={adminToken} onChange={(e) => setAdminToken(e.target.value)} placeholder="X-Admin-Token (optional)" />
          <button className="px-3 py-2 rounded bg-white/10 border border-white/20 text-xs hover:bg-white/20" onClick={run}>
            Run
          </button>
        </section>

        <section className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6">
          <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <div className="text-xs text-neutral-400 uppercase tracking-[0.2em]">Presets</div>
            <div className="space-y-2">
              {ENDPOINTS.map((ep) => (
                <button
                  key={ep.label}
                  className="w-full text-left px-3 py-2 rounded bg-black/40 border border-white/10 text-xs hover:bg-white/10"
                  onClick={() => {
                    setMethod(ep.method as HttpMethod);
                    setPath(ep.path);
                  }}
                >
                  <div className="text-neutral-200 font-semibold">{ep.label}</div>
                  <div className="text-[11px] text-neutral-500">{ep.method} {ep.path}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-6 gap-2">
              <select className="bg-black/40 border border-white/10 rounded p-2 text-xs" value={method} onChange={(e) => setMethod(e.target.value as HttpMethod)}>
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PATCH">PATCH</option>
                <option value="DELETE">DELETE</option>
              </select>
              <input className="md:col-span-5 bg-black/40 border border-white/10 rounded p-2 text-xs font-mono" value={path} onChange={(e) => setPath(e.target.value)} />
            </div>
            <textarea
              className="w-full h-40 bg-black/40 border border-white/10 rounded p-3 text-xs font-mono"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
            {error && <div className="text-xs text-rose-300">{error}</div>}
            <pre className="text-[11px] bg-black/40 p-3 rounded overflow-auto max-h-96">{result}</pre>
          </div>
        </section>
      </div>
    </div>
  );
}
