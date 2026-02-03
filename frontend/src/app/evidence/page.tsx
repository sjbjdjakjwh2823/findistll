"use client";

import React, { useState } from 'react';
import { 
  Button, 
  Menu, 
  MenuItem, 
  Popover, 
  Position,
  InputGroup
} from "@blueprintjs/core";
import { 
  Filter, 
  MoreHorizontal, 
  ArrowUpDown, 
  Download,
  FileText
} from 'lucide-react';

const evidenceData = [
  { id: 'EV-2024-001', type: 'Invoice', source: 'SAP_ERP_Primary', confidence: 0.98, date: '2024-02-01 14:32:00', status: 'VERIFIED', owner: 'System' },
  { id: 'EV-2024-002', type: 'Email', source: 'Exchange_Archive', confidence: 0.85, date: '2024-02-01 14:35:12', status: 'PENDING', owner: 'L. Sangmin' },
  { id: 'EV-2024-003', type: 'Transaction', source: 'Swift_Gateway', confidence: 0.99, date: '2024-02-01 15:01:45', status: 'VERIFIED', owner: 'System' },
  { id: 'EV-2024-004', type: 'Contract', source: 'DocuSign_API', confidence: 0.92, date: '2024-02-01 15:15:22', status: 'REVIEW', owner: 'Legal_Bot' },
  { id: 'EV-2024-005', type: 'Log', source: 'Splunk_Fwd', confidence: 0.76, date: '2024-02-01 15:20:01', status: 'FLAGGED', owner: 'Sec_Ops' },
  { id: 'EV-2024-006', type: 'Invoice', source: 'SAP_ERP_Secondary', confidence: 0.97, date: '2024-02-01 15:22:10', status: 'VERIFIED', owner: 'System' },
  { id: 'EV-2024-007', type: 'Audio', source: 'Call_Center', confidence: 0.65, date: '2024-02-01 15:45:33', status: 'PENDING', owner: 'Analyst_01' },
  { id: 'EV-2024-008', type: 'Image', source: 'OCR_Service', confidence: 0.88, date: '2024-02-01 16:00:00', status: 'VERIFIED', owner: 'System' },
];

export default function EvidencePage() {
  const [selectedRow, setSelectedRow] = useState<string | null>(null);

  return (
    <div className="h-full flex flex-col bg-[#1a1c1e] text-[#f6f7f9]">
      {/* Action Bar */}
      <div className="h-12 border-b border-[#30404d] bg-[#202b33] flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-2">
          <InputGroup 
            leftIcon="search" 
            placeholder="Search evidence ID..." 
            className="!bg-[#182026] !w-80 custom-input"
            small
          />
          <Popover
            content={
              <Menu>
                <MenuItem icon="sort-asc" text="Date Ascending" />
                <MenuItem icon="sort-desc" text="Date Descending" />
                <MenuItem icon="filter" text="Status: Verified" />
              </Menu>
            }
            position={Position.BOTTOM_LEFT}
          >
            <Button icon="filter" text="Filter" rightIcon="caret-down" small minimal className="!text-[#a7b6c2]" />
          </Popover>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[#5c7080] font-mono mr-2">{evidenceData.length} RECORDS FOUND</span>
          <Button icon="add" text="Manual Upload" intent="primary" small outlined className="!rounded-none" />
        </div>
      </div>

      {/* Data Table */}
      <div className="flex-1 overflow-auto bg-[#1a1c1e]">
        <table className="w-full text-left text-xs border-collapse">
          <thead className="bg-[#293742] text-[#a7b6c2] font-semibold sticky top-0 z-10 font-mono text-[10px] uppercase tracking-wider">
            <tr>
              <th className="p-0"><div className="p-3 border-r border-[#30404d] flex items-center gap-2 cursor-pointer hover:bg-[#30404d]">ID <ArrowUpDown size={10}/></div></th>
              <th className="p-0"><div className="p-3 border-r border-[#30404d]">Type</div></th>
              <th className="p-0"><div className="p-3 border-r border-[#30404d]">Source</div></th>
              <th className="p-0"><div className="p-3 border-r border-[#30404d]">Confidence</div></th>
              <th className="p-0"><div className="p-3 border-r border-[#30404d]">Date Ingested</div></th>
              <th className="p-0"><div className="p-3 border-r border-[#30404d]">Status</div></th>
              <th className="p-0"><div className="p-3 border-r border-[#30404d]">Owner</div></th>
              <th className="p-0"><div className="p-3 text-center">Actions</div></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#30404d]">
            {evidenceData.map((row) => (
              <tr 
                key={row.id} 
                onClick={() => setSelectedRow(row.id)}
                className={`
                  group transition-colors duration-75 cursor-default font-mono
                  ${selectedRow === row.id ? 'bg-[#2B95D6]/20' : 'hover:bg-[#202b33]'}
                `}
              >
                <td className="p-3 text-[#f6f7f9] font-medium border-r border-[#30404d]">{row.id}</td>
                <td className="p-3 text-[#a7b6c2] border-r border-[#30404d] flex items-center gap-2">
                  <FileText size={12} />
                  {row.type}
                </td>
                <td className="p-3 text-[#a7b6c2] border-r border-[#30404d]">{row.source}</td>
                <td className="p-3 border-r border-[#30404d]">
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-[#10161a] rounded-sm overflow-hidden">
                      <div 
                        className={`h-full ${row.confidence > 0.9 ? 'bg-[#0f9960]' : row.confidence > 0.7 ? 'bg-[#d9822b]' : 'bg-[#db3737]'}`} 
                        style={{ width: `${row.confidence * 100}%` }}
                      ></div>
                    </div>
                    <span className="text-[10px] text-[#f6f7f9]">{(row.confidence * 100).toFixed(0)}%</span>
                  </div>
                </td>
                <td className="p-3 text-[#5c7080] border-r border-[#30404d]">{row.date}</td>
                <td className="p-3 border-r border-[#30404d]">
                  <span className={`
                    px-1.5 py-0.5 text-[9px] font-bold border rounded-sm
                    ${row.status === 'VERIFIED' ? 'border-[#0f9960] text-[#0f9960] bg-[#0f9960]/10' : 
                      row.status === 'PENDING' ? 'border-[#d9822b] text-[#d9822b] bg-[#d9822b]/10' : 
                      row.status === 'FLAGGED' ? 'border-[#db3737] text-[#db3737] bg-[#db3737]/10' : 
                      'border-[#2B95D6] text-[#2B95D6] bg-[#2B95D6]/10'}
                  `}>
                    {row.status}
                  </span>
                </td>
                <td className="p-3 text-[#a7b6c2] border-r border-[#30404d]">{row.owner}</td>
                <td className="p-2 text-center">
                  <Button icon="more" minimal small className="!text-[#5c7080] group-hover:!text-[#f6f7f9]" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
