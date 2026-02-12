import React from "react";

interface AuthorityMarkersProps {
  owner?: string;
  reviewer?: string;
  approver?: string;
  watchers?: string[];
}

function marker(label: string, value?: string) {
  if (!value) {
    return (
      <div className="text-xs text-neutral-500">
        {label}: <span className="text-neutral-600">Unassigned</span>
      </div>
    );
  }
  return (
    <div className="text-xs text-neutral-300">
      {label}: <span className="text-neutral-100">{value}</span>
    </div>
  );
}

export function AuthorityMarkers({ owner, reviewer, approver, watchers = [] }: AuthorityMarkersProps) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/40 p-3">
      <div className="text-[11px] text-neutral-500 mb-2">Authority Markers</div>
      <div className="grid grid-cols-2 gap-2">
        {marker("Owner", owner)}
        {marker("Reviewer", reviewer)}
        {marker("Approver", approver)}
        <div className="text-xs text-neutral-300">
          Watchers: {watchers.length ? watchers.join(", ") : "None"}
        </div>
      </div>
    </div>
  );
}
