"use client";

import React from "react";
import { 
  Briefcase, 
  Search, 
  Plus, 
  ArrowUpRight,
  Filter
} from "lucide-react";
import StatsCard from "@/components/dashboard/StatsCard";

export default function CasesPage() {
  const cases = [
    { id: "CASE-2026-0042", entity: "NVIDIA Corp.", status: "Refining", confidence: "98.2%", date: "2026-02-02" },
    { id: "CASE-2026-0041", entity: "Tesla Inc.", status: "Completed", confidence: "96.4%", date: "2026-02-01" },
    { id: "CASE-2026-0040", entity: "Apple Inc.", status: "Decision", confidence: "93.1%", date: "2026-01-31" },
  ];

  return (
    <div className="p-8 space-y-8">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white uppercase">Case Inventory</h2>
          <p className="text-muted text-sm font-mono">ACTIVE INTELLIGENCE SESSIONS</p>
        </div>
        <button className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-none text-xs font-bold uppercase tracking-widest shadow-lg shadow-primary/10">
          <Plus size={16} />
          Create New Case
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <StatsCard label="Active" value="12" description="Currently processing" />
        <StatsCard label="Pending" value="4" description="Awaiting human review" />
        <StatsCard label="Completed" value="142" description="Total archived cases" />
      </div>

      <div className="glass-panel overflow-hidden">
        <div className="p-4 border-b border-border bg-white/[0.02] flex justify-between items-center">
           <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={14} />
              <input 
                type="text" 
                placeholder="Filter cases..." 
                className="bg-black/20 border border-border pl-9 pr-4 py-1.5 text-sm w-64 focus:outline-none focus:border-primary"
              />
           </div>
           <button className="flex items-center gap-2 text-xs font-bold text-muted hover:text-white transition-colors">
              <Filter size={14} />
              Advanced Filter
           </button>
        </div>
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-border text-muted uppercase text-[10px] tracking-widest font-bold">
              <th className="px-6 py-4">Case ID</th>
              <th className="px-6 py-4">Entity</th>
              <th className="px-6 py-4">Status</th>
              <th className="px-6 py-4">Confidence</th>
              <th className="px-6 py-4">Date</th>
              <th className="px-6 py-4"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {cases.map((c) => (
              <tr key={c.id} className="hover:bg-white/[0.03] group cursor-pointer transition-colors" onClick={() => window.location.href=`/cases/sample-case`}>
                <td className="px-6 py-4 font-mono text-xs text-primary font-bold">{c.id}</td>
                <td className="px-6 py-4 text-sm font-bold text-white uppercase">{c.entity}</td>
                <td className="px-6 py-4">
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-bold bg-primary/10 text-primary border border-primary/20">
                    {c.status}
                  </span>
                </td>
                <td className="px-6 py-4 font-mono text-xs text-secondary">{c.confidence}</td>
                <td className="px-6 py-4 text-xs text-muted">{c.date}</td>
                <td className="px-6 py-4 text-right">
                  <ArrowUpRight size={14} className="text-muted group-hover:text-primary transition-all" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
