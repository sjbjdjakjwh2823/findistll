"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { BackgroundBeams } from "@/components/ui/background-beams";

const API_BASE = "/api/proxy";

type LogRow = Record<string, unknown>;

const PIPELINE_ACTIONS: Record<string, string> = {
  ingest: "ingest",
  approval: "approval",
  training: "training",
  rag: "rag",
  lakehouse: "lakehouse",
  collab: "collab",
  partners: "partner",
  quality: "quality_gate",
};

export default function LogsPage() {
  const [adminToken, setAdminToken] = useState("");
  const [pipeline, setPipeline] = useState("ingest");
  const [tenantId, setTenantId] = useState("public");
  const [actorId, setActorId] = useState("");
  const [limit, setLimit] = useState(200);
  const [logs, setLogs] = useState<LogRow[]>([]);
  const [logErr, setLogErr] = useState<string | null>(null);

  const [service, setService] = useState<"backend" | "worker" | "event_worker">("backend");
  const [contains, setContains] = useState("");
  const [tail, setTail] = useState<string[]>([]);
  const [tailErr, setTailErr] = useState<string | null>(null);

  const adminHeaders = useMemo(
    () => ({
      "Content-Type": "application/json",
      ...(adminToken ? { "X-Admin-Token": adminToken } : {}),
      "X-Preciso-User-Role": "admin",
      "X-Preciso-User-Id": "logs",
    }),
    [adminToken]
  );

  const loadPipelineLogs = async () => {
    setLogErr(null);
    try {
      const params = new URLSearchParams();
      params.set("limit", String(limit));
      if (tenantId) params.set("tenant_id", tenantId);
      if (actorId) params.set("actor_id", actorId);
      const action = PIPELINE_ACTIONS[pipeline] || pipeline;
      if (action) params.set("action", action);
      const res = await fetch(`${API_BASE}/api/v1/admin/logs/tenant?${params.toString()}`, {
        headers: adminHeaders,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "failed to load logs");
      setLogs(data.items || []);
    } catch (e: unknown) {
      setLogErr(e instanceof Error ? e.message : "failed to load logs");
    }
  };

  const loadTail = async () => {
    setTailErr(null);
    try {
      const params = new URLSearchParams();
      params.set("lines", "300");
      params.set("service", service);
      if (contains) params.set("contains", contains);
      const res = await fetch(`${API_BASE}/api/v1/admin/logs/tail?${params.toString()}`, {
        headers: adminHeaders,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "failed to fetch tail");
      setTail(data.items || []);
    } catch (e: unknown) {
      setTailErr(e instanceof Error ? e.message : "failed to fetch tail");
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden">
      <BackgroundBeams className="z-0" />
      <div className="relative z-10 mx-auto w-full max-w-6xl px-6 py-10 text-white">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-3xl font-semibold">Pipeline Logs</h1>
          <Link href="/" className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs">
            Back
          </Link>
        </div>

        <div className="rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Admin Token (required)</div>
          <input
            className="w-full rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
            value={adminToken}
            onChange={(e) => setAdminToken(e.target.value)}
            placeholder="X-Admin-Token"
          />
        </div>

        <div className="mt-6 rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Pipeline Audit Logs</div>
          <div className="grid gap-2 md:grid-cols-4">
            <select
              value={pipeline}
              onChange={(e) => setPipeline(e.target.value)}
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
            >
              {Object.keys(PIPELINE_ACTIONS).map((key) => (
                <option key={key} value={key}>
                  {key}
                </option>
              ))}
            </select>
            <input
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              placeholder="tenant_id"
            />
            <input
              value={actorId}
              onChange={(e) => setActorId(e.target.value)}
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              placeholder="actor_id (optional)"
            />
            <input
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value || 200))}
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              placeholder="limit"
            />
          </div>
          <div className="mt-3">
            <button
              onClick={loadPipelineLogs}
              className="rounded-full bg-cyan-400/20 px-3 py-1 text-xs ring-1 ring-cyan-400/40"
            >
              Load Logs
            </button>
          </div>
          {logErr && <div className="mt-3 text-xs text-rose-300">{logErr}</div>}
          <pre className="mt-3 max-h-[320px] overflow-auto rounded-md border border-white/10 bg-black/60 p-3 text-[11px] text-slate-200">
{JSON.stringify(logs, null, 2)}
          </pre>
        </div>

        <div className="mt-6 rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Service Log Tail</div>
          <div className="grid gap-2 md:grid-cols-3">
            <select
              value={service}
              onChange={(e) => setService(e.target.value as "backend" | "worker" | "event_worker")}
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
            >
              <option value="backend">backend</option>
              <option value="worker">worker</option>
              <option value="event_worker">event_worker</option>
            </select>
            <input
              value={contains}
              onChange={(e) => setContains(e.target.value)}
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              placeholder="contains filter"
            />
          </div>
          <div className="mt-3">
            <button
              onClick={loadTail}
              className="rounded-full bg-emerald-400/20 px-3 py-1 text-xs ring-1 ring-emerald-400/40"
            >
              Tail Logs
            </button>
          </div>
          {tailErr && <div className="mt-3 text-xs text-rose-300">{tailErr}</div>}
          <pre className="mt-3 max-h-[320px] overflow-auto rounded-md border border-white/10 bg-black/60 p-3 text-[11px] text-slate-200">
{tail.join("\n")}
          </pre>
        </div>
      </div>
    </main>
  );
}
