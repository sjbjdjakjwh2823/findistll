"use client";
import { cn } from "@/utils/cn";
import React from "react";
import { motion } from "framer-motion";

export const BackgroundLines = ({
  children,
  className,
  containerClassName,
}: {
  children?: React.ReactNode;
  className?: string;
  containerClassName?: string;
}) => {
  return (
    <div
      className={cn(
        "h-[100vh] w-full bg-[#1a1c1e] relative overflow-hidden flex flex-col items-center justify-center",
        containerClassName
      )}
    >
      <div className="absolute inset-0 z-0">
        <svg
          className="h-full w-full opacity-20"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <pattern
              id="grid"
              width="40"
              height="40"
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 40 0 L 0 0 0 40"
                fill="none"
                stroke="#30404d"
                strokeWidth="1"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>
      <div className="absolute inset-0 z-0 bg-[radial-gradient(circle_at_center,transparent_0%,#1a1c1e_70%)]" />
      
      {/* Animated lines */}
      <div className="absolute inset-0 z-0 pointer-events-none">
        {[...Array(5)].map((_, i) => (
          <motion.div
            key={i}
            initial={{ left: "-100%", top: `${20 * i}%` }}
            animate={{ left: "100%" }}
            transition={{
              duration: 10 + i * 2,
              repeat: Infinity,
              ease: "linear",
              delay: i * 2,
            }}
            className="absolute h-px w-64 bg-gradient-to-r from-transparent via-[#2B95D6] to-transparent opacity-50"
          />
        ))}
      </div>

      <div className={cn("relative z-10", className)}>{children}</div>
    </div>
  );
};
