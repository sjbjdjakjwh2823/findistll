"use client";

import React, { useMemo, useState } from "react";
import {
  BadgeCheck,
  FileSignature,
  Fingerprint,
  FlaskConical,
  PencilLine,
  Scale,
  Sparkles,
} from "lucide-react";
import { Button, Slider, Checkbox, TextArea, InputGroup, Card, Elevation } from "@blueprintjs/core";
import DecisionTimeline from "../../components/dashboard/DecisionTimeline";

type Recommendation = {
  id: string;
  agent: string;
  title: string;
  action: string;
  rationale: string;
  confidence: number;
  selected: boolean;
};

type EvidenceItem = {
  id: string;
  source: string;
  quote: string;
  weight: number;
  selected: boolean;
};

const initialRecommendations: Recommendation[] = [
  {
    id: "rec_1",
    agent: "Agent Macro",
    title: "Duration Exposure Trim",
    action: "Reduce high-duration software weight by 280 bps.",
    rationale: "Inflation persistence implies policy higher-for-longer; discount pressure remains elevated.",
    confidence: 87,
    selected: true,
  },
  {
    id: "rec_2",
    agent: "Agent Equity",
    title: "Barbell Rotation",
    action: "Rotate 160 bps from unprofitable growth to quality cash-flow compounders.",
    rationale: "Earnings resilience plus pricing power protects downside while preserving upside convexity.",
    confidence: 82,
    selected: true,
  },
  {
    id: "rec_3",
    agent: "Agent Risk",
    title: "Shock-Absorber Hedge",
    action: "Add tactical collar on Nasdaq-sensitive sleeve for next 45 days.",
    rationale: "Yield volatility remains a first-order driver of factor crowding and sharp de-rating.",
    confidence: 74,
    selected: false,
  },
];

const initialEvidence: EvidenceItem[] = [
  {
    id: "ev_1",
    source: "Fed Minutes Digest",
    quote: "Committee participants repeatedly flagged upside inflation risks and limited confidence in immediate easing.",
    weight: 81,
    selected: true,
  },
  {
    id: "ev_2",
    source: "10Y Real Yield Tape",
    quote: "Real yield break above prior range compressed software EV/S multiples within two sessions.",
    weight: 89,
    selected: true,
  },
  {
    id: "ev_3",
    source: "Earnings Breadth Snapshot",
    quote: "Top decile margin performers sustained guidance despite financing-cost pressure.",
    weight: 72,
    selected: true,
  },
  {
    id: "ev_4",
    source: "Liquidity Regime Monitor",
    quote: "Balance-sheet runoff pace remains a headwind for speculative duration assets.",
    weight: 69,
    selected: false,
  },
];

const rootCausePath = {
  root: "Inflation Surprise",
  hops: [
    "Inflation Surprise",
    "Policy Rate Path",
    "Discount Rate",
    "Tech Valuation Multiple",
  ],
  influence: 0.53,
  directionalEffect: -0.53,
};

