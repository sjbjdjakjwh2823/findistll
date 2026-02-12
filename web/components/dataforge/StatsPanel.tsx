"use client";

import React, { useEffect, useState } from "react";

interface StatsPanelProps {
  apiBase: string;
  annotatorId: string;
}

type QueueStats = {
  total_pending?: number;
  total_approved?: number;
  total_corrected?: number;
  total_rejected?: number;
};

export function StatsPanel({ apiBase, annotatorId }: StatsPanelProps) {
  const [stats, setStats] = useState<QueueStats | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(`${apiBase}/api/v1/annotate/stats/queue`);
        if (res.ok) {
          setStats((await res.json()) as QueueStats);
        }
      } catch (e) {
        console.error("Failed to fetch stats:", e);
      }
    };

    fetchStats();
  }, [apiBase, annotatorId]);

  if (!stats) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/5 p-4 text-neutral-400">
        Loading stats...
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="text-sm text-neutral-400 mb-3">Queue Stats</div>
      <div className="grid grid-cols-2 gap-3 text-xs text-neutral-200">
        <div>Pending: {Number(stats.total_pending ?? 0)}</div>
        <div>Approved: {Number(stats.total_approved ?? 0)}</div>
        <div>Corrected: {Number(stats.total_corrected ?? 0)}</div>
        <div>Rejected: {Number(stats.total_rejected ?? 0)}</div>
      </div>
    </div>
  );
}
