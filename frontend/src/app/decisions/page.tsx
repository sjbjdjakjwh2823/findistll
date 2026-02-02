"use client";

import React, { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  BadgeCheck,
  FileSignature,
  Fingerprint,
  FlaskConical,
  PencilLine,
  Scale,
  Sparkles,
} from "lucide-react";

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
    <div className="min-h-full p-8 space-y-8 bg-[radial-gradient(circle_at_12%_20%,rgba(99,102,241,0.18),transparent_34%),radial-gradient(circle_at_80%_10%,rgba(16,185,129,0.14),transparent_28%),linear-gradient(180deg,#060607_0%,#0a0a0a_56%,#080808_100%)]">
      <motion.section
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="glass-panel p-6 lg:p-7"
      >
        <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4">
          <div className="space-y-2">
            <p className="text-[11px] text-primary uppercase tracking-[0.2em] font-semibold flex items-center gap-2">
              <Sparkles size={12} /> Sovereign Decision Composer
            </p>
            <h1 className="text-2xl lg:text-3xl font-bold tracking-tight">Agent Recommendation Governance</h1>
            <p className="text-sm text-muted max-w-3xl">
              에이전트 제안과 근거를 실시간으로 조정하고, Oracle의 인과 경로를 반영해 최종 결정을 서명합니다.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs font-semibold">
            <span className="px-3 py-1 rounded-full bg-primary/15 text-primary border border-primary/40">Case: NVDA-Duration-2026Q1</span>
            <span className="px-3 py-1 rounded-full bg-secondary/15 text-secondary border border-secondary/40">Live Evidence Sync</span>
            <span className="px-3 py-1 rounded-full bg-amber-400/15 text-amber-300 border border-amber-300/30">Human-in-Command</span>
          </div>
        </div>
      </motion.section>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.05 }}
          className="xl:col-span-2 glass-panel p-5 lg:p-6 space-y-4"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold tracking-wider uppercase text-muted">Recommendation Stack</h2>
            <span className="text-xs text-primary font-semibold">Selected {selectedRecommendations.length}/{recommendations.length}</span>
          </div>

          <div className="space-y-3">
            {recommendations.map((row) => (
              <article key={row.id} className="rounded-xl border border-border bg-black/30 p-4 space-y-3">
                <div className="flex flex-col lg:flex-row lg:items-center gap-2 justify-between">
                  <label className="flex items-center gap-2 text-sm font-semibold">
                    <input
                      type="checkbox"
                      checked={row.selected}
                      onChange={() =>
                        setRecommendations((prev) =>
                          prev.map((item) =>
                            item.id === row.id ? { ...item, selected: !item.selected } : item
                          )
                        )
                      }
                      className="accent-primary"
                    />
                    {row.title}
                  </label>
                  <div className="text-[11px] uppercase tracking-wider text-muted">{row.agent}</div>
                </div>

                <textarea
                  value={row.action}
                  onChange={(event) =>
                    setRecommendations((prev) =>
                      prev.map((item) =>
                        item.id === row.id ? { ...item, action: event.target.value } : item
                      )
                    )
                  }
                  rows={2}
                  className="w-full rounded-lg bg-glass border border-border px-3 py-2 text-sm focus:outline-none focus:border-primary"
                />

                <p className="text-xs text-muted">{row.rationale}</p>

                <div className="space-y-2">
                  <div className="flex justify-between text-xs">
                    <span className="text-muted">Confidence</span>
                    <span className="data-font text-secondary">{row.confidence.toFixed(0)}</span>
                  </div>
                  <input
                    type="range"
                    min={45}
                    max={99}
                    value={row.confidence}
                    onChange={(event) =>
                      setRecommendations((prev) =>
                        prev.map((item) =>
                          item.id === row.id ? { ...item, confidence: Number(event.target.value) } : item
                        )
                      )
                    }
                    className="w-full accent-primary"
                  />
                </div>
              </article>
            ))}
          </div>
        </motion.section>

        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="glass-panel p-5 lg:p-6 space-y-5"
        >
          <h2 className="text-sm font-bold tracking-wider uppercase text-muted">Decision Core</h2>

          <div className="rounded-xl border border-border bg-black/35 p-4 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted">Disposition</span>
              <span className="font-semibold text-primary">{composer.disposition}</span>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between"><span>Agent Score</span><span className="data-font text-secondary">{composer.recScore.toFixed(1)}</span></div>
              <div className="flex items-center justify-between"><span>Evidence Score</span><span className="data-font text-secondary">{composer.evidenceScore.toFixed(1)}</span></div>
              <div className="h-px bg-border" />
              <div className="flex items-center justify-between text-sm font-semibold"><span>Weighted</span><span className="data-font text-primary">{composer.weightedScore.toFixed(1)}</span></div>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-black/35 p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted">
              <FlaskConical size={14} /> Oracle Root Cause
            </div>
            <div className="text-[11px] text-secondary font-semibold">Strongest Cause: {rootCausePath.root}</div>
            <div className="flex flex-wrap gap-2">
              {rootCausePath.hops.map((hop, index) => (
                <React.Fragment key={hop}>
                  <span className="px-2.5 py-1 rounded-md border border-border bg-glass text-[11px]">{hop}</span>
                  {index < rootCausePath.hops.length - 1 ? <span className="text-muted text-[11px] pt-1">→</span> : null}
                </React.Fragment>
              ))}
            </div>
            <div className="text-[11px] text-muted">Influence score {rootCausePath.influence.toFixed(2)} / directional {rootCausePath.directionalEffect.toFixed(2)}</div>
          </div>

          <div className="space-y-2">
            <label className="text-xs uppercase tracking-wider text-muted">Approver Signature</label>
            <input
              value={approver}
              onChange={(event) => setApprover(event.target.value)}
              className="w-full rounded-lg bg-glass border border-border px-3 py-2 text-sm focus:outline-none focus:border-primary"
            />
            <textarea
              rows={3}
              value={decisionMemo}
              onChange={(event) => setDecisionMemo(event.target.value)}
              className="w-full rounded-lg bg-glass border border-border px-3 py-2 text-sm focus:outline-none focus:border-primary"
            />
          </div>

          <div className="grid grid-cols-1 gap-2">
            <button className="flex items-center justify-center gap-2 rounded-lg bg-primary hover:bg-indigo-500 px-3 py-2 text-sm font-semibold text-white transition-colors">
              <FileSignature size={16} /> Approve & Sign Packet
            </button>
            <button className="flex items-center justify-center gap-2 rounded-lg border border-border bg-glass hover:bg-white/[0.06] px-3 py-2 text-sm font-semibold transition-colors">
              <PencilLine size={16} /> Send Revision to Agent Team
            </button>
          </div>
        </motion.section>
      </div>

      <motion.section
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, delay: 0.15 }}
        className="glass-panel p-5 lg:p-6 space-y-4"
      >
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
          <h2 className="text-sm font-bold tracking-wider uppercase text-muted">Evidence Control Board</h2>
          <div className="flex items-center gap-3 text-xs text-muted">
            <span className="inline-flex items-center gap-1"><BadgeCheck size={14} /> curated {selectedEvidence.length}/{evidence.length}</span>
            <span className="inline-flex items-center gap-1"><Fingerprint size={14} /> immutable audit ready</span>
            <span className="inline-flex items-center gap-1"><Scale size={14} /> policy compliant</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {evidence.map((row) => (
            <article key={row.id} className="rounded-xl border border-border bg-black/30 p-4 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-sm font-semibold">
                  <input
                    type="checkbox"
                    checked={row.selected}
                    onChange={() =>
                      setEvidence((prev) =>
                        prev.map((item) =>
                          item.id === row.id ? { ...item, selected: !item.selected } : item
                        )
                      )
                    }
                    className="accent-secondary"
                  />
                  {row.source}
                </label>
                <span className="text-[10px] font-mono text-secondary">w={row.weight}</span>
              </div>

              <p className="text-xs text-muted leading-relaxed">{row.quote}</p>

              <input
                type="range"
                min={40}
                max={99}
                value={row.weight}
                onChange={(event) =>
                  setEvidence((prev) =>
                    prev.map((item) =>
                      item.id === row.id ? { ...item, weight: Number(event.target.value) } : item
                    )
                  )
                }
                className="w-full accent-secondary"
              />
            </article>
          ))}
        </div>
      </motion.section>
    </div>
  );
}
