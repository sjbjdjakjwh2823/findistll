"use client";

import React from "react";
import type { JsonRecord } from "@/lib/types";
import type { Sample } from "@/lib/dataforge_types";

interface ReviewInterfaceProps {
  sample: Sample | null;
  loading: boolean;
  onApprove: () => void;
  onCorrect: (corrections: JsonRecord, reasoning?: string) => void;
  onReject: (reasoning?: string) => void;
  onSkip: () => void;
  onFetchNext: () => void;
}

export function ReviewInterface({
  sample,
  loading,
  onApprove,
  onCorrect,
  onReject,
  onSkip,
  onFetchNext,
}: ReviewInterfaceProps) {
  const [draftText, setDraftText] = React.useState<string>("");
  const [reasoning, setReasoning] = React.useState<string>("");

  React.useEffect(() => {
    if (sample) {
      setDraftText(JSON.stringify(sample.generated_content || {}, null, 2));
    }
  }, [sample]);

  if (!sample) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/5 p-6 text-neutral-400">
        Select a sample to review.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="rounded-xl border border-white/10 bg-black/40 p-4">
        <div className="text-sm text-neutral-400 mb-2">Source</div>
        <pre className="text-xs text-neutral-200 whitespace-pre-wrap">
          {JSON.stringify(sample.raw_documents?.raw_content || {}, null, 2)}
        </pre>
      </div>
      <div className="rounded-xl border border-white/10 bg-black/40 p-4">
        <div className="text-sm text-neutral-400 mb-2">AI Output</div>
        <textarea
          className="w-full h-56 bg-black/60 border border-white/10 rounded-lg p-3 text-xs text-neutral-200"
          value={draftText}
          onChange={(e) => setDraftText(e.target.value)}
        />
        <input
          className="w-full mt-3 bg-black/60 border border-white/10 rounded-lg p-2 text-xs text-neutral-200"
          placeholder="Reasoning (optional)"
          value={reasoning}
          onChange={(e) => setReasoning(e.target.value)}
        />
        <div className="flex gap-2 mt-3">
          <button
            className="px-3 py-2 text-xs bg-emerald-500/20 text-emerald-300 rounded"
            disabled={loading}
            onClick={onApprove}
          >
            Approve
          </button>
          <button
            className="px-3 py-2 text-xs bg-amber-500/20 text-amber-300 rounded"
            disabled={loading}
            onClick={() => {
              try {
                const parsed = JSON.parse(draftText);
                if (parsed && typeof parsed === "object") {
                  onCorrect(parsed as JsonRecord, reasoning || undefined);
                } else {
                  onCorrect({ raw: parsed }, reasoning || undefined);
                }
              } catch {
                onCorrect({ raw: draftText }, reasoning || undefined);
              }
            }}
          >
            Save Edit
          </button>
          <button
            className="px-3 py-2 text-xs bg-red-500/20 text-red-300 rounded"
            disabled={loading}
            onClick={() => onReject(reasoning || undefined)}
          >
            Reject
          </button>
          <button
            className="px-3 py-2 text-xs bg-white/10 text-neutral-300 rounded"
            disabled={loading}
            onClick={onSkip}
          >
            Skip
          </button>
          <button
            className="px-3 py-2 text-xs bg-white/10 text-neutral-300 rounded"
            disabled={loading}
            onClick={onFetchNext}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
