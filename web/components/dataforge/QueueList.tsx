"use client";

import React, { useEffect, useState } from "react";
import type { Sample } from "@/lib/dataforge_types";

interface QueueListProps {
  apiBase: string;
  onSelectSample: (sample: Sample) => void;
}

export function QueueList({ apiBase, onSelectSample }: QueueListProps) {
  const [queue, setQueue] = useState<Sample[]>([]);

  useEffect(() => {
    const fetchQueue = async () => {
      try {
        const res = await fetch(`${apiBase}/api/v1/generate/queue`);
        if (res.ok) {
          const data = await res.json();
          const raw = (data.queue || []) as Array<Partial<Sample>>;
          setQueue(
            raw.map((s, idx) => ({
              id: String(s.id ?? idx),
              template_type: String(s.template_type ?? ""),
              generated_content: (s.generated_content ?? null) as Sample["generated_content"],
              confidence_score: Number(s.confidence_score ?? 0),
              raw_documents: s.raw_documents as Sample["raw_documents"],
            }))
          );
        }
      } catch (e) {
        console.error("Failed to fetch queue:", e);
      }
    };

    fetchQueue();
  }, [apiBase]);

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4">
      <div className="text-sm text-neutral-400 mb-3">Queue</div>
      <ul className="space-y-2">
        {queue.map((sample) => (
          <li
            key={String(sample.id || "")}
            className="flex items-center justify-between rounded-lg border border-white/10 bg-black/40 p-3"
          >
            <div>
              <div className="text-sm text-white">{String(sample.template_type || "")}</div>
              <div className="text-xs text-neutral-500">
                {String(sample.id || "").slice(0, 8)}
              </div>
            </div>
            <button
              onClick={() => onSelectSample(sample)}
              className="text-xs text-cyan-300 hover:text-cyan-200"
            >
              Open
            </button>
          </li>
        ))}
        {queue.length === 0 && (
          <li className="text-xs text-neutral-500">No pending samples.</li>
        )}
      </ul>
    </div>
  );
}
