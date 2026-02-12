"use client";

import React from "react";

const STAGES = [
  "draft",
  "ai_generated",
  "under_review",
  "pending_approval",
  "approved",
  "closed",
];

export function CaseTimeline({ status }: { status: string }) {
  const currentIndex = Math.max(0, STAGES.indexOf(status));
  return (
    <div className="flex items-center gap-2 text-xs text-neutral-400">
      {STAGES.map((stage, idx) => (
        <div key={stage} className="flex items-center gap-2">
          <div
            className={
              idx <= currentIndex
                ? "w-2 h-2 rounded-full bg-emerald-400"
                : "w-2 h-2 rounded-full bg-white/20"
            }
          />
          {idx < STAGES.length - 1 && <div className="w-6 h-[1px] bg-white/10" />}
        </div>
      ))}
    </div>
  );
}
