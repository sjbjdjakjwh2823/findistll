"use client";

import { useMemo, useState } from "react";
import StatsCard from "@/components/dashboard/StatsCard";
import {
  Plus,
  Search,
  ArrowUpRight,
  ChevronRight,
  Building2,
  Activity,
  AlertTriangle,
  Link2,
  Spline,
} from "lucide-react";

type BusinessObjectType = "company" | "metric" | "event";

interface BusinessObject {
  id: string;
  type: BusinessObjectType;
  label: string;
  status: string;
  confidence: string;
  description: string;
}

interface ObjectRelation {
  source: string;
  target: string;
  relation: string;
  effect: string;
  confidence: string;
}

const objects: BusinessObject[] = [
  {
    id: "obj-tsla",
    type: "company",
    label: "Tesla Inc.",
    status: "Live",
    confidence: "98.2%",
    description: "EV demand and margin recovery assumptions",
  },
  {
    id: "obj-nvda",
    type: "company",
    label: "NVIDIA Corp.",
    status: "Critical",
    confidence: "96.4%",
    description: "AI capex concentration and hyperscaler cycle",
  },
  {
    id: "obj-yield",
    type: "metric",
    label: "10Y Treasury Yield",
    status: "Tracking",
    confidence: "93.1%",
    description: "Discount-rate pressure channel",
  },
  {
    id: "obj-guidance",
    type: "event",
    label: "Q2 Forward Guidance",
    status: "Pending",
    confidence: "90.6%",
    description: "Potential consensus reset trigger",
  },
];

const relations: ObjectRelation[] = [
  { source: "obj-yield", target: "obj-nvda", relation: "compresses valuation", effect: "negative", confidence: "0.79" },
  { source: "obj-guidance", target: "obj-tsla", relation: "re-prices demand outlook", effect: "positive", confidence: "0.73" },
  { source: "obj-nvda", target: "obj-tsla", relation: "sets AI hardware sentiment", effect: "positive", confidence: "0.68" },
  { source: "obj-yield", target: "obj-guidance", relation: "tightens scenario baseline", effect: "negative", confidence: "0.66" },
];

function iconForObjectType(type: BusinessObjectType) {
  if (type === "company") return <Building2 size={16} />;
  if (type === "metric") return <Activity size={16} />;
  return <AlertTriangle size={16} />;
}

