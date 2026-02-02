"use client";

import React from "react";
import ForceGraph from "@/components/graph/ForceGraph";
import { Filter, Calendar, Layers } from "lucide-react";

export default function GraphPage() {
  return (
    <div className="p-8 space-y-8 h-full flex flex-col">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Temporal Ontology Graph</h2>
          <p className="text-muted text-sm">Visualize shifting causal relationships over time</p>
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 bg-glass border border-border px-3 py-2 rounded-lg text-xs font-bold hover:text-primary transition-colors">
            <Calendar size={14} />
            As of: Feb 2, 2026
          </button>
          <button className="flex items-center gap-2 bg-glass border border-border px-3 py-2 rounded-lg text-xs font-bold hover:text-primary transition-colors">
            <Filter size={14} />
            Focus: Macro
          </button>
          <button className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg text-sm font-medium">
            <Layers size={16} />
            Analyze Clusters
          </button>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        <ForceGraph />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-panel p-5 space-y-3">
          <h4 className="text-xs font-bold text-muted uppercase tracking-widest">Active Causal Links</h4>
          <div className="space-y-2">
            {[
              { from: "Inflation", to: "Fed Policy", strength: "0.85" },
              { from: "Fed Policy", to: "Interest Rates", strength: "0.92" },
            ].map((link, i) => (
              <div key={i} className="flex justify-between items-center p-2 bg-glass rounded border border-border/50">
                <div className="flex items-center gap-2 text-xs font-medium">
                  <span>{link.from}</span>
                  <span className="text-muted">→</span>
                  <span>{link.to}</span>
                </div>
                <span className="text-[10px] font-mono font-bold text-secondary">{link.strength}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="glass-panel p-5 md:col-span-2">
          <h4 className="text-xs font-bold text-muted uppercase tracking-widest">Temporal Drift Analysis</h4>
          <p className="text-sm text-muted mt-2">
            Knowledge relationships in the tech sector have weakened by 12.4% since last quarter, while macro-dependence has strengthened. 
            The system suggests a shift from fundamental valuation to liquidity-driven correlation.
          </p>
        </div>
      </div>
    </div>
  );
}
