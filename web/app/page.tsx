import Link from "next/link";
import { Space_Grotesk, Fraunces } from "next/font/google";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import {
  ArrowUpRight,
  CheckCircle2,
  ShieldCheck,
  Database,
  Cpu,
  Sparkles,
  LineChart,
  ClipboardCheck,
  Building2,
  BookOpen,
  Network,
} from "lucide-react";

const space = Space_Grotesk({ subsets: ["latin"], weight: ["400", "500", "600", "700"] });
const fraunces = Fraunces({ subsets: ["latin"], weight: ["600", "700"] });

const NAV = [
  { label: "Products", href: "#products" },
  { label: "Platform", href: "#platform" },
  { label: "Solutions", href: "#solutions" },
  { label: "Security", href: "#security" },
  { label: "Resources", href: "#resources" },
];

const PRODUCT_CARDS = [
  {
    title: "Preciso Data Engine",
    desc: "Findistill + DataForge: document normalization, evidence, and quality gates.",
    icon: Database,
  },
  {
    title: "Preciso AI Brain",
    desc: "PinRobot with RAG + causal graph for auditable decisions.",
    icon: Cpu,
  },
  {
    title: "Preciso Lakehouse",
    desc: "Delta/Spark/MLflow/Unity Catalog for lineage and reproducibility.",
    icon: Network,
  },
];

const PLATFORM_FEATURES = [
  {
    title: "Evidence-First RAG",
    desc: "All claims trace back to evidence with numeric consistency checks.",
    icon: ClipboardCheck,
  },
  {
    title: "Approval to Training",
    desc: "Auto-train on approval or batch datasets with one click.",
    icon: Sparkles,
  },
  {
    title: "Enterprise Operations",
    desc: "RBAC, tenant isolation, rate limits, and full audit logs.",
    icon: ShieldCheck,
  },
];

const SOLUTIONS = [
  { title: "Risk Intelligence", desc: "Portfolio stress, contagion, and early-warning signals." },
  { title: "Compliance Ops", desc: "Audit-ready evidence, immutable logs, and approvals." },
  { title: "Treasury & Liquidity", desc: "Macro-aware forecasting and cashflow risk analytics." },
  { title: "Research Teams", desc: "Cross-source reasoning with RAG + causal narratives." },
];

const PIPELINE = [
  "Ingest multi-format financial data",
  "Normalize facts + tables with evidence",
  "Route to HITL approval",
  "Generate Spoke A/B/C/D outputs",
  "Auto-train or batch fine-tune",
  "Serve decisions with governance",
];

const LOGOS = ["NovaBank", "Atlas Capital", "Helios Gov", "BlueRock AM", "Argent Treasury", "Kite Research"];

const CASE_STUDIES = [
  {
    title: "Global Bank",
    metric: "85% faster approvals",
    summary: "Automated evidence checks cut review time while improving audit quality.",
  },
  {
    title: "Asset Manager",
    metric: "3x signal coverage",
    summary: "RAG + causal graph increased cross-source insight coverage by 3x.",
  },
  {
    title: "Treasury Team",
    metric: "99.9% audit SLA",
    summary: "Immutable logs and governance workflows passed strict compliance gates.",
  },
];

function SectionHeading({ label, title, subtitle }: { label: string; title: string; subtitle: string }) {
  return (
    <div className="mb-10">
      <div className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">{label}</div>
      <h2 className={`mt-4 text-3xl font-semibold text-slate-900 ${fraunces.className}`}>{title}</h2>
      <p className="mt-3 text-base text-slate-600 max-w-3xl">{subtitle}</p>
    </div>
  );
}

