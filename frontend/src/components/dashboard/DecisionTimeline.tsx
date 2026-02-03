"use client";

import React from "react";
import { CheckCircle, ArrowRight, GitCommit, FileText, BrainCircuit, Gavel } from "lucide-react";

type TimelineStep = {
  id: string;
  type: "evidence" | "cot" | "decision";
  title: string;
  description: string;
  timestamp: string;
  status: "completed" | "active" | "pending";
};

const steps: TimelineStep[] = [
  {
    id: "step_1",
    type: "evidence",
    title: "Data Ingestion & Extraction",
    description: "Ingested 'Fed Minutes' & '10Y Yield' data. Validated by 3 self-reflection agents.",
    timestamp: "10:00:23 AM",
    status: "completed",
  },
  {
    id: "step_2",
    type: "cot",
    title: "Chain-of-Thought Reasoning",
    description: "Agent Macro identified inflation persistence. Agent Risk flagged duration exposure.",
    timestamp: "10:00:25 AM",
    status: "completed",
  },
  {
    id: "step_3",
    type: "decision",
    title: "Draft Proposal Generated",
    description: "Proposed 280bps cut to duration software. Confidence Score: 87%.",
    timestamp: "10:00:28 AM",
    status: "active",
  },
];

const icons = {
  evidence: FileText,
  cot: BrainCircuit,
  decision: Gavel,
};

const colors = {
  evidence: "text-blue-400 border-blue-400/30 bg-blue-400/10",
  cot: "text-purple-400 border-purple-400/30 bg-purple-400/10",
  decision: "text-green-400 border-green-400/30 bg-green-400/10",
};

export default function DecisionTimeline() {
  return (
    <div className="border border-[#30404d] bg-[#202b33] flex flex-col h-full">
      <div className="h-10 border-b border-[#30404d] bg-[#293742] flex items-center justify-between px-4 shrink-0">
        <h2 className="text-xs font-bold tracking-wider uppercase text-[#a7b6c2] font-mono">Decision Timeline</h2>
        <span className="text-[10px] text-[#21ce99] font-mono flex items-center gap-1">
          <GitCommit size={10} /> LIVE
        </span>
      </div>
      
      <div className="p-4 space-y-6 overflow-y-auto bg-[#1a1c1e] flex-1">
        {steps.map((step, index) => {
          const Icon = icons[step.type];
          const colorClass = colors[step.type];
          const isLast = index === steps.length - 1;

          return (
            <div key={step.id} className="relative flex gap-4">
              {/* Connector Line */}
              {!isLast && (
                <div className="absolute left-[15px] top-8 bottom-[-24px] w-px bg-[#30404d]" />
              )}
              
              {/* Icon Bubble */}
              <div className={`shrink-0 w-8 h-8 rounded-full border flex items-center justify-center z-10 ${colorClass}`}>
                <Icon size={14} />
              </div>

              {/* Content */}
              <div className="flex-1 space-y-1 pt-1">
                <div className="flex justify-between items-start">
                  <h3 className="text-sm font-bold text-[#f6f7f9]">{step.title}</h3>
                  <span className="text-[10px] font-mono text-[#5c7080]">{step.timestamp}</span>
                </div>
                <p className="text-xs text-[#a7b6c2] leading-relaxed">
                  {step.description}
                </p>
                
                {step.status === "completed" && (
                   <div className="pt-1 flex items-center gap-1 text-[10px] text-[#21ce99] font-bold uppercase tracking-wider">
                      <CheckCircle size={10} /> Verified
                   </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
