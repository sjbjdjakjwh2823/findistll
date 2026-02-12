"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { BackgroundBeams } from "@/components/ui/background-beams";
import { Network, ClipboardList, ShieldCheck, ArrowLeft } from "lucide-react";
import { CaseStatusBadge } from "@/components/ops/CaseStatusBadge";
import { CaseTimeline } from "@/components/ops/CaseTimeline";
import { PermissionGate } from "@/components/rbac/PermissionGate";
import { SLABadge } from "@/components/ops/SLABadge";
import { AuthorityMarkers } from "@/components/ops/AuthorityMarkers";
import { SignalSummary } from "@/components/ops/SignalSummary";
import { ExtractedFactsTable } from "@/components/ops/ExtractedFactsTable";
import { DecisionComparison } from "@/components/ops/DecisionComparison";
import { WorkflowProgress } from "@/components/ops/WorkflowProgress";
import { DocumentPreview } from "@/components/ops/DocumentPreview";
import type { JsonRecord } from "@/lib/types";

export default function OpsGraphPage() {
  const [cases, setCases] = useState<JsonRecord[]>([]);
  const [auditLogs, setAuditLogs] = useState<JsonRecord[]>([]);
  const [auditFilter, setAuditFilter] = useState<string>("");
  const [selectedAudit, setSelectedAudit] = useState<JsonRecord | null>(null);
  const [metrics, setMetrics] = useState<JsonRecord[]>([]);
  const API_BASE = "/api/proxy";

  useEffect(() => {
    const fetchData = async () => {
      try {
        const resCases = await fetch(`${API_BASE}/api/v1/opsgraph/cases`);
        if (resCases.ok) {
          const data = await resCases.json();
          setCases(data.cases || []);
        }
        const resAudit = await fetch(`${API_BASE}/api/v1/opsgraph/audit`);
        if (resAudit.ok) {
          const data = await resAudit.json();
          setAuditLogs(data.audit_logs || []);
        }
        const resMetrics = await fetch(`${API_BASE}/api/v1/metrics/recent?limit=10`);
        if (resMetrics.ok) {
          const data = await resMetrics.json();
          setMetrics(data.metrics || []);
        }
      } catch (e) {
        console.error("Failed to fetch opsgraph data", e);
      }
    };
    fetchData();
  }, [API_BASE]);
  const inboxItems = cases.slice(0, 5).map((c, idx) => ({
    case_id: String(c.id ?? `case-${idx + 1}`),
    title: String(c.title ?? `Case ${idx + 1}`),
    status: String(c.status ?? "pending"),
    priority: String(c.priority ?? "MEDIUM"),
    assigned_to: String(c.assigned_to ?? "Unassigned"),
    created_at: String(c.created_at ?? "Today"),
    due_at: String(c.due_at ?? "Tomorrow"),
    sla_status: idx % 3 === 0 ? "AT_RISK" : idx % 2 === 0 ? "ON_TIME" : "OVERDUE",
    unread_count: Number(c.unread_count ?? 0),
  }));

  const extractedFacts = [
    {
      id: "fact-1",
      category: "financial",
      key: "total_assets",
      value: "125.4B",
      unit: "USD",
      source_document: "10-K Filing 2025",
      source_page: 42,
      confidence: 0.92,
    },
    {
      id: "fact-2",
      category: "risk",
      key: "debt_ratio",
      value: "3.2",
      unit: "x",
      source_document: "10-K Filing 2025",
      source_page: 41,
      confidence: 0.88,
    },
    {
      id: "fact-3",
      category: "liquidity",
      key: "cash_reserves",
      value: "2.1B",
      unit: "USD",
      source_document: "Earnings Deck",
      source_page: 12,
      confidence: 0.81,
    },
  ];

  const anchors = [
    {
      document_name: "10-K Filing 2025",
      page_number: 42,
      snippet_text: "Total debt increased by 45% YoY due to new long-term borrowings.",
    },
    {
      document_name: "FRED Macro Data",
      page_number: 3,
      snippet_text: "Interest rates climbed to 5.25% across the period.",
    },
  ];

  const aiDecision = {
    decision: "HIGH RISK — Default likely",
    confidence: 0.78,
    actions: ["Reduce exposure 50%", "Freeze new credit", "Weekly monitoring"],
    reasoning: ["Debt ratio 3.2x", "Interest costs rising", "Liquidity drawdown"],
  };

  const humanDecision = {
    decision: "HIGH RISK — Monitor closely",
    confidence: 0.85,
    actions: ["Reduce exposure 25%", "Add quarterly review", "Engage treasury"],
    notes: "Recent refinancing may offset short-term pressure; keep watch on covenants.",
  };

  const workflowStages = [
    { stage: "Analysis", status: "done", assigned_to: "J. Doe", completed_at: "2h ago" },
    { stage: "Review", status: "done", assigned_to: "J. Smith", completed_at: "1h ago" },
    { stage: "Approval", status: "pending", assigned_to: "A. Kim" },
  ];

  const signalSummary = {
    riskScore: 87,
    riskLevel: "HIGH",
    signals: [
      { type: "ANOMALY", severity: 3, description: "Debt spike +45% YoY" },
      { type: "TREND", severity: 2, description: "Cash flow -18% QoQ" },
      { type: "THRESHOLD", severity: 2, description: "Interest rate 5.25%" },
    ],
    trends: [
      { metric: "Leverage", direction: "UP", change_pct: 12, period: "12M" },
      { metric: "Liquidity", direction: "DOWN", change_pct: -6, period: "6M" },
      { metric: "Profitability", direction: "STABLE", change_pct: 1, period: "3M" },
    ],
  };
  return (
    <main className="min-h-screen bg-black text-white relative overflow-hidden">
      <BackgroundBeams className="z-0 opacity-30" />

      <div className="relative z-10 p-6 max-w-7xl mx-auto">
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
                <Network className="h-8 w-8 text-cyan-400" />
                <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-300 to-blue-500">
                  OpsGraph
                </span>
              </h1>
              <p className="text-neutral-500 text-sm mt-1">
                Phase 3: Operations OS — Cases, Ontology, and Audit Trail
              </p>
            </div>
          </div>
        </header>

        <section className="grid grid-cols-12 gap-6">
          <PermissionGate requiredRoles={["analyst", "reviewer", "approver", "admin"]} fallback={<div className="col-span-8 rounded-xl border border-white/10 bg-white/5 p-5 text-sm text-neutral-500">Restricted</div>}>
            <div className="col-span-8 space-y-6">
              <div className="rounded-xl border border-white/10 bg-white/5 p-5">
                <div className="flex items-center gap-2 mb-4">
                  <ClipboardList className="h-5 w-5 text-emerald-400" />
                  <h2 className="text-lg font-semibold">Inbox</h2>
                </div>
                <div className="space-y-3">
                  {inboxItems.length === 0 && (
                    <div className="rounded-lg border border-white/10 bg-black/40 p-4 text-sm text-neutral-500">
                      No inbox items yet.
                    </div>
                  )}
                  {inboxItems.map((item) => (
                    <div key={item.case_id} className="rounded-lg border border-white/10 bg-black/40 p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm text-white">{item.title}</div>
                          <div className="text-xs text-neutral-500">{item.case_id}</div>
                        </div>
                        <div className="flex items-center gap-3">
                          <SLABadge status={item.sla_status} />
                          <CaseStatusBadge status={item.status} />
                        </div>
                      </div>
                      <div className="mt-2 flex items-center justify-between text-xs text-neutral-400">
                        <div>Assigned: {item.assigned_to}</div>
                        <div>Due: {item.due_at}</div>
                        <div>Priority: {item.priority}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <AuthorityMarkers
                owner="J. Doe"
                reviewer="J. Smith"
                approver="A. Kim"
                watchers={["Risk Ops", "Compliance"]}
              />
            </div>
          </PermissionGate>

          <div className="col-span-4 space-y-6">
            <SignalSummary
              riskScore={signalSummary.riskScore}
              riskLevel={signalSummary.riskLevel}
              signals={signalSummary.signals}
              trends={signalSummary.trends}
            />

            <div className="rounded-xl border border-white/10 bg-white/5 p-5">
              <div className="flex items-center gap-2 mb-4">
                <ShieldCheck className="h-5 w-5 text-purple-300" />
                <h2 className="text-lg font-semibold">Audit Trail</h2>
              </div>
              <input
                className="w-full mb-3 bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
                placeholder="Filter by action or actor"
                value={auditFilter}
                onChange={(e) => setAuditFilter(e.target.value)}
              />
              <ul className="space-y-3 text-sm text-neutral-400">
                {auditLogs.filter((log) => {
                  const hay = `${log.action} ${log.actor_type} ${log.actor_id}`.toLowerCase();
                  return hay.includes(auditFilter.toLowerCase());
                }).slice(0, 5).map((log, idx) => (
                  <li key={idx} className="rounded-lg border border-white/10 bg-black/40 p-3">
                    <button className="text-left w-full" onClick={() => setSelectedAudit(log)}>
                      {String(log.action ?? "")} · {String(log.actor_type ?? "")} · {String(log.created_at ?? "")}
                    </button>
                  </li>
                ))}
                {auditLogs.length === 0 && (
                  <li className="rounded-lg border border-white/10 bg-black/40 p-3">
                    No audit logs yet.
                  </li>
                )}
              </ul>
              {selectedAudit && (
                <div className="mt-4 rounded-lg border border-white/10 bg-black/40 p-3 text-xs text-neutral-300">
                  <div className="font-semibold mb-2">Audit Detail</div>
                  <pre className="whitespace-pre-wrap">{JSON.stringify(selectedAudit, null, 2)}</pre>
                </div>
              )}
            </div>

            <div className="rounded-xl border border-white/10 bg-white/5 p-5">
              <div className="flex items-center gap-2 mb-4">
                <ClipboardList className="h-5 w-5 text-emerald-300" />
                <h2 className="text-lg font-semibold">Performance KPIs</h2>
              </div>
              <div className="space-y-2 text-xs text-neutral-300">
                {metrics.length === 0 && (
                  <div className="text-neutral-500">No metrics yet.</div>
                )}
                {metrics.map((metric, idx) => (
                  <div
                    key={String(metric.id ?? metric.name ?? idx)}
                    className="flex items-center justify-between border-b border-white/5 pb-2"
                  >
                    <div className="text-neutral-200">{String(metric.name ?? "")}</div>
                    <div className="text-neutral-400">{String(metric.value ?? "")}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section className="mt-6 grid grid-cols-12 gap-6">
          <div className="col-span-8 space-y-6">
            <ExtractedFactsTable facts={extractedFacts} />
            <DocumentPreview anchors={anchors} />
          </div>
          <div className="col-span-4 space-y-6">
            <DecisionComparison aiDecision={aiDecision} humanDecision={humanDecision} />
            <WorkflowProgress stages={workflowStages} />
          </div>
        </section>

        <section className="mt-6 rounded-xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center gap-2 mb-4">
            <ClipboardList className="h-5 w-5 text-emerald-300" />
            <h2 className="text-lg font-semibold">Cases</h2>
          </div>
          <div className="space-y-3">
            {cases.slice(0, 8).map((c) => (
              <div key={String(c.id ?? "")} className="rounded-lg border border-white/10 bg-black/40 p-4">
                <div className="flex items-center justify-between">
                  <div className="text-sm text-white">{String(c.title ?? c.id ?? "")}</div>
                  <CaseStatusBadge status={String(c.status ?? "draft")} />
                </div>
                <div className="mt-2">
                  <CaseTimeline status={String(c.status ?? "draft")} />
                </div>
                <div className="mt-2 text-xs text-neutral-500">Priority: {String(c.priority ?? "medium")}</div>
              </div>
            ))}
            {cases.length === 0 && (
              <div className="rounded-lg border border-white/10 bg-black/40 p-4 text-sm text-neutral-500">
                No cases yet.
              </div>
            )}
          </div>
        </section>

        <section className="mt-6 rounded-xl border border-white/10 bg-white/5 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Network className="h-5 w-5 text-cyan-300" />
            <h2 className="text-lg font-semibold">Graph Explorer</h2>
          </div>
          <div className="rounded-lg border border-white/10 bg-black/40 p-6 text-neutral-400 text-sm">
            Render 1-hop relationships from `/api/v1/opsgraph/entities/:id/graph` using a
            force-graph component.
          </div>
        </section>
      </div>
    </main>
  );
}
