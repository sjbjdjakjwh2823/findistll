"use client";

import React from "react";
import { 
  BarChart3, 
  Database, 
  ShieldCheck, 
  GitBranch, 
  Clock, 
  Settings,
  Briefcase
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const navItems = [
  { name: "Cases", icon: Briefcase, href: "/cases" },
  { name: "Evidence", icon: Database, href: "/evidence" },
  { name: "Decisions", icon: ShieldCheck, href: "/decisions" },
  { name: "Temporal Graph", icon: GitBranch, href: "/graph" },
  { name: "Audit Trail", icon: Clock, href: "/audit" },
  { name: "Analytics", icon: BarChart3, href: "/analytics" },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-64 h-screen border-r border-border bg-background flex flex-col">
      <div className="p-6">
        <h1 className="text-xl font-bold tracking-tight flex items-center gap-2">
          <div className="w-6 h-6 bg-primary rounded-md flex items-center justify-center text-xs text-white">P</div>
          PRECISO
        </h1>
        <p className="text-[10px] text-muted uppercase tracking-widest mt-1 font-medium">Sovereign Intelligence</p>
      </div>

      <nav className="flex-1 px-3 py-2 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.name}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
                isActive 
                  ? "bg-primary/10 text-primary" 
                  : "text-muted hover:text-foreground hover:bg-glass"
              )}
            >
              <item.icon size={18} />
              {item.name}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-border">
        <button className="flex items-center gap-3 px-3 py-2 w-full text-muted hover:text-foreground transition-colors text-sm font-medium">
          <Settings size={18} />
          Settings
        </button>
        <div className="mt-4 flex items-center gap-3 px-3">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-primary to-secondary" />
          <div className="flex flex-col">
            <span className="text-xs font-semibold">Lee Sangmin</span>
            <span className="text-[10px] text-muted">Master</span>
          </div>
        </div>
      </div>
    </div>
  );
}
