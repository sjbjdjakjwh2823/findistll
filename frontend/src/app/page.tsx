"use client";

import React, { useState } from 'react';
import { 
  Button, 
  Tag, 
  Intent,
  Spinner,
  Card,
  Elevation
} from "@blueprintjs/core";
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer 
} from 'recharts';
import { Network, Info, Database, TrendingUp, FileSearch, LayoutDashboard, Share2 } from 'lucide-react';
import KnowledgeGraph3D from '@/components/graph/KnowledgeGraph3D';
import LineageViewer from '@/components/dashboard/LineageViewer';
import InteractiveLogicTree from '@/components/dashboard/InteractiveLogicTree';

// Data for Chart
const chartData = [
  { time: '10:00', value: 400 },
  { time: '11:00', value: 300 },
  { time: '12:00', value: 550 },
  { time: '13:00', value: 450 },
  { time: '14:00', value: 600 },
  { time: '15:00', value: 650 },
];

// Sample Logic Data
const sampleLogicNodes: any[] = [
  { id: 'AN-01', role: 'analyst', content: 'Extracted 15% revenue growth for Q1. Margins expanding due to AI chip demand.', timestamp: '10:00:12', status: 'passed' },
  { id: 'CR-01', role: 'critic', content: 'Wait. Supply chain inventory is at a 3-year high. Growth may be front-loaded.', timestamp: '10:00:45', status: 'refined' },
  { id: 'ST-01', role: 'strategist', content: 'Maintain Buy rating but hedge with protective puts. Inventory peak is a signal.', timestamp: '10:01:05', status: 'passed' },
];

const sovereignProofData = {
  merkleRoot: '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8',
  integrity: 0.9999,
  lastVerified: '2026-02-03 10:42 KST',
};

export default function Page() {
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [viewMode, setViewMode] = useState<'graph' | 'evidence'>('graph');

  return (
    <div className="h-full w-full p-1.5 bg-[#0A1317] overflow-y-auto font-sans">
      <div className="flex flex-col gap-1.5 min-h-screen">
        
        {/* Top Section: Graph & Detail */}
        <div className="grid grid-cols-12 gap-1.5 h-[600px] shrink-0">
          {/* Panel 1: Main View */}
          <div className="col-span-8 border border-[#30404d] bg-[#152127] relative flex flex-col">
            <div className="h-[36px] border-b border-[#30404d] bg-[#1C2B33] flex items-center justify-between px-3">
              <div className="flex items-center gap-2">
                <div className="w-1.5 h-1.5 bg-[#2B95D6]"></div>
                <span className="text-[10px] font-bold text-[#f6f7f9] uppercase tracking-widest font-mono">
                  {viewMode === 'graph' ? "3D Causal Ontology" : "Source Evidence Linkage"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                 <div className="flex bg-[#0A1317] border border-[#30404d] p-0.5">
                    <Button minimal small active={viewMode === 'graph'} onClick={() => setViewMode('graph')} icon={<LayoutDashboard size={12} />} />
                    <Button minimal small active={viewMode === 'evidence'} onClick={() => setViewMode('evidence')} icon={<FileSearch size={12} />} />
                 </div>
              </div>
            </div>
            <div className="flex-1 relative bg-[#0A1317]">
               {viewMode === 'graph' ? (
                  <KnowledgeGraph3D onNodeClick={setSelectedNode} />
               ) : (
                  <LineageViewer fileUrl="/sample.pdf" highlight={selectedNode?.source_anchor} />
               )}
            </div>
          </div>

          {/* Panel 2: Detail/Signals */}
          <div className="col-span-4 border border-[#30404d] bg-[#152127] flex flex-col overflow-hidden">
            <div className="h-[36px] border-b border-[#30404d] bg-[#1C2B33] flex items-center justify-between px-3 text-[10px] font-bold text-[#f6f7f9] uppercase font-mono">
              Intelligence Signal Stream
            </div>
            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="flex-1 overflow-auto bg-[#0A1317]">
                <table className="w-full text-left text-[10px] font-mono border-collapse">
                    <tbody className="text-[#f5f8fa]">
                        <tr className="hover:bg-[#2B95D6]/10 cursor-pointer border-b border-[#30404d]/50 group">
                          <td className="p-3 text-[#5c7080]">18:42:01</td>
                          <td className="p-3">MARGIN_EXP_DELTA</td>
                          <td className="p-3 text-[#0f9960]">98%</td>
                        </tr>
                        <tr className="hover:bg-[#2B95D6]/10 cursor-pointer border-b border-[#30404d]/50 group">
                          <td className="p-3 text-[#5c7080]">18:41:55</td>
                          <td className="p-3">SUPPLY_CHAIN_SHOCK</td>
                          <td className="p-3 text-[#db3737]">CRITICAL</td>
                        </tr>
                        <tr className="bg-[#0f9960]/5 border-b border-[#30404d]/50">
                          <td className="p-3 text-[#5c7080]">NEW</td>
                          <td className="p-3 text-[#0f9960]">KINETIC_ACTION_TRIGGER</td>
                          <td className="p-3">HEDGE_OXY</td>
                        </tr>
                    </tbody>
                </table>
              </div>
              
              {/* Sovereign Proof Mini-Panel */}
              <div className="h-24 bg-[#1C2B33] border-t border-[#30404d] p-3 flex flex-col gap-1 shadow-inner">
                <div className="flex justify-between items-center">
                  <span className="text-[8px] font-bold text-[#2B95D6] uppercase tracking-tighter">Sovereign Proof (Phase 4)</span>
                  <Tag intent="success" minimal round style={{ fontSize: '7px', height: '12px' }}>VERIFIED</Tag>
                </div>
                <div className="text-[10px] font-mono text-[#f6f7f9] truncate selection:bg-[#2B95D6]">
                  {sovereignProofData.merkleRoot}
                </div>
                <div className="flex justify-between mt-1 text-[8px] text-[#5c7080] font-mono">
                  <span>INTEGRITY: {(sovereignProofData.integrity * 100).toFixed(2)}%</span>
                  <span>SYNC: {sovereignProofData.lastVerified}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Section: Logic Tree */}
        <div className="flex-1 border border-[#30404d] bg-[#152127] flex flex-col min-h-[400px]">
          <div className="h-[36px] border-b border-[#30404d] bg-[#1C2B33] flex items-center justify-between px-3">
            <div className="flex items-center gap-2">
              <Share2 size={12} className="text-[#2B95D6]" />
              <span className="text-[10px] font-bold text-[#f6f7f9] uppercase tracking-widest font-mono">Collaborative Decision Matrix</span>
            </div>
            <div className="text-[8px] font-mono text-[#5c7080]">WORKFLOW_ID: WF-9942-X</div>
          </div>
          <div className="flex-1 bg-[#0A1317]">
             <InteractiveLogicTree nodes={sampleLogicNodes} edges={[]} />
          </div>
        </div>

      </div>
    </div>
  );
}
