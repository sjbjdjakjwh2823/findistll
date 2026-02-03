import React, { useMemo } from 'react';
import { Network, ArrowRight, Zap, AlertTriangle, ShieldCheck } from 'lucide-react';

interface LogicNode {
  id: string;
  role: 'analyst' | 'critic' | 'strategist';
  content: string;
  timestamp: string;
  status: 'passed' | 'rejected' | 'refined';
}

interface LogicEdge {
  from: string;
  to: string;
  label: string;
}

interface InteractiveLogicTreeProps {
  nodes: LogicNode[];
  edges: LogicEdge[];
}

const roleColors = {
  analyst: 'border-blue-400/50 bg-blue-400/5',
  critic: 'border-amber-400/50 bg-amber-400/5',
  strategist: 'border-green-400/50 bg-green-400/5',
};

const statusIcons = {
  passed: <ShieldCheck size={12} className="text-green-400" />,
  rejected: <AlertTriangle size={12} className="text-red-400" />,
  refined: <Zap size={12} className="text-blue-400" />,
};

export const InteractiveLogicTree: React.FC<InteractiveLogicTreeProps> = ({ nodes, edges }) => {
  return (
    <div className="flex flex-col gap-6 p-4 bg-[#0A1317] border border-[#30404d] overflow-x-auto min-h-[400px]">
      <div className="flex items-center gap-2 mb-2">
        <Network size={14} className="text-[#2B95D6]" />
        <span className="text-[10px] font-bold text-[#f6f7f9] uppercase tracking-widest font-mono">Agentic Reasoning Matrix</span>
      </div>

      <div className="flex items-start gap-8">
        {nodes.map((node, index) => (
          <React.Fragment key={node.id}>
            <div className={`flex flex-col w-64 border p-3 ${roleColors[node.role]} relative group transition-all hover:scale-[1.02]`}>
               <div className="flex justify-between items-center mb-2">
                  <span className="text-[9px] font-mono font-bold uppercase tracking-tighter opacity-70">
                    {node.role} // {node.id}
                  </span>
                  <div className="flex items-center gap-1">
                     {statusIcons[node.status]}
                     <span className="text-[8px] font-mono text-[#5c7080]">{node.timestamp}</span>
                  </div>
               </div>
               <p className="text-[11px] text-[#a7b6c2] leading-relaxed font-sans italic">
                 "{node.content}"
               </p>
               
               {/* Metadata badges */}
               <div className="mt-3 pt-2 border-t border-[#30404d]/50 flex gap-2">
                  <div className="px-1.5 py-0.5 bg-[#182026] text-[8px] font-mono text-[#5c7080] border border-[#30404d]">
                    CONF: 0.94
                  </div>
                  <div className="px-1.5 py-0.5 bg-[#182026] text-[8px] font-mono text-[#5c7080] border border-[#30404d]">
                    P1_REFLECTED
                  </div>
               </div>
            </div>

            {index < nodes.length - 1 && (
              <div className="flex items-center justify-center h-24">
                <ArrowRight size={20} className="text-[#30404d] animate-pulse" />
              </div>
            )}
          </React.Fragment>
        ))}
      </div>
      
      <div className="mt-auto pt-4 flex justify-between border-t border-[#30404d]/30 text-[9px] font-mono text-[#5c7080]">
         <span>LOG_STATE: SECURE_CHAIN_SYNCED</span>
         <span>AUTH: MASTER_OVERRIDE_ENABLED</span>
      </div>
    </div>
  );
};

export default InteractiveLogicTree;
