"use client";

import React, { useState } from "react";
import { 
  FileText, 
  Zap, 
  ShieldAlert,
  X
} from "lucide-react";
import { Button, Drawer, Position } from "@blueprintjs/core";
import dynamic from 'next/dynamic';

const LineageViewer = dynamic(() => import("@/components/dashboard/LineageViewer"), {
  ssr: false,
});

export default function CaseDetailClient({ id }: { id: string }) {
  const [showLineage, setShowLineage] = useState(false);
  const [activeHighlight, setActiveHighlight] = useState<{page: number, box: [number, number, number, number]} | undefined>(undefined);

  const mockFacts = [
    { 
      statement: "Data Center Revenue grew by 409% YoY", 
      ref: "P1.L1", 
      anchor: { page: 1, box: [100, 138, 300, 155] as [number, number, number, number] } 
    },
    { 
      statement: "Operating margin increased to 62.3%", 
      ref: "P1.L5", 
      anchor: { page: 1, box: [100, 180, 250, 195] as [number, number, number, number] } 
    }
  ];

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
    <div className="h-full flex flex-col bg-[#1a1c1e] text-[#f6f7f9] overflow-y-auto">
      {/* Detail Header */}
      <div className="border-b border-[#30404d] bg-[#202b33] p-6 shrink-0 flex justify-between items-start">
        <div>
          <div className="flex items-center gap-3 mb-2 font-mono text-[11px] text-[#2B95D6]">
            <span className="px-2 py-0.5 bg-[#2B95D6]/20 border border-[#2B95D6]/40 uppercase">High Priority</span>
            <span>Ref ID: CASE-2026-0042-{id}</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-[#f6f7f9] uppercase">NVIDIA Corp (NVDA)</h2>
          <p className="text-[#5c7080] mt-1 font-mono text-xs">AIP-DRIVEN ANALYTIC WORKSPACE // VERSION 2.0.4</p>
        </div>
        <div className="flex gap-3">
          <Button icon="history" text="Audit Trail" minimal className="!text-[#a7b6c2]" />
          <Button intent="primary" text="RELEASE DECISION" className="!font-bold !rounded-none" />
        </div>
      </div>

      <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-1 space-y-4">
          <h3 className="text-xs font-bold text-[#5c7080] uppercase tracking-[0.2em] px-1 border-l-2 border-[#2B95D6] ml-1 pl-3">Data Lineage</h3>
          <div className="bg-[#182026] border border-[#30404d] p-6 space-y-0 relative shadow-none">
            {steps.map((step, i) => (
              <div key={step.id} className="relative pb-8 last:pb-0">
                {i < steps.length - 1 && (
                  <div className="absolute left-[9px] top-7 bottom-0 w-px bg-[#30404d]" />
                )}
                <div className="flex gap-5 items-start relative">
                  <div className={`mt-1.5 w-4 h-4 flex items-center justify-center z-10 border border-transparent ${
                    step.status === 'complete' ? 'bg-[#21ce99] shadow-[0_0_8px_rgba(33,206,153,0.4)]' : 
                    step.status === 'processing' ? 'bg-[#2B95D6] animate-pulse shadow-[0_0_8px_rgba(43,149,214,0.4)]' : 
                    'bg-[#202b33] border-[#30404d]'
                  }`}>
                    {step.status === 'complete' && <div className="w-1.5 h-1.5 bg-[#1a1c1e]" />}
                  </div>
                  <div>
                    <h4 className={`text-xs font-bold uppercase tracking-wider ${step.status === 'pending' ? 'text-[#5c7080]' : 'text-[#f6f7f9]'}`}>
                      {step.label}
                    </h4>
                    <p className="text-[11px] text-[#5c7080] mt-1">{step.desc}</p>
                    <div className="mt-2 flex gap-3">
                        <span className="text-[10px] font-mono text-[#2B95D6] bg-[#2B95D6]/10 px-1.5 py-0.5 uppercase border border-[#2B95D6]/20">
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
          <div className="flex items-center gap-4 bg-[#182026] border border-[#30404d] p-3">
             <div className="p-2 bg-[#2B95D6]/10 text-[#2B95D6] border border-[#2B95D6]/20">
                <FileText size={20} />
             </div>
             <div>
                <p className="text-xs font-bold text-[#f6f7f9] uppercase tracking-wider">Master Document</p>
                <p className="text-[11px] text-[#5c7080]">SEC-FILING-10K-NVDA-2025.pdf (Verified)</p>
             </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 font-mono">
            {mockFacts.map((fact, idx) => (
              <div key={idx} className="bg-[#1c2127] border border-[#30404d] p-4 space-y-3">
                <div className="flex items-center gap-2 text-[#5c7080] border-b border-[#30404d] pb-2">
                  <span className="text-[10px] font-bold uppercase tracking-widest">Raw Fact #{4102 + idx}</span>
                </div>
                <p className="text-xs leading-relaxed italic text-[#f6f7f9]/70">"{fact.statement}"</p>
                <div className="flex justify-between items-center pt-1">
                  <span className="text-[9px] bg-[#293742] px-1 text-[#f6f7f9]">REF: {fact.ref}</span>
                  <button 
                    onClick={() => {
                      setActiveHighlight(fact.anchor);
                      setShowLineage(true);
                    }}
                    className="text-[#2B95D6] text-[10px] hover:text-[#4CAEE8] hover:underline"
                  >
                    View Source
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="bg-[#182026] border border-[#30404d] h-64 flex flex-col items-center justify-center text-center p-8 relative overflow-hidden">
            <div className="absolute inset-0 opacity-10 pointer-events-none overflow-hidden">
                <div className="grid grid-cols-12 gap-1 w-full h-full">
                    {Array.from({length: 48}).map((_, i) => (
                        <div key={i} className="border-r border-b border-[#f6f7f9]/20 h-8 w-full" />
                    ))}
                </div>
            </div>
            <div className="z-10">
                <div className="w-12 h-12 bg-[#2B95D6]/10 border border-[#2B95D6]/30 flex items-center justify-center text-[#2B95D6] mb-4 mx-auto">
                <Zap className="animate-pulse" size={24} />
                </div>
                <h4 className="font-bold text-[#f6f7f9] uppercase tracking-[0.2em]">Causal Oracle Active</h4>
                <p className="text-xs text-[#5c7080] max-w-sm mt-3 font-mono leading-relaxed">
                SIMULATING SEMICONDUCTOR VALUE CHAIN PROPAGATION...
                IDENTIFYING CORRELATIONS AT DEPTH 8...
                </p>
                <div className="w-48 bg-black/40 border border-[#30404d] h-1.5 mt-6 mx-auto overflow-hidden">
                <div className="bg-[#2B95D6] h-full w-3/4" />
                </div>
            </div>
          </div>
        </div>
      </div>

      <Drawer
        isOpen={showLineage}
        onClose={() => setShowLineage(false)}
        position={Position.RIGHT}
        size="50%"
        title={
          <div className="flex items-center gap-2 text-[#f6f7f9] uppercase tracking-widest text-xs font-bold">
            <FileText size={14} className="text-[#2B95D6]" />
            <span>Pixel-Level Data Lineage</span>
          </div>
        }
        className="!bg-[#1a1c1e] !text-[#f6f7f9] border-l border-[#30404d]"
      >
        <div className="h-full flex flex-col">
          <div className="p-4 bg-[#202b33] border-b border-[#30404d] flex justify-between items-center">
             <div className="font-mono text-[10px] text-[#5c7080]">
                SOURCE: SEC-FILING-10K-NVDA-2025.pdf
             </div>
             <Button icon="cross" minimal onClick={() => setShowLineage(false)} />
          </div>
          <div className="flex-1 overflow-hidden">
             <LineageViewer 
                fileUrl="/sample.pdf" 
                highlight={activeHighlight} 
             />
          </div>
        </div>
      </Drawer>
    </div>
  );
}
