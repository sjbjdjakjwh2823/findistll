"use client";

import React from 'react';
import { 
  Button, 
  ButtonGroup,
  Card, 
  Elevation,
  InputGroup
} from "@blueprintjs/core";
import { 
  AreaChart, 
  Area, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
  ComposedChart,
  Line
} from 'recharts';
import { Search, Filter, Download, Calendar } from 'lucide-react';

const data = [
  { name: 'Jan', uv: 4000, pv: 2400, amt: 2400 },
  { name: 'Feb', uv: 3000, pv: 1398, amt: 2210 },
  { name: 'Mar', uv: 2000, pv: 9800, amt: 2290 },
  { name: 'Apr', uv: 2780, pv: 3908, amt: 2000 },
  { name: 'May', uv: 1890, pv: 4800, amt: 2181 },
  { name: 'Jun', uv: 2390, pv: 3800, amt: 2500 },
  { name: 'Jul', uv: 3490, pv: 4300, amt: 2100 },
];

const rangeData = [
  { name: 'A', x: 12, y: 23, z: 122 },
  { name: 'B', x: 22, y: 3, z: 73 },
  { name: 'C', x: 13, y: 15, z: 32 },
  { name: 'D', x: 44, y: 35, z: 23 },
  { name: 'E', x: 35, y: 45, z: 20 },
  { name: 'F', x: 62, y: 25, z: 29 },
  { name: 'G', x: 37, y: 17, z: 61 },
];

export default function AnalyticsPage() {
  return (
    <div className="h-full flex flex-col bg-[#1a1c1e] text-[#f6f7f9]">
      {/* Toolbar */}
      <div className="h-12 border-b border-[#30404d] bg-[#202b33] flex items-center justify-between px-4 shrink-0">
        <div className="flex items-center gap-2">
           <InputGroup 
             leftIcon="search" 
             placeholder="Search metrics..." 
             className="!bg-[#182026] !text-white !w-64 custom-input"
             small
           />
           <Button icon="filter" text="Filter View" minimal small className="!text-[#a7b6c2]" />
        </div>
        <div className="flex items-center gap-2">
           <ButtonGroup minimal>
             <Button icon="time" text="Last 24h" active small className="!text-[#f6f7f9] !bg-[#2B95D6]/20" />
             <Button icon="time" text="7d" small className="!text-[#a7b6c2]" />
             <Button icon="time" text="30d" small className="!text-[#a7b6c2]" />
           </ButtonGroup>
           <div className="w-[1px] h-4 bg-[#30404d] mx-2"></div>
           <Button icon="export" text="Export CSV" intent="primary" small outlined className="!rounded-none" />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 p-4 overflow-y-auto">
        <div className="grid grid-cols-12 gap-4 auto-rows-[300px]">
          
          {/* Chart 1: Revenue Trend (Area) */}
          <div className="col-span-8 border border-[#30404d] bg-[#202b33] flex flex-col">
            <div className="p-3 border-b border-[#30404d] flex justify-between items-center bg-[#293742]">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#f6f7f9] font-mono">Revenue & Volume Trend</h3>
              <span className="text-[10px] text-[#0f9960] font-mono">+12.5% YOY</span>
            </div>
            <div className="flex-1 p-4 bg-[#1a1c1e]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data}>
                  <defs>
                    <linearGradient id="colorUv" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#2B95D6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#2B95D6" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorPv" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#21ce99" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#21ce99" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="name" stroke="#5c7080" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis stroke="#5c7080" fontSize={10} tickLine={false} axisLine={false} />
                  <CartesianGrid strokeDasharray="3 3" stroke="#30404d" vertical={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#10161a', borderColor: '#30404d', color: '#f6f7f9' }} 
                  />
                  <Area type="monotone" dataKey="uv" stroke="#2B95D6" fillOpacity={1} fill="url(#colorUv)" />
                  <Area type="monotone" dataKey="pv" stroke="#21ce99" fillOpacity={1} fill="url(#colorPv)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 2: Entity Distribution (Bar) */}
          <div className="col-span-4 border border-[#30404d] bg-[#202b33] flex flex-col">
             <div className="p-3 border-b border-[#30404d] flex justify-between items-center bg-[#293742]">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#f6f7f9] font-mono">Entity Risk Score</h3>
            </div>
            <div className="flex-1 p-4 bg-[#1a1c1e]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rangeData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke="#30404d" horizontal={false} />
                  <XAxis type="number" stroke="#5c7080" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis dataKey="name" type="category" stroke="#5c7080" fontSize={10} tickLine={false} axisLine={false} />
                  <Tooltip cursor={{fill: '#202b33'}} contentStyle={{ backgroundColor: '#10161a', borderColor: '#30404d', color: '#f6f7f9' }} />
                  <Bar dataKey="x" stackId="a" fill="#2B95D6" />
                  <Bar dataKey="y" stackId="a" fill="#21ce99" />
                  <Bar dataKey="z" stackId="a" fill="#db3737" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Chart 3: Composition (Composed) */}
           <div className="col-span-12 border border-[#30404d] bg-[#202b33] flex flex-col">
             <div className="p-3 border-b border-[#30404d] flex justify-between items-center bg-[#293742]">
              <h3 className="text-xs font-bold uppercase tracking-wider text-[#f6f7f9] font-mono">System Load & Latency</h3>
            </div>
            <div className="flex-1 p-4 bg-[#1a1c1e]">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={data}>
                  <XAxis dataKey="name" stroke="#5c7080" fontSize={10} tickLine={false} axisLine={false} />
                  <YAxis stroke="#5c7080" fontSize={10} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: '#10161a', borderColor: '#30404d', color: '#f6f7f9' }} />
                  <CartesianGrid strokeDasharray="3 3" stroke="#30404d" vertical={false} />
                  <Bar dataKey="uv" barSize={20} fill="#293742" />
                  <Line type="monotone" dataKey="uv" stroke="#db3737" />
                  <Line type="monotone" dataKey="amt" stroke="#21ce99" />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
