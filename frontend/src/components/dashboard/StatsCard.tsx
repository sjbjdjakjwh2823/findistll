import React from "react";
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

interface StatsCardProps {
  label: string;
  value: string | number;
  description: string;
  trend?: {
    value: string;
    positive: boolean;
  };
}

export default function StatsCard({ label, value, description, trend }: StatsCardProps) {
  return (
    <div className="glass-panel p-5 flex flex-col gap-1">
      <span className="text-[11px] font-semibold text-muted uppercase tracking-widest">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold">{value}</span>
        {trend && (
          <span className={cn(
            "text-[10px] font-bold px-1.5 py-0.5 rounded",
            trend.positive ? "text-secondary bg-secondary/10" : "text-red-500 bg-red-500/10"
          )}>
            {trend.value}
          </span>
        )}
      </div>
      <p className="text-xs text-muted mt-1">{description}</p>
    </div>
  );
}