export default async function HomePage() {
  const session = await getServerSession(authOptions);
  if (session?.user) {
    redirect("/ops-console");
  }
  return (
    <div className={`min-h-screen bg-[#f7f6f2] text-slate-900 ${space.className}`}>
      <header className="sticky top-0 z-30 border-b border-slate-200/70 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-full bg-slate-900" />
            <div>
              <div className="text-sm font-semibold">Preciso</div>
              <div className="text-xs text-slate-500">Financial Intelligence Platform</div>
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
              href="/auth/login"
              className="hidden rounded-full border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-700 hover:border-slate-300 md:inline-flex"
            >
              Log In
            </Link>
            <Link
              href="/auth/signup"
              className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
            >
              Get Started
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid gap-12 md:grid-cols-[1.15fr_0.85fr]">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold text-slate-600">
              Breakthrough financial AI, from data to deployment
            </div>
            <h1 className={`mt-6 text-4xl font-semibold leading-tight md:text-5xl ${fraunces.className}`}>
              Preciso powers audited decisions
              <span className="block text-slate-700">across markets, risk, and compliance.</span>
            </h1>
            <p className="mt-4 text-base text-slate-600 max-w-xl">
              Convert financial documents into evidence-backed intelligence. Automate approvals, training, and
              production-grade RAG with full governance.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/ops-console"
                className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
              >
                Launch Console
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
              <Link
                href="/dataforge"
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700"
              >
                Start Ingest
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>
            <div className="mt-8 grid grid-cols-2 gap-3 text-xs text-slate-500 md:grid-cols-4">
              {["Banks", "Asset Managers", "Gov/Regulators", "Enterprises"].map((item) => (
                <div key={item} className="rounded-full border border-slate-200 bg-white px-3 py-1 text-center">
                  {item}
                </div>
              ))}
            </div>
          </div>
          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="text-xs font-semibold text-slate-500">Live System Status</div>
              <div className="mt-4 flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center animate-pulse">
                  <CheckCircle2 className="h-5 w-5" />
                </div>
                <div>
                  <div className="text-sm font-semibold">All pipelines operational</div>
                  <div className="text-xs text-slate-500">RAG, Training, Lakehouse, Audit</div>
                </div>
              </div>
              <div className="mt-6 grid grid-cols-2 gap-3 text-xs text-slate-500">
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">P95 RAG: 1.2s</div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">Approval SLA: 99.9%</div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">Training: Auto + Batch</div>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">Audit: Immutable</div>
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-white to-slate-50 p-6 shadow-sm">
              <div className="text-xs font-semibold text-slate-500">Core Modules</div>
              <div className="mt-4 space-y-3 text-sm text-slate-700">
                <div className="flex items-center gap-2"><Building2 className="h-4 w-4" /> Financial Document Engine</div>
                <div className="flex items-center gap-2"><LineChart className="h-4 w-4" /> Market + Macro Fusion</div>
                <div className="flex items-center gap-2"><BookOpen className="h-4 w-4" /> Evidence & Governance</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16">
        <div className="rounded-2xl border border-slate-200 bg-white px-6 py-5 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Trusted By</div>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm text-slate-600 md:grid-cols-6">
            {LOGOS.map((logo) => (
              <div key={logo} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-center">
                {logo}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="products" className="mx-auto max-w-6xl px-6 pb-16">
        <SectionHeading
          label="Products"
          title="Full-stack financial AI platform"
          subtitle="Preciso unifies data, approvals, and decisioning into one secure system."
        />
        <div className="grid gap-4 md:grid-cols-3">
          {PRODUCT_CARDS.map((card) => {
            const Icon = card.icon;
            return (
              <div key={card.title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-900 text-white">
                  <Icon className="h-5 w-5" />
                </div>
                <div className="mt-4 text-sm font-semibold text-slate-900">{card.title}</div>
                <div className="mt-2 text-sm text-slate-600">{card.desc}</div>
              </div>
            );
          })}
        </div>
      </section>

      <section id="platform" className="mx-auto max-w-6xl px-6 pb-16">
        <SectionHeading
          label="Platform"
          title="From ingestion to deployment"
          subtitle="Every step is evidence-backed, audited, and production-grade."
        />
        <div className="grid gap-4 md:grid-cols-3">
          {PLATFORM_FEATURES.map((feature) => {
            const Icon = feature.icon;
            return (
              <div key={feature.title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-900 text-white">
                  <Icon className="h-5 w-5" />
                </div>
                <div className="mt-4 text-sm font-semibold text-slate-900">{feature.title}</div>
                <div className="mt-2 text-sm text-slate-600">{feature.desc}</div>
              </div>
            );
          })}
        </div>
        <div className="mt-8 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="text-xs font-semibold text-slate-500">Pipeline Flow</div>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {PIPELINE.map((step) => (
              <div key={step} className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                {step}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="solutions" className="mx-auto max-w-6xl px-6 pb-16">
        <SectionHeading
          label="Solutions"
          title="Built for finance-grade operations"
          subtitle="Preciso serves the teams that need reliability, transparency, and speed."
        />
        <div className="grid gap-4 md:grid-cols-2">
          {SOLUTIONS.map((item) => (
            <div key={item.title} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="text-sm font-semibold text-slate-900">{item.title}</div>
              <div className="mt-2 text-sm text-slate-600">{item.desc}</div>
            </div>
          ))}
        </div>
        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {CASE_STUDIES.map((item) => (
            <div key={item.title} className="rounded-2xl border border-slate-200 bg-slate-50 p-5 shadow-sm">
              <div className="text-xs uppercase tracking-[0.2em] text-slate-500">{item.title}</div>
              <div className={`mt-3 text-2xl font-semibold text-slate-900 ${fraunces.className}`}>{item.metric}</div>
              <div className="mt-2 text-sm text-slate-600">{item.summary}</div>
            </div>
          ))}
        </div>
      </section>

      <section id="security" className="mx-auto max-w-6xl px-6 pb-16">
        <SectionHeading
          label="Security"
          title="Governance built-in"
          subtitle="Tenant isolation, RBAC, and immutable audit trails are default." 
        />
        <div className="grid gap-4 md:grid-cols-3">
          {[
            "RBAC + OIDC optional",
            "Tenant isolation with hard gates",
            "Audit logs and evidence lineage",
            "Rate limiting and policy engine",
            "Data retention controls",
            "Redaction + egress controls",
          ].map((item) => (
            <div key={item} className="rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
              {item}
            </div>
          ))}
        </div>
      </section>

      <section id="resources" className="mx-auto max-w-6xl px-6 pb-20">
        <SectionHeading
          label="Resources"
          title="Operate with confidence"
          subtitle="Docs, runbooks, and system dashboards are built into the platform UI."
        />
        <div className="grid gap-4 md:grid-cols-3">
          <Link href="/ops-console" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-sm font-semibold text-slate-900">Operations Console</div>
            <div className="mt-2 text-sm text-slate-600">Single hub for every pipeline.</div>
          </Link>
          <Link href="/logs" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-sm font-semibold text-slate-900">Logs & Audits</div>
            <div className="mt-2 text-sm text-slate-600">Pipeline logs and immutable trails.</div>
          </Link>
          <Link href="/mlops" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="text-sm font-semibold text-slate-900">MLOps Workspace</div>
            <div className="mt-2 text-sm text-slate-600">Model registry, training, and serving.</div>
          </Link>
        </div>
        <div className="mt-10 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="grid gap-6 md:grid-cols-[1.1fr_0.9fr]">
            <div>
              <div className="text-xs font-semibold uppercase tracking-[0.3em] text-slate-500">Book a Demo</div>
              <h3 className={`mt-4 text-2xl font-semibold text-slate-900 ${fraunces.className}`}>
                See Preciso running on your data
              </h3>
              <p className="mt-3 text-sm text-slate-600">
                Share your requirements and we will tailor an onboarding path for your team.
              </p>
              <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                30-minute guided setup
              </div>
            </div>
            <form className="grid gap-3 text-sm">
              <input
                placeholder="Full name"
                className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
              />
              <input
                placeholder="Work email"
                className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
              />
              <input
                placeholder="Company"
                className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
              />
              <textarea
                placeholder="What do you want to automate?"
                className="min-h-[90px] rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
              />
              <button
                type="button"
                className="inline-flex items-center justify-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white"
              >
                Request Demo
                <ArrowUpRight className="h-3.5 w-3.5" />
              </button>
              <div className="text-[11px] text-slate-500">
                This form is UI-only in the MVP. Connect your CRM endpoint when ready.
              </div>
            </form>
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-6 py-6 text-xs text-slate-500">
          <div>Preciso — Financial Intelligence Platform</div>
          <div className="flex items-center gap-4">
            <Link href="/ops-console" className="hover:text-slate-900">Console</Link>
            <Link href="/settings" className="hover:text-slate-900">Settings</Link>
            <Link href="/audit" className="hover:text-slate-900">Audit</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
