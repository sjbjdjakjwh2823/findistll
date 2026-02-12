"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { BackgroundBeams } from "@/components/ui/background-beams";
import type { JsonRecord } from "@/lib/types";
import {
  ArrowLeft,
  KeyRound,
  UploadCloud,
  Settings2,
  Database,
  ShieldCheck,
  ClipboardCopy,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";

const API_BASE = "/api/proxy";

type PublicConfig = {
  partner_auth?: {
    mode?: string;
  };
  integrations?: Record<string, unknown>;
  [key: string]: unknown;
};

function safeJsonParse(s: string): unknown {
  try {
    return JSON.parse(s);
  } catch {
    return null;
  }
}

function defaultPartnerPayload(partnerId: string) {
  return {
    title: "Partner Financials (Example)",
    facts: [
      {
        entity: "ACME",
        metric: "Revenue",
        period: "2024Q4",
        raw_value: "100000000",
        normalized_value: "100000000",
        unit: "currency",
        currency: "USD",
        evidence: {
          document_id: `partner:${partnerId}:2024Q4`,
          page: 1,
          section: "Income Statement",
          snippet: "Total revenue ...",
          method: "partner_api",
          confidence: 0.9,
        },
      },
    ],
    tables: [],
    metadata: { company: "ACME", fiscal_year: "2024" },
  };
}

function defaultMarketPayload(partnerId: string) {
  return {
    title: "Partner Market Snapshot (Example)",
    facts: [
      {
        entity: "ACME",
        metric: "close",
        period: "2024-12-31",
        value: "123.45",
        unit: "currency",
        currency: "USD",
        evidence: {
          document_id: `partner:${partnerId}:market:2024-12-31`,
          page: 1,
          section: "Market Data",
          snippet: "Closing price 123.45 USD",
          method: "partner_api",
          confidence: 0.92,
        },
      },
    ],
    metadata: { category: "market", vendor: "partner_feed" },
  };
}

function defaultEventPayload(partnerId: string) {
  return {
    title: "Partner Event Payload (Example)",
    events: [
      {
        entity: "ACME",
        event_type: "dividend",
        announced_at: "2024-12-31",
        effective_at: "2025-01-15",
        payload: { amount: "0.50", currency: "USD" },
        evidence: {
          document_id: `partner:${partnerId}:event:2024-12-31`,
          section: "Press Release",
          snippet: "Board declared a dividend of $0.50 per share",
          method: "partner_api",
          confidence: 0.9,
        },
      },
    ],
    metadata: { category: "event", vendor: "partner_feed" },
  };
}

function defaultAltPayload(partnerId: string) {
  return {
    title: "Partner Alternative Data (Example)",
    facts: [
      {
        entity: "ACME",
        metric: "sentiment_score",
        period: "2024-12-31",
        value: "0.62",
        unit: "score",
        evidence: {
          document_id: `partner:${partnerId}:alt:2024-12-31`,
          section: "News/Sentiment",
          snippet: "Positive sentiment trend detected",
          method: "partner_api",
          confidence: 0.85,
        },
      },
    ],
    metadata: { category: "alternative", vendor: "partner_feed" },
  };
}

export default function SdkUiPage() {
  const [publicConfig, setPublicConfig] = useState<PublicConfig | null>(null);

  const [adminToken, setAdminToken] = useState("");
  const [rbacUserId, setRbacUserId] = useState("sdkui");
  const [rbacRole, setRbacRole] = useState("admin");
  const [partnerId, setPartnerId] = useState("acme-inc");
  const [partnerName, setPartnerName] = useState("ACME Inc.");
  const [keyLabel, setKeyLabel] = useState("default");
  const [issuedApiKey, setIssuedApiKey] = useState<string | null>(null);
  const [issuedKeyPrefix, setIssuedKeyPrefix] = useState<string | null>(null);

  const [partnerApiKey, setPartnerApiKey] = useState("");
  const [partnerSource, setPartnerSource] = useState("partner");
  const [partnerTicker, setPartnerTicker] = useState("ACME");
  const [partnerDocType, setPartnerDocType] = useState("partner_financials");
  const [payloadType, setPayloadType] = useState<"financials" | "market" | "event" | "alt">("financials");
  const [payloadText, setPayloadText] = useState("");

  const [ingestResult, setIngestResult] = useState<JsonRecord | null>(null);
  const [ingestError, setIngestError] = useState<string | null>(null);
  const [causalStory, setCausalStory] = useState<JsonRecord | null>(null);
  const [causalErr, setCausalErr] = useState<string | null>(null);
  const [adminLogs, setAdminLogs] = useState<string[] | null>(null);
  const [adminLogsErr, setAdminLogsErr] = useState<string | null>(null);
  const [adminLogService, setAdminLogService] = useState<"backend" | "worker" | "event_worker">("backend");
  const [adminLogFilter, setAdminLogFilter] = useState("");
  const [qualitySummary, setQualitySummary] = useState<JsonRecord | null>(null);
  const [qualityErr, setQualityErr] = useState<string | null>(null);

  const [docsResult, setDocsResult] = useState<JsonRecord | null>(null);
  const [docsError, setDocsError] = useState<string | null>(null);

  const [supabaseUrl, setSupabaseUrl] = useState("");
  const [supabaseServiceKey, setSupabaseServiceKey] = useState("");
  const [supabaseResult, setSupabaseResult] = useState<JsonRecord | null>(null);
  const [supabaseErr, setSupabaseErr] = useState<string | null>(null);

  const [dbUrl, setDbUrl] = useState("");
  const [redisUrl, setRedisUrl] = useState("");
  const [httpUrl, setHttpUrl] = useState("");
  const [connectivityResult, setConnectivityResult] = useState<JsonRecord | null>(null);
  const [connectivityErr, setConnectivityErr] = useState<string | null>(null);

  // External provider keys
  const [extKeys, setExtKeys] = useState<JsonRecord[] | null>(null);
  const [extErr, setExtErr] = useState<string | null>(null);
  const [extProvider, setExtProvider] = useState("finnhub");
  const [extApiKey, setExtApiKey] = useState("");
  const [extLabel, setExtLabel] = useState("default");
  const [extTestResult, setExtTestResult] = useState<JsonRecord | null>(null);

  const payloadObj = useMemo(() => safeJsonParse(payloadText), [payloadText]);
  const toErrorMessage = (e: unknown) => (e instanceof Error ? e.message : String(e));

  useEffect(() => {
    // Do not persist secrets in browser storage.
    setAdminToken("");
    setPartnerApiKey("");
    setPartnerId("acme-inc");
  }, []);

  useEffect(() => {
    if (!payloadText) {
      setPayloadText(JSON.stringify(defaultPartnerPayload(partnerId), null, 2));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [partnerId]);

  useEffect(() => {
    if (payloadType === "financials") {
      setPartnerDocType("partner_financials");
      setPayloadText(JSON.stringify(defaultPartnerPayload(partnerId), null, 2));
      return;
    }
    if (payloadType === "market") {
      setPartnerDocType("partner_market");
      setPayloadText(JSON.stringify(defaultMarketPayload(partnerId), null, 2));
      return;
    }
    if (payloadType === "event") {
      setPartnerDocType("partner_event");
      setPayloadText(JSON.stringify(defaultEventPayload(partnerId), null, 2));
      return;
    }
    setPartnerDocType("partner_alt");
    setPayloadText(JSON.stringify(defaultAltPayload(partnerId), null, 2));
  }, [payloadType, partnerId]);

  useEffect(() => {
    const run = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/config/public`);
        if (res.ok) setPublicConfig((await res.json()) as PublicConfig);
      } catch {
        // ignore
      }
    };
    run();
  }, []);

  const adminHeaders = useMemo(() => {
    return {
      "Content-Type": "application/json",
      ...(adminToken ? { "X-Admin-Token": adminToken } : {}),
      ...(rbacRole ? { "X-Preciso-User-Role": rbacRole } : {}),
      ...(rbacUserId ? { "X-Preciso-User-Id": rbacUserId } : {}),
    } as Record<string, string>;
  }, [adminToken, rbacRole, rbacUserId]);

  const fetchAdminLogs = async () => {
    setAdminLogsErr(null);
    setAdminLogs(null);
    try {
      const qs = new URLSearchParams();
      qs.set("lines", "200");
      qs.set("service", adminLogService);
      if (adminLogFilter.trim()) qs.set("contains", adminLogFilter.trim());
      const res = await fetch(`${API_BASE}/api/v1/admin/logs/tail?${qs.toString()}`, {
        headers: adminHeaders,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body?.detail || "failed to fetch logs");
      setAdminLogs(body?.items || []);
    } catch (e: unknown) {
      setAdminLogsErr(toErrorMessage(e));
    }
  };

  const fetchQualitySummary = async () => {
    setQualityErr(null);
    setQualitySummary(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/logs/quality?limit=2000`, {
        headers: adminHeaders,
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body?.detail || "failed to fetch quality summary");
      setQualitySummary(body);
    } catch (e: unknown) {
      setQualityErr(toErrorMessage(e));
    }
  };

  const registerPartner = async () => {
    setIssuedApiKey(null);
    setIssuedKeyPrefix(null);
    setIngestError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/partners`, {
        method: "POST",
        headers: adminHeaders,
        body: JSON.stringify({
          partner_id: partnerId,
          name: partnerName,
          metadata: { created_via: "sdkui" },
          key_label: keyLabel,
        }),
      });
      if (!res.ok) {
        const txt = await res.text();
        throw new Error(txt || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setIssuedApiKey(data.api_key);
      setIssuedKeyPrefix(data.key_prefix);
      setPartnerApiKey(data.api_key);
    } catch (e: unknown) {
      setIngestError(`Partner registration failed: ${toErrorMessage(e)}`);
    }
  };

  const loadExternalKeys = async () => {
    setExtErr(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/integrations/keys?limit=50`, {
        headers: adminHeaders,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setExtKeys(data.keys || []);
    } catch (e: unknown) {
      setExtErr(`Load external keys failed: ${toErrorMessage(e)}`);
    }
  };

  const setExternalKey = async () => {
    setExtErr(null);
    setExtTestResult(null);
    if (!extApiKey) {
      setExtErr("API key is empty.");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/integrations/keys`, {
        method: "POST",
        headers: adminHeaders,
        body: JSON.stringify({ provider: extProvider, api_key: extApiKey, label: extLabel }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setExtApiKey("");
      await loadExternalKeys();
    } catch (e: unknown) {
      setExtErr(`Set external key failed: ${toErrorMessage(e)}`);
    }
  };

  const revokeExternalKey = async (provider: string) => {
    setExtErr(null);
    setExtTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/integrations/keys/${encodeURIComponent(provider)}`, {
        method: "DELETE",
        headers: adminHeaders,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      await loadExternalKeys();
    } catch (e: unknown) {
      setExtErr(`Revoke failed: ${toErrorMessage(e)}`);
    }
  };

  const testExternalProvider = async () => {
    setExtErr(null);
    setExtTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/integrations/test/${encodeURIComponent(extProvider)}`, {
        method: "POST",
        headers: adminHeaders,
        body: JSON.stringify({ symbol: "AAPL", series_id: "FEDFUNDS" }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setExtTestResult(data);
      await loadExternalKeys();
    } catch (e: unknown) {
      setExtErr(`Test failed: ${toErrorMessage(e)}`);
    }
  };

  const ingestPartner = async () => {
    setIngestResult(null);
    setIngestError(null);
    setCausalStory(null);
    setCausalErr(null);
    const payload = safeJsonParse(payloadText);
    if (!payload) {
      setIngestError("Payload JSON parse failed. Fix JSON first.");
      return;
    }
    try {
      const endpoint =
        payloadType === "market"
          ? "market"
          : payloadType === "event"
            ? "events"
            : payloadType === "alt"
              ? "alt"
              : "financials";
      const res = await fetch(`${API_BASE}/api/v1/partners/${endpoint}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(partnerApiKey ? { "X-Partner-Api-Key": partnerApiKey } : {}),
        },
        body: JSON.stringify({
          partner_id: partnerId,
          payload,
          source: partnerSource,
          document_type: partnerDocType,
          ticker: partnerTicker || null,
          symbol: partnerTicker || null,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.detail || `HTTP ${res.status}`);
      }
      setIngestResult(data);
    } catch (e: unknown) {
      setIngestError(`Partner ingest failed: ${toErrorMessage(e)}`);
    }
  };

  const buildCausalStory = async () => {
    setCausalStory(null);
    setCausalErr(null);
    const docId = ingestResult?.document_id;
    if (!docId) {
      setCausalErr("No document_id found. Ingest first.");
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/v1/causal/story`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity: partnerTicker || undefined,
          document_id: docId,
          horizon_days: 30,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setCausalStory(data);
    } catch (e: unknown) {
      setCausalErr(`Causal story failed: ${toErrorMessage(e)}`);
    }
  };

  const loadPartnerDocs = async () => {
    setDocsResult(null);
    setDocsError(null);
    try {
      const res = await fetch(
        `${API_BASE}/api/v1/partners/documents?partner_id=${encodeURIComponent(partnerId)}&limit=50`,
        {
          headers: {
            ...(partnerApiKey ? { "X-Partner-Api-Key": partnerApiKey } : {}),
          },
        }
      );
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setDocsResult(data);
    } catch (e: unknown) {
      setDocsError(`List documents failed: ${toErrorMessage(e)}`);
    }
  };

  const validateSupabase = async () => {
    setSupabaseErr(null);
    setSupabaseResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/supabase/validate`, {
        method: "POST",
        headers: adminHeaders,
        body: JSON.stringify({ url: supabaseUrl, service_role_key: supabaseServiceKey }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setSupabaseResult(data);
    } catch (e: unknown) {
      setSupabaseErr(`Supabase validation failed: ${toErrorMessage(e)}`);
    }
  };

  const validateConnectivity = async () => {
    setConnectivityErr(null);
    setConnectivityResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/v1/admin/connectivity/validate`, {
        method: "POST",
        headers: adminHeaders,
        body: JSON.stringify({
          supabase_url: supabaseUrl || null,
          supabase_service_role_key: supabaseServiceKey || null,
          db_url: dbUrl || null,
          redis_url: redisUrl || null,
          http_url: httpUrl || null,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
      setConnectivityResult(data);
    } catch (e: unknown) {
      setConnectivityErr(`Connectivity check failed: ${toErrorMessage(e)}`);
    }
  };

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // ignore
    }
  };

  const configStatus = useMemo(() => {
    if (!publicConfig) return null;
    const mode = publicConfig?.partner_auth?.mode;
    const secure = mode === "env" || mode === "db" || mode === "env_or_db";
    return { mode, secure };
  }, [publicConfig]);

  return (
    <main className="min-h-screen bg-black text-white relative overflow-hidden">
      <BackgroundBeams className="z-0 opacity-30" />

      <div className="relative z-10 p-6 max-w-6xl mx-auto">
        <header className="mb-8 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="p-2 hover:bg-white/5 rounded-lg transition"
              title="Back to Dashboard"
            >
              <ArrowLeft className="h-5 w-5 text-neutral-400" />
            </Link>
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-3">
                <Settings2 className="h-8 w-8 text-emerald-400" />
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-emerald-300 to-cyan-400">
                  SDK UI
                </span>
              </h1>
              <p className="text-neutral-500 text-sm mt-1">
                Partner registration, ingest, and downstream pipeline consumption.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/guide"
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs font-semibold text-white/80 hover:bg-white/10 transition"
            >
              Usage Guide
            </Link>
            <Link
              href="/collab"
              className="inline-flex items-center gap-2 rounded-lg border border-fuchsia-400/40 bg-fuchsia-500/15 px-3 py-2 text-xs font-semibold text-fuchsia-200 hover:bg-fuchsia-500/25 transition"
            >
              Open Collaboration
            </Link>
          </div>
        </header>

        <section className="grid grid-cols-12 gap-6">
          <div className="col-span-12 rounded-xl border border-white/10 bg-white/5 p-5">
            <div className="flex items-center gap-2 mb-3">
              <ShieldCheck className="h-5 w-5 text-purple-300" />
              <h2 className="text-lg font-semibold">API Settings</h2>
            </div>
            <div className="grid grid-cols-12 gap-4 text-sm">
              <div className="col-span-4 rounded-lg border border-white/10 bg-black/40 p-4">
                <div className="text-xs text-neutral-500 mb-1">Admin Token</div>
                <input
                  className="w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200 font-mono"
                  placeholder="ADMIN_API_TOKEN"
                  value={adminToken}
                  onChange={(e) => setAdminToken(e.target.value)}
                />
                <div className="mt-2 text-[11px] text-neutral-500">토큰은 저장하지 않습니다.</div>
              </div>
              <div className="col-span-4 rounded-lg border border-white/10 bg-black/40 p-4">
                <div className="text-xs text-neutral-500 mb-1">RBAC User</div>
                <input
                  className="w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                  placeholder="ops-admin"
                  value={rbacUserId}
                  onChange={(e) => setRbacUserId(e.target.value)}
                />
                <div className="mt-2 text-[11px] text-neutral-500">Optional. Default: sdkui</div>
              </div>
              <div className="col-span-4 rounded-lg border border-white/10 bg-black/40 p-4">
                <div className="text-xs text-neutral-500 mb-1">RBAC Role</div>
                <input
                  className="w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                  placeholder="admin"
                  value={rbacRole}
                  onChange={(e) => setRbacRole(e.target.value)}
                />
                <div className="mt-2 text-[11px] text-neutral-500">Optional. Default: admin</div>
              </div>
              <div className="col-span-4 rounded-lg border border-white/10 bg-black/40 p-4">
                <div className="text-xs text-neutral-500 mb-1">API Base</div>
                <div className="font-mono text-neutral-200 break-all">
                  {API_BASE}
                </div>
              </div>
              <div className="col-span-4 rounded-lg border border-white/10 bg-black/40 p-4">
                <div className="text-xs text-neutral-500 mb-1">Partner Auth Mode</div>
                <div className="font-mono text-neutral-200">
                  {configStatus?.mode || "(unavailable)"}
                </div>
                {configStatus && !configStatus.secure && (
                  <div className="mt-2 text-xs text-amber-300 flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    open mode allows unauthenticated partner ingest (dev only)
                  </div>
                )}
              </div>
              <div className="col-span-4 rounded-lg border border-white/10 bg-black/40 p-4">
                <div className="text-xs text-neutral-500 mb-1">Integrations</div>
                <div className="text-xs text-neutral-300">
                  {publicConfig
                    ? Object.entries(publicConfig.integrations || {})
                        .map(([k, v]) => `${k}:${v ? "on" : "off"}`)
                        .join(" · ")
                    : "(unavailable)"}
                </div>
              </div>
            </div>
          </div>

          <div className="col-span-12 rounded-xl border border-white/10 bg-white/5 p-5">
            <div className="flex items-center gap-2 mb-3">
              <Database className="h-5 w-5 text-emerald-300" />
              <h2 className="text-lg font-semibold">Database + Connectivity Checks</h2>
            </div>
            <div className="grid grid-cols-12 gap-4 text-sm">
              <div className="col-span-4">
                <label className="text-xs text-neutral-500">Supabase URL</label>
                <input
                  className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                  placeholder="https://xxxx.supabase.co"
                  value={supabaseUrl}
                  onChange={(e) => setSupabaseUrl(e.target.value)}
                />
                <label className="mt-3 text-xs text-neutral-500">Service Role Key</label>
                <input
                  className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200 font-mono"
                  placeholder="service_role key"
                  value={supabaseServiceKey}
                  onChange={(e) => setSupabaseServiceKey(e.target.value)}
                />
                <div className="mt-3 flex gap-3">
                  <button
                    onClick={validateSupabase}
                    className="px-4 py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-200 text-sm transition"
                  >
                    Validate Supabase
                  </button>
                </div>
                <div className="mt-2 text-[11px] text-neutral-500">
                  Uses `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY`.
                </div>
              </div>
              <div className="col-span-8">
                <div className="rounded-lg border border-white/10 bg-black/40 p-4 text-xs">
                  {supabaseErr && <div className="text-rose-300">{supabaseErr}</div>}
                  {supabaseResult && (
                    <details className="text-neutral-200">
                      <summary className="cursor-pointer text-xs text-neutral-400">Supabase Result</summary>
                      <pre className="mt-2 whitespace-pre-wrap text-neutral-200">
                        {JSON.stringify(supabaseResult, null, 2)}
                      </pre>
                    </details>
                  )}
                  {!supabaseErr && !supabaseResult && (
                    <div className="text-neutral-500">Run validation to see results.</div>
                  )}
                </div>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-12 gap-4 text-sm">
              <div className="col-span-4">
                <label className="text-xs text-neutral-500">Postgres DB URL</label>
                <input
                  className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200 font-mono"
                  placeholder="postgresql://user:pass@host:5432/db"
                  value={dbUrl}
                  onChange={(e) => setDbUrl(e.target.value)}
                />
                <label className="mt-3 text-xs text-neutral-500">Redis URL</label>
                <input
                  className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200 font-mono"
                  placeholder="redis://localhost:6379"
                  value={redisUrl}
                  onChange={(e) => setRedisUrl(e.target.value)}
                />
                <label className="mt-3 text-xs text-neutral-500">HTTP Health URL</label>
                <input
                  className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200 font-mono"
                  placeholder="https://your-api-domain/health"
                  value={httpUrl}
                  onChange={(e) => setHttpUrl(e.target.value)}
                />
                <div className="mt-3 flex gap-3">
                  <button
                    onClick={validateConnectivity}
                    className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-neutral-200 text-sm transition"
                  >
                    Validate Connectivity
                  </button>
                </div>
                <div className="mt-2 text-[11px] text-neutral-500">
                  Uses `SUPABASE_DB_URL`, `REDIS_URL`, `PUBLIC_DOMAIN`.
                </div>
              </div>
              <div className="col-span-8">
                <div className="rounded-lg border border-white/10 bg-black/40 p-4 text-xs">
                  {connectivityErr && <div className="text-rose-300">{connectivityErr}</div>}
                  {connectivityResult && (
                    <details className="text-neutral-200">
                      <summary className="cursor-pointer text-xs text-neutral-400">Connectivity Result</summary>
                      <pre className="mt-2 whitespace-pre-wrap text-neutral-200">
                        {JSON.stringify(connectivityResult, null, 2)}
                      </pre>
                    </details>
                  )}
                  {!connectivityErr && !connectivityResult && (
                    <div className="text-neutral-500">Run connectivity checks to see results.</div>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="col-span-12 rounded-xl border border-white/10 bg-white/5 p-5">
            <div className="flex items-center gap-2 mb-3">
              <KeyRound className="h-5 w-5 text-amber-400" />
              <h2 className="text-lg font-semibold">Partner Registration (Admin)</h2>
            </div>

            <div className="grid grid-cols-12 gap-4">
              <div className="col-span-4">
                <label className="text-xs text-neutral-500">Admin Token (optional, recommended)</label>
                <input
                  className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                  placeholder="X-Admin-Token"
                  value={adminToken}
                  onChange={(e) => setAdminToken(e.target.value)}
                />
                <div className="mt-2 text-xs text-neutral-500">
                  If `ADMIN_API_TOKEN` is set on the backend, this must match.
                </div>
                <div className="mt-1 text-[11px] text-neutral-600">
                  Secrets are kept in memory only and are not stored in the browser.
                </div>
              </div>
              <div className="col-span-4">
                <label className="text-xs text-neutral-500">Partner ID</label>
                <input
                  className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200 font-mono"
                  value={partnerId}
                  onChange={(e) => setPartnerId(e.target.value)}
                />
              </div>
              <div className="col-span-4">
                <label className="text-xs text-neutral-500">Partner Name</label>
                <input
                  className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                  value={partnerName}
                  onChange={(e) => setPartnerName(e.target.value)}
                />
              </div>
              <div className="col-span-4">
                <label className="text-xs text-neutral-500">Initial Key Label</label>
                <input
                  className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                  value={keyLabel}
                  onChange={(e) => setKeyLabel(e.target.value)}
                />
              </div>
              <div className="col-span-8 flex items-end gap-3">
                <button
                  onClick={registerPartner}
                  className="px-4 py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-200 text-sm transition"
                >
                  Register Partner + Issue Key
                </button>
                {issuedApiKey && (
                  <div className="text-xs text-neutral-300 flex items-center gap-2">
                    <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                    Key issued (prefix: <span className="font-mono">{issuedKeyPrefix}</span>)
                  </div>
                )}
              </div>
            </div>

            {issuedApiKey && (
              <div className="mt-4 rounded-lg border border-white/10 bg-black/40 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <div className="text-xs text-neutral-500 mb-1">One-time API Key</div>
                    <div className="font-mono text-xs text-neutral-200 break-all">
                      {issuedApiKey}
                    </div>
                  </div>
                  <button
                    onClick={() => copy(issuedApiKey)}
                    className="px-3 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs text-neutral-200 transition flex items-center gap-2"
                  >
                    <ClipboardCopy className="h-4 w-4" />
                    Copy
                  </button>
                </div>
                <div className="mt-2 text-xs text-neutral-500">
                  Store this securely. In DB mode, only the hash is stored.
                </div>
              </div>
            )}
          </div>

          <div className="col-span-12 rounded-xl border border-white/10 bg-white/5 p-5">
            <div className="flex items-center gap-2 mb-3">
              <ShieldCheck className="h-5 w-5 text-emerald-300" />
              <h2 className="text-lg font-semibold">External API Keys (Admin)</h2>
            </div>

            <div className="grid grid-cols-12 gap-4">
              <div className="col-span-4">
                <label className="text-xs text-neutral-500">Provider</label>
                <select
                  className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                  value={extProvider}
                  onChange={(e) => setExtProvider(e.target.value)}
                >
                  <option value="finnhub">finnhub</option>
                  <option value="fred">fred</option>
                  <option value="fmp">fmp</option>
                  <option value="sec">sec</option>
                  <option value="gemini">gemini</option>
                  <option value="openai">openai</option>
                </select>
                <div className="mt-3">
                  <label className="text-xs text-neutral-500">Label</label>
                  <input
                    className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                    value={extLabel}
                    onChange={(e) => setExtLabel(e.target.value)}
                  />
                </div>
                <div className="mt-3">
                  <label className="text-xs text-neutral-500">API Key (stored encrypted)</label>
                  <input
                    className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200 font-mono"
                    value={extApiKey}
                    onChange={(e) => setExtApiKey(e.target.value)}
                    placeholder="paste secret here"
                  />
                </div>
                <div className="mt-4 flex gap-3">
                  <button
                    onClick={setExternalKey}
                    className="px-4 py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-200 text-sm transition"
                  >
                    Save Key
                  </button>
                  <button
                    onClick={testExternalProvider}
                    className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-neutral-200 text-sm transition"
                  >
                    Test
                  </button>
                  <button
                    onClick={loadExternalKeys}
                    className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-neutral-200 text-sm transition"
                  >
                    Refresh
                  </button>
                </div>
                {extErr && (
                  <div className="mt-3 text-xs text-rose-300">{extErr}</div>
                )}
              </div>

              <div className="col-span-8">
                <div className="rounded-lg border border-white/10 bg-black/40 p-4">
                  <div className="text-xs text-neutral-500 mb-2">Registered Keys (safe metadata only)</div>
                  {!extKeys && (
                    <div className="text-xs text-neutral-500">
                      Click Refresh to load.
                    </div>
                  )}
                  {extKeys && extKeys.length === 0 && (
                    <div className="text-xs text-neutral-500">No keys yet.</div>
                  )}
                  {extKeys && extKeys.length > 0 && (
                    <div className="space-y-2">
                      {extKeys.map((k, idx) => (
                        <div
                          key={String(k.id ?? k.provider ?? idx)}
                          className="flex items-center justify-between gap-4 rounded-lg border border-white/10 bg-black/30 p-3"
                        >
                          <div className="min-w-0">
                            <div className="text-xs text-neutral-200 font-mono">
                              {String(k.provider ?? "")}{" "}
                              <span className="text-neutral-500">{String(k.hint ?? "")}</span>
                            </div>
                            <div className="text-[11px] text-neutral-500">
                              {String(k.label ?? "")} · created {String(k.created_at ?? "")} · last_test{" "}
                              {String(k.last_test_status ?? "n/a")}
                            </div>
                          </div>
                          <button
                            onClick={() => revokeExternalKey(String(k.provider ?? ""))}
                            className="px-3 py-2 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-rose-200 text-xs transition"
                          >
                            Revoke
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {extTestResult && (
                  <div className="mt-4 rounded-lg border border-white/10 bg-black/40 p-4 text-xs">
                    <details className="text-neutral-200">
                      <summary className="cursor-pointer text-xs text-neutral-400">Test Result</summary>
                      <pre className="mt-2 whitespace-pre-wrap text-neutral-200">
                        {JSON.stringify(extTestResult, null, 2)}
                      </pre>
                    </details>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="col-span-12 rounded-xl border border-white/10 bg-white/5 p-5">
            <div className="flex items-center gap-2 mb-3">
              <UploadCloud className="h-5 w-5 text-cyan-300" />
              <h2 className="text-lg font-semibold">Partner Ingest Test</h2>
            </div>

            <div className="grid grid-cols-12 gap-4">
              <div className="col-span-4">
                <label className="text-xs text-neutral-500">Partner API Key</label>
                <input
                  className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200 font-mono"
                  placeholder="X-Partner-Api-Key"
                  value={partnerApiKey}
                  onChange={(e) => setPartnerApiKey(e.target.value)}
                />
                <div className="mt-3">
                  <label className="text-xs text-neutral-500">Payload Type</label>
                  <select
                    className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                    value={payloadType}
                    onChange={(e) =>
                      setPayloadType(e.target.value as "financials" | "market" | "event" | "alt")
                    }
                  >
                    <option value="financials">financials</option>
                    <option value="market">market</option>
                    <option value="event">event</option>
                    <option value="alt">alternative</option>
                  </select>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-neutral-500">Ticker</label>
                    <input
                      className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                      value={partnerTicker}
                      onChange={(e) => setPartnerTicker(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-neutral-500">Source</label>
                    <input
                      className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                      value={partnerSource}
                      onChange={(e) => setPartnerSource(e.target.value)}
                    />
                  </div>
                </div>
                <div className="mt-3">
                  <label className="text-xs text-neutral-500">Document Type</label>
                  <input
                    className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                    value={partnerDocType}
                    onChange={(e) => setPartnerDocType(e.target.value)}
                  />
                </div>
                <div className="mt-4 flex gap-3">
                  <button
                    onClick={ingestPartner}
                    className="px-4 py-2 rounded-lg bg-cyan-500/20 hover:bg-cyan-500/30 border border-cyan-500/40 text-cyan-200 text-sm transition"
                  >
                    Ingest
                  </button>
                  <button
                    onClick={buildCausalStory}
                    className="px-4 py-2 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-200 text-sm transition"
                  >
                    Causal Story
                  </button>
                  <button
                    onClick={loadPartnerDocs}
                    className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-neutral-200 text-sm transition"
                  >
                    List Documents
                  </button>
                </div>
              </div>

              <div className="col-span-8">
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-neutral-500">Payload JSON</label>
                  <div className="text-xs text-neutral-500">
                    {payloadObj ? "valid" : "invalid"}
                  </div>
                </div>
                <textarea
                  className="w-full h-[320px] bg-black/60 border border-white/10 rounded-lg p-3 text-xs text-neutral-200 font-mono"
                  value={payloadText}
                  onChange={(e) => setPayloadText(e.target.value)}
                />
              </div>
            </div>

            {(ingestError || ingestResult) && (
              <div className="mt-4 rounded-lg border border-white/10 bg-black/40 p-4 text-xs">
                {ingestError && <div className="text-rose-300">{ingestError}</div>}
                {ingestResult && (
                  <details className="text-neutral-200">
                    <summary className="cursor-pointer text-xs text-neutral-400">Ingest Result</summary>
                    <pre className="mt-2 whitespace-pre-wrap text-neutral-200">
                      {JSON.stringify(ingestResult, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            )}

            {(causalErr || causalStory) && (
              <div className="mt-4 rounded-lg border border-white/10 bg-black/40 p-4 text-xs">
                {causalErr && <div className="text-rose-300">{causalErr}</div>}
                {causalStory && (
                  <details className="text-neutral-200">
                    <summary className="cursor-pointer text-xs text-neutral-400">Causal Story</summary>
                    <pre className="mt-2 whitespace-pre-wrap text-neutral-200">
                      {JSON.stringify(causalStory, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            )}

            {(docsError || docsResult) && (
              <div className="mt-4 rounded-lg border border-white/10 bg-black/40 p-4 text-xs">
                {docsError && <div className="text-rose-300">{docsError}</div>}
                {docsResult && (
                  <details className="text-neutral-200">
                    <summary className="cursor-pointer text-xs text-neutral-400">Documents</summary>
                    <pre className="mt-2 whitespace-pre-wrap text-neutral-200">
                      {JSON.stringify(docsResult, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            )}

            <div className="mt-6 rounded-lg border border-white/10 bg-black/40 p-4 text-xs">
              <div className="flex items-center justify-between">
                <div className="text-neutral-200 font-semibold">Enterprise Logs (Tail)</div>
                <button
                  onClick={fetchAdminLogs}
                  className="px-3 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-neutral-200 text-xs transition"
                >
                  Fetch Logs
                </button>
              </div>
              <div className="mt-2 text-neutral-500">
                Requires `ADMIN_API_TOKEN` or RBAC admin headers. Secrets are redacted server-side.
              </div>
              <div className="mt-3 grid grid-cols-3 gap-3">
                <div>
                  <label className="text-xs text-neutral-500">Service</label>
                  <select
                    className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                    value={adminLogService}
                    onChange={(e) => setAdminLogService(e.target.value as "backend" | "worker" | "event_worker")}
                  >
                    <option value="backend">backend</option>
                    <option value="worker">worker</option>
                    <option value="event_worker">event_worker</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <label className="text-xs text-neutral-500">Contains Filter</label>
                  <input
                    className="mt-1 w-full bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                    value={adminLogFilter}
                    onChange={(e) => setAdminLogFilter(e.target.value)}
                    placeholder="ex) doc_id, tenant_id, ERROR"
                  />
                </div>
              </div>
              {adminLogsErr && <div className="mt-2 text-rose-300">{adminLogsErr}</div>}
              {adminLogs && (
                <details className="mt-3 text-neutral-200">
                  <summary className="cursor-pointer text-xs text-neutral-400">Logs</summary>
                  <pre className="mt-2 max-h-[260px] overflow-auto whitespace-pre-wrap text-neutral-200 bg-black/60 border border-white/10 rounded-lg p-3">
                    {adminLogs.join("\n")}
                  </pre>
                </details>
              )}
            </div>

            <div className="mt-4 rounded-lg border border-white/10 bg-black/40 p-4 text-xs">
              <div className="flex items-center justify-between">
                <div className="text-neutral-200 font-semibold">Quality Gate Summary</div>
                <button
                  onClick={fetchQualitySummary}
                  className="px-3 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-neutral-200 text-xs transition"
                >
                  Fetch Summary
                </button>
              </div>
              {qualityErr && <div className="mt-2 text-rose-300">{qualityErr}</div>}
              {qualitySummary && (
                <details className="mt-3 text-neutral-200">
                  <summary className="cursor-pointer text-xs text-neutral-400">Quality Summary</summary>
                  <pre className="mt-2 max-h-[260px] overflow-auto whitespace-pre-wrap text-neutral-200 bg-black/60 border border-white/10 rounded-lg p-3">
                    {JSON.stringify(qualitySummary, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          </div>

          <div className="col-span-12 rounded-xl border border-white/10 bg-white/5 p-5">
            <div className="flex items-center gap-2 mb-3">
              <Database className="h-5 w-5 text-emerald-300" />
              <h2 className="text-lg font-semibold">How This Flows Through Preciso</h2>
            </div>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <FlowCard
                title="1) Partner Ingest"
                body="Partner pushes structured facts/tables. Preciso converts and stores it as a raw_document for downstream traceability."
              />
              <FlowCard
                title="2) HITL + Quality Gates"
                body="If evidence is missing/weak, it is marked needs_review and routed to DataForge review. Approved artifacts become training candidates."
              />
              <FlowCard
                title="3) Downstream Consumption"
                body="WS8 consumes approved data: Spoke A JSONL for SFT, Spoke B Parquet facts/features for quant and numeric ground truth, Spoke C RAG for retrieval."
              />
            </div>
            <div className="mt-4 text-xs text-neutral-500">
              UI shortcuts: <Link className="underline hover:text-neutral-300" href="/dataforge">DataForge</Link> ·{" "}
              <Link className="underline hover:text-neutral-300" href="/ops">OpsGraph</Link> ·{" "}
              <Link className="underline hover:text-neutral-300" href="/audit">Audit</Link>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function FlowCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/40 p-4">
      <div className="text-sm font-semibold text-white mb-2">{title}</div>
      <div className="text-xs text-neutral-400 leading-relaxed">{body}</div>
    </div>
  );
}
