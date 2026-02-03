"use client";

import React from 'react';
import { 
  Button,
  Tag,
  InputGroup,
  Card,
  Spinner
} from "@blueprintjs/core";
import { 
  AlertCircle, 
  CheckCircle, 
  Info, 
  Clock, 
  User, 
  Terminal,
  Search
} from 'lucide-react';

const logs = [
  { id: 1, time: '18:45:02', level: 'INFO', message: 'User [leesangmin] initiated session', user: 'leesangmin', ip: '192.168.1.10' },
  { id: 2, time: '18:45:05', level: 'INFO', message: 'Dashboard layout loaded successfully', user: 'system', ip: 'localhost' },
  { id: 3, time: '18:46:12', level: 'WARN', message: 'High latency detected on node-kr-04 (120ms)', user: 'watchdog', ip: '10.0.0.4' },
  { id: 4, time: '18:48:30', level: 'INFO', message: 'Data ingestion job [Job-442] completed', user: 'airflow', ip: '10.0.0.8' },
  { id: 5, time: '18:50:01', level: 'ERROR', message: 'Failed to sync with Oracle EBS - Retry 1/3', user: 'connector-svc', ip: '10.0.0.12' },
  { id: 6, time: '18:50:05', level: 'INFO', message: 'Retry successful for Oracle EBS', user: 'connector-svc', ip: '10.0.0.12' },
  { id: 7, time: '18:55:00', level: 'INFO', message: 'Evidence [EV-2024-009] uploaded manually', user: 'leesangmin', ip: '192.168.1.10' },
  { id: 8, time: '19:00:00', level: 'INFO', message: 'Hourly aggregate calculation started', user: 'system', ip: 'localhost' },
  { id: 9, time: '19:00:15', level: 'INFO', message: 'Hourly aggregate calculation finished (15s)', user: 'system', ip: 'localhost' },
  { id: 10, time: '19:05:22', level: 'WARN', message: 'API Rate limit approaching for [AlphaVantage]', user: 'market-data', ip: '10.0.0.2' },
];

export default function AuditPage() {
  return (
    <div className="h-full flex flex-col bg-[#1a1c1e] text-[#f6f7f9]">
      
      {/* Search Header */}
      <div className="h-14 border-b border-[#30404d] bg-[#202b33] flex items-center px-4 gap-4 shrink-0">
         <div className="flex items-center gap-2 text-[#a7b6c2]">
            <Terminal size={16} />
            <span className="text-xs font-bold font-mono">SYSTEM_AUDIT_LOG</span>
         </div>
         <div className="h-6 w-[1px] bg-[#30404d]"></div>
         <InputGroup 
           leftIcon="search"
           placeholder="Search logs (regex supported)..."
           className="!bg-[#182026] !w-96 custom-input font-mono text-xs"
           small
         />
         <div className="flex-1"></div>
         <div className="flex items-center gap-2">
            <Tag minimal intent="success" className="font-mono">LIVE</Tag>
            <Button icon="refresh" minimal small />
         </div>
      </div>

      {/* Log Stream */}
      <div className="flex-1 overflow-auto p-0 bg-[#10161a] font-mono text-xs">
        {logs.map((log, index) => (
          <div 
            key={log.id} 
            className={`
              flex items-center gap-4 px-4 py-2 border-b border-[#1a1c1e] hover:bg-[#202b33] group
              ${log.level === 'ERROR' ? 'bg-[#db3737]/5' : ''}
              ${log.level === 'WARN' ? 'bg-[#d9822b]/5' : ''}
            `}
          >
            {/* Time */}
            <div className="w-24 text-[#5c7080] shrink-0 flex items-center gap-2">
              <span className="text-[10px] opacity-50">{index + 1}</span>
              {log.time}
            </div>

            {/* Level */}
            <div className="w-16 shrink-0">
              <span className={`
                font-bold
                ${log.level === 'INFO' ? 'text-[#2B95D6]' : 
                  log.level === 'WARN' ? 'text-[#d9822b]' : 
                  log.level === 'ERROR' ? 'text-[#db3737]' : 'text-[#f6f7f9]'}
              `}>
                {log.level}
              </span>
            </div>

            {/* Message */}
            <div className="flex-1 text-[#a7b6c2] group-hover:text-[#f6f7f9]">
              {log.message}
            </div>

            {/* Meta */}
            <div className="w-48 text-[#5c7080] text-[10px] text-right flex items-center justify-end gap-3">
              <span className="flex items-center gap-1">
                <User size={10} /> {log.user}
              </span>
              <span className="opacity-50">{log.ip}</span>
            </div>
          </div>
        ))}

        {/* Loading Indicator at bottom */}
        <div className="p-4 flex items-center justify-center gap-2 text-[#5c7080] border-t border-[#30404d]">
          <Spinner size={16} intent="primary" />
          <span>Awaiting new events...</span>
        </div>
      </div>
    </div>
  );
}
