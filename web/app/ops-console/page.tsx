"use client";

import Link from "next/link";
import React, { useState } from "react";
import { ArrowRight, ChevronRight, ShieldCheck, Activity, Database, CheckCircle2, ClipboardList } from "lucide-react";

const NAV = [
  { label: "Overview", href: "#overview" },
  { label: "Pipelines", href: "#pipelines" },
  { label: "Operations", href: "#operations" },
  { label: "Models", href: "#models" },
  { label: "Governance", href: "#governance" },
  { label: "Logs", href: "#logs" },
];

const PILLARS = [
  {
    title: "End-to-end Operations",
    desc: "Ingest to approval, training, and serving. One console, full control.",
    icon: Activity,
  },
  {
    title: "Quality + Compliance",
    desc: "Evidence-first decisions with audit trails, gates, and lineage.",
    icon: ShieldCheck,
  },
  {
    title: "Lakehouse + MLflow",
    desc: "Delta, Spark, MLflow, Unity Catalog—wired into every flow.",
    icon: Database,
  },
];

const PIPELINE_CARDS = [
  { title: "Ingest", desc: "Files, partner APIs, market feeds, OCR + iXBRL.", href: "/dataforge" },
  { title: "Spoke A/B/C/D", desc: "Facts, RAG context, causal graph, training sets.", href: "/ops" },
  { title: "Approvals", desc: "HITL review, corrections, and gate enforcement.", href: "/dataforge" },
  { title: "RAG + LLM", desc: "Evidence retrieval, LLM runs, model routing.", href: "/console" },
  { title: "Training", desc: "Auto-train, batch datasets, local fine-tune.", href: "/mlops" },
  { title: "Lakehouse", desc: "Delta history, time travel, job status.", href: "/lakehouse" },
];

const QUICK_ACTIONS = [
  { title: "1. Run Setup Wizard", desc: "Connect DB/Redis, run preflight checks.", href: "/setup" },
  { title: "2. Upload Documents", desc: "Start ingest pipeline and parsing.", href: "/dataforge" },
  { title: "3. Review & Approve", desc: "Approve results and create training candidates.", href: "/dataforge" },
  { title: "4. Train & Serve", desc: "Auto-train or batch train and set serving model.", href: "/mlops" },
  { title: "5. Monitor & Audit", desc: "Track logs, quotas, and compliance exports.", href: "/logs" },
];

const OPS_CARDS = [
  { title: "Settings", desc: "Feature flags, security controls, rate limits.", href: "/settings" },
  { title: "Organization", desc: "Tenant users + roles (RBAC) management.", href: "/org" },
  { title: "Logs", desc: "Pipeline logs and service tails with filters.", href: "/logs" },
  { title: "Governance", desc: "Policies, lineage, and tenant access control.", href: "/governance" },
  { title: "Collaboration", desc: "Teams, sharing, transfers, tenant pipeline.", href: "/collab" },
  { title: "Partner SDK", desc: "External API registration + ingest testing.", href: "/sdkui" },
  { title: "Admin Tools", desc: "All remaining APIs in one web console.", href: "/admin-tools" },
  { title: "Audit Trail", desc: "Compliance exports and immutable logs.", href: "/audit" },
];

const MODEL_CARDS = [
  { title: "Serving Models", desc: "Pick which model serves production requests.", href: "/mlops" },
  { title: "Model Registry", desc: "Track runs, promote, rollback with MLflow.", href: "/mlops" },
  { title: "Local Fine-tune", desc: "QLoRA training with one click.", href: "/mlops" },
];

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="mb-8">
      <div className="text-xs uppercase tracking-[0.3em] text-slate-500">{subtitle}</div>
      <h2 className="mt-3 text-3xl font-semibold text-slate-900">{title}</h2>
    </div>
  );
}

function Card({ title, desc, href }: { title: string; desc: string; href: string }) {
  return (
    <Link
      href={href}
      className="group flex h-full flex-col justify-between rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md"
    >
      <div>
        <div className="text-sm font-semibold text-slate-900">{title}</div>
        <div className="mt-2 text-sm text-slate-600">{desc}</div>
      </div>
      <div className="mt-6 inline-flex items-center gap-2 text-xs font-semibold text-slate-900">
        Open
        <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
      </div>
    </Link>
  );
}

