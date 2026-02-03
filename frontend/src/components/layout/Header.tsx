"use client";

import React from "react";
import { Button, Intent } from "@blueprintjs/core";
import { usePathname } from "next/navigation";

export default function Header() {
  const pathname = usePathname();
  const pathSegments = pathname.split('/').filter(Boolean);
  
  return (
    <header className="h-[48px] border-b border-[#30404d] bg-[#1a1c1e] flex items-center justify-between px-4 shrink-0 font-sans">
      <div className="flex items-center gap-2 text-[11px] font-medium text-[#a7b6c2]">
        <div className="flex items-center gap-1.5 hover:text-[#f6f7f9] cursor-pointer transition-colors">
          <span className="opacity-70">PRECISO</span>
          <span className="text-[#30404d] font-normal">/</span>
          <span className="font-semibold tracking-wide">FOUNDRY</span>
        </div>
        {pathSegments.length > 0 && (
          <>
            <span className="text-[#30404d] font-normal">/</span>
            <span className="text-[#2B95D6] font-bold uppercase tracking-tight">{pathSegments[0]}</span>
          </>
        )}
        {pathSegments.length === 0 && (
           <>
            <span className="text-[#30404d] font-normal">/</span>
            <span className="text-[#2B95D6] font-bold uppercase tracking-tight">Intelligence</span>
           </>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-1.5 px-2 py-0.5 border border-[#30404d] bg-[#182026] text-[9px] text-[#a7b6c2] font-mono">
          <div className="w-1.5 h-1.5 rounded-full bg-[#0f9960] animate-pulse" />
          <span className="opacity-80">SYS_STATE:</span> 
          <span className="text-[#0f9960] font-bold">OPTIMAL</span>
        </div>
        <div className="h-6 w-[1px] bg-[#30404d] mx-1" />
        <Button 
          small 
          intent={Intent.PRIMARY} 
          text="EXECUTE WORKFLOW" 
          icon="play" 
          className="!font-bold !text-[10px] !rounded-none !h-[28px] !px-3 !bg-[#2B95D6] hover:!bg-[#39a3e6]" 
        />
      </div>
    </header>
  );
}
