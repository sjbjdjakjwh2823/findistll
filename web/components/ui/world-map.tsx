"use client";
import React from "react";
import { motion } from "framer-motion";

export type Connection = {
  from: string;
  to: string;
  intensity: number;
  type: string;
};

export const WorldMap = ({ 
  className,
  connections = [] 
}: { 
  className?: string;
  connections?: Connection[];
}) => {
  // Mapping region names to SVG coordinates
  const regionCoords: Record<string, { x: number; y: number }> = {
    "North America": { x: 200, y: 175 },
    "Europe": { x: 525, y: 170 },
    "Asia": { x: 800, y: 240 },
    "S.America": { x: 250, y: 360 },
    "Global": { x: 500, y: 250 }
  };

  return (
    <div className={`relative w-full h-full bg-black/50 overflow-hidden ${className}`}>
      <svg
        viewBox="0 0 1000 500"
        className="w-full h-full opacity-20 grayscale"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Simple World Map Shapes */}
        <rect x="80" y="80" width="220" height="170" fill="white" opacity="0.1" rx="10" />
        <rect x="440" y="100" width="160" height="120" fill="white" opacity="0.1" rx="10" />
        <rect x="640" y="130" width="280" height="220" fill="white" opacity="0.1" rx="10" />
        <rect x="180" y="280" width="120" height="140" fill="white" opacity="0.1" rx="10" />
      </svg>
      
      {/* Animated Connection Lines Based on Real Data */}
      <svg className="absolute inset-0 w-full h-full">
        {connections.map((conn, i) => {
          const start = regionCoords[conn.from] || regionCoords["Global"];
          const end = regionCoords[conn.to] || regionCoords["Global"];
          
          // Bezier curve control point
          const cpX = (start.x + end.x) / 2;
          const cpY = Math.min(start.y, end.y) - 50;

          return (
            <motion.path
              key={i}
              d={`M ${start.x} ${start.y} Q ${cpX} ${cpY} ${end.x} ${end.y}`}
              stroke={conn.type === 'revenue_exposure' ? '#22d3ee' : '#f87171'}
              strokeWidth={Math.max(1, conn.intensity * 3)}
              fill="none"
              initial={{ pathLength: 0, opacity: 0 }}
              animate={{ pathLength: 1, opacity: [0, 1, 0.5] }}
              transition={{ 
                duration: 3, 
                repeat: Infinity, 
                delay: i * 0.5,
                ease: "easeInOut"
              }}
            />
          );
        })}

        {/* Fallback lines if no data */}
        {connections.length === 0 && (
          <>
            <motion.path
              d="M 200 175 Q 400 100 525 170"
              stroke="#22d3ee"
              strokeWidth="1"
              fill="none"
              opacity="0.2"
            />
            <motion.path
              d="M 525 170 Q 700 150 800 240"
              stroke="#f87171"
              strokeWidth="1"
              fill="none"
              opacity="0.2"
            />
          </>
        )}
      </svg>

      <div className="absolute top-4 left-4 text-[8px] font-mono text-cyan-500/50 uppercase">
        {connections.length > 0 ? `Mapping ${connections.length} research-backed links` : "Standby for Geo-Quant data..."}
      </div>
    </div>
  );
};
