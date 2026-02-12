import React from "react";

interface Anchor {
  document_name: string;
  page_number: number;
  snippet_text: string;
}

export function DocumentPreview({ anchors }: { anchors: Anchor[] }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/40 p-4">
      <div className="text-xs text-neutral-500 mb-2">Source Anchors</div>
      <div className="space-y-3">
        {anchors.length === 0 && (
          <div className="text-xs text-neutral-500">No anchors yet.</div>
        )}
        {anchors.map((anchor, idx) => (
          <div key={idx} className="text-xs text-neutral-300">
            <div className="text-neutral-400">
              {anchor.document_name} · p{anchor.page_number}
            </div>
            <div className="mt-1">{anchor.snippet_text}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
