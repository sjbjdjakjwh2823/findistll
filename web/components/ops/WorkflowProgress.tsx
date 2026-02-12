import React from "react";

interface Stage {
  stage: string;
  status: string;
  assigned_to: string;
  completed_at?: string;
}

export function WorkflowProgress({ stages }: { stages: Stage[] }) {
  return (
    <div className="rounded-lg border border-white/10 bg-black/40 p-4">
      <div className="text-xs text-neutral-500 mb-2">Workflow Progress</div>
      <div className="space-y-2">
        {stages.map((stage) => (
          <div key={stage.stage} className="flex items-center justify-between text-xs">
            <div className="text-neutral-300">
              {stage.stage} · {stage.assigned_to}
            </div>
            <div className="text-neutral-500">
              {stage.status}{stage.completed_at ? ` · ${stage.completed_at}` : ""}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
