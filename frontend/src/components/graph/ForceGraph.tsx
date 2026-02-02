"use client";

import React, { useMemo } from "react";
import dynamic from "next/dynamic";

// Dynamic import to avoid SSR issues with 3D canvas
const ForceGraph3D = dynamic(() => import("react-force-graph-3d"), { ssr: false });

interface Node {
  id: string;
  name: string;
  val: number;
  color?: string;
}

interface Link {
  source: string;
  target: string;
  strength: number;
}

export default function TemporalGraph() {
  const data = useMemo(() => {
    const nodes: Node[] = [
      { id: "fed", name: "Federal Reserve", val: 20, color: "#6366f1" },
      { id: "rates", name: "Interest Rates", val: 15, color: "#f59e0b" },
      { id: "tech", name: "Tech Sector", val: 12, color: "#10b981" },
      { id: "inflation", name: "Inflation", val: 18, color: "#ef4444" },
      { id: "nasdaq", name: "NASDAQ", val: 10, color: "#10b981" },
      { id: "jobs", name: "Employment Data", val: 8, color: "#3b82f6" },
    ];

    const links: Link[] = [
      { source: "fed", target: "rates", strength: 0.9 },
      { source: "rates", target: "tech", strength: 0.75 },
      { source: "inflation", target: "fed", strength: 0.85 },
      { source: "tech", target: "nasdaq", strength: 0.95 },
      { source: "jobs", target: "fed", strength: 0.6 },
      { source: "rates", target: "nasdaq", strength: 0.7 },
    ];

    return { nodes, links };
  }, []);

  return (
    <div className="w-full h-[600px] glass-panel overflow-hidden relative">
      <div className="absolute top-4 left-4 z-10 space-y-1">
        <h3 className="text-sm font-bold tracking-tight">Temporal Ontology Explorer</h3>
        <p className="text-[10px] text-muted uppercase tracking-widest">Pillar 3: Dynamic Knowledge Visualization</p>
      </div>
      
      <div className="absolute bottom-4 right-4 z-10 flex gap-4">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-primary" />
          <span className="text-[10px] font-medium text-muted">Entity</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-accent" />
          <span className="text-[10px] font-medium text-muted">Metric</span>
        </div>
      </div>

      <ForceGraph3D
        graphData={data}
        backgroundColor="#00000000"
        linkColor={() => "rgba(255,255,255,0.15)"}
        nodeLabel={(node: any) => node.name}
        nodeColor={(node: any) => node.color}
        nodeRelSize={6}
        linkDirectionalParticles={2}
        linkDirectionalParticleSpeed={0.01}
        enableNodeDrag={false}
      />
    </div>
  );
}