export default function DecisionsPage() {
  const [recommendations, setRecommendations] = useState<Recommendation[]>(initialRecommendations);
  const [evidence, setEvidence] = useState<EvidenceItem[]>(initialEvidence);
  const [decisionMemo, setDecisionMemo] = useState(
    "승인 전, 헤지 크기(3번)만 리밸런스 허용 한도 내에서 20% 축소 검토."
  );
  const [approver, setApprover] = useState("Sovereign PM Desk");

  const selectedRecommendations = recommendations.filter((row) => row.selected);
  const selectedEvidence = evidence.filter((row) => row.selected);

  const composer = useMemo(() => {
    const recScore =
      selectedRecommendations.length === 0
        ? 0
        : selectedRecommendations.reduce((acc, row) => acc + row.confidence, 0) / selectedRecommendations.length;

    const evidenceScore =
      selectedEvidence.length === 0
        ? 0
        : selectedEvidence.reduce((acc, row) => acc + row.weight, 0) / selectedEvidence.length;

    const weightedScore = recScore * 0.55 + evidenceScore * 0.45;
    const disposition = weightedScore >= 80 ? "Approve" : weightedScore >= 65 ? "Conditional" : "Escalate";

    return {
      recScore,
      evidenceScore,
      weightedScore,
      disposition,
    };
  }, [selectedRecommendations, selectedEvidence]);

  return (
    <div className="h-full flex flex-col bg-[#1a1c1e] text-[#f6f7f9]">
      {/* Header */}
      <div className="h-16 border-b border-[#30404d] bg-[#202b33] flex items-center justify-between px-6 shrink-0">
        <div className="space-y-1">
          <p className="text-[10px] text-[#2B95D6] uppercase tracking-[0.2em] font-semibold flex items-center gap-2">
            <Sparkles size={12} /> Sovereign Decision Composer
          </p>
          <h1 className="text-lg font-bold tracking-tight text-[#f6f7f9] uppercase">Agent Recommendation Governance</h1>
        </div>
        <div className="flex flex-wrap gap-2 text-xs font-semibold">
          <span className="px-3 py-1 bg-[#2B95D6]/10 text-[#2B95D6] border border-[#2B95D6]/30">Case: NVDA-Duration-2026Q1</span>
          <span className="px-3 py-1 bg-[#21ce99]/10 text-[#21ce99] border border-[#21ce99]/30">Live Evidence Sync</span>
          <span className="px-3 py-1 bg-[#d9822b]/10 text-[#d9822b] border border-[#d9822b]/30">Human-in-Command</span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <div className="grid grid-cols-12 gap-4">
          
          {/* Main Recommendations Column */}
          <div className="col-span-8 flex flex-col gap-4">
            
            {/* Recommendation Stack */}
            <div className="border border-[#30404d] bg-[#202b33] flex flex-col">
              <div className="h-10 border-b border-[#30404d] bg-[#293742] flex items-center justify-between px-4">
                <h2 className="text-xs font-bold tracking-wider uppercase text-[#a7b6c2] font-mono">Recommendation Stack</h2>
                <span className="text-[10px] text-[#2B95D6] font-semibold font-mono">Selected {selectedRecommendations.length}/{recommendations.length}</span>
              </div>
              <div className="p-4 space-y-4 bg-[#1a1c1e]">
                {recommendations.map((row) => (
                  <div key={row.id} className="border border-[#30404d] bg-[#202b33] p-4 flex flex-col gap-3 group hover:border-[#5c7080] transition-colors">
                    <div className="flex items-center justify-between">
                      <Checkbox 
                        checked={row.selected} 
                        onChange={() => setRecommendations(prev => prev.map(item => item.id === row.id ? { ...item, selected: !item.selected } : item))}
                        label={row.title}
                        className="!m-0 !text-sm !font-bold !text-[#f6f7f9]"
                      />
                      <span className="text-[10px] uppercase tracking-wider text-[#5c7080] font-mono">{row.agent}</span>
                    </div>

                    <InputGroup 
                      value={row.action}
                      onChange={(e) => setRecommendations(prev => prev.map(item => item.id === row.id ? { ...item, action: e.target.value } : item))}
                      className="!bg-[#182026] !text-[#a7b6c2] !text-xs font-mono"
                      small
                    />
                    
                    <p className="text-xs text-[#5c7080] italic">{row.rationale}</p>

                    <div className="flex items-center gap-4">
                      <span className="text-[10px] text-[#5c7080] uppercase">Confidence</span>
                      <div className="flex-1 px-2">
                        <Slider 
                           min={45} max={99} stepSize={1} 
                           value={row.confidence} 
                           onChange={(val) => setRecommendations(prev => prev.map(item => item.id === row.id ? { ...item, confidence: val } : item))}
                           labelStepSize={50}
                           className=""
                        />
                      </div>
                      <span className="text-xs font-bold text-[#21ce99] font-mono">{row.confidence.toFixed(0)}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Evidence Control Board */}
            <div className="border border-[#30404d] bg-[#202b33] flex flex-col">
              <div className="h-10 border-b border-[#30404d] bg-[#293742] flex items-center justify-between px-4">
                 <h2 className="text-xs font-bold tracking-wider uppercase text-[#a7b6c2] font-mono">Evidence Control Board</h2>
                 <div className="flex items-center gap-3 text-[10px] text-[#5c7080] font-mono">
                    <span className="inline-flex items-center gap-1"><BadgeCheck size={10} /> {selectedEvidence.length}/{evidence.length}</span>
                    <span className="inline-flex items-center gap-1"><Fingerprint size={10} /> AUDIT READY</span>
                 </div>
              </div>
              <div className="p-4 grid grid-cols-2 gap-3 bg-[#1a1c1e]">
                 {evidence.map((row) => (
                    <div key={row.id} className="border border-[#30404d] bg-[#202b33] p-3 flex flex-col gap-2 hover:border-[#5c7080]">
                       <div className="flex items-center justify-between">
                          <Checkbox 
                            checked={row.selected}
                            onChange={() => setEvidence(prev => prev.map(item => item.id === row.id ? { ...item, selected: !item.selected } : item))}
                            label={row.source}
                            className="!m-0 !text-xs !font-bold !text-[#f6f7f9]"
                          />
                          <span className="text-[9px] font-mono text-[#21ce99]">W={row.weight}</span>
                       </div>
                       <p className="text-[10px] text-[#a7b6c2] leading-tight">{row.quote}</p>
                    </div>
                 ))}
              </div>
            </div>
          </div>

          {/* Decision Core Column */}
          <div className="col-span-4 flex flex-col gap-4">
            
            {/* Decision Timeline */}
            <div className="flex-1 min-h-[300px]">
              <DecisionTimeline />
            </div>

            {/* Scorecard */}
            <div className="border border-[#30404d] bg-[#202b33] p-0">
               <div className="h-10 border-b border-[#30404d] bg-[#293742] flex items-center px-4">
                  <h2 className="text-xs font-bold tracking-wider uppercase text-[#a7b6c2] font-mono">Decision Core</h2>
               </div>
               <div className="p-4 bg-[#1a1c1e] space-y-4">
                  <div className="border border-[#30404d] bg-[#202b33] p-3">
                     <div className="flex items-center justify-between text-xs mb-2">
                        <span className="text-[#a7b6c2]">Disposition</span>
                        <span className="font-bold text-[#2B95D6] uppercase tracking-wider">{composer.disposition}</span>
                     </div>
                     <div className="space-y-1 text-xs font-mono">
                        <div className="flex justify-between"><span>AGENT_SCORE</span><span className="text-[#21ce99]">{composer.recScore.toFixed(1)}</span></div>
                        <div className="flex justify-between"><span>EVIDENCE_SCORE</span><span className="text-[#21ce99]">{composer.evidenceScore.toFixed(1)}</span></div>
                        <div className="h-px bg-[#30404d] my-1" />
                        <div className="flex justify-between font-bold text-[#f6f7f9]"><span>WEIGHTED_AVG</span><span>{composer.weightedScore.toFixed(1)}</span></div>
                     </div>
                  </div>

                  <div className="border border-[#30404d] bg-[#202b33] p-3 space-y-2">
                     <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-[#a7b6c2]">
                        <FlaskConical size={12} /> Oracle Root Cause
                     </div>
                     <div className="text-[10px] text-[#21ce99] font-mono font-bold">Strongest: {rootCausePath.root}</div>
                     <div className="flex flex-wrap gap-1">
                        {rootCausePath.hops.map((hop, index) => (
                           <React.Fragment key={hop}>
                              <span className="px-1.5 py-0.5 border border-[#30404d] bg-[#1a1c1e] text-[9px] text-[#a7b6c2]">{hop}</span>
                              {index < rootCausePath.hops.length - 1 ? <span className="text-[#30404d] text-[9px]">→</span> : null}
                           </React.Fragment>
                        ))}
                     </div>
                  </div>
               </div>
            </div>

            {/* Approval */}
            <div className="border border-[#30404d] bg-[#202b33] p-4 flex flex-col gap-3">
               <label className="text-[10px] uppercase tracking-wider text-[#5c7080] font-bold">Approver Signature</label>
               <InputGroup 
                  value={approver}
                  onChange={(e) => setApprover(e.target.value)}
                  className="!bg-[#182026] !text-xs font-mono"
               />
               <TextArea 
                  value={decisionMemo}
                  onChange={(e) => setDecisionMemo(e.target.value)}
                  className="!bg-[#182026] !text-[#a7b6c2] !text-xs !resize-none"
                  rows={4}
               />
               <Button icon="edit" text="Approve & Sign" intent="primary" className="w-full !font-bold !rounded-none" />
               <Button icon="annotation" text="Request Revision" className="w-full !bg-transparent !border !border-[#30404d] !text-[#a7b6c2] !rounded-none" />
            </div>

          </div>
        </div>
      </div>
    </div>
  );
}
