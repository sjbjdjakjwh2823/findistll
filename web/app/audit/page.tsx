"use client";

import React from "react";
import { BackgroundBeams } from "@/components/ui/background-beams";
import { ShieldCheck, History, AlertCircle } from "lucide-react";

export default function AuditDashboard() {
  const logs = [
    { id: 1, event: "ZKP_VERIFICATION", case: "CASE_001", status: "SUCCESS", timestamp: "2026-02-05 14:10" },
    { id: 2, event: "DATA_INGESTION", case: "CASE_001", status: "SUCCESS", timestamp: "2026-02-05 14:05" },
    { id: 3, event: "AI_DECISION_GEN", case: "CASE_002", status: "PENDING", timestamp: "2026-02-05 13:58" },
    { id: 4, event: "ZKP_VERIFICATION", case: "CASE_002", status: "FAILED", timestamp: "2026-02-05 13:45" },
  ];

  return (
    <main className="min-h-screen bg-black text-white p-8 md:p-24 relative overflow-hidden">
      <BackgroundBeams className="z-0" />
      <div className="z-10 relative max-w-5xl mx-auto">
        <header className="mb-12 border-b border-neutral-800 pb-6">
          <div className="flex items-center gap-3">
            <History className="h-8 w-8 text-cyan-500" />
            <h1 className="text-3xl font-bold tracking-tight">Institutional Audit Trail</h1>
          </div>
          <p className="text-neutral-500 mt-2">Immutable ledger of AI decisions and cryptographic proofs.</p>
        </header>

        <div className="bg-neutral-900/50 border border-neutral-800 rounded-2xl overflow-hidden backdrop-blur-md">
          <table className="w-full text-left text-sm">
            <thead className="bg-neutral-800/50 text-neutral-400 font-mono text-[10px] uppercase tracking-widest">
              <tr>
                <th className="px-6 py-4">Event Type</th>
                <th className="px-6 py-4">Case ID</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Timestamp</th>
                <th className="px-6 py-4">Proof</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-800">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-white/[0.02] transition">
                  <td className="px-6 py-4 font-medium">{log.event}</td>
                  <td className="px-6 py-4 font-mono text-neutral-400">{log.case}</td>
                  <td className="px-6 py-4">
                    <span className={`flex items-center gap-1.5 ${log.status === 'SUCCESS' ? 'text-emerald-400' : log.status === 'FAILED' ? 'text-red-400' : 'text-amber-400'}`}>
                      {log.status === 'SUCCESS' ? <ShieldCheck className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
                      {log.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-neutral-500 font-mono text-xs">{log.timestamp}</td>
                  <td className="px-6 py-4">
                    <button className="text-cyan-500 hover:underline text-xs">View Hash</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}