export default function Home() {
  const [search, setSearch] = useState("");
  const [selectedObjectId, setSelectedObjectId] = useState<string>(objects[0].id);

  const visibleObjects = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return objects;
    return objects.filter((obj) => {
      return obj.label.toLowerCase().includes(q) || obj.description.toLowerCase().includes(q) || obj.type.includes(q);
    });
  }, [search]);

  const selectedObject = visibleObjects.find((obj) => obj.id === selectedObjectId) || visibleObjects[0] || objects[0];

  const selectedRelations = useMemo(() => {
    if (!selectedObject) return [];
    return relations.filter((edge) => edge.source === selectedObject.id || edge.target === selectedObject.id);
  }, [selectedObject]);

  return (
    <div className="p-8 space-y-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:justify-between lg:items-center fade-rise">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Intelligence Overview</h2>
          <p className="text-muted text-sm">Blueprint control room for object-level financial intelligence</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={14} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search business objects..."
              className="rounded-lg pl-9 pr-4 py-2 text-sm w-72"
            />
          </div>
          <button className="flex items-center gap-2 bg-primary hover:bg-sky-400 text-[#10161a] px-4 py-2 rounded-lg text-sm font-semibold shadow-[0_8px_20px_rgba(72,175,240,0.25)]">
            <Plus size={16} />
            New Case
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 fade-rise" style={{ animationDelay: "70ms" }}>
        <StatsCard label="Total Cases" value="1,284" description="Active across all sectors" trend={{ value: "+12.5%", positive: true }} />
        <StatsCard label="Data Precision" value="99.92%" description="Pillar 1 Self-Reflection score" trend={{ value: "+0.04%", positive: true }} />
        <StatsCard label="SCM Coverage" value="42 Paths" description="Direct causal equations codified" />
        <StatsCard label="System Health" value="Stable" description="All spokes operational" trend={{ value: "99.9% Uptime", positive: true }} />
      </div>

      <div className="glass-panel p-6 space-y-5 fade-rise" style={{ animationDelay: "120ms" }}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Spline size={18} className="text-primary" />
            <h3 className="font-bold text-lg">Object-Oriented View</h3>
          </div>
          <button className="text-xs font-semibold px-3 py-1.5 rounded-md badge hover:border-primary/70">Explore Full Ontology</button>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">
          <div className="xl:col-span-2 space-y-3">
            {visibleObjects.map((obj) => (
              <button
                key={obj.id}
                onClick={() => setSelectedObjectId(obj.id)}
                data-selected={selectedObject?.id === obj.id}
                className="object-card w-full rounded-lg p-4 text-left"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-primary">
                    {iconForObjectType(obj.type)}
                    <span className="text-xs uppercase tracking-[0.16em] text-muted">{obj.type}</span>
                  </div>
                  <span className="badge rounded px-2 py-0.5 text-[10px] text-muted">{obj.status}</span>
                </div>
                <p className="mt-2 text-sm font-semibold">{obj.label}</p>
                <p className="mt-1 text-xs text-muted">{obj.description}</p>
                <p className="mt-2 text-[11px] data-font text-secondary">Confidence {obj.confidence}</p>
              </button>
            ))}
          </div>

          <div className="xl:col-span-3 glass-panel p-5">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-muted">Selected Object</p>
                <h4 className="text-lg font-bold">{selectedObject?.label}</h4>
              </div>
              <span className="badge rounded px-3 py-1 text-xs data-font">{selectedObject?.confidence}</span>
            </div>

            <div className="mt-4 space-y-3">
              {selectedRelations.map((edge, idx) => (
                <div key={`${edge.source}-${edge.target}-${idx}`} className="rounded-lg border border-border bg-[#131b21] p-3 hover:border-primary/55">
                  <div className="flex items-center justify-between text-xs text-muted">
                    <span className="flex items-center gap-2"><Link2 size={12} /> Causal Link</span>
                    <span className="data-font">p={edge.confidence}</span>
                  </div>
                  <p className="mt-1 text-sm font-medium">{edge.relation}</p>
                  <div className="mt-1 flex items-center justify-between text-xs">
                    <span className="text-muted">{objects.find((obj) => obj.id === edge.source)?.label}</span>
                    <ChevronRight size={14} className="text-primary" />
                    <span className={edge.effect === "positive" ? "text-secondary" : "text-accent"}>{objects.find((obj) => obj.id === edge.target)?.label}</span>
                  </div>
                </div>
              ))}
              {selectedRelations.length === 0 && <p className="text-xs text-muted">No connected relations for this object.</p>}
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 fade-rise" style={{ animationDelay: "170ms" }}>
        <div className="lg:col-span-2 space-y-4">
          <div className="flex justify-between items-center px-1">
            <h3 className="font-bold text-lg">Active High-Priority Cases</h3>
            <button className="text-primary text-xs font-semibold flex items-center gap-1 hover:underline">
              View All <ChevronRight size={14} />
            </button>
          </div>
          <div className="glass-panel overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border bg-white/[0.02]">
                  <th className="px-6 py-4 text-xs font-bold text-muted uppercase tracking-widest">Entity</th>
                  <th className="px-6 py-4 text-xs font-bold text-muted uppercase tracking-widest">Status</th>
                  <th className="px-6 py-4 text-xs font-bold text-muted uppercase tracking-widest">Confidence</th>
                  <th className="px-6 py-4 text-xs font-bold text-muted uppercase tracking-widest">Last Event</th>
                  <th className="px-6 py-4"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {[
                  { name: "Tesla Inc.", ticker: "TSLA", status: "Refining", conf: "98.2%", time: "2m ago" },
                  { name: "NVIDIA Corp.", ticker: "NVDA", status: "Decision", conf: "94.5%", time: "12m ago" },
                  { name: "Apple Inc.", ticker: "AAPL", status: "Completed", conf: "99.1%", time: "1h ago" },
                  { name: "Microsoft", ticker: "MSFT", status: "Simulation", conf: "89.4%", time: "3h ago" },
                ].map((row, i) => (
                  <tr key={row.ticker} className="hover:bg-white/[0.03] group cursor-pointer">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="text-sm font-bold">{row.name}</span>
                        <span className="text-[10px] text-muted tracking-widest uppercase font-semibold">{row.ticker}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-1.5 h-1.5 rounded-full bg-primary"
                          style={{ boxShadow: "0 0 0 6px rgba(72,175,240,0.1)", animation: `beacon 1.7s ${i * 0.12}s infinite` }}
                        />
                        <span className="text-xs font-medium">{row.status}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4 data-font text-xs font-semibold text-secondary">{row.conf}</td>
                    <td className="px-6 py-4 text-xs text-muted">{row.time}</td>
                    <td className="px-6 py-4 text-right">
                      <ArrowUpRight size={14} className="text-muted group-hover:text-primary" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex justify-between items-center px-1">
            <h3 className="font-bold text-lg">System Audit Vault</h3>
          </div>
          <div className="glass-panel p-6 space-y-6">
            <div className="space-y-4">
              {[
                { stage: "Distill", msg: "Reflected 12 facts for NVDA", time: "2m ago" },
                { stage: "Oracle", msg: "Simulated 5 what-if scenarios", time: "15m ago" },
                { stage: "Robot", msg: "Decision recommendation signed", time: "1h ago" },
                { stage: "System", msg: "Database indexing completed", time: "2h ago" },
              ].map((log) => (
                <div key={`${log.stage}-${log.time}`} className="flex gap-4 items-start">
                  <div className="w-1 h-8 bg-border rounded-full" />
                  <div className="flex-1">
                    <div className="flex justify-between items-center">
                      <span className="text-[10px] font-bold text-primary uppercase tracking-widest">{log.stage}</span>
                      <span className="text-[10px] text-muted">{log.time}</span>
                    </div>
                    <p className="text-xs font-medium mt-1">{log.msg}</p>
                  </div>
                </div>
              ))}
            </div>
            <button className="w-full py-2 rounded-lg text-xs font-bold border border-border bg-[#141c22] hover:border-primary/70">
              Launch Full Audit Vault
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
