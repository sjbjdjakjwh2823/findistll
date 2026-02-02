import React from "react";
import { 
  CheckCircle2, 
  Search, 
  ArrowRight, 
  FileText, 
  Zap, 
  ShieldAlert,
  ArrowDown
} from "lucide-react";

export function generateStaticParams() {
  return [{ id: 'sample-case' }];
}

export const dynamic = 'force-static';
export const dynamicParams = false;

export default async function CaseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const steps = [
    { 
      id: "ingest", 
      label: "Ingestion", 
      status: "complete", 
      desc: "SEC 10-K parsed with high-res OCR.",
      meta: "4.2 MB processed"
    },
    { 
      id: "reflect", 
      label: "Self-Reflection (Pillar 1)", 
      status: "complete", 
      desc: "2 rounds of critique-repair loop finished. Hallucinations eliminated.",
      meta: "99.9% precision"
    },
    { 
      id: "graph", 
      label: "Ontology Mapping", 
      status: "complete", 
      desc: "Causal links established in Spoke D.",
      meta: "12 new edges"
    },
    { 
      id: "predict", 
      label: "Oracle Simulation", 
      status: "processing", 
      desc: "Projecting counterfactual impacts for interest rate hikes.",
      meta: "8-Hop depth"
    },
    { 
      id: "decide", 
      label: "Robot Decision", 
      status: "pending", 
      desc: "Layer 4 RAG-FLARKO evidence synthesis.",
      meta: "Awaiting simulation"
    }
  ];

  return (
    <div className="p-8 space-y-8 max-w-5xl mx-auto">
      <div className="flex justify-between items-start border-b border-border pb-6">
        <div>
          <div className="flex items-center gap-3 mb-2 font-mono text-[11px] text-primary">
            <span className="px-2 py-0.5 bg-primary/20 border border-primary/40 rounded uppercase">High Priority</span>
            <span>Ref ID: CASE-2026-0042-{id}</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-white uppercase">NVIDIA Corp (NVDA)</h2>
          <p className="text-muted mt-1 font-mono text-xs">AIP-DRIVEN ANALYTIC WORKSPACE // VERSION 2.0.4</p>
        </div>
        <div className="flex gap-3">
          <button className="px-4 py-2 bg-[#182026] border border-border rounded shadow-sm text-sm font-semibold text-white/90 hover:bg-[#202b33]">Audit Trail</button>
          <button className="px-4 py-2 bg-[#106ba3] hover:bg-[#137cbd] text-white rounded shadow-sm text-sm font-bold">RELEASE DECISION</button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 space-y-4">
          <h3 className="text-xs font-bold text-muted uppercase tracking-[0.2em] px-1 border-l-2 border-primary ml-1 pl-3">Data Lineage</h3>
          <div className="bg-[#182026] border border-border p-6 space-y-0 relative shadow-xl">
            {steps.map((step, i) => (
              <div key={step.id} className="relative pb-8 last:pb-0">
                {i < steps.length - 1 && (
                  <div className="absolute left-[9px] top-7 bottom-0 w-px bg-border/50" />
                )}
                <div className="flex gap-5 items-start relative">
                  <div className={`mt-1.5 w-4 h-4 rounded-full border-2 flex items-center justify-center z-10 ${
                    step.status === 'complete' ? 'bg-secondary border-secondary shadow-[0_0_8px_rgba(16,185,129,0.4)]' : 
                    step.status === 'processing' ? 'bg-primary border-primary animate-pulse shadow-[0_0_8px_rgba(72,175,240,0.4)]' : 
                    'bg-[#202b33] border-border'
                  }`}>
                    {step.status === 'complete' && <div className="w-1.5 h-1.5 bg-white rounded-full" />}
                  </div>
                  <div>
                    <h4 className={`text-xs font-bold uppercase tracking-wider ${step.status === 'pending' ? 'text-muted' : 'text-white'}`}>
                      {step.label}
                    </h4>
                    <p className="text-[11px] text-muted mt-1">{step.desc}</p>
                    <div className="mt-2 flex gap-3">
                        <span className="text-[10px] font-mono text-primary bg-primary/10 px-1.5 py-0.5 rounded uppercase">
                        {step.meta}
                        </span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-2 space-y-6">
          <div className="flex items-center gap-4 bg-[#182026] border border-border p-3">
             <div className="p-2 bg-indigo-500/10 text-primary border border-primary/20">
                <FileText size={20} />
             </div>
             <div>
                <p className="text-xs font-bold text-white uppercase tracking-wider">Master Document</p>
                <p className="text-[11px] text-muted">SEC-FILING-10K-NVDA-2025.pdf (Verified)</p>
             </div>
          </div>

          <div className="grid grid-cols-2 gap-4 font-mono">
            <div className="bg-[#1c2127] border border-border p-4 space-y-3 shadow-inner">
              <div className="flex items-center gap-2 text-muted border-b border-border/30 pb-2">
                <span className="text-[10px] font-bold uppercase tracking-widest">Raw Fact #4102</span>
              </div>
              <p className="text-xs leading-relaxed italic text-white/70">"Data Center Revenue grew by 409% YoY..."</p>
              <div className="flex justify-between items-center pt-1">
                <span className="text-[9px] bg-[#293742] px-1 text-white">REF: P42.L12</span>
                <button className="text-primary text-[10px] hover:text-sky-400">View Source</button>
              </div>
            </div>
            <div className="bg-[#1c2127] border border-primary/20 p-4 space-y-3 relative overflow-hidden shadow-inner">
              <div className="absolute top-0 right-0 p-1 bg-primary/10 border-l border-b border-primary/20">
                  <ShieldAlert size={12} className="text-primary" />
              </div>
              <div className="flex items-center gap-2 text-primary border-b border-primary/10 pb-2">
                <span className="text-[10px] font-bold uppercase tracking-widest">Self-Correction</span>
              </div>
              <p className="text-xs leading-relaxed text-white/90">Validated against Balance Sheet Page 89. Adjusted for FX headwinds.</p>
              <div className="flex justify-between items-center pt-1">
                <span className="text-[9px] text-secondary">CERTAINTY: 0.998</span>
              </div>
            </div>
          </div>

          <div className="bg-[#182026] border border-border h-64 flex flex-col items-center justify-center text-center p-8 relative overflow-hidden">
            <div className="absolute inset-0 opacity-10 pointer-events-none overflow-hidden">
                <div className="grid grid-cols-12 gap-1 w-full h-full">
                    {Array.from({length: 48}).map((_, i) => (
                        <div key={i} className="border-r border-b border-white/20 h-8 w-full" />
                    ))}
                </div>
            </div>
            <div className="z-10">
                <div className="w-12 h-12 bg-primary/10 border border-primary/30 rounded-lg flex items-center justify-center text-primary mb-4 mx-auto">
                <Zap className="animate-pulse" size={24} />
                </div>
                <h4 className="font-bold text-white uppercase tracking-[0.2em]">Causal Oracle Active</h4>
                <p className="text-xs text-muted max-w-sm mt-3 font-mono leading-relaxed">
                SIMULATING SEMICONDUCTOR VALUE CHAIN PROPAGATION...
                IDENTIFYING CORRELATIONS AT DEPTH 8...
                </p>
                <div className="w-48 bg-black/40 border border-border h-1.5 rounded-full mt-6 mx-auto overflow-hidden">
                <div className="bg-primary h-full w-3/4 rounded-full" />
                </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
