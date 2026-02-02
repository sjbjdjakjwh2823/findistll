"use client";

import { useMemo, useState } from "react";
import StatsCard from "@/components/dashboard/StatsCard";
import {
  Plus,
  Search,
  ArrowUpRight,
  ArrowRight,
  ChevronRight,
  Building2,
  Activity,
  AlertTriangle,
  Link2,
  Spline,
  LayoutDashboard,
  Box,
  Share2,
  ShieldCheck
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
    <div className="flex flex-col h-full">
      {/* Top Breadcrumb Bar */}
      <div className="border-b border-border bg-[#182026] px-6 py-2 flex items-center gap-4 text-xs font-mono">
        <span className="text-muted">Home</span>
        <ChevronRight size={12} className="text-muted" />
        <span className="text-white font-bold uppercase tracking-wider">Workspace: Sovereign Intelligence</span>
        <div className="ml-auto flex items-center gap-4">
            <span className="flex items-center gap-1.5 text-secondary"><ShieldCheck size={14} /> System Verified</span>
            <span className="text-muted italic">Last sync: 2s ago</span>
        </div>
      </div>

      <div className="p-8 space-y-8 flex-1">
        <div className="flex flex-col gap-4 lg:flex-row lg:justify-between lg:items-center fade-rise">
            <div>
            <h2 className="text-2xl font-bold tracking-tight text-white uppercase italic">Overview // Foundry Core</h2>
            <p className="text-muted text-xs font-mono uppercase mt-1">Cross-Asset Object Explorer & Integrated Data Plane</p>
            </div>
            <div className="flex items-center gap-3">
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" size={14} />
                <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search business objects..."
                className="bg-[#1c2127] border border-border rounded-none px-9 py-2 text-sm w-72 text-white focus:border-primary outline-none"
                />
            </div>
            <button className="flex items-center gap-2 bg-[#137cbd] hover:bg-[#137cbd]/80 text-white px-4 py-2 rounded-none text-xs font-bold uppercase tracking-widest shadow-lg shadow-primary/10">
                <Plus size={16} />
                New Analytics Case
            </button>
            </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 fade-rise" style={{ animationDelay: "70ms" }}>
            <StatsCard label="Live Entities" value="2,184" description="Objects in active graph" trend={{ value: "+8%", positive: true }} />
            <StatsCard label="Analytic Threads" value="142" description="Concurrent reasoning jobs" trend={{ value: "4 Running", positive: true }} />
            <StatsCard label="Causal Integrity" value="99.9%" description="Verified by Pillar 1" />
            <StatsCard label="Latency (ms)" value="24.5" description="End-to-end processing" trend={{ value: "-12ms", positive: true }} />
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-5 gap-6 fade-rise" style={{ animationDelay: "120ms" }}>
            {/* Sidebar: Object Inventory */}
            <div className="xl:col-span-2 space-y-3 bg-[#182026] border border-border p-4 shadow-xl">
                <div className="flex items-center gap-2 mb-4 border-b border-border pb-3">
                    <Box size={18} className="text-primary" />
                    <h3 className="font-bold text-sm uppercase tracking-widest">Data Inventory</h3>
                </div>
                {visibleObjects.map((obj) => (
                <button
                    key={obj.id}
                    onClick={() => setSelectedObjectId(obj.id)}
                    data-selected={selectedObject?.id === obj.id}
                    className="object-card w-full p-4 text-left rounded-none border-l-4 border-l-transparent data-[selected=true]:border-l-primary"
                >
                    <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2 text-primary">
                        {iconForObjectType(obj.type)}
                        <span className="text-[10px] uppercase tracking-widest font-bold">{obj.type}</span>
                    </div>
                    <span className="text-[9px] text-muted font-mono">{obj.status}</span>
                    </div>
                    <p className="text-sm font-bold text-white uppercase">{obj.label}</p>
                    <p className="text-[11px] text-muted line-clamp-1 mt-1">{obj.description}</p>
                </button>
                ))}
            </div>

            {/* Main: Object Details & Causal Graph */}
            <div className="xl:col-span-3 space-y-6">
                <div className="bg-[#182026] border border-border p-6 shadow-xl relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-2 bg-[#293742] text-xs font-mono text-primary font-bold border-l border-b border-border">
                        {selectedObject?.confidence} CONFIDENCE
                    </div>
                    
                    <div className="mb-8">
                        <p className="text-[10px] uppercase tracking-[0.2em] text-primary font-bold">Selected Object</p>
                        <h4 className="text-3xl font-bold text-white uppercase mt-1">{selectedObject?.label}</h4>
                        <p className="text-sm text-muted mt-2 max-w-lg">{selectedObject?.description}</p>
                    </div>

                    <div className="space-y-4">
                        <div className="flex items-center gap-2">
                            <Share2 size={16} className="text-primary" />
                            <h5 className="text-xs font-bold uppercase tracking-widest text-white/90">Upstream \ Downstream Linkages</h5>
                        </div>
                        <div className="grid grid-cols-1 gap-3">
                            {selectedRelations.map((edge, idx) => (
                                <div key={`${edge.source}-${edge.target}-${idx}`} className="group relative bg-[#1c2127] border border-border p-4 hover:border-primary/50 transition-all">
                                    <div className="flex items-center justify-between text-[10px] font-mono mb-2">
                                        <span className="flex items-center gap-2 text-primary font-bold uppercase"><Link2 size={12} /> Causal Path</span>
                                        <span className="bg-[#293742] px-1.5 py-0.5 text-white">PROBABILITY: {edge.confidence}</span>
                                    </div>
                                    <p className="text-sm font-bold text-white italic mb-3">"{edge.relation}"</p>
                                    <div className="flex items-center gap-4">
                                        <div className="bg-black/30 border border-border px-3 py-1.5 text-xs font-bold text-muted uppercase">
                                            {objects.find((obj) => obj.id === edge.source)?.label}
                                        </div>
                                        <ArrowRight size={16} className="text-primary animate-pulse" />
                                        <div className={`bg-black/30 border border-border px-3 py-1.5 text-xs font-bold uppercase ${edge.effect === "positive" ? "text-secondary" : "text-accent"}`}>
                                            {objects.find((obj) => obj.id === edge.target)?.label}
                                        </div>
                                    </div>
                                </div>
                            ))}
                            {selectedRelations.length === 0 && (
                                <div className="py-8 text-center border border-dashed border-border">
                                    <p className="text-xs text-muted">No active causal chains detected for this entity.</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                <div className="flex gap-4">
                    <button className="flex-1 bg-[#137cbd] hover:bg-[#137cbd]/90 text-white py-3 text-xs font-bold uppercase tracking-widest transition-all shadow-lg shadow-primary/10">
                        Launch Simulation
                    </button>
                    <button className="flex-1 bg-glass hover:bg-white/5 border border-border text-white py-3 text-xs font-bold uppercase tracking-widest transition-all">
                        Deep Export
                    </button>
                </div>
            </div>
        </div>
      </div>
    </div>
  );
}
