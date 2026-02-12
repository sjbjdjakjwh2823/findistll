'use client';

import * as React from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, AlertTriangle } from 'lucide-react';

export type ZKPStatusProps = {
  status?: 'verified' | 'warning';
  label?: string;
  className?: string;
};

export default function ZKPStatus({
  status = 'verified',
  label = 'Sovereign Data Integrity',
  className = '',
}: ZKPStatusProps) {
  const ok = status === 'verified';

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-b from-white/10 to-white/[0.02] p-5 shadow-[0_0_40px_rgba(0,0,0,0.35)] backdrop-blur-xl ${className}`}
      aria-label={label}
    >
      {/* glow */}
      <div className="pointer-events-none absolute -inset-6 bg-[radial-gradient(circle_at_top,_rgba(120,170,255,0.25),_transparent_55%)]" />

      {/* scanning beam */}
      <motion.div
        className="pointer-events-none absolute -left-1/2 top-0 h-full w-1/2 bg-gradient-to-r from-transparent via-cyan-300/30 to-transparent blur-2xl"
        animate={{ x: ['-60%', '160%'] }}
        transition={{ duration: 2.6, repeat: Infinity, ease: 'linear' }}
      />

      <div className="relative z-10 flex items-center gap-4">
        <div className="relative grid h-12 w-12 place-items-center rounded-xl bg-white/5 ring-1 ring-white/10">
          <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-cyan-400/20 to-blue-500/10" />
          {ok ? (
            <ShieldCheck className="relative h-6 w-6 text-cyan-200" />
          ) : (
            <AlertTriangle className="relative h-6 w-6 text-amber-300" />
          )}
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium uppercase tracking-[0.28em] text-white/60">
              ZKP STATUS
            </span>
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                ok ? 'bg-emerald-400 shadow-[0_0_10px_rgba(16,185,129,0.8)]' : 'bg-amber-400'
              }`}
            />
          </div>
          <h3 className="truncate text-base font-semibold text-white">
            {label}
          </h3>
          <p className="text-xs text-white/60">
            {ok ? 'Zero-knowledge proof verified' : 'Proof anomaly detected'}
          </p>
        </div>
      </div>

      {/* subtle scanline */}
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(to_bottom,rgba(255,255,255,0.06)_1px,transparent_1px)] opacity-20 [background-size:100%_6px]" />
    </div>
  );
}