export default function OpsConsolePage() {
  const [query, setQuery] = useState("");
  const queryNorm = query.trim().toLowerCase();
  const match = (text: string) => text.toLowerCase().includes(queryNorm);
  const filteredPipelines = PIPELINE_CARDS.filter((c) => !queryNorm || match(`${c.title} ${c.desc}`));
  const filteredOps = OPS_CARDS.filter((c) => !queryNorm || match(`${c.title} ${c.desc}`));
  const filteredModels = MODEL_CARDS.filter((c) => !queryNorm || match(`${c.title} ${c.desc}`));

  return (
    <div className="min-h-screen bg-[#f7f7f4] text-slate-900">
      <header className="border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-900 text-white">
              <ClipboardList className="h-4 w-4" />
            </div>
            <div>
              <div className="text-sm font-semibold">Preciso Operations</div>
              <div className="text-xs text-slate-500">Enterprise Control Center</div>
            </div>
          </div>
          <nav className="hidden items-center gap-6 text-xs font-semibold text-slate-600 md:flex">
            {NAV.map((item) => (
              <a key={item.href} href={item.href} className="hover:text-slate-900">
                {item.label}
              </a>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="hidden rounded-full border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 md:inline-flex"
            >
              Dashboard
            </Link>
            <Link
              href="/guide"
              className="hidden rounded-full border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 md:inline-flex"
            >
              Usage Guide
            </Link>
            <Link
              href="/settings"
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
            >
              Settings
              <ChevronRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      <section id="overview" className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-12 md:grid-cols-[1.2fr_0.8fr]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600">
              운영 전체 통제
            </div>
            <h1 className="mt-6 text-4xl font-semibold leading-tight md:text-5xl">
              Preciso 운영을
              <span className="block text-slate-700">웹 한 곳에서 끝내세요.</span>
            </h1>
            <p className="mt-4 text-base text-slate-600">
              데이터 인입부터 Spoke A/B/C/D, 승인, 학습, 모델 서빙, Lakehouse까지 모든 운영을 한 화면에서
              관리합니다.
            </p>
            <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600">
              비개발자도 바로 따라할 수 있도록 <span className="font-semibold text-slate-900">단계별 가이드</span>와
              <span className="font-semibold text-slate-900"> 쉬운 버튼</span>만 제공합니다.
            </div>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/dataforge"
                className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
              >
                Start Ingest
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
              <Link
                href="/logs"
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700"
              >
                View Logs
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
            <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-xs font-semibold text-slate-500">Search Operations</div>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search pipelines, models, governance, logs..."
                className="mt-3 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-slate-400"
              />
            </div>
          </div>
          <div className="grid gap-4">
            {PILLARS.map((p) => {
              const Icon = p.icon;
              return (
                <div key={p.title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-900 text-white">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{p.title}</div>
                      <div className="text-sm text-slate-600">{p.desc}</div>
                    </div>
                  </div>
                </div>
              );
            })}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-xs font-semibold text-slate-500">Guided Onboarding</div>
              <div className="mt-4 grid gap-3 text-sm">
                {QUICK_ACTIONS.map((action) => (
                  <Link
                    key={action.title}
                    href={action.href}
                    className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-3 py-2"
                  >
                    <div>
                      <div className="text-sm font-semibold text-slate-900">{action.title}</div>
                      <div className="text-xs text-slate-600">{action.desc}</div>
                    </div>
                    <ArrowRight className="h-4 w-4 text-slate-500" />
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-12">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold text-slate-500">Who Uses This</div>
            <div className="mt-2 text-sm font-semibold text-slate-900">Non‑technical teams</div>
            <div className="mt-2 text-sm text-slate-600">
              실행 버튼과 자동 검증으로 운영합니다. 토글과 가이드만 보면 됩니다.
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold text-slate-500">What You Control</div>
            <div className="mt-2 text-sm font-semibold text-slate-900">Quality, Approval, Training</div>
            <div className="mt-2 text-sm text-slate-600">
              증거 기반 승인과 자동 학습 루프로 품질을 올립니다.
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-xs font-semibold text-slate-500">Where You Start</div>
            <div className="mt-2 text-sm font-semibold text-slate-900">Setup → Ingest → Approve</div>
            <div className="mt-2 text-sm text-slate-600">처음 30분 안에 엔드투엔드 흐름을 완료합니다.</div>
          </div>
        </div>
      </section>

      <section id="pipelines" className="mx-auto max-w-6xl px-6 pb-16">
        <SectionHeader title="Pipeline Operations" subtitle="Pipelines" />
        <div className="grid gap-4 md:grid-cols-3">
          {filteredPipelines.map((card) => (
            <Card key={card.title} {...card} />
          ))}
        </div>
        {filteredPipelines.length === 0 && (
          <div className="mt-3 text-sm text-slate-500">No pipeline matches.</div>
        )}
      </section>

      <section id="operations" className="mx-auto max-w-6xl px-6 pb-16">
        <SectionHeader title="Core Operations" subtitle="Operations" />
        <div className="grid gap-4 md:grid-cols-3">
          {filteredOps.map((card) => (
            <Card key={card.title} {...card} />
          ))}
        </div>
        {filteredOps.length === 0 && (
          <div className="mt-3 text-sm text-slate-500">No operations match.</div>
        )}
      </section>

      <section id="models" className="mx-auto max-w-6xl px-6 pb-16">
        <SectionHeader title="Model Control" subtitle="Models" />
        <div className="grid gap-4 md:grid-cols-3">
          {filteredModels.map((card) => (
            <Card key={card.title} {...card} />
          ))}
        </div>
        {filteredModels.length === 0 && (
          <div className="mt-3 text-sm text-slate-500">No models match.</div>
        )}
      </section>

      <section id="governance" className="mx-auto max-w-6xl px-6 pb-16">
        <SectionHeader title="Governance & Compliance" subtitle="Governance" />
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Unity Catalog Policies" desc="Grant, audit, and enforce access across tenants." href="/governance" />
          <Card title="Audit Trail" desc="Immutable logs and compliance export bundles." href="/audit" />
        </div>
      </section>

      <section id="logs" className="mx-auto max-w-6xl px-6 pb-20">
        <SectionHeader title="Operational Logs" subtitle="Logs" />
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Pipeline Logs" desc="Filter audit events by pipeline, tenant, or actor." href="/logs" />
          <Card title="Service Tail" desc="Backend/worker/event_worker logs in one place." href="/logs" />
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-6 text-xs text-slate-500">
          <div className="inline-flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            All operations are centralized and auditable.
          </div>
          <div className="inline-flex items-center gap-3">
            <Link href="/settings" className="text-slate-600 hover:text-slate-900">Settings</Link>
            <Link href="/mlops" className="text-slate-600 hover:text-slate-900">MLOps</Link>
            <Link href="/logs" className="text-slate-600 hover:text-slate-900">Logs</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
