"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { BackgroundBeams } from "@/components/ui/background-beams";

const API_BASE = "/api/proxy";

type OrgUser = {
  tenant_id: string;
  user_id: string;
  email?: string | null;
  display_name?: string | null;
  role: string;
  status: string;
};

export default function OrgPage() {
  const [tenantId, setTenantId] = useState("public");
  const [items, setItems] = useState<OrgUser[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const [userId, setUserId] = useState("");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("viewer");
  const [status, setStatus] = useState("active");

  const setTenant = async () => {
    setErr(null);
    await fetch("/api/tenant", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant_id: tenantId }),
    });
  };

  const load = async () => {
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/org/users?limit=200`);
      const data = (await res.json().catch(() => ({}))) as { items?: OrgUser[]; detail?: string };
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setItems(data.items || []);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "failed to load");
    }
  };

  const upsert = async () => {
    setErr(null);
    setMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/org/users`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: userId,
          email: email || null,
          display_name: displayName || null,
          role,
          status,
        }),
      });
      const data = (await res.json().catch(() => ({}))) as { detail?: string };
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setMsg("saved");
      await load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "failed to save");
    }
  };

  useEffect(() => {
    load();
  }, []);

  return (
    <main className="relative min-h-screen overflow-hidden">
      <BackgroundBeams className="z-0" />
      <div className="relative z-10 mx-auto w-full max-w-5xl px-6 py-10 text-white space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-semibold">Organization & Roles</h1>
          <Link href="/" className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs">
            Back
          </Link>
        </div>

        <div className="rounded-2xl border border-white/10 bg-black/40 p-6 space-y-3">
          <div className="text-xs text-slate-300">Tenant</div>
          <div className="flex gap-2">
            <input
              className="w-full rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              placeholder="public"
            />
            <button
              onClick={async () => {
                await setTenant();
                await load();
              }}
              className="rounded-full bg-white/10 px-3 py-2 text-xs text-white ring-1 ring-white/10"
            >
              Set
            </button>
            <button
              onClick={load}
              className="rounded-full bg-cyan-400/20 px-3 py-2 text-xs ring-1 ring-cyan-400/40"
            >
              Refresh
            </button>
          </div>
          <div className="text-[11px] text-slate-400">
            이 페이지는 admin만 사용합니다. 역할은 RAG/파일가시성/승인흐름 정책에 직접 연결됩니다.
          </div>
          {err && <div className="text-xs text-rose-300">{err}</div>}
          {msg && <div className="text-xs text-emerald-300">{msg}</div>}
        </div>

        <div className="rounded-2xl border border-white/10 bg-black/40 p-6 space-y-3">
          <div className="text-xs text-slate-300">Upsert User</div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <input
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="user_id (web session id)"
            />
            <input
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email (optional)"
            />
            <input
              className="rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="display name (optional)"
            />
            <div className="flex gap-2">
              <select
                className="w-full rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
                value={role}
                onChange={(e) => setRole(e.target.value)}
              >
                <option value="viewer">viewer</option>
                <option value="analyst">analyst</option>
                <option value="reviewer">reviewer</option>
                <option value="approver">approver</option>
                <option value="auditor">auditor</option>
                <option value="admin">admin</option>
              </select>
              <select
                className="w-full rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
                value={status}
                onChange={(e) => setStatus(e.target.value)}
              >
                <option value="active">active</option>
                <option value="disabled">disabled</option>
              </select>
            </div>
          </div>
          <button
            onClick={upsert}
            className="rounded-full bg-emerald-400/20 px-3 py-2 text-xs ring-1 ring-emerald-400/40"
            disabled={!userId.trim()}
          >
            Save
          </button>
        </div>

        <div className="rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Users</div>
          <div className="max-h-[420px] overflow-auto rounded-md border border-white/10 bg-black/30">
            {(items || []).map((u, idx) => (
              <div
                key={`${u.tenant_id}:${u.user_id}:${idx}`}
                className="flex items-center justify-between gap-4 border-b border-white/5 px-3 py-2 text-xs"
              >
                <div className="min-w-0">
                  <div className="font-mono text-slate-200">{u.user_id}</div>
                  <div className="text-[11px] text-slate-500">
                    {String(u.email ?? "")} {u.display_name ? `· ${u.display_name}` : ""}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-white/10 px-2 py-1 text-[11px]">{u.role}</span>
                  <span className="rounded-full bg-white/10 px-2 py-1 text-[11px]">{u.status}</span>
                </div>
              </div>
            ))}
            {items.length === 0 && <div className="px-3 py-3 text-xs text-slate-500">No users yet.</div>}
          </div>
        </div>
      </div>
    </main>
  );
}
