"use client";

import React, { useState } from "react";
import Link from "next/link";
import { BackgroundBeams } from "@/components/ui/background-beams";
import type { JsonRecord } from "@/lib/types";

const API_BASE = "/api/proxy";

export default function LakehousePage() {
  const [layer, setLayer] = useState("silver");
  const [table, setTable] = useState("fin_facts");
  const [history, setHistory] = useState<JsonRecord[]>([]);
  const [queryResult, setQueryResult] = useState<JsonRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadHistory = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/lakehouse/tables/${layer}/${table}/history`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "history failed");
      setHistory(data.history || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "history failed");
    }
  };

  const runTimeTravel = async () => {
    setError(null);
    try {
      const delta_version = history?.[0]?.delta_version || null;
      const res = await fetch(`${API_BASE}/api/v1/lakehouse/tables/${layer}/${table}/time-travel-query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ delta_version, limit: 20 }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "time travel failed");
      setQueryResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "time travel failed");
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden">
      <BackgroundBeams className="z-0" />
      <div className="relative z-10 mx-auto w-full max-w-6xl px-6 py-10 text-white">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-3xl font-semibold">Lakehouse Console</h1>
          <Link href="/" className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs">Back</Link>
        </div>
        <div className="rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Delta Table History + Time Travel</div>
          <div className="grid gap-3 md:grid-cols-3">
            <input value={layer} onChange={(e) => setLayer(e.target.value)} className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs" />
            <input value={table} onChange={(e) => setTable(e.target.value)} className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs" />
            <div className="flex gap-2">
              <button onClick={loadHistory} className="rounded-full bg-cyan-400/20 px-3 py-1 text-xs ring-1 ring-cyan-400/40">Load History</button>
              <button onClick={runTimeTravel} className="rounded-full bg-emerald-400/20 px-3 py-1 text-xs ring-1 ring-emerald-400/40">Time Travel</button>
            </div>
          </div>
          {error && <div className="mt-3 text-xs text-rose-300">{error}</div>}
          <pre className="mt-4 max-h-64 overflow-auto rounded-md border border-white/10 bg-black/50 p-3 text-[11px] text-slate-200">
{JSON.stringify({ history, queryResult }, null, 2)}
          </pre>
        </div>
      </div>
    </main>
  );
}
