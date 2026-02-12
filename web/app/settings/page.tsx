"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BackgroundBeams } from "@/components/ui/background-beams";

const API_BASE = "/api/proxy";

type FlagItem = {
  enabled: boolean;
  source?: string;
  description?: string;
};

const FLAG_META: Record<string, { label: string; help: string }> = {
  rag_cache_enabled: {
    label: "RAG Cache",
    help: "최근 질의 결과를 캐시해 응답 속도를 높입니다.",
  },
  rag_rerank_enabled: {
    label: "Rerank",
    help: "가져온 증거를 재정렬해 더 정확한 근거를 선택합니다.",
  },
  rag_compress_enabled: {
    label: "Context Compression",
    help: "질의 컨텍스트를 압축해 LLM 비용과 지연을 줄입니다.",
  },
  auto_train_on_approval: {
    label: "Auto-Train After Approval",
    help: "승인 완료 후 자동으로 학습 후보를 생성합니다.",
  },
  egress_sensitive_block: {
    label: "Egress Sensitive Block",
    help: "민감 데이터 외부 반출을 차단합니다.",
  },
  egress_approval_required: {
    label: "Egress Approval Required",
    help: "외부 전송 전 관리자 승인을 요구합니다.",
  },
  license_check_enabled: {
    label: "License Check",
    help: "라이선스 검증을 활성화합니다.",
  },
  rate_limit_enabled: {
    label: "Rate Limit",
    help: "사용량 보호를 위해 요청 제한을 적용합니다.",
  },
  lakehouse_enabled: {
    label: "Lakehouse",
    help: "Delta/Spark/MLflow/UC 연동 기능을 활성화합니다.",
  },
  finrobot_enabled: {
    label: "FinRobot",
    help: "분석/요약용 고급 추론 모듈을 켭니다.",
  },
};

const GROUPS: Record<string, string[]> = {
  "RAG / Retrieval": ["rag_cache_enabled", "rag_rerank_enabled", "rag_compress_enabled"],
  "Training & Models": ["auto_train_on_approval"],
  "Security & Governance": ["egress_sensitive_block", "egress_approval_required", "license_check_enabled"],
  "Operations": ["rate_limit_enabled", "lakehouse_enabled", "finrobot_enabled"],
  "Automation": ["auto_scale_enabled"],
};

export default function SettingsPage() {
  const [flags, setFlags] = useState<Record<string, FlagItem>>({});
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState("public");

  const adminHeaders = useMemo(
    () => ({
      "Content-Type": "application/json",
      // Auth/tenant headers are injected by `/api/proxy` using NextAuth session + cookie.
    }),
    []
  );

  const setTenant = async () => {
    setError(null);
    try {
      const res = await fetch("/api/tenant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tenant_id: tenantId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "failed to set tenant");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "failed to set tenant");
    }
  };

  const loadFlags = async () => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/config/flags`, { headers: adminHeaders });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "failed to load flags");
      setFlags(data.flags || {});
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "failed to load flags");
    }
  };

  const toggleFlag = async (name: string, enabled: boolean) => {
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/config/flags`, {
        method: "POST",
        headers: adminHeaders,
        body: JSON.stringify({ name, enabled }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "failed to update");
      setFlags(data.flags || {});
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "failed to update");
    }
  };

  useEffect(() => {
    loadFlags();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const grouped = useMemo(() => {
    const remaining = { ...flags };
    const result: Array<{ title: string; keys: string[] }> = [];
    Object.entries(GROUPS).forEach(([title, keys]) => {
      const active = keys.filter((k) => remaining[k]);
      active.forEach((k) => delete remaining[k]);
      if (active.length > 0) result.push({ title, keys: active });
    });
    const leftover = Object.keys(remaining);
    if (leftover.length > 0) {
      result.push({ title: "Other", keys: leftover });
    }
    return result;
  }, [flags]);

  return (
    <main className="relative min-h-screen overflow-hidden">
      <BackgroundBeams className="z-0" />
      <div className="relative z-10 mx-auto w-full max-w-5xl px-6 py-10 text-white">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-3xl font-semibold">System Settings</h1>
          <Link href="/" className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs">
            Back
          </Link>
        </div>

        <div className="rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Tenant</div>
          <div className="flex flex-col gap-2 md:flex-row md:items-center">
            <input
              className="w-full flex-1 rounded-md border border-white/10 bg-black/50 px-3 py-2 text-xs"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
              placeholder="public"
            />
            <button
              onClick={setTenant}
              className="rounded-full bg-white/10 px-3 py-2 text-xs text-white ring-1 ring-white/10"
            >
              Set Tenant
            </button>
            <button
              onClick={loadFlags}
              className="rounded-full bg-cyan-400/20 px-3 py-2 text-xs ring-1 ring-cyan-400/40"
            >
              Refresh Flags
            </button>
          </div>
          <div className="mt-2 text-[11px] text-slate-400">
            모든 API 호출은 브라우저에서 직접 백엔드로 가지 않고, 웹 서버의 `/api/proxy`가 세션 기반으로
            `X-Tenant-Id / X-Preciso-User-* / (admin 시) X-Admin-Token`을 주입합니다.
          </div>
          {error && <div className="mt-3 text-xs text-rose-300">{error}</div>}
        </div>

        <div className="mt-6 rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">Feature Flags</div>
          <div className="space-y-6 text-xs text-slate-300">
            {grouped.map((group) => (
              <div key={group.title}>
                <div className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">
                  {group.title}
                </div>
                <div className="space-y-2">
                  {group.keys.map((name) => {
                    const flag = flags[name];
                    if (!flag) return null;
                    const meta = FLAG_META[name];
                    return (
                      <div
                        key={name}
                        className="flex items-center justify-between gap-3 rounded-md border border-white/10 bg-black/50 px-3 py-2"
                      >
                        <div>
                          <div className="text-slate-200">{meta?.label || name}</div>
                          <div className="text-[11px] text-slate-500">
                            {meta?.help || flag.description || ""} · source: {flag.source || "env"}
                          </div>
                        </div>
                        <button
                          onClick={() => toggleFlag(name, !flag.enabled)}
                          className={`rounded-full px-2 py-1 text-[11px] ring-1 ${
                            flag.enabled
                              ? "bg-emerald-400/20 text-emerald-200 ring-emerald-400/40"
                              : "bg-rose-400/20 text-rose-200 ring-rose-400/40"
                          }`}
                        >
                          {flag.enabled ? "On" : "Off"}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-6 rounded-2xl border border-white/10 bg-black/40 p-6">
          <div className="mb-3 text-xs text-slate-300">API Connections</div>
          <div className="text-xs text-slate-400">
            외부 API 키 등록/테스트는 SDK UI에서 수행합니다.
          </div>
          <div className="mt-4 flex gap-2">
            <Link
              href="/sdkui"
              className="rounded-full bg-white/10 px-3 py-1 text-xs text-white ring-1 ring-white/10"
            >
              Open SDK UI
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
