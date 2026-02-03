"use client";

import React, { useState, useEffect, useRef, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { 
  Spinner,
  Tag,
  Button,
  Slider,
  HTMLSelect
} from "@blueprintjs/core";
import { 
  Network,
  Zap,
  RefreshCw,
  Search
} from 'lucide-react';

// Dynamically import ForceGraph3D to avoid SSR issues
const ForceGraph3D = dynamic(() => import('react-force-graph-3d'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full w-full bg-transparent text-[#5c7080]">
      <div className="flex flex-col items-center gap-4">
        <Spinner size={40} intent="primary" />
        <span className="font-mono text-[10px] tracking-widest uppercase">Initializing Neural Matrix...</span>
      </div>
    </div>
  )
});

interface GraphData {
  nodes: any[];
  links: any[];
}

interface KnowledgeGraph3DProps {
  caseId?: string;
  onNodeClick?: (node: any) => void;
  showControls?: boolean;
}

export default function KnowledgeGraph3D({ caseId, onNodeClick, showControls = true }: KnowledgeGraph3DProps) {
  const [data, setData] = useState<GraphData>({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [regimeShift, setRegimeShift] = useState<string | null>(null);
  const [delta, setDelta] = useState(0.5);
  const [horizon, setHorizon] = useState(3);
  const fgRef = useRef<any>(null);
  const dragStartRef = useRef<Map<string, { x: number; y: number; z: number }>>(new Map());

  const fetchData = async () => {
    setLoading(true);
    try {
      const url = caseId ? `/graph/data?case_id=${caseId}` : '/graph/data';
      const res = await fetch(url);
      if (res.ok) {
        const json = await res.json();
        setData(json);
        if (typeof json.regime_shift === 'string') {
          setRegimeShift(json.regime_shift);
        } else {
          setRegimeShift(null);
        }
      }
    } catch (err) {
      console.error("Failed to fetch graph data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [caseId]);

  const runSimulation = async (options?: { node?: any; deltaOverride?: number }) => {
    const targetNode = options?.node ?? selectedNode;
    if (!targetNode) return;
    setSimulating(true);
    try {
      const valueDelta = options?.deltaOverride ?? delta;
      const res = await fetch('/oracle/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          case_id: caseId,
          node_id: targetNode.id,
          value_delta: valueDelta,
          horizon_steps: horizon
        })
      });
      
      if (res.ok) {
        const result = await res.json();
        // Animate impacts
        animateImpacts(result.impacts);
      }
    } catch (err) {
      console.error("Simulation failed:", err);
    } finally {
      setSimulating(false);
    }
  };

  const animateImpacts = (impacts: any[]) => {
    if (!fgRef.current) return;
    
    // Create a map for quick lookup
    const impactMap = new Map(impacts.map(i => [i.node_id, i.delta]));
    
    // Trigger particles on links that are part of the impact path
    // For simplicity, we just pulse the nodes and emit particles
    data.links.forEach((link: any) => {
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
      const targetId = typeof link.target === 'object' ? link.target.id : link.target;
      
      if (impactMap.has(sourceId) && impactMap.has(targetId)) {
        const d = impactMap.get(sourceId);
        if (Math.abs(d as number) > 0.01) {
            fgRef.current.emitParticle(link);
        }
      }
    });
  };

  const nodeColor = (node: any) => {
    if (selectedNode && node.id === selectedNode.id) return "#FF3B30"; // Red for selected
    
    switch (node.group) {
        case 'company': return '#2B95D6'; // Blue
        case 'metric': return '#21ce99'; // Green
        case 'event': return '#d9822b'; // Orange
        default: return '#a7b6c2'; // Gray
    }
  };

  const handleNodeClick = (node: any) => {
    setSelectedNode(node);
    if (onNodeClick) onNodeClick(node);
  };

  const handleNodeDragStart = (node: any) => {
    if (!node || node.id == null) return;
    dragStartRef.current.set(String(node.id), { x: node.x ?? 0, y: node.y ?? 0, z: node.z ?? 0 });
  };

  const handleNodeDragEnd = (node: any) => {
    if (!node || node.id == null) return;
    const start = dragStartRef.current.get(String(node.id));
    const end = { x: node.x ?? 0, y: node.y ?? 0, z: node.z ?? 0 };
    dragStartRef.current.delete(String(node.id));

    if (!start) return;
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const dz = end.z - start.z;
    const distance = Math.sqrt(dx * dx + dy * dy + dz * dz);
    if (distance < 1) return;

    const shockDelta = Math.min(2, Math.max(0.05, distance / 50));
    setSelectedNode(node);
    setDelta(shockDelta);
    runSimulation({ node, deltaOverride: shockDelta });
  };

  return (
    <div
      className="w-full h-full relative"
      style={
        regimeShift === "Crisis"
          ? {
              background: "radial-gradient(circle at 50% 50%, rgba(120,0,0,0.25), rgba(10,19,23,0.9))",
              filter: "saturate(1.1)",
            }
          : undefined
      }
    >
      <ForceGraph3D
        ref={fgRef}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        nodeLabel="label"
        nodeColor={nodeColor}
        linkColor={(link: any) => (Number(link?.polarity) < 0 ? "#ff4d4d" : "#2B95D6")}
        linkWidth={(link: any) => {
          const value = Number(link?.value ?? 0.5);
          return Math.max(0.5, value);
        }}
        linkDirectionalParticles={(link: any) => Math.max(0, Math.floor(Number(link?.value ?? 0) * 5))}
        linkDirectionalParticleSpeed={0.005}
        nodeResolution={16}
        onNodeClick={handleNodeClick}
        onNodeDragStart={handleNodeDragStart}
        onNodeDragEnd={handleNodeDragEnd}
        showNavInfo={false}
      />

      {showControls && selectedNode && (
        <div className="absolute top-4 right-4 w-64 bg-[#202b33]/90 backdrop-blur border border-[#30404d] p-3 z-10 shadow-xl animate-in fade-in slide-in-from-right-4">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#30404d]">
                <div className="flex items-center gap-2">
                    <Zap size={14} className="text-[#2B95D6]" />
                    <span className="text-[10px] font-bold uppercase tracking-widest text-[#f6f7f9] font-mono">Oracle Control</span>
                </div>
                <Button icon="cross" minimal small onClick={() => setSelectedNode(null)} />
            </div>

            <div className="space-y-4">
                <div className="space-y-1">
                    <div className="flex justify-between items-center">
                        <label className="text-[9px] uppercase tracking-wider text-[#5c7080] font-bold">Injected Delta</label>
                        <span className="text-[10px] font-mono text-[#2B95D6]">{delta > 0 ? '+' : ''}{delta.toFixed(2)}</span>
                    </div>
                    <Slider
                        min={-2}
                        max={2}
                        stepSize={0.1}
                        labelStepSize={1}
                        value={delta}
                        onChange={setDelta}
                        className="tight-slider"
                    />
                </div>

                <div className="space-y-1">
                    <label className="text-[9px] uppercase tracking-wider text-[#5c7080] font-bold">Temporal Horizon</label>
                    <Slider
                        min={1}
                        max={10}
                        stepSize={1}
                        labelStepSize={2}
                        value={horizon}
                        onChange={setHorizon}
                        className="tight-slider"
                    />
                </div>

                <Button 
                    intent="primary" 
                    fill 
                    small 
                    icon={simulating ? <Spinner size={12} /> : "play"}
                    onClick={runSimulation}
                    disabled={simulating}
                    className="!font-mono !text-[10px] !tracking-widest"
                >
                    {simulating ? "PROCESING..." : "SIMULATE WHAT-IF"}
                </Button>
            </div>
        </div>
      )}

      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-[#1a1c1e]/50 backdrop-blur-sm z-20">
            <Spinner size={30} intent="primary" />
        </div>
      )}

      <div className="absolute bottom-4 left-4 pointer-events-none">
          <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2 opacity-60">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#2B95D6]"></div>
                  <span className="text-[9px] text-[#a7b6c2] font-mono">ENTITY</span>
              </div>
              <div className="flex items-center gap-2 opacity-60">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#21ce99]"></div>
                  <span className="text-[9px] text-[#a7b6c2] font-mono">METRIC</span>
              </div>
              <div className="flex items-center gap-2 opacity-60">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#d9822b]"></div>
                  <span className="text-[9px] text-[#a7b6c2] font-mono">EVENT</span>
              </div>
          </div>
      </div>
    </div>
  );
}
