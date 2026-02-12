"use client";

import React from "react";

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  draft: { label: "Draft", color: "bg-gray-500/20 text-gray-300" },
  ai_generated: { label: "AI Proposal", color: "bg-blue-500/20 text-blue-300" },
  under_review: { label: "Under Review", color: "bg-yellow-500/20 text-yellow-300" },
  edited: { label: "Edited", color: "bg-orange-500/20 text-orange-300" },
  pending_approval: { label: "Pending Approval", color: "bg-purple-500/20 text-purple-300" },
  revision_requested: { label: "Revision Requested", color: "bg-amber-500/20 text-amber-300" },
  approved: { label: "Approved", color: "bg-emerald-500/20 text-emerald-300" },
  rejected: { label: "Rejected", color: "bg-red-500/20 text-red-300" },
  closed: { label: "Closed", color: "bg-gray-500/20 text-gray-300" },
  cancelled: { label: "Cancelled", color: "bg-gray-500/20 text-gray-300" },
};

export function CaseStatusBadge({ status }: { status: string }) {
  const cfg = STATUS_MAP[status] || { label: status, color: "bg-white/10 text-white" };
  return (
    <span className={`px-2 py-1 rounded text-xs ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}
