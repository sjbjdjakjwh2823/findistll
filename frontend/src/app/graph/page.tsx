"use client";

import React, { useState } from 'react';
import { 
  Button, 
  Card, 
  Tag
} from "@blueprintjs/core";
import { 
  Search, 
  Network
} from 'lucide-react';
import KnowledgeGraph3D from '@/components/graph/KnowledgeGraph3D';

export default function GraphPage() {
  const [selectedNode, setSelectedNode] = useState<any>(null);

  return (
    <div className="h-full w-full relative bg-[#1a1c1e] overflow-hidden">
      
      {/* 3D Graph Container */}
      <div className="absolute inset-0 z-0">
        <KnowledgeGraph3D onNodeClick={setSelectedNode} />
      </div>

      {/* Top Toolbar overlay */}
      <div className="absolute top-0 left-0 right-0 p-4 z-10 pointer-events-none">
        <div className="flex justify-between items-start pointer-events-auto">
          <div className="bg-[#202b33]/90 backdrop-blur border border-[#30404d] p-2 flex items-center gap-2 w-96">
            <Search className="text-[#5c7080]" size={16} />
            <input 
              type="text" 
              placeholder="Search ontology objects..." 
              className="bg-transparent border-none text-[#f6f7f9] text-xs focus:outline-none w-full placeholder:text-[#5c7080] font-mono"
            />
            <div className="h-4 w-[1px] bg-[#30404d]"></div>
            <Button icon="arrow-right" minimal small />
          </div>

          <div className="flex gap-2">
            <Button icon="layout-auto" text="Auto-Layout" small className="!bg-[#202b33]/90 !border !border-[#30404d] !text-[#a7b6c2] backdrop-blur" />
            <Button icon="settings" text="Display" small className="!bg-[#202b33]/90 !border !border-[#30404d] !text-[#a7b6c2] backdrop-blur" />
          </div>
        </div>
      </div>

      {/* Right Sidebar Detail Panel (Optional, since KnowledgeGraph3D has its own control) */}
      {/* But the user asked for detailed info in side panel, so let's keep it consistent with Dashboard */}
      {selectedNode && (
        <div className="absolute top-16 right-4 w-80 bg-[#202b33]/95 backdrop-blur border border-[#30404d] flex flex-col z-20 shadow-2xl animate-in slide-in-from-right-10 duration-200">
          <div className="h-10 border-b border-[#30404d] bg-[#293742] flex items-center justify-between px-4">
             <div className="flex items-center gap-2">
                <Network size={14} className="text-[#2B95D6]" />
                <span className="text-xs font-bold uppercase tracking-wider text-[#f6f7f9] font-mono">Object Profile</span>
             </div>
             <Button icon="cross" minimal small onClick={() => setSelectedNode(null)} className="!text-[#a7b6c2]" />
          </div>
          
          <div className="p-4 space-y-4">
             <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-[#5c7080] font-bold">Object Label</label>
                <div className="text-lg font-bold text-[#f6f7f9] font-mono">{selectedNode.label}</div>
             </div>

             <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-[#5c7080] font-bold">Object Type</label>
                <div className="flex items-center gap-2">
                   <Tag intent="primary" minimal className="font-mono">{selectedNode.group.toUpperCase()}</Tag>
                </div>
             </div>

             <div className="space-y-1">
                <label className="text-[10px] uppercase tracking-wider text-[#5c7080] font-bold">Pillar 1 Attributes</label>
                <div className="bg-[#1a1c1e] border border-[#30404d] p-2 space-y-2">
                   <div className="flex justify-between text-xs font-mono">
                      <span className="text-[#a7b6c2]">id</span>
                      <span className="text-[#2B95D6]">{selectedNode.id}</span>
                   </div>
                   <div className="flex justify-between text-xs font-mono">
                      <span className="text-[#a7b6c2]">confidence</span>
                      <span className="text-[#21ce99]">0.92</span>
                   </div>
                   <div className="flex justify-between text-xs font-mono">
                      <span className="text-[#a7b6c2]">last_updated</span>
                      <span className="text-[#f6f7f9]">2026-02-02</span>
                   </div>
                </div>
             </div>

             <div className="space-y-2 pt-2 border-t border-[#30404d]">
                <Button icon="send-to-graph" text="Expand Neighbors" small fill className="!justify-start" />
                <Button icon="document" text="View Source Record" small fill className="!justify-start" intent="primary" outlined />
             </div>
          </div>
        </div>
      )}

    </div>
  );
}
