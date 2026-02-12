"use client";

import React, { useState } from "react";
import Link from "next/link";
import { BackgroundBeams } from "@/components/ui/background-beams";
import type { JsonRecord } from "@/lib/types";

const API_BASE = "/api/proxy";

export default function GovernancePage() {
  const [domain, setDomain] = useState("fundamental");
  const [principal, setPrincipal] = useState("finance-team");
  const [role, setRole] = useState("analyst");
  const [policies, setPolicies] = useState<JsonRecord[]>([]);
  const [lineage, setLineage] = useState<JsonRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      const [pRes, lRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/governance/policies`),
        fetch(`${API_BASE}/api/v1/governance/lineage`),
      ]);
      const pData = await pRes.json();
      const lData = await lRes.json();
      if (!pRes.ok) throw new Error(pData?.detail || "policies failed");
      if (!lRes.ok) throw new Error(lData?.detail || "lineage failed");
      setPolicies(pData.policies || []);
      setLineage(lData.events || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "load failed");
    }
  };

  const apply = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/governance/policies/apply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain, principal, role, effect: "allow", rules: { default_deny: true } }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "apply failed");
      load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "apply failed");
    }
  };

  return (
    <main className="relative min-h-screen overflow-hidden">
      <BackgroundBeams className="z-0" />
      <div className="relative z-10 mx-auto w-full max-w-6xl px-6 py-10 text-white">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-3xl font-semibold">Governance (Unity Catalog)</h1>
          <Link href="/" className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs">Back</Link>
        </div>
        <div className="rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Policies + Lineage</div>
          <div className="grid gap-2 md:grid-cols-3">
            <input value={domain} onChange={(e) => setDomain(e.target.value)} className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs" />
            <input value={principal} onChange={(e) => setPrincipal(e.target.value)} className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs" />
            <input value={role} onChange={(e) => setRole(e.target.value)} className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs" />
          </div>
          <div className="mt-3 flex gap-2">
            <button onClick={apply} className="rounded-full bg-emerald-400/20 px-3 py-1 text-xs ring-1 ring-emerald-400/40">Apply Policy</button>
            <button onClick={load} className="rounded-full bg-cyan-400/20 px-3 py-1 text-xs ring-1 ring-cyan-400/40">Reload</button>
          </div>
          {error && <div className="mt-3 text-xs text-rose-300">{error}</div>}
          <pre className="mt-4 max-h-64 overflow-auto rounded-md border border-white/10 bg-black/50 p-3 text-[11px] text-slate-200">
{JSON.stringify({ policies, lineage }, null, 2)}
          </pre>
        </div>
      </div>
    </main>
  );
}
