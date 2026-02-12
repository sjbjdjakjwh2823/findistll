import React from "react";

const SLA_COLORS: Record<string, string> = {
  ON_TIME: "bg-emerald-500/20 text-emerald-200 border-emerald-500/30",
  AT_RISK: "bg-amber-500/20 text-amber-200 border-amber-500/30",
  OVERDUE: "bg-red-500/20 text-red-200 border-red-500/30",
};

export function SLABadge({ status }: { status: string }) {
  const classes = SLA_COLORS[status] || "bg-white/10 text-white/70 border-white/20";
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${classes}`}>
      {status}
    </span>
  );
}
