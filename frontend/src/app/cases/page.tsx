"use client";

import React from "react";
import { 
  Button, 
  Card, 
  Elevation, 
  ProgressBar, 
  Tag, 
  InputGroup 
} from "@blueprintjs/core";
import { 
  Briefcase, 
  Search, 
  Plus, 
  ArrowUpRight,
  Filter,
  MoreVertical,
  Clock,
  Activity
} from "lucide-react";
import Link from "next/link";

const cases = [
  { id: "CASE-2026-0042", entity: "NVIDIA Corp.", status: "Refining", confidence: 0.98, date: "2026-02-02", tasks: 12, completed: 8 },
  { id: "CASE-2026-0041", entity: "Tesla Inc.", status: "Completed", confidence: 1.0, date: "2026-02-01", tasks: 20, completed: 20 },
  { id: "CASE-2026-0040", entity: "Apple Inc.", status: "Decision", confidence: 0.93, date: "2026-01-31", tasks: 15, completed: 14 },
  { id: "CASE-2026-0039", entity: "Microsoft", status: "In Progress", confidence: 0.65, date: "2026-01-30", tasks: 10, completed: 3 },
  { id: "CASE-2026-0038", entity: "Google LLC", status: "Audit", confidence: 0.88, date: "2026-01-29", tasks: 18, completed: 18 },
  { id: "CASE-2026-0037", entity: "Amazon.com", status: "Refining", confidence: 0.72, date: "2026-01-28", tasks: 22, completed: 10 },
  { id: "CASE-2026-0036", entity: "Meta Inc.", status: "Blocked", confidence: 0.40, date: "2026-01-25", tasks: 8, completed: 1 },
  { id: "CASE-2026-0035", entity: "Netflix", status: "Completed", confidence: 0.99, date: "2026-01-24", tasks: 14, completed: 14 },
];

export default function CasesPage() {
  return (
    <div className="h-full flex flex-col bg-[#1a1c1e] text-[#f6f7f9]">
      {/* Header Toolbar */}
      <div className="h-16 border-b border-[#30404d] bg-[#202b33] flex items-center justify-between px-6 shrink-0">
        <div>
          <h2 className="text-sm font-bold tracking-wider text-[#f6f7f9] uppercase flex items-center gap-2">
            <Briefcase size={16} className="text-[#2B95D6]" />
            Case Inventory
          </h2>
          <p className="text-[10px] text-[#5c7080] font-mono mt-1">ACTIVE INTELLIGENCE SESSIONS: {cases.length}</p>
        </div>
        <div className="flex items-center gap-3">
          <InputGroup 
            leftIcon="search" 
            placeholder="Search cases..." 
            className="!bg-[#182026] !w-64 custom-input"
            small
          />
          <Button icon="filter" minimal small className="!text-[#a7b6c2]" />
          <Button intent="primary" icon="add" text="New Case" small outlined className="!rounded-none font-bold" />
        </div>
      </div>

      {/* Grid Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          
          {cases.map((c) => (
            <Link key={c.id} href={`/cases/${c.id}`} className="no-underline block h-full">
              <div 
                className={`
                  h-full border border-[#30404d] bg-[#202b33] p-0 flex flex-col
                  hover:border-[#2B95D6] hover:shadow-[0_0_0_1px_#2B95D6] transition-all duration-100 group relative
                `}
              >
                 {/* Top Colored Bar based on Status */}
                 <div className={`h-1 w-full 
                    ${c.status === 'Completed' ? 'bg-[#0f9960]' : 
                      c.status === 'Blocked' ? 'bg-[#db3737]' : 
                      'bg-[#2B95D6]'}
                 `}></div>

                 <div className="p-4 flex flex-col gap-4 flex-1">
                    <div className="flex justify-between items-start">
                       <div>
                          <h3 className="text-sm font-bold text-[#f6f7f9] group-hover:text-[#2B95D6]">{c.entity}</h3>
                          <span className="text-[10px] text-[#5c7080] font-mono">{c.id}</span>
                       </div>
                       <Button icon="more" minimal small className="!text-[#5c7080] -mr-2 -mt-2" />
                    </div>

                    <div className="grid grid-cols-2 gap-2 mt-2">
                       <div className="bg-[#182026] p-2 border border-[#30404d]">
                          <span className="text-[9px] text-[#5c7080] block font-mono">CONFIDENCE</span>
                          <span className={`text-sm font-bold ${c.confidence > 0.9 ? 'text-[#0f9960]' : 'text-[#d9822b]'}`}>{(c.confidence * 100).toFixed(1)}%</span>
                       </div>
                       <div className="bg-[#182026] p-2 border border-[#30404d]">
                          <span className="text-[9px] text-[#5c7080] block font-mono">STATUS</span>
                          <span className="text-xs font-bold text-[#f6f7f9]">{c.status}</span>
                       </div>
                    </div>

                    <div className="mt-auto">
                       <div className="flex justify-between text-[9px] text-[#a7b6c2] mb-1 font-mono">
                          <span>PROGRESS</span>
                          <span>{c.completed}/{c.tasks} TASKS</span>
                       </div>
                       <ProgressBar 
                          value={c.completed / c.tasks} 
                          intent={c.status === 'Completed' ? "success" : "primary"} 
                          className="!h-1 !rounded-none !bg-[#10161a]" 
                          animate={false} 
                          stripes={false}
                        />
                    </div>
                 </div>

                 <div className="px-4 py-2 border-t border-[#30404d] bg-[#1a1c1e] flex justify-between items-center">
                    <div className="flex items-center gap-1 text-[10px] text-[#5c7080]">
                       <Clock size={10} />
                       <span>{c.date}</span>
                    </div>
                    <ArrowUpRight size={12} className="text-[#5c7080] group-hover:text-[#2B95D6]" />
                 </div>
              </div>
            </Link>
          ))}
          
        </div>
      </div>
    </div>
  );
}
