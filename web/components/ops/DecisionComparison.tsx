import React from "react";

interface DecisionComparisonProps {
  aiDecision: {
    decision: string;
    confidence: number;
    actions: string[];
    reasoning: string[];
  };
  humanDecision: {
    decision: string;
    confidence: number;
    actions: string[];
    notes: string;
  };
}

export function DecisionComparison({ aiDecision, humanDecision }: DecisionComparisonProps) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div className="rounded-lg border border-white/10 bg-black/40 p-4">
        <div className="text-xs text-neutral-500 mb-2">AI Proposal</div>
        <div className="text-sm text-white">{aiDecision.decision}</div>
        <div className="text-xs text-neutral-400 mt-2">Confidence {aiDecision.confidence}</div>
        <div className="text-[11px] text-neutral-500 mt-3">Actions</div>
        <ul className="mt-2 space-y-1 text-xs text-neutral-300">
          {aiDecision.actions.map((action, idx) => (
            <li key={idx}>{action}</li>
          ))}
        </ul>
        <div className="text-[11px] text-neutral-500 mt-3">Reasoning</div>
        <ul className="mt-2 space-y-1 text-xs text-neutral-300">
          {aiDecision.reasoning.map((reason, idx) => (
            <li key={idx}>{reason}</li>
          ))}
        </ul>
      </div>
      <div className="rounded-lg border border-white/10 bg-black/40 p-4">
        <div className="text-xs text-neutral-500 mb-2">Human Edit</div>
        <div className="text-sm text-white">{humanDecision.decision}</div>
        <div className="text-xs text-neutral-400 mt-2">Confidence {humanDecision.confidence}</div>
        <div className="text-[11px] text-neutral-500 mt-3">Actions</div>
        <ul className="mt-2 space-y-1 text-xs text-neutral-300">
          {humanDecision.actions.map((action, idx) => (
            <li key={idx}>{action}</li>
          ))}
        </ul>
        <div className="text-[11px] text-neutral-500 mt-3">Notes</div>
        <div className="mt-2 text-xs text-neutral-300">{humanDecision.notes}</div>
      </div>
    </div>
  );
}
