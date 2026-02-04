"use client";

import React from "react";
import { 
  BarChart3, 
  Database, 
  ShieldCheck, 
  GitBranch, 
  Clock, 
  Settings,
  Briefcase,
  RefreshCw
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { useAuthStore } from "@/store/useAuthStore";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const navItems = [
  { name: "Cases", icon: Briefcase, href: "/cases" },
  { name: "Evidence", icon: Database, href: "/evidence" },
  { name: "Convert", icon: RefreshCw, href: "/convert" },
  { name: "Decisions", icon: ShieldCheck, href: "/decisions" },
  { name: "Temporal Graph", icon: GitBranch, href: "/graph" },
  { name: "Audit Trail", icon: Clock, href: "/audit" },
  { name: "Analytics", icon: BarChart3, href: "/analytics" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const user = useAuthStore((state) => state.user);
  const logout = useAuthStore((state) => state.logout);

  return (
    <div className="w-[200px] h-screen border-r border-[#30404d] bg-[#1a1c1e] flex flex-col font-sans select-none shrink-0">
      <div className="h-[48px] flex items-center px-3 border-b border-[#30404d]">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 bg-[#2B95D6] flex items-center justify-center text-[9px] font-bold text-white square">
            P
          </div>
          <div className="flex flex-col">
            <h1 className="text-[12px] font-bold tracking-tight text-[#f6f7f9] leading-none">PRECISO</h1>
            <span className="text-[8px] text-[#5c7080] uppercase tracking-wider font-mono mt-0.5">V.2.0.4_STITCH</span>
          </div>
        </div>
      </div>

      <nav className="flex-1 py-1 space-y-[0px]">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "group flex items-center gap-2.5 px-3 py-1.5 text-[11px] font-medium transition-colors",
                isActive 
                  ? "bg-[#202b33] text-[#2B95D6] shadow-[inset_3px_0_0_0_#2B95D6]" 
                  : "text-[#a7b6c2] hover:bg-[#1c242c] hover:text-[#f6f7f9]"
              )}
            >
              <item.icon size={12} className={isActive ? "text-[#2B95D6]" : "text-[#5c7080] group-hover:text-[#f6f7f9]"} />
              <span className="tracking-tight">{item.name.toUpperCase()}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-[#30404d] bg-[#1a1c1e]">
        <button 
          onClick={logout}
          className="flex items-center gap-2.5 px-3 py-2 w-full text-[#a7b6c2] hover:bg-[#202b33] hover:text-[#f6f7f9] text-[11px] font-medium transition-colors cursor-pointer"
        >
          <Settings size={12} />
          <span className="tracking-tight uppercase">Logout</span>
        </button>
        <div className="px-3 py-2 border-t border-[#30404d] flex items-center gap-2.5 bg-[#182026]">
          <div className="w-5 h-5 bg-[#293742] flex items-center justify-center text-[9px] text-[#a7b6c2] font-mono border border-[#30404d]">
            {user?.name?.substring(0, 2).toUpperCase() || "LS"}
          </div>
          <div className="flex flex-col min-w-0">
            <span className="text-[11px] font-semibold text-[#f6f7f9] truncate">{user?.name || "Sangmin Lee"}</span>
            <span className="text-[8px] text-[#5c7080] font-mono uppercase tracking-tighter">Master_Auth</span>
          </div>
        </div>
      </div>
    </div>
  );
}
