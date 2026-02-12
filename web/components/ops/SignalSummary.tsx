import React from "react";

interface Signal {
  type: string;
  severity: number;
  description: string;
}

interface SignalSummaryProps {
  riskScore?: number;
  riskLevel?: string;
  signals?: Signal[];
  trends?: { metric: string; direction: string; change_pct: number; period: string }[];
}

export function SignalSummary({ riskScore, riskLevel, signals = [], trends = [] }: SignalSummaryProps) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/40 p-4">
      <div className="text-xs text-neutral-500 mb-2">Signals</div>
      <div className="flex items-center justify-between">
        <div className="text-sm text-neutral-200">Risk Score</div>
        <div className="text-sm text-red-200">{riskScore ?? "N/A"}</div>
      </div>
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm text-neutral-200">Risk Level</div>
        <div className="text-sm text-amber-200">{riskLevel ?? "UNKNOWN"}</div>
      </div>
      <div className="text-[11px] text-neutral-400">Key Signals</div>
      <ul className="mt-2 space-y-1 text-xs text-neutral-300">
        {signals.length === 0 && <li>No signals yet.</li>}
        {signals.map((signal, idx) => (
          <li key={idx}>
            {signal.type} · {signal.description} (sev {signal.severity})
          </li>
        ))}
      </ul>
      <div className="text-[11px] text-neutral-400 mt-3">Trends</div>
      <ul className="mt-2 space-y-1 text-xs text-neutral-300">
        {trends.length === 0 && <li>No trends yet.</li>}
        {trends.map((trend, idx) => (
          <li key={idx}>
            {trend.metric} {trend.direction} {trend.change_pct}% ({trend.period})
          </li>
        ))}
      </ul>
    </div>
  );
}
