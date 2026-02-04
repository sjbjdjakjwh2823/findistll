"use client";

import React, { useState } from "react";
import { 
  FileUp, 
  RefreshCw, 
  Download, 
  AlertCircle,
  FileText,
  Shield
} from "lucide-react";
import { Button, Card, Elevation, Spinner, Tag } from "@blueprintjs/core";
import { CardSpotlight } from "@/components/ui/card-spotlight";

export default function ConvertPage() {
  const [file, setFile] = useState<File | null>(null);
  const [converting, setConverting] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setResult(null);
    }
  };

  const startConversion = () => {
    if (!file) return;
    setConverting(true);
    setProgress(0);
    
    // Simulate conversion progress
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setConverting(false);
          setResult(`${file.name.split('.')[0]}_refined.parquet`);
          return 100;
        }
        return prev + 10;
      });
    }, 300);
  };

  return (
    <div className="h-full flex flex-col bg-[#1a1c1e] p-6 font-sans">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#f6f7f9] uppercase">Data Refinement Foundry</h1>
          <p className="text-[10px] text-[#5c7080] font-mono mt-1">MODULE_CONVERT_V1.0_STITCH</p>
        </div>
        <div className="flex items-center gap-4">
           <div className="flex items-center gap-1.5 px-2 py-0.5 border border-[#30404d] bg-[#182026] text-[9px] text-[#a7b6c2] font-mono">
              <div className="w-1.5 h-1.5 rounded-full bg-[#0f9960] animate-pulse"></div>
              <span className="opacity-80">ENGINE:</span>
              <span className="text-[#0f9960] font-bold">READY</span>
           </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6 flex-1">
        {/* Left Column: Upload Area */}
        <div className="col-span-7 flex flex-col gap-6">
          <CardSpotlight className="flex flex-col items-center justify-center border-dashed border-2 min-h-[300px] relative group hover:border-[#2B95D6] transition-colors p-8">
            {!file ? (
              <>
                <div className="h-16 w-16 bg-[#2B95D6]/10 flex items-center justify-center rounded-full mb-4 group-hover:scale-110 transition-transform relative z-20">
                  <FileUp className="text-[#2B95D6]" size={32} />
                </div>
                <h3 className="text-[#f6f7f9] font-bold relative z-20">Select financial source document</h3>
                <p className="text-[11px] text-[#5c7080] mt-1 relative z-20">PDF, XBRL, CSV, or EXCEL (Max 50MB)</p>
                <input 
                  type="file" 
                  className="absolute inset-0 opacity-0 cursor-pointer z-30" 
                  onChange={handleFileChange}
                  accept=".pdf,.xbrl,.csv,.xlsx"
                />
              </>
            ) : (
              <div className="w-full flex flex-col items-center relative z-20">
                <div className="h-16 w-16 bg-[#21ce99]/10 flex items-center justify-center rounded-full mb-4">
                  <FileText className="text-[#21ce99]" size={32} />
                </div>
                <h3 className="text-[#f6f7f9] font-bold">{file.name}</h3>
                <p className="text-[11px] text-[#5c7080] mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                
                <div className="flex gap-4 mt-6">
                  <Button 
                    text="Change File" 
                    minimal 
                    small 
                    className="!text-[#a7b6c2]"
                    onClick={() => setFile(null)}
                  />
                  {!result && (
                    <Button 
                      intent="primary" 
                      icon="refresh" 
                      text="Process Document" 
                      onClick={startConversion}
                      loading={converting}
                    />
                  )}
                </div>
              </div>
            )}
          </CardSpotlight>

          {converting && (
            <div className="bg-[#182026] border border-[#30404d] p-4">
              <div className="flex justify-between items-center mb-2">
                <span className="text-[10px] font-mono text-[#a7b6c2] uppercase tracking-widest">Converting Stream...</span>
                <span className="text-[10px] font-mono text-[#2B95D6]">{progress}%</span>
              </div>
              <div className="w-full h-1 bg-[#0A1317] overflow-hidden">
                <div 
                  className="h-full bg-[#2B95D6] transition-all duration-300" 
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {result && (
            <div className="bg-[#21ce99]/10 border border-[#21ce99]/30 p-6 flex flex-col gap-4 animate-in fade-in zoom-in-95 duration-300">
               <div className="flex items-center gap-3">
                  <div className="h-10 w-10 bg-[#21ce99]/20 flex items-center justify-center rounded-full">
                    <Download className="text-[#21ce99]" size={20} />
                  </div>
                  <div>
                    <h4 className="text-[#f6f7f9] font-bold">Conversion Successful</h4>
                    <p className="text-[10px] text-[#21ce99] font-mono uppercase">Dataset refined and audited</p>
                  </div>
               </div>
               <div className="flex justify-between items-center bg-[#0A1317] p-3 border border-[#30404d]">
                  <span className="text-xs font-mono text-[#a7b6c2]">{result}</span>
                  <Button intent="success" small icon="download">Download Parquet</Button>
               </div>
            </div>
          )}
        </div>

        {/* Right Column: Engine Config / Stats */}
        <div className="col-span-5 flex flex-col gap-6">
           <Card elevation={Elevation.ZERO} className="!bg-[#1C2B33] !border-[#30404d] !p-4">
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-[#a7b6c2] mb-4 font-mono">Foundry Config</h4>
              <div className="space-y-4">
                 <div className="space-y-1">
                    <label className="text-[9px] uppercase tracking-wider text-[#5c7080] font-bold">Target Schema</label>
                    <HTMLSelect fill minimal className="!bg-[#0A1317] !text-[#f6f7f9] !text-xs font-mono">
                      <option value="quantmeta">Preciso QuantMeta v2.4</option>
                      <option value="parquet">Apache Parquet (Standard)</option>
                      <option value="arrow">Apache Arrow Stream</option>
                    </HTMLSelect>
                 </div>
                 
                 <div className="flex items-center justify-between p-2 bg-[#0A1317] border border-[#30404d]">
                    <div className="flex items-center gap-2">
                       <Shield size={14} className="text-[#2B95D6]" />
                       <span className="text-[10px] text-[#f6f7f9] font-mono">Merkle Integrity Guard</span>
                    </div>
                    <Tag intent="success" minimal className="text-[8px] font-mono">ACTIVE</Tag>
                 </div>

                 <div className="flex items-center justify-between p-2 bg-[#0A1317] border border-[#30404d]">
                    <div className="flex items-center gap-2">
                       <Zap size={14} className="text-[#d9822b]" />
                       <span className="text-[10px] text-[#f6f7f9] font-mono">Pillar 1 Self-Reflection</span>
                    </div>
                    <Tag intent="warning" minimal className="text-[8px] font-mono">AUTO</Tag>
                 </div>
              </div>
           </Card>

           <Card elevation={Elevation.ZERO} className="!bg-[#152127] !border-[#30404d] !p-4 flex-1">
              <h4 className="text-[10px] font-bold uppercase tracking-widest text-[#a7b6c2] mb-4 font-mono">System Insight</h4>
              <div className="space-y-4">
                 <div className="flex items-start gap-3">
                    <AlertCircle size={14} className="text-[#2B95D6] mt-0.5" />
                    <p className="text-[11px] text-[#a7b6c2] leading-relaxed">
                      Datasets are automatically normalized using the 2026 IFRS standards. Coordinate-aware anchors are preserved for lineage auditing.
                    </p>
                 </div>
                 <div className="h-px bg-[#30404d]" />
                 <div className="grid grid-cols-2 gap-4">
                    <div>
                       <div className="text-[9px] text-[#5c7080] uppercase font-bold">Refinement Latency</div>
                       <div className="text-xl font-bold text-[#f6f7f9] font-mono">~1.2s <small className="text-[10px] font-normal opacity-50">/ pg</small></div>
                    </div>
                    <div>
                       <div className="text-[9px] text-[#5c7080] uppercase font-bold">Accuracy Index</div>
                       <div className="text-xl font-bold text-[#21ce99] font-mono">99.98%</div>
                    </div>
                 </div>
              </div>
           </Card>
        </div>
      </div>
    </div>
  );
}
