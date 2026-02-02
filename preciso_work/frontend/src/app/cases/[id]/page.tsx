"use client";

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

export default function CaseDetailPage() {
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
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3 mb-2">
            <span className="px-2 py-0.5 bg-primary/20 text-primary text-[10px] font-bold rounded uppercase tracking-tighter">High Priority</span>
            <span className="text-muted text-sm font-mono">CASE-2026-0042</span>
          </div>
          <h2 className="text-3xl font-bold tracking-tight">NVIDIA Corp (NVDA) - Q4 Review</h2>
          <p className="text-muted mt-1">Intelligence analysis of FY2025 Annual Disclosure</p>
        </div>
        <div className="flex gap-3">
          <button className="px-4 py-2 bg-glass border border-border rounded-lg text-sm font-bold hover:bg-white/5">Audit Trail</button>
          <button className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-bold shadow-lg shadow-primary/20">Finalize Decision</button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: Progress Timeline */}
        <div className="lg:col-span-1 space-y-4">
          <h3 className="text-sm font-bold text-muted uppercase tracking-widest px-1">Pipeline Timeline</h3>
          <div className="glass-panel p-6 space-y-0 relative">
            {steps.map((step, i) => (
              <div key={step.id} className="relative pb-8 last:pb-0">
                {i < steps.length - 1 && (
                  <div className="absolute left-2.5 top-7 bottom-0 w-0.5 bg-border" />
                )}
                <div className="flex gap-4 items-start relative">
                  <div className={`mt-1 w-5 h-5 rounded-full flex items-center justify-center z-10 ${
                    step.status === 'complete' ? 'bg-secondary text-black' : 
                    step.status === 'processing' ? 'bg-primary text-white animate-pulse' : 
                    'bg-border text-muted'
                  }`}>
                    {step.status === 'complete' ? <CheckCircle2 size={12} strokeWidth={3} /> : 
                     step.status === 'processing' ? <Zap size={10} fill="currentColor" /> : 
                     <div className="w-1 h-1 rounded-full bg-muted" />}
                  </div>
                  <div>
                    <h4 className={`text-sm font-bold ${step.status === 'pending' ? 'text-muted' : 'text-foreground'}`}>
                      {step.label}
                    </h4>
                    <p className="text-xs text-muted mt-0.5 leading-relaxed">{step.desc}</p>
                    <span className="text-[10px] font-mono font-bold text-primary/80 mt-2 block tracking-tight uppercase">
                      {step.meta}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: Data Analysis View */}
        <div className="lg:col-span-2 space-y-6">
          <div className="grid grid-cols-2 gap-4">
            <div className="glass-panel p-4 space-y-2">
              <div className="flex items-center gap-2 text-muted">
                <FileText size={14} />
                <span className="text-[10px] font-bold uppercase tracking-widest">Evidence Node</span>
              </div>
              <p className="text-sm font-medium">"Data Center Revenue grew by 409% YoY, driven by H100 demand."</p>
              <div className="pt-2 border-t border-border flex justify-between items-center">
                <span className="text-[10px] text-muted font-mono">Source: SEC 10-K Pg. 42</span>
                <button className="text-primary text-[10px] font-bold hover:underline">View Source</button>
              </div>
            </div>
            <div className="glass-panel p-4 space-y-2 border-primary/30">
              <div className="flex items-center gap-2 text-primary">
                <ShieldAlert size={14} />
                <span className="text-[10px] font-bold uppercase tracking-widest">Reflection Insight</span>
              </div>
              <p className="text-sm font-medium">Original extraction missed $1.2B in accounts receivable offset. Corrected in Round 2.</p>
              <div className="pt-2 border-t border-border flex justify-between items-center">
                <span className="text-[10px] text-muted font-mono">Confidence: High (0.982)</span>
              </div>
            </div>
          </div>

          <div className="glass-panel h-80 flex flex-col items-center justify-center text-center p-8 border-dashed">
            <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center text-primary mb-4">
              <Search className="animate-bounce" size={24} />
            </div>
            <h4 className="font-bold">Oracle Simulation in Progress</h4>
            <p className="text-sm text-muted max-w-xs mt-2">
              The engine is currently calculating causal propagation across 42 dependent entities in the semiconductor supply chain.
            </p>
            <div className="w-full max-w-xs bg-border h-1 rounded-full mt-6 overflow-hidden">
              <div className="bg-primary h-full w-2/3 rounded-full animate-progress" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
